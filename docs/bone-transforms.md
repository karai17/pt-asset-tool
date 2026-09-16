# SMD/SMB Bone Transform Conventions

How static bone transforms (`Tm`, `px/py/pz`, `qx..qw`, `sx/sy/sz`) work in the
original engine, why the shipped data mixes two conflicting conventions, and how
`src/pt/decode/smd.py` resolves them.

## The engine's source of truth: `Tm`

At runtime the engine treats each bone's `Tm` matrix as its **accumulated world
transform**. `smOBJ3D::TmAnimation` (`smObj3d.cpp`) builds the render matrix
with, in the static (no key) branch:

```c
qmat     = Tm * pParent->TmInvert;        // parent-local transform
TmResult = qmat * pParent->TmResult;      // compose up the chain
```

and for an animated bone the same `TmResult = qmat * pParent->TmResult` with
`qmat` from the keyframes. Because every level multiplies by
`Tm[k] * inv(Tm[k-1])`, the product telescopes:

```
world(bone) = Tm(bone) * inv(Tm(parent)) * Tm(parent) * ... = Tm(bone)
```

So **a bone's world transform equals its `Tm` exactly**, and the engine derives
the parent-local transform on the fly with a *general* 4x4 inverse
(`smMatrixInvert`, `smmatrix.cpp`). The inverse is general, not a rigid-body
transpose - this matters because some authored matrices are not orthonormal
(see [Degenerate matrices](#degenerate-matrices-in-shipped-data)).

## Where `px..qw` are actually used

A full audit of `smObj3d.cpp` finds the static fields have exactly **three**
runtime uses, none of them in the static hierarchy:

| Field | Use | Guard |
| --- | --- | --- |
| `px/py/pz` | Animation position fallback: `qmat._41 = float(px) / fONE` | only when the bone has **no** position keys (`TmPosCnt == 0` or no key window covers the frame) |
| `qx..qw` | Baked into `TmRotate` at import (`smRead3d.cpp:1268`), then `smFMatrixFromMatrix(qmat, TmRotate)` | only when the bone has **no** rotation keys |
| `sx/sy/sz` | `ReformTM` scale normalization: `Tm._ij = (Tm._ij << FLOATNS) / ((sx+sy+sz)/3)` | once at import (`smRead3d.cpp:1894/1980/2066`), and only for the mesh/bone converter path |

`smOBJ3D::LoadFile` (the SMD reader) does none of this - it `ReadFile`s the
structs verbatim and never recomputes anything. The conversions above run only
in the ASE-to-SMD converter (`smASE_ReadBone` and siblings). For an animated
bone - i.e. every biped bone that matters - `px..qw` are never consulted while
`Tm` is authoritative for the bind.

## The two conflicting static conventions

Because the runtime leans entirely on `Tm`, nobody noticed that the *static
fields* are written in different spaces by different ASE exporters. The
converter copies them verbatim (`smRead3d.cpp:1237-1268`):

```c
*TM_POS      -> obj->px, obj->py, obj->pz
*TM_ROTAXIS  -> obj->qx, obj->qy, obj->qz
*TM_ROTANGLE -> obj->qw
```

Those ASE chunks are produced by the 3ds Max ASE exporter and may contain either
the **parent-relative** local TM or the **world-space** `NODE_TM`, depending on
exporter version/settings. Both variants exist in shipped data, and one shipped
ASE demonstrates the ambiguity directly (`StartImage/Opening/test/fly.ASE`):

```
*NODE_NAME "Bip-01"
*TM_ROW3  679.134  1.543  366.227     <- world position
*TM_POS   679.134  1.543  366.227     <- equals TM_ROW3: world-space TM_POS

*NODE_NAME "Bip-03"
*TM_ROW3  681.223  1.281  366.478     <- world position
*TM_POS   0.000    2.056  0.517      <- differs: parent-relative TM_POS
```

Measured over 892 SMB files: ~761 store parent-relative statics (e.g. Buma),
~128 store world-space statics (e.g. Aragonian, Acero, Crios, Raeda), 31 are
inconclusive (degenerate/empty). The split does **not** correlate with the INX
format revision (both appear among the 95268-byte `smMODELINFO_EX` files), so it
reflects per-model export settings rather than one clean pipeline cutover.

Confirmation on real files:

- Aragonian (world): `quat(Tm rotation)` vs stored `qx..qw` dot = 0.9995+ -
  the statics are a copy of the world `Tm`.
- Buma (local): dot ~ 0 - the statics are genuinely different (local) data.

The engine renders both correctly because it never reads `px..qw` for animated
bones; `Tm` carries the whole truth.

## Why this breaks a glTF pipeline

glTF has no per-bone world matrix. A node carries a parent-relative TRS, and
the skin's inverse-bind matrices are expected to match the same hierarchy. Two
consequences:

1. Writing the static `px..qw` directly as node TRS is correct for local-files
   (Buma) and **explodes** world-files (Aragonian): each bone inherits its full
   world transform as if it were an offset, compounding down the chain.
2. The bind information must instead be *derived* from `Tm`, the only
   consistent data.

## The decode strategy

`decode_actor_transform` in `src/pt/decode/smd.py` therefore mirrors the
engine's runtime math instead of trusting the static fields:

```
local = Tm * inv(Tm_parent)     # the engine's static branch, in float
position = translation row of local        (already inches, fONE divided out)
rotation = quaternion of local's 3x3
scale    = sx/sy/sz/256 scaled by the per-axis norms of local's 3x3
```

- Root bones use `Tm` directly (no parent inverse), matching the engine.
- The inverse is a general Gauss-Jordan (`_invert_general`), matching
  `smMatrixInvert`. A singular matrix returns `None` and the stored fields are
  left untouched - the engine also produces garbage for those (degenerate
  helper bones) but never samples them.
- The `ReformTM` scale fixup (`(sx+sy+sz)/3`) is applied to the rotation rows
  before decomposition, mirroring the order the engine runs in. It is the
  identity for the unit-scale (256) bones of every shipped biped.
- `PTObjectTransform`'s matrix fields (`_11.._44`) keep the **world** `Tm`.
  The glTF exporter's vertex bake and inverse-bind matrices pair against them,
  so `baked_v * invBind * jointWorld == v * jointWorld` regardless of
  convention.
- A final consistency property holds for every well-formed model: composing
  the decoded local TRS down each chain reproduces `Tm`'s translation
  (verified across all 368 boned models; median worst-bone deviation 0.065
  inches).

## Degenerate matrices in shipped data

Because the engine never decomposes to TRS, exporters emitted `Tm` matrices
that are *not* pure rotation+uniform scale:

- **Baked scale** - Raeda's clavicles carry `det(R) = 0.9925` (bones ~0.4%
  short). The scale is recovered from the row norms before quaternion
  extraction; otherwise a shrink pushes the matrix trace negative and the
  naive extraction misroutes into the 180-degree branch.
- **Mirrors** - negative determinant matrices (encoded in glTF as a negative
  scale component, flipped on the third axis).
- **True shear** - a handful of decoration bones (QuartzBat
  `Bip01_R_Wing_03_02_03`: row scales `0.046, 1.542, 0.911`) are not
  representable as TRS at all. These are inherent format limitations; several
  of them have zero vertex-skin references.

## Summary table

| Data | Engine usage | Decoder usage |
| --- | --- | --- |
| `Tm` | Authoritative world bind (`TmAnimation`) | Source for matrix fields and derived local TRS |
| `px/py/pz` | Animation position fallback (no pos keys) | Not used for bind pose |
| `qx..qw` → `TmRotate` | Animation rotation fallback (no rot keys) | `transform_rotate` on mesh objects; not used for bone bind |
| `sx/sy/sz` | `ReformTM` normalization | Node scale component (multiplied by recovered matrix scale) |
| `TmInvert` | Recomputed by `ReformTM`; used for local derivation | Recomputed in float (`_invert_general`) |
