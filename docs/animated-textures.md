# Animated Textures

Flipbook materials (`anim2:`..`anim16:` in the 3D Studio Max ASE material
name) swap a whole texture every few engine ticks. This doc covers how the
engine stores and renders them, how the tool decodes them, and how they are
exported to glTF. For static multi-texture (lightmap) materials see
`docs/texlink.md`.

## 1. Engine: data layout

The `smMATERIAL` struct (320 bytes) carries the flipbook state:

| field | meaning |
| --- | --- |
| `TextureCounter` | number of static textures (1 for flipbooks: the diffuse) |
| `AnimTexCounter` | number of flipbook frames (2..16) |
| `TextureType` | `SMTEX_TYPE_ANIMATION = 0x1` for flipbooks |
| `Shift_FrameSpeed` | frame duration = `2^Shift_FrameSpeed` ms (right shift of the tick count) |
| `FrameMask` | `frame count - 1`; ANDed after the shift to wrap the index |
| `AnimationFrame` | `SMTEX_AUTOANIMATION = 0x100` = run automatically; any other value pins the frame (`SetMaterialAnimFrame`) |
| `MatFrame` | render-batch cache stamp, not frame data (always 0 on disk) |

Authoring: the ASE material name carries the script (`anim8:` etc.). At
import, `ChangeMaterialToAnimation` (`smTexture.cpp:1110-1136`) appends the
frame bitmaps as extra (Name, NameA) path pairs after the diffuse, then
`AddMaterial` packs the blob. Two authoring rules matter for tooling:

- the frames are expected in the **same directory** as the diffuse
  (`AddMaterial` derives the folder from `BITMAP[0]`, smTexture.cpp:1002-1016),
- the frame count is a power of two (`anim2`..`anim16`), so `FrameMask` can
  wrap with a simple AND.

File layout: after the `smMATERIAL` struct, `smReadMaterial` loads one blob
per material when `InUse != 0`: `TextureCounter` NUL-terminated path pairs
(Name, NameA) first, then `AnimTexCounter` more pairs
(`smTexture.cpp:738-764`). The decoded group is overlaid onto
`smMaterial[MatNum]` only on success (`smTexture.cpp:735`), which is why a
skipped material must not shift the material array.

## 2. Engine: rendering

Every frame, for `TextureType == SMTEX_TYPE_ANIMATION` materials
(`smRend3d.cpp:3835-3854`):

```
frame = (RendStatTime >> Shift_FrameSpeed) & FrameMask
SetTexture(0, smAnimTexture[frame])
```

- `RendStatTime` is the Win32 tick count in **milliseconds**, so the frame
  period is exactly `2^Shift_FrameSpeed` ms. All shipped materials use
  `Shift_FrameSpeed = 6` (64 ms/frame, ~15.6 fps).
- The animation is a **whole-texture swap** (one image file per frame), not a
  uv scroll. For static multi-texture (lightmap) materials see
`docs/texlink.md`; section 5-6 lists every shipped stage/actor that uses
flipbooks or lightmaps. Tiling/atlas tricks inside a frame are free to author since the
  uv coordinates are the diffuse's.
- While the material animates, the static `smTexture[0]` (the diffuse) is
  never sampled. Shipped data confirms: some flipbook materials have a
  diffuse that is *not* frame 0 (e.g. forever-fall `3ani-*` uses `ftwa_3`).

## 3. Decoder (`src/pt/decode/smd.py`)

`decode_material` reads the animation pairs after the texture pairs into
`PTTextureMap.anim_frames` (raw engine path strings, backslashes preserved).
Timing fields surface on `PTModelMaterial`:

| PTModelMaterial | smMATERIAL |
| --- | --- |
| `anim_speed` | `Shift_FrameSpeed` |
| `anim_mask` | `FrameMask` |
| `mat_frame` | `MatFrame` |

Materials with `InUse == 0` return `None` (they occupy a slot but carry no
blob; shipped data has none).

Survey of the shipped client: 288 animated materials across 211 SMD files,
all `TextureType = 0x1`, `Shift_FrameSpeed = 6`, `AnimationFrame = 0x100`,
`FrameMask = count - 1`. Frame files are sometimes missing on disk (97
materials have zero frames present, 2 are partial); the decoder keeps what
the filesystem offers, matching what the engine would have shown.

## 4. glTF export (`src/pt/encode/gltf.py`)

glTF has no flipbook concept, so each animated material is exported as one
atlas texture plus a uv animation that walks the atlas slots:

