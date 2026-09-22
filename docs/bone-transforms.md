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
in the ASE-to-SMD converter (`smASE_ReadBone` and siblings), and `ReformTM`
never runs again after that: `smPAT3D::LoadFile` (smObj3d.cpp:2937) and
`smOBJ3D::TmAnimation`'s static branch (root `qmat = Tm`; child
`qmat = Tm * pParent->TmInvert`, telescoping to `TmResult == Tm`) use the
on-disk `Tm` verbatim. For an animated
bone - i.e. every biped bone that matters - `px..qw` are never consulted while
`Tm` is authoritative for the bind.

### ReformTM is rendering-neutral, so the decoder must not re-apply it

`ReformTM` (smObj3d.cpp:920-985) rescales the rotation rows of `Tm` by
`256/S` (`S = (sx+sy+sz)/3`; roots use their own scale, children their
parent's) and, in the same pass, premultiplies the mesh vertices by
`inv(Tm)` (smObj3d.cpp:965-1000). The two operations cancel:
`Tm_new * (v * inv(Tm_new)) == Tm_old * v`. It runs solely in the ASE-to-SMD
converter (smRead3d.cpp:1894/1980/2066, immediately before `SaveFile`), so
whether or not a given shipped file went through it, the invariant

```
world = on-disk Tm x on-disk vertices
```

always holds. An exporter must therefore reproduce `Tm` verbatim - multiplying
the rotation rows by `S/256` to "recover the authored ASE matrix" corrupts the
pairing whenever `S != 256`. Full-corpus survey (4,843 SMD/SMB files, 46,261
objects): 5,511 non-skinned objects carry non-unit `(sx,sy,sz)`; 4,548 of them
have unit rotation rows (e.g. DropItem `itGF104`: identity `Tm`, `sx = 110` -
the engine renders it at 100%, not the 43% the recovered scale suggested),
734 carry the scale in the rows themselves (`Field/Greedy/door.smd` `Box01`:
rows `[256, 448, 58]` - the engine renders that static door 1.75x tall and
0.23x thin; the sky-fog cylinders `Cylinder03` `[137, 137, 492]` render at
`[0.54, 1.92, 0.54]`), and the rest are mixed. One caveat mirrors
`TmAnimation`: the row scale is engine-visible only for objects with NO
animation keys (the key branch rebuilds `qmat` from keys with no scale
fallback) and only for non-skinned meshes (skinned vertices transform through
the bone matrices). For animated/skinned objects a wrong recovered scale (e.g.
`kn5_CrescentMoon`'s `2*I` rows, or `hammer_goblin`'s `Monho-*` at ~2,088x
after double application) corrupts the decoded data without changing the
render. Consequently `sx/sy/sz` are treated as ReformTM bookkeeping data only,
never as transform inputs.

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
scale    = per-axis norms of local's 3x3
```

- Root bones use `Tm` directly (no parent inverse), matching the engine.
- The inverse is a general Gauss-Jordan (`_invert_general`), matching
  `smMatrixInvert`. A singular matrix returns `None` and the stored fields are
  left untouched - the engine also produces garbage for those (degenerate
  helper bones) but never samples them.
- `Tm` is converted verbatim (fONE divided out, no rescaling): the runtime
  reads `Tm` from disk and uses it as-is, and re-applying `ReformTM`'s
  `256/S` factor would corrupt the `Tm x vertices` pairing for the 1,018
  non-unit-scale objects (see above). For the unit-scale (256) bipeds of
  every shipped model it is the identity either way.
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

### Static (key-less) mesh objects export the whole Tm as a node matrix

Mesh objects are flat scene nodes in the glTF, so the exporter can write the
Tm verbatim instead of a TRS approximation - and it must for two reasons
found on `Field/Greedy/door.smd`:

1. TmRotate (the static-field rotation) disagrees with Tm's rotation rows for
   key-less objects (Object04: ~180° off). The engine renders Tm's rows, so
   the exporter must not feed TmRotate into key-less nodes.
2. Tm rows can carry genuine shear (Object04: rows non-orthonormal by ~2%,
   mirrored) that a TRS node loses up to ~1 m on. A glTF node.matrix has no
   such limit - the exported door matches the engine's
   `world = v @ Tm` render to 0.000000 m on all three objects.

The matrix is `P @ Tm_engine.T @ P` with the axis permutation `P =
[[-1,0,0],[0,0,1],[0,1,0]]` (the same (-x, z, y) map the static vertices use),
translation scaled to meters. Animated objects keep the TRS path (TmRotate
rotation, unit scale) because animation channels target TRS.

## Summary table

| Data | Engine usage | Decoder usage |
| --- | --- | --- |
| `Tm` | Authoritative world bind (`TmAnimation`) | Source for matrix fields and derived local TRS |
| `px/py/pz` | Animation position fallback (no pos keys) | Not used for bind pose |
| `qx..qw` → `TmRotate` | Animation rotation fallback (no rot keys) | `transform_rotate` on mesh objects; not used for bone bind |
| `sx/sy/sz` | `ReformTM` normalization (converter-only, rendering-neutral) | Not used; carried as data |
| `TmInvert` | Recomputed by `ReformTM`; used for local derivation | Recomputed in float (`_invert_general`) |
