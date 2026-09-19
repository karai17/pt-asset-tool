# SMD / SMB Format Reference

This document is grounded in the original engine source at `src/smLib3d`
(`smObj3d.cpp`, `smStage3d.cpp`, `smTexture.cpp`, `smRead3d.cpp`, `smType.h`,
`smObj3d.h`, `smStage3d.h`, `smTexture.h`).

The SMD format comes in two variants, identified by the ASCII signature stored
at the start of the file (`smDFILE_HEADER.szHeader`, compared with `lstrcmp`):

| Variant | Signature | Written by | Contents | Typical companion files |
| --- | --- | --- | --- | --- |
| Stage | `SMD Stage data Ver 0.72` (`smStage3d.cpp:2288`) | `smSTAGE3D::SaveFile` | One static map mesh with materials, vertex colors and lights | none |
| Actor | `SMD Model data Ver 0.62` (`smObj3d.cpp:2852`) | `smPAT3D::SaveFile` | Hierarchical objects with skeletal bindings and transform-keyframe animation | `.inx` (metadata), `.smb` (bones) |

A commented-out `SMD Model data Ver 1.00` in `smObj3d.cpp:2853` shows a planned
version bump that never shipped.

SMB files (model bones) are **not** a separate format: during the ASE-to-SMD
conversion the bone hierarchy is saved with the same `smPAT3D::SaveFile` to a
file with the `smb` extension (`smRead3d.cpp:1985`), so an SMB is simply an
Actor SMD containing only biped/bone objects (see [SMB files](#smb-files)).

All data is **little-endian**. `int32` fields used for geometry are fixed point
with 8 fractional bits (value = raw / 256). Matrices are 16.16 fixed point
(value = raw / 65536), except the translation row, which uses 1/256 scaling.
`smMATRIX` is stored column-major despite DirectX being row-major; matrix
multiplication in the original engine compensates by multiplying backwards
(reference: `smmatrix.cpp::smMatrixMult`).

Pointers stored in the files (`*_ptr`, `lpTexLink`, `NextTex`, `hTexture`,
`pParent`, `Physique`, ...) are runtime addresses captured by `WriteFile` on
the in-memory structs. They are meaningless as addresses. The loaders
reconstitute links by pointer *difference* in element units, so
`lpTexLink_ptr` / `NextTex_ptr` differences divided by `sizeof(smTEXLINK)`
yield array indices (reference: `smOBJ3D::LoadFile`, `smSTAGE3D::LoadFile`).
Debug-built files frequently contain `0xCDCDCDCD` (MSVC debug-heap fill) in
fields that were never initialized; several of these are fields the loaders
blindly trust (see [Original code quirks and bugs](#original-code-quirks-and-bugs)).

## Table of Contents

- [File layout](#file-layout)
	- [smDFILE_HEADER](#smdfile_header)
	- [Stage data Ver 0.72](#stage-data-ver-072)
	- [Model data Ver 0.62](#model-data-ver-062)
	- [SMB files](#smb-files)
	- [Material block](#material-block)
	- [MeshState semantics](#meshstate-semantics)
		- [Render order](#render-order)
	- [Stage area partition data](#stage-area-partition-data)
- [Structures](#structures)
	- [Primitives](#primitives)
	- [Transform keys](#transform-keys)
	- [Matrices](#matrices)
	- [smMATERIAL_GROUP](#smmaterial_group)
	- [smMATERIAL](#smmaterial)
	- [smOBJ3D](#smobj3d)
	- [smSTAGE3D](#smstage3d)
- [Original code quirks and bugs](#original-code-quirks-and-bugs)
- [Coordinates and units](#coordinates-and-units)

## File layout

### smDFILE_HEADER

Both variants start with this 556-byte header. Decoded with
`smDFILE_HEADER` from `src/pt/cdef.py`; defined in `smObj3d.h:51`
(`OBJ_FRAME_SEARCH_MAX = 32`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 24 | `szHeader` | `int8[24]` | NUL-padded ASCII signature. `SMD Stage data Ver 0.72` or `SMD Model data Ver 0.62` |
| 24 | 4 | `ObjCounter` | `int32` | Number of objects. **Stage writer never initializes this** — it contains stack garbage (usually `0xCCCCCCCC`); stage dispatch must use the signature only |
| 28 | 4 | `MatCounter` | `int32` | Number of materials. 0 in SMB files |
| 32 | 4 | `MatFilePoint` | `int32` | Actor: absolute file offset of the `smMATERIAL_GROUP`, computed as `556 + 40 * ObjCounter` (`smPAT3D::SaveFile:2881`). Stage: **always written as 556 regardless of the actual position** (`smSTAGE3D::SaveFile:2310`); the stage loader ignores it and reads materials directly after `smSTAGE3D` |
| 36 | 4 | `First_ObjInfoPoint` | `int32` | Actor: offset of the first `smOBJ3D` (objects are contiguous, the objinfo table precedes the materials). Stage: offset just past the material blocks (the loader never seeks with it, it just reads sequentially) |
| 40 | 4 | `TmFrameCounter` | `int32` | Number of used entries in `TmFrame` (copy of `smPAT3D::TmFrameCnt`) |
| 44 | 512 | `TmFrame` | `smFRAME_POS[32]` | Per-animation frame ranges (see [smFRAME_POS](#smframe_pos)) |

### Stage data Ver 0.72

Reference: `smSTAGE3D::SaveFile` (`smStage3d.cpp:2291`) and
`smSTAGE3D::LoadFile` (`smStage3d.cpp:2362`).

| Block | Count |
| --- | --- |
| `smDFILE_HEADER` | 1 |
| `smSTAGE3D` | 1 |
| `smMATERIAL_GROUP` | 1, only if `MatCounter > 0` (directly after `smSTAGE3D`) |
| Material block (see [Material block](#material-block)) | `MatCounter` |
| `smSTAGE_VERTEX` | `smSTAGE3D.nVertex` |
| `smSTAGE_FACE` | `smSTAGE3D.nFace` |
| `smTEXLINK` | `smSTAGE3D.nTexLink` |
| `smLIGHT3D` | `smSTAGE3D.nLight`, only if `nLight > 0` |
| Area partition data (see [Stage area partition data](#stage-area-partition-data)) | variable |

The geometry arrays are contiguous and the loaders read them with plain
sequential `ReadFile` calls. Verified across every stage file in
`.local/input/Field`. The `sum` / `CalcSum` sorting fields and the stale
`*_ptr` fields inside the geometry records often contain `0xCDCDCDCD`; only
the coordinates, colors, vertex indices, material ids and UVs are meaningful.

Only dungeons 1-5 (dun 1-3, sanctuary 1-2) carry lightmaps (materials named
`*LM_`); lights themselves occur in many stages (`nLight` up to ~200).

Files named like `v-ani*.smd`, `*_ani*.smd`, `*_Bip*.smd` inside `Field`
directories are **not** stage files; they use the Actor layout (animated
props). Always dispatch on the signature, never the directory.

### Model data Ver 0.62

Reference: `smPAT3D::SaveFile` (`smObj3d.cpp:2856`) / `smPAT3D::LoadFile`
(`smObj3d.cpp:2937`), `smOBJ3D::SaveFile` (`smObj3d.cpp:2110`) /
`smOBJ3D::LoadFile` (`smObj3d.cpp:2146`), `smOBJ3D::GetSaveSize`
(`smObj3d.cpp:2089`).

| Block | Count |
| --- | --- |
| `smDFILE_HEADER` | 1 |
| `smDFILE_OBJINFO` | `ObjCounter` (immediately after the header, at offset 556) |
| `smMATERIAL_GROUP` | 1, only if `MatCounter > 0` (seek to `MatFilePoint`) |
| Material block (see [Material block](#material-block)) | `MatCounter` |
| Object block (below), starting at `First_ObjInfoPoint` | `ObjCounter` |

Each object block, read sequentially, is laid out exactly as written by
`smOBJ3D::SaveFile` and sized by `smOBJ3D::GetSaveSize`:

| Block | Count | Present |
| --- | --- | --- |
| `smOBJ3D` | 1 | always |
| `smVERTEX` | `nVertex` | when `nVertex > 0` |
| `smFACE` | `nFace` | when `nFace > 0` |
| `smTEXLINK` | `nTexLink` | when `nTexLink > 0` |
| `smTM_ROT` | `TmRotCnt` | when `TmRotCnt > 0` |
| `smTM_POS` | `TmPosCnt` | when `TmPosCnt > 0` |
| `smTM_SCALE` | `TmScaleCnt` | when `TmScaleCnt > 0` |
| 64-byte matrix (`TmPrevRot`) | `TmRotCnt` | when `TmRotCnt > 0`; skipped, not used by the decoders |
| `int8[32]` physique bone name | `nVertex` | only when `Physique_ptr > 0` |

Notes:

- The `TmPrevRot` block is allocated as `smFMATRIX[TmRotCnt]` but sized with
	`sizeof(smMATRIX) * TmRotCnt` in `SaveFile` / `GetSaveSize` — both are 64
	bytes so the on-disk result is identical either way.
- `smDFILE_OBJINFO.Length` is `GetSaveSize()`: `2236 + nVertex*24 + nFace*36 +
	nTexLink*32 + TmRotCnt*20 + TmPosCnt*16 + TmScaleCnt*16 + TmRotCnt*64 +
	(32*nVertex if Physique)`.
- The first three vertex indices of `smFACE` map 1:1 onto the `smTEXLINK`
	array: texture link `i` holds the UVs of face `i`
	(reference: `decode_actor_texture_coords`). In practice `nTexLink == nFace`
	for the vast majority of objects; deviations are found in objects with
	malformed or uninitialized headers.

#### smDFILE_OBJINFO

40 bytes. One directory entry per object, directly after the header. Written
from `smPAT3D::SaveFile:2895-2902`.

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 32 | `szNodeName` | `int8[32]` | NUL-padded object name |
| 32 | 4 | `Length` | `int32` | Byte length of the object's data block (`GetSaveSize()`) |
| 36 | 4 | `ObjFilePoint` | `int32` | Absolute file offset of the object's `smOBJ3D` |

The loader only uses `ObjFilePoint` when loading a single named object; for
full loads it reads objects sequentially and trusts them to be contiguous
(which `SaveFile` guarantees).

### SMB files

Reference: `smRead3d.cpp:1782` (`smReadModel_Bip`), `smRead3d.cpp:1983-1985`
(SMB written via `ChangeFileExt(file, "smb")` + `Pat3d->SaveFile`).

SMB files are Actor-layout SMD files containing only the bone hierarchy.
Differences enforced by `decode_bones`:

- `smDFILE_HEADER.MatCounter` must be 0 (no material group, no material blocks).
- `smDFILE_HEADER.ObjCounter` must be > 0.
- Objects start at `First_ObjInfoPoint` and are read as `smOBJ3D` directly
	(the objinfo table still precedes them as in any actor file).
- Each object's `Head` must be `0xC1424344` (current writer:
	`0x41424344 | OBJ_HEAD_TYPE_NEW_NORMAL`, `smObj3d.cpp:2115-2119`) or
	`0x41424344` (older files), see `OBJECT_HEAD` / `OBJECT_HEAD_OLD` in
	`src/pt/const.py`.
- `Physique_ptr` must be 0: bones themselves must not carry physique bindings.
- Objects without vertices/faces/texture links are normal; bones are mostly
	transforms (`Tm`, quaternion, `TmRotCnt` / `TmPosCnt` / `TmScaleCnt` keys).
- `NodeParent` names the parent bone; an empty string means root bone.

The actor SMD references the bones through the physique names of its objects.
When a `.smb` companion exists (same basename as the `.smd`), the last
animation frame is taken from the bones instead of the mesh objects.

### Material block

Each material is a 320-byte `smMATERIAL` followed by a texture-path blob.
Reference: `smMATERIAL_GROUP::SaveFile` (`smTexture.cpp:603`),
`smMATERIAL_GROUP::LoadFile` (`smTexture.cpp:713`),
`smMATERIAL_GROUP::GetSaveSize` (`smTexture.cpp:631`).

| Block | Size | Notes |
| --- | --- | --- |
| `smMATERIAL` | 320 | See [smMATERIAL](#smmaterial) |
| Path blob length | 4 | `int32`, byte length of the next field. Written **only when `InUse != 0`** |
| Path blob | path blob length | NUL-separated CP949 strings |

Materials with `InUse == 0` write and read no blob at all.

The blob layout, in order:

1. For each of `TextureCounter` textures: `Name` (NUL-terminated path) then
	`NameA` (NUL-terminated second name).
2. For each of `AnimTexCounter` animated textures: `Name` then `NameA`.

`Name` and `NameA` come from `smTEXTUREHANDLE` (`smType.h:528`, two 64-char
buffers). `Name` is the texture file path; `NameA` is a secondary name whose
mere presence (`NameA[0] != 0`) switches the texture to an alternative pixel
format (`smTexture.cpp:422`) — in the shipped data `NameA` is usually either
empty or a duplicate of `Name`. The engine's loader walks the blob as exactly
`(Name, NameA)` pairs for `TextureCounter` and again for `AnimTexCounter`
strings; the Python decoder currently reads only the `TextureCounter` pairs.
Because the blob length is explicit this cannot desynchronize the cursor, but
animated-texture paths are not decoded.

| Pair index | Role |
| --- | --- |
| 0 | Diffuse texture (map name from `TextureStageState[0]` / `TextureFormState[0]`) |
| 1 | Self-illumination texture (map name from `TextureStageState[1]` / `TextureFormState[1]`), only when exactly 2 paths |

If `MapOpacity == 1`, the diffuse texture doubles as the opacity map.
Map names are reconstructed from script/blend flag bits
(`STAGE_SCRIPT`, `FORM_SCRIPT`, `MTL_FORM_SCRIPT`, `MTL_FORM_BLEND` in
`src/pt/const.py`; reference: `decode_material_name`, `decode_texture_map_name`).

#### MeshState semantics

`MeshState` bit 0 is `SMMAT_STAT_CHECK_FACE` (`smType.h:649`) — the engine's
"solid ground / wall" flag. When a character moves, `smSTAGE3D` height and
movement routines test `MeshState & SMMAT_STAT_CHECK_FACE` on the face's
material and only settle or block on faces that pass (`smStage3d.cpp:648`,
`:748`, `:788`, `:1667`, `:1787`, `:1824`). Faces whose material fails the test
are ghost geometry for movement: the same routines instead probe them for the
water-surface height when `Transparency > 0.1` or the material carries
`sMATS_SCRIPT_ORG_WATER` (`smStage3d.cpp:667`). The upper bits are rendering
attributes riding in the same word: `RENDLATTER` 0x2000 (draw last), `ICE`
0x8000 (slippery friction, `CheckFaceIceFoot`, `smStage3d.cpp:1405`),
`ORG_WATER` 0x10000.

At authoring time the max plugin builds the word with a sequential-overwrite
state machine in `smMATERIAL_GROUP::AddMaterial`
(`smTexture.cpp:880-940`), reproduced exactly by `decode_mesh_state` in
`src/pt/decode/smd.py`. The byte-level outcome:

1. Start `MeshState = 1` when `Transparency == 0`, else 0 — the baseline is
   "opaque materials collide"; the steps below can still clear it.
2. Any wind or `water:` script flag clears the word to 0.
3. `notpass:` forces the word back to 1; `pass:` clears it to 0 (later wins).
4. `render_latter:` ORs in 0x2000, `ice:` ORs in 0x8000.
5. `orgwater:` overwrites the whole word to 0x10000 (non-collidable water).

The plugin writes the result to the file and the client loads it verbatim,
never recomputing it, so the stored `MeshState` is authoritative. Decoders do
not need to re-derive it; `PTModelMaterial.collide` is simply
`(MeshState & 1) == 1`.

In the shipped data the machine produces only five words — 0x1, 0x0, 0x2000,
0x2001, 0x8001 — and `ORG_WATER` never occurs (0 of 182,191 in-use materials
across the entire 3,856-file corpus). `Collidable ⇒ opaque` is exact, but
opaque does not imply collidable: wind, water and `pass:` scripts clear the
flag on 3,210 opaque materials (glass, fences, animated props). Transparent
materials ship with `Transparency` 0.4/0.5, above the 0.1 water-probe
threshold.

`render_latter:` (0x2000) is common in stage files (6,439 materials; the
heaviest user is ice1.smd with 68 on one animated-object file) — see
[Render order](#render-order) for how the engine consumes it.

#### Render order

`RenderD3D` (`smRend3d.cpp:4171-4244`) never sorts triangles. Materials
register into `RendMatrialList` at first use — opaque at the front,
transparent (`MapOpacity || Transparency != 0`) at the rear — so blend order
falls out of registration order, and `RENDLATTER` materials are pulled out of
both regions into a deferred buffer (max 1024, overflow draws inline) drawn
after everything else (§8.6 of the PTClassic draft, chapter 3.2). It is a
painter's-order override for translucent or animated overlays that must draw
over the world regardless of material registration order (ice panes, water
tiles, glow). The misspelling is the engine's own (`sMATS_SCRIPT_RENDLATTER`,
smRead3d.h:61).

For glTF, keep opaque/transparent as the primary sort key (the engine already
splits its lists that way) and carry `render_latter` in extras; consumers can
use it to pick `renderPass` / custom sorting.

### Stage area partition data

After the lights, `smSTAGE3D::SaveFile:2340-2349` writes one record per
non-empty cell of the 256x256 `StageArea` grid (loop order `cnt2` outer, `cnt`
inner — column-major over `[cnt][cnt2]`):

| Block | Size | Notes |
| --- | --- | --- |
| `slen` | 4 | `int32`, equal to `StageArea[cnt][cnt2][0] + 1` — the first `WORD` of the stored buffer is a 0-style terminator, so `slen` = word count |
| Area buffer | `slen * 2` | `uint16[slen]`; word 0 is `slen - 1`, the remaining words are face indices into the stage face array |

On load (`smStage3d.cpp:2476-2491`) each record is read into a shared
`lpwAreaBuff` arena and the cell pointer is rebased into it; `wAreaSize` is
the arena size in `WORD`s. This is engine draw-call batching data; it is not
needed to reconstruct the mesh, and decoders can stop after the lights.
Total size varies from ~30 KB to ~2 MB per stage.

## Structures

### Primitives

#### smVERTEX

24 bytes. Actor mesh vertex (`smType.h:184`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `x` | `int32` | Fixed point 1/256 |
| 4 | 4 | `y` | `int32` | Fixed point 1/256 |
| 8 | 4 | `z` | `int32` | Fixed point 1/256 |
| 12 | 4 | `nx` | `int32` | Normal, fixed point 1/256 |
| 16 | 4 | `ny` | `int32` | Normal, fixed point 1/256 |
| 20 | 4 | `nz` | `int32` | Normal, fixed point 1/256 |

#### smFACE

36 bytes. Actor mesh face (`smType.h:189`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 8 | `v` | `uint16[4]` | Vertex indices a, b, c; `v[3]` is the material id (sic: "matrial") |
| 8 | 24 | `t` | `float[2][3]` | UV per corner (`smFTPOINT t[3]`); unused in files, UVs come from `smTEXLINK` |
| 32 | 4 | `lpTexLink_ptr` | `uint32` | Stale pointer, non-zero means the face has texture links |

#### smTEXLINK

32 bytes. One triangle's texture coordinates (`smType.h:178`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 12 | `u` | `float[3]` | U for corners a, b, c |
| 12 | 12 | `v` | `float[3]` | V for corners a, b, c. Actor: `1 - v`; stage: `-v` |
| 24 | 4 | `hTexture_ptr` | `uint32` | Stale texture handle |
| 28 | 4 | `NextTex_ptr` | `uint32` | Stale pointer to the next link of multi-texture faces; loader converts pointer differences to element indices |

#### smSTAGE_VERTEX

28 bytes. Stage vertex (`smType.h:300`, original comment confirms "28 bytes").

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `sum` | `uint32` | Runtime sorting value |
| 4 | 4 | `lpRendVertex_ptr` | `uint32` | Stale pointer |
| 8 | 4 | `x` | `int32` | Fixed point 1/256 |
| 12 | 4 | `y` | `int32` | Fixed point 1/256 |
| 16 | 4 | `z` | `int32` | Fixed point 1/256 |
| 20 | 8 | `sDef_Color` | `int16[4]` | Vertex color. Comment claims "( RGBA )" but the engine color macros `SMC_B=0, SMC_G=1, SMC_R=2, SMC_A=3` (`smType.h:59-62`) make the memory order **BGRA** |

#### smSTAGE_FACE

28 bytes. Stage face (`smType.h:315`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `sum` | `uint32` | Runtime sorting value |
| 4 | 4 | `CalcSum` | `int32` | Runtime sorting value |
| 8 | 8 | `Vertex` | `uint16[4]` | Vertex indices a, b, c; `Vertex[3]` is the material id (sic: "Matrial") |
| 16 | 4 | `lpTexLink_ptr` | `uint32` | Stale pointer; consecutive faces' pointers differ by exactly `sizeof(smTEXLINK)` (32), so the index into the `smTEXLINK` array is derived from the pointer difference (see `decode_stage_texture_coords`) |
| 20 | 8 | `VectNormal` | `int16[4]` | Face normal; comment: "(nx, ny, nz, [0,1,0]-axis Y)" |

#### smLIGHT3D

26 bytes of payload, 28 bytes on disk (2 bytes of trailing struct padding).
`smType.h:124`.

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `type` | `int32` | Light type flags: `smLIGHT_TYPE_NIGHT=0x1`, `LENS=0x2`, `PULSE2=0x4`, `OBJ=0x8` (patched-in), `DYNAMIC=0x80000` |
| 4 | 4 | `x` | `int32` | Fixed point 1/256 |
| 8 | 4 | `y` | `int32` | Fixed point 1/256 |
| 12 | 4 | `z` | `int32` | Fixed point 1/256 |
| 16 | 4 | `Range` | `int32` | Fixed point 1/256 |
| 20 | 2 | `r` | `int16` | 0-255 |
| 22 | 2 | `g` | `int16` | 0-255 |
| 24 | 2 | `b` | `int16` | 0-255 |

The 2 pad bytes are serialized with the struct; in debug-built files they
contain `0xCDCDCD` fill, elsewhere zeros. A 26-byte stride desynchronizes
every record after the first — the correct on-disk stride is 28 (verified
against all lightmapped stages).

### Transform keys

#### smTM_ROT

20 bytes. Rotation keyframe (`smType.h:197`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `frame` | `int32` | Frame number in engine ticks |
| 4 | 16 | `x`, `y`, `z`, `w` | `float` | Rotation quaternion |

#### smTM_POS

16 bytes. Position keyframe (`smType.h:208`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `frame` | `int32` | Frame number in engine ticks |
| 4 | 12 | `x`, `y`, `z` | `float` | Position. Note: floats, unlike `smVERTEX` / `smTM_SCALE` which use fixed point |

#### smTM_SCALE

16 bytes. Scale keyframe (`smType.h:214`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `frame` | `int32` | Frame number in engine ticks |
| 4 | 12 | `x`, `y`, `z` | `int32` | Fixed point 1/256 |

#### smFRAME_POS

16 bytes. Frame range for one object's transform keys, as stored in
`smDFILE_HEADER.TmFrame` and `smOBJ3D.TmRotFrame` / `TmPosFrame` /
`TmScaleFrame` (`smObj3d.h:44`).

| Offset | Size | Field | Type |
| ---: | ---: | --- | --- |
| 0 | 4 | `StartFrame` | `int32` |
| 4 | 4 | `EndFrame` | `int32` |
| 8 | 4 | `PosNum` | `int32` |
| 12 | 4 | `PosCnt` | `int32` |

### Matrices

#### smMATRIX

64 bytes. 16.16 fixed point, column-major. The decoder divides the rotation
part by 256 (compensating for scale encoded in the matrix) and the translation
row by 256.

| Offset | Size | Field | Type |
| ---: | ---: | --- | --- |
| 0 | 64 | `_11` .. `_44` | `int32[16]`, row-major naming of a column-major matrix |

#### smFMATRIX

64 bytes. Same layout as `smMATRIX` but `float` (`smType.h:108`). Written
after the scale keys of each object as the `TmPrevRot` block; the decoders
skip it without using it.

### smMATERIAL_GROUP

88 bytes. Written before the material blocks (`smTexture.h:102`).

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `Head` | `uint32` | Block magic |
| 4 | 4 | `smMaterial_ptr` | `uint32` | Stale pointer |
| 8 | 4 | `MaterialCount` | `uint32` | Should match `smDFILE_HEADER.MatCounter` |
| 12 | 4 | `ReformTexture` | `int32` | |
| 16 | 4 | `MaxMaterial` | `int32` | |
| 20 | 4 | `LastSearchMaterial` | `int32` | |
| 24 | 64 | `szLastSearchName` | `int8[64]` | |

### smMATERIAL

320 bytes. One material (`smType.h:592`). Only decoded when `InUse > 0`.

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `InUse` | `uint32` | 0 = no path blob follows, skip material |
| 4 | 4 | `TextureCounter` | `uint32` | Number of textures used by this material |
| 8 | 32 | `smTexture_ptr` | `uint32[8]` | Stale pointers |
| 40 | 32 | `TextureStageState` | `uint32[8]` | Per-stage script flags (map name bits) |
| 72 | 32 | `TextureFormState` | `uint32[8]` | Per-stage form flags (map name bits) |
| 104 | 4 | `ReformTexture` | `int32` | |
| 108 | 4 | `MapOpacity` | `int32` | 1 = diffuse texture is also the opacity map |
| 112 | 4 | `TextureType` | `uint32` | `SMTEX_TYPE_MULTIMIX=0`, `SMTEX_TYPE_ANIMATION=1` |
| 116 | 4 | `BlendType` | `uint32` | Blend flags (map name bits) |
| 120 | 4 | `Shade` | `uint32` | |
| 124 | 4 | `TwoSide` | `uint32` | Non-zero = two-sided |
| 128 | 4 | `SerialNum` | `uint32` | |
| 132 | 12 | `Diffuse` | `float[3]` | RGB diffuse color (`smFCOLOR`) |
| 144 | 4 | `Transparency` | `float` | 0 = opaque; > 0.1 also feeds the water-height path at load |
| 152 | 4 | `TextureSwap` | `int32` | |
| 156 | 4 | `MatFrame` | `int32` | Material animation frame |
| 160 | 4 | `TextureClip` | `int32` | TRUE allows texture clipping |
| 164 | 4 | `UseState` | `int32` | Script flags (map name bits) |
| 168 | 4 | `MeshState` | `int32` | Collision / rendering attributes, see [MeshState semantics](#meshstate-semantics) |
| 172 | 4 | `WindMeshBottom` | `int32` | Wind script flags (`sMATS_SCRIPT_WINDZ1` etc.) |
| 176 | 128 | `smAnimTexture_ptr` | `uint32[32]` | Stale pointers |
| 304 | 4 | `AnimTexCounter` | `uint32` | Animated texture count |
| 308 | 4 | `FrameMask` | `uint32` | Animation frame mask |
| 312 | 4 | `Shift_FrameSpeed` | `uint32` | Frame speed (timer shift) |
| 316 | 4 | `AnimationFrame` | `uint32` | Current frame (`SMTEX_AUTOANIMATION=0x100` = auto) |

### smOBJ3D

2236 bytes. One mesh object or bone (`smObj3d.h:76`). Followed inline by its
vertex, face, texture link and transform-key arrays.

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `Head` | `uint32` | `0xC1424344` = `0x41424344 \| 0x80000000` (`OBJ_HEAD_TYPE_NEW_NORMAL`); older files `0x41424344` |
| 4 | 4 | `Vertex_ptr` | `uint32` | Stale pointer |
| 8 | 4 | `Face_ptr` | `uint32` | Stale pointer |
| 12 | 4 | `TexLink_ptr` | `uint32` | Stale pointer |
| 16 | 4 | `Physique_ptr` | `uint32` | Stale pointer, non-zero = object is bound to bones (physique names follow the key arrays) |
| 20 | 24 | `ZeroVertex` | `smVERTEX` | Object-center vertex scratch |
| 44 | 24 | `maxZ`, `minZ`, `maxY`, `minY`, `maxX`, `minX` | `int32` | Bounding box, fixed point 1/256 |
| 68 | 4 | `dBound` | `int32` | Bounding sphere radius^2 |
| 72 | 4 | `Bound` | `int32` | Bounding sphere radius |
| 76 | 4 | `MaxVertex` | `int32` | |
| 80 | 4 | `MaxFace` | `int32` | |
| 84 | 4 | `nVertex` | `int32` | Vertex count |
| 88 | 4 | `nFace` | `int32` | Face count |
| 92 | 4 | `nTexLink` | `int32` | Texture link count |
| 96 | 4 | `ColorEffect` | `int32` | Color effect flag |
| 100 | 4 | `ClipStates` | `uint32` | Clip request mask |
| 104 | 12 | `Posi` | `POINT3D` | Runtime position |
| 116 | 12 | `CameraPosi` | `POINT3D` | Runtime position |
| 128 | 12 | `Angle` | `POINT3D` | Runtime angle |
| 140 | 32 | `Trig` | `int32[8]` | |
| 172 | 32 | `NodeName` | `int8[32]` | NUL-padded object name |
| 204 | 32 | `NodeParent` | `int8[32]` | NUL-padded parent object name; empty = root |
| 236 | 4 | `pParent_ptr` | `uint32` | Stale pointer |
| 240 | 64 | `Tm` | `smMATRIX` | Base transform matrix |
| 304 | 64 | `TmInvert` | `smMATRIX` | Inverse of `Tm` |
| 368 | 64 | `TmResult` | `smFMATRIX` | Animation result scratch |
| 432 | 64 | `TmRotate` | `smMATRIX` | Base rotation matrix (used on objects without rotation keys) |
| 496 | 64 | `mWorld` | `smMATRIX` | World transform scratch |
| 560 | 64 | `mLocal` | `smMATRIX` | Scale-coordinate transform scratch |
| 624 | 4 | `lFrame` | `int32` | Last frame |
| 628 | 16 | `qx`, `qy`, `qz`, `qw` | `float` | Rotation quaternion |
| 644 | 12 | `sx`, `sy`, `sz` | `int32` | Scale, fixed point 1/256 |
| 656 | 12 | `px`, `py`, `pz` | `int32` | Position, fixed point 1/256 |
| 668 | 4 | `TmRot_ptr` | `uint32` | Stale pointer |
| 672 | 4 | `TmPos_ptr` | `uint32` | Stale pointer |
| 676 | 4 | `TmScale_ptr` | `uint32` | Stale pointer |
| 680 | 4 | `TmPrevRot_ptr` | `uint32` | Stale pointer; points at the 64-byte-per-rotation matrix block stored after the keys |
| 684 | 4 | `TmRotCnt` | `int32` | Rotation key count |
| 688 | 4 | `TmPosCnt` | `int32` | Position key count |
| 692 | 4 | `TmScaleCnt` | `int32` | Scale key count |
| 696 | 512 | `TmRotFrame` | `smFRAME_POS[32]` | |
| 1208 | 512 | `TmPosFrame` | `smFRAME_POS[32]` | |
| 1720 | 512 | `TmScaleFrame` | `smFRAME_POS[32]` | |
| 2232 | 4 | `TmFrameCnt` | `int32` | Total TM frame count |

### smSTAGE3D

262260 bytes. Read directly after `smDFILE_HEADER` in stage files
(`smStage3d.h:12`). The huge `StageArea_ptr` array is runtime data; only the
tail fields carry file information.

| Offset | Size | Field | Type | Notes |
| ---: | ---: | --- | --- | --- |
| 0 | 4 | `Head` | `uint32` | Written as `FALSE` (0) by the stage writer |
| 4 | 262144 | `StageArea_ptr` | `uint32[256][256]` | Stale pointers |
| 262148 | 4 | `AreaList_ptr` | `uint32` | Stale pointer |
| 262152 | 4 | `AreaListCnt` | `int32` | Cursor count for area faces |
| 262156 | 4 | `MemMode` | `int32` | Memory mode |
| 262160 | 4 | `SumCount` | `uint32` | Render sum count |
| 262164 | 4 | `CalcSumCount` | `int32` | Calc number count (incremented after load) |
| 262168 | 4 | `Vertex_ptr` | `uint32` | Stale pointer |
| 262172 | 4 | `Face_ptr` | `uint32` | Stale pointer |
| 262176 | 4 | `TexLink_ptr` | `uint32` | Stale pointer |
| 262180 | 4 | `smLight_ptr` | `uint32` | Stale pointer |
| 262184 | 4 | `smMaterialGroup_ptr` | `uint32` | Stale pointer |
| 262188 | 4 | `StageObject_ptr` | `uint32` | Stale pointer |
| 262192 | 4 | `smMaterial_ptr` | `uint32` | Stale pointer |
| 262196 | 4 | `nVertex` | `int32` | Stage vertex count |
| 262200 | 4 | `nFace` | `int32` | Stage face count |
| 262204 | 4 | `nTexLink` | `int32` | Stage texture link count |
| 262208 | 4 | `nLight` | `int32` | Stage light count |
| 262212 | 4 | `nVertColor` | `int32` | Vertex color input count |
| 262216 | 4 | `Contrast` | `int32` | Contrast (chroma) |
| 262220 | 4 | `Bright` | `int32` | Brightness |
| 262224 | 12 | `VectLight` | `POINT3D` | Smooth-lighting light vector (sun direction) |
| 262236 | 4 | `lpwAreaBuff_ptr` | `uint32` | Stale pointer |
| 262240 | 4 | `wAreaSize` | `int32` | Area buffer arena size in `WORD`s |
| 262244 | 16 | `StageMapRect` | `RECT` | Rect covering the whole stage |

## Original code quirks and bugs

These behaviors are in the original engine. They are preserved and documented
because real files depend on them.

1. **Stage writer leaves `ObjCounter` uninitialized** (`smSTAGE3D::SaveFile`
	never assigns it). Debug builds write `0xCCCCCCCC`. Stage dispatch must use
	`szHeader` only.
2. **Stage writer hardcodes `MatFilePoint = 556`** even though the material
	group is written after the 262260-byte `smSTAGE3D`. The stage loader
	compensates by never seeking — it reads materials directly after
	`smSTAGE3D`. Actor files compute `MatFilePoint` correctly
	(`556 + 40 * ObjCounter`).
3. **Physique reading is gated on a stale pointer.** `smOBJ3D::SaveFile`
	writes physique names when the runtime `Physique` pointer is non-null, but
	`smOBJ3D::LoadFile` decides whether to read them using the `Physique` field
	**as loaded from disk** — i.e. the stale runtime address. It works only
	because non-null garbage is still non-null. A file whose physique pointer
	happened to be 0 would desynchronize the loader.
4. **`TmPrevRot` size mismatch.** The block is allocated as `smFMATRIX` but
	written/sized with `sizeof(smMATRIX)`; both are 64 bytes so the file format
	is unaffected.
5. **`smFACE.t` UVs are written but never used.** The loader immediately
	re-links faces to `smTEXLINK` entries; the `t` array is payload dead weight
	kept for struct compatibility.
6. **Debug-heap garbage in serialized data.** `sum`, `CalcSum`,
	`lpRendVertex_ptr`, `TmPrevRot` pad bytes and other uninitialized fields are
	written verbatim, so shipped files contain `0xCDCDCDCD` fill from MSVC
	debug builds. Loaders either ignore these fields or (bug 3) accidentally
	rely on them being non-zero.
7. **`smSTAGE_VERTEX.sDef_Color` is documented as RGBA but stored BGRA** (see
	struct table). The color macros are the only truth.
8. **`smMATERIAL_GROUP::LoadFile` reads the blob only for `InUse != 0`**
	materials, matching the writer; nothing skips the blob for unused
	materials because there is nothing to skip. Any tool that assumes one blob
	per material regardless of `InUse` will desynchronize.
9. **The loader never validates `Head` in stage files** and the stage writer
	writes `Head = 0`; only the actor object path checks `Head`.
10. **`smOBJ3D::LoadFile` trusts `nVertex` / `nFace` / `nTexLink` /
	`TmRotCnt` counts blindly** — malformed counts read out of desynced
	positions produce wild allocations in the original engine; decoders must
	therefore never resync mid-object and should treat a failed object read as
	fatal.

## Coordinates and units

- Positions and normals are fixed point `raw / 256` (engine units are inches;
	`SCALE_INCH_TO_METER = 0.0254` in `src/pt/const.py` converts to meters).
- Actor vertices decode as-is (`x, y, z`).
- Stage vertices decode with Y and Z swapped (`x, z, y`); reference:
	`smRead3d.cpp::smSTAGE3D_ReadASE_GEOMOBJECT`.
- Texture V coordinates are flipped: actor `v' = 1 - v` (file `v` is in
	0..1), stage `v' = -v` (file `v` is in -4..0, lightmap tiles go negative).
- Vertex colors are BGRA in the file (see quirk 7). Averaging in the original
	exporter makes them lossy; they are surfaced as-is for manual review
	(`decode_stage_vertices`).
- Stage vertex colors observed so far are grayscale (r = g = b) with alpha 255.
- Animation frames are engine ticks; `last_frame / ticks_per_frame` yields
	display frames (see `decode_actor_animation`, `decode_bones`). The engine
	computes a pattern's max frame from the last rotation or position key
	(`smPAT3D::AddObject`), ignoring scale keys for this purpose.