1. **Atlas packing** - the frames found on disk are packed into
   `<first-frame-root>-anim.png`: a uniform grid (up to
   `ANIM_ATLAS_COLUMNS = 4` cells per row) on a canvas whose width and
   height are each a power of two. Frame k sits at column `k % 4`, row
   `k // 4`.
2. **Material override** - the material's `baseColorTexture` points at the
   atlas with a `KHR_texture_transform` showing frame `MatFrame % count` at
   rest (offset/scale of that cell). The engine never samples the diffuse
   for these materials, so the atlas *replaces* it.
3. **Dedicated mesh nodes** - every primitive using an animated material is
   split out of its object's static meshes into a separate mesh node named
   `<object>-<n>-anim` (same node transform). This keeps the uv animation
   from touching non-animated primitives that share the object.
4. **`tex-anim` animation** - one glTF animation (plus one per extra
   material if a file mixes flipbooks) with a `uv` channel per `-anim`
   node: keys every `2^speed` ms moving the `KHR_texture_transform`
   offset/scale to frame k's cell; the last key wraps back to frame 0. The
   channel target carries `KHR_texture_transform` with the texture index the
   keyframes address.

### Consumer support

- **three.js-style loaders**: read channel-target `KHR_texture_transform`
  and play the flipbook.
- **Blender / Godot**: import the static state only - the material shows
  the rest frame (`MatFrame % count`) and the `-anim` nodes appear as
  separate objects. The `tex-anim` animation is listed but Blender has no
  image-swap concept for glTF, so texture animation must be re-authored
  there (the atlas + timing data above is everything an authoring script
  needs).

## 5. Where animated textures are used

Actors **never** render flipbook frames - their material lists mention
`anim:` names only as leftovers from effect/weapon scripts, and no face
references those materials. Only **stages** (plus their prop/rotation
objects) use them. 152 exported glTFs carry animated materials:

| output folder | files | content |
| --- | --- | --- |
| `Field/cave` | 31 | `Dcave_ani01`-`13`, `Tcave_ani01`-`16` (+ base cave stages): flames (`flame_0`-`7`), water glow (`ftwa_0`-`3`) |
| `Field/dungeon` | 58 | `dun-1`..`dun-5`, all `dun-4-ani-*` / `dun-5-ani-*`: dungeon flames |
| `Field/forever-fall` | 30 | `1ani-*`, `3ani-*`, `forever-fall-02/03`: falling-leaf/water (`ftwa_*`, `kwa_*`) |
| `Field/forest` | 15 | `3ani-01`-`14`, `fore-3` |
| `Field/Ruin` | 5 | `ruin-1`..`4`, `ruin_ani01`: flames, wood fire (`fwood_0`-`3`), sea (`sea_0`-`3`) |
| `Field/endless` | 3 | `dun-7`, `dun-8`, `dun-9` |
| `Field/Ice` | 2 | `ice_ani_01`, `ice_ura` |
| `Field/Sod` | 2 | `sod-1`, `sod-2` |
| `Field/AncientW` | 1 | `ancientW` (also `RotObj05`-`10` props) |
| `Field/Boss` | 1 | `Boss` |
| `Field/HeartOfFire` | 1 | `HeartOfFire` |
| `Field/Mine` | 1 | `mine-1` |
| `Field/Quest` | 1 | `quest_IV` |
| `Field/Slab` | 1 | `Slab` |

Sampling suggestion: `Field/cave/Tcave_ani13.gltf` (8-frame flame + 4-frame
water glow), `Field/Ruin/ruin-2.gltf` (three different flipbooks incl.
`fwood`), `Field/forever-fall/3ani-04.gltf` (diffuse ≠ frame 0 case).

## 6. Lightmap quick reference

Baked lightmaps (exported as `occlusionTexture` with `texCoord = 1`, second
texture of the NextTex chain - see `docs/texlink.md`) exist **only on
stages**: `Field/dungeon` (all 79 files), `Field/SeaA` (12),
`Field/Fall_Game` (19 chandelier props), `Field/endless` (3),
`Field/AncientW`, `Field/Mine`, `Field/Slab`, `Field/swamp`. No actor has a
baked lightmap. (`occlusionTexture` with `texCoord = 0` on actors/items is
the *opacity* map export, not a lightmap.)

The `Field/Mine`, `Field/endless`, `Field/LandofNurwn` and `Field/Slab` files
also carry three-texture materials (diffuse + glow + `*LightingMap.*`), where
the lightmap rides the third chain link and exports as `occlusionTexture`
with `texCoord = 2` (see `docs/texlink.md` §2).
