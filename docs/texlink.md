# The TexLink System

How Priston Tale stores per-face texture coordinates, and how one face ends up
with more than one set of them.

This document covers the `smTEXLINK` system as it exists in the shipped files
and in the original engine source (`.local/PTClassic/src/smLib3d`). Everything
here was verified against both the source and the binary data.

---

## 1. Why TexLink exists

In a modern mesh, every vertex carries one UV coordinate and the index buffer
says which vertices make up a triangle. Priston Tale's meshes do neither of
those things.

Instead:

- **Vertices are just positions.** `smVERTEX` / `smSTAGE_VERTEX` have no UVs.
- **Faces are just vertex indices.** `smFACE` / `smSTAGE_FACE` are
  `(v0, v1, v2, material_id)` plus dead weight (a `t[3][2]` float block that
  the ASE importer never filled in - real UVs never live there).
- **All texture coordinates live in a separate array:** `TexLink`, an array of
  `smTEXLINK` structs, pointed at by the face through a **raw pointer**.

So the relationship is:

```
Face[i] --lpTexLink--> TexLink[k] --u[3], v[3]--> UVs for face i
```

`smTEXLINK` (smType.h:178):

| field           | size | meaning                                                |
|-----------------|------|--------------------------------------------------------|
| `u[3]`, `v[3]`  | 24   | one UV triplet for the face's three vertices           |
| `hTexture_ptr`  | 4    | runtime texture handle (garbage on disk)               |
| `NextTex_ptr`   | 4    | pointer to the next link of the face (0 = end of chain)|

That's 32 bytes per link. One link = one UV set = one texture stage.

## 2. The chain: how one face gets several textures

`AddTexLink` (smObj3d.cpp:590-618, stage twin at smStage3d.cpp:1152-1180) is
called once per face *per texture* by the ASE importers. Its logic:

1. If the face has no link yet, the new link becomes the face's
   `lpTexLink`.
2. If the face already has one, walk that link's `NextTex` chain to the end
   (max 8 hops) and append the new link there.

So the first texture's UVs land in link 0 of the chain, the second texture's
UVs in link 1, and so on. A face drawn with `diffuse + lightmap` has a chain
of exactly two links.

The renderer is the consumer that makes the semantics precise
(smRend3d.cpp:3216-3250, `SetD3DRendBuff`): for each face it walks the chain
with a counter `tcnt`, using the *chain index as the Direct3D texture
coordinate index*:

```
tl = rendface->lpTexLink;
for (tcnt = 0; tcnt < 8; tcnt++) {
    ...
    // UVs of tl feed texture stage tcnt (TEXCOORD_tcnt)
    tl = tl->NextTex;
}
```

The second stage is combined with the first with `D3DTOP_ADD`
(smRend3d.cpp:3628-3630). So the on-disk chain order **is** the blend order:
`chain[0]` = diffuse, `chain[1]` = the map added on top of it.

**What goes in the second slot, in shipped data:**

- **Stage dungeons** (dun 1-5, the `*LM_` maps): a baked lightmap -
  `Dun-1f-XXLightingMap.bmp`. These materials have `TextureCounter == 2` and
  the material blob carries both paths: `[diffuse, LightingMap]`. This is
  96%+ of all faces in dun-1 / Dun-6a.
- **A handful of actors**: a second state (`BS_MODULATE:FS_NONE:`) that acts
  as an emissive/glow pass. Same chain mechanics, different blend intent.

The chain depth equals the number of texture stages the face participates in.
Histograms from shipped files:

| file                    | 0 links | 1 link | 2 links |
|-------------------------|---------|--------|---------|
| `dun-1.smd` (stage)     | 12      | 1,358  | 33,439  |
| `Dun-6a.smd` (stage)    | 0       | 1,242  | 61,421  |
| `ruin-2.smd` (stage)    | 93      | 60,350 | 0       |
| `MN-012.smd` (actor)    | 0       | 1,144  | 0       |

Nothing in shipped data ever exceeds 2 (the engine's "max 8" is defensive).

## 3. The pointer fixup: why the on-disk "pointers" are garbage

`smOBJ3D::SaveFile` / `smSTAGE3D::SaveFile` dump the C structs to disk
verbatim, **including pointer fields**. Those pointers were valid only inside
the exporting process. On disk they are stale addresses from 2001-something,
meaningless to everyone - but *relatively* meaningful.

On load (smObj3d.cpp:2188-2204, smStage3d.cpp:2429-2453) the engine rebases
them:

```c
lpOldTexLink = TexLink;             // address TexLink had in the exporter
for (cnt = 0; cnt < nTexLink; cnt++)
    if (TexLink[cnt].NextTex)
        TexLink[cnt].NextTex = TexLink + (TexLink[cnt].NextTex - lpOldTexLink);
for (cnt = 0; cnt < nFace; cnt++)
    if (Face[cnt].lpTexLink)
        Face[cnt].lpTexLink = TexLink + (Face[cnt].lpTexLink - lpOldTexLink);
```

The trick: `TexLink[cnt].NextTex - lpOldTexLink` is a *difference of two
stale addresses*, which equals the element offset between them **if both
pointers came from the same memory layout**. The exporters allocated the
whole model in one go, so they did.

The same arithmetic works in Python with integer pointers: the array index of
a stale pointer `p` is `(p - base) / 32`, where `base` is any stale address
whose element index you know.

### Choosing `base`

`AddTexLink` appends links strictly in face order, so `TexLink[0]` belongs to
the *first face that has any link*. Therefore:

- the **smallest** non-null face pointer in the file is the stale address of
  `TexLink[0]`,
- and shipped files point face `i` at `TexLink[base_face + i]`, which makes
  the whole rebase a linear index with no overlaps.

Observed in every shipped stage and actor: face pointers are monotonically
increasing with a delta of exactly 32 bytes, and `NextTex` targets are fully
disjoint from face heads (a link never serves two faces).

Note that `hTexture_ptr` cannot be salvaged this way - the exporter's texture
handles point into a different allocation (the material group), not into the
TexLink array. The engine never re-derives them either; it re-resolves
textures by material id at draw time. Which face uses which *texture* is
determined by `face.material_id`, not by the chain. The chain only carries
*UV sets*.

## 4. File layout (where the arrays actually sit)

The loaders read sequentially, so layout is file order:

**Stage SMD** (smSTAGE3D::LoadFile, smStage3d.cpp:2362):

```
smDFILE_HEADER (556)
smSTAGE3D                          <- nVertex, nFace, nTexLink, nLight live here
material group + material blobs    <- only if MatCounter > 0
smSTAGE_VERTEX[nVertex]
smSTAGE_FACE[nFace]                <- each with stale lpTexLink_ptr
smTEXLINK[nTexLink]                <- the UV pool, chains live here
smLIGHT3D[nLight]
StageArea partitions               <- engine draw-batching, unused by us
```

**Actor SMD**, per object block (smOBJ3D::LoadFile, smObj3d.cpp:2146):

```
smOBJ3D                            <- nVertex, nFace, nTexLink
smVERTEX[nVertex]
smFACE[nFace]                      <- stale lpTexLink_ptr
smTEXLINK[nTexLink]
physique strings[nVertex]          <- only if Physique_ptr != 0
TmRot keys, TmPos keys, TmScale keys, TmPrevRot matrices
```

The **gotcha** between the two layouts: in *stages*, vertices+faces+texlinks
are three consecutive arrays, so from the texlink cursor the faces sit at
`cursor - nFace*sizeof(face)`. In *actors*, the face array is at the same
relative offset **but the cursor must end at `texlink_offset +
nTexLink*sizeof(smTEXLINK)`**, not where the face re-read ends - because
`sizeof(smFACE)` is 36 bytes while the links are 32, so re-reading `nFace`
faces from before the array overshoots by 4 bytes per face. The decoders
compensate by always seeking to the *computed* end of the TexLink array after
reading, which is what the next function (physique or animation keys) expects.

## 5. UV convention quirks

The two importers store V differently, and the decoders invert both:

- **Stage importer**: `AddVertex` maps ASE `(x,y,z)` to `(x,z,y)` and stores
  `v` as-authored (which tiles: stage diffuse UVs routinely run to ±10).
  The decoder negates: `v_stored = -v`, so exported UV = `-v`.
- **Actor importer**: `AddTexLink` receives `1-fv` at import
  (smRead3d.cpp:1548). The decoder undoes it: `v = 1 - v_stored`.

Both decoders write PT space UVs into the internal model; the glTF exporter
then applies the glTF-mandated `1 - v` flip once more on the way out
(glTF's UV origin is top-left; D3D's is bottom-left).

For the dungeon lightmaps this composes to exactly the authored atlas
coordinates: stored lightmap `v` comes out negated in [−1, 0], the internal
model holds −(stored v) ∈ [0, 1], and the exporter's final `1 - v` flip maps
it back to the [0, 1] atlas range. Verified over all 100,317 lightmapped
vertices of dun-1: exported `TEXCOORD_1` spans [0.003, 0.997] on both axes,
exactly the lightmap atlas footprint.

## 6. How this project decodes it now

`src/pt/decode/smd.py`:

- `decode_texlink_chain(texlinks, base, tex_index)` walks the `NextTex`
  chain of one link, returning every link of the face. Cycle-safe, bounded by
  the array.
- `decode_stage_texture_coords` / `decode_actor_texture_coords` rebase each
  face's stale pointer to `TexLink[...]` index, walk the chain, and emit one
  `uv_sets` list per face: `uv_sets[0]` = primary UV set,
  `uv_sets[1]` = lightmap/glow set, etc. Faces without a link get an empty
  list (no UVs, never written).
- `decode_material` classifies the second texture path: names containing
  `lightingmap` become `texture_map.lightmap_path`, everything else stays
  `selfillum_path` (actor glow maps).

`src/pt/encode/gltf.py`:

- `make_primitives` writes `uv_sets[0]` to `TEXCOORD_0` and `uv_sets[1]` to
  `TEXCOORD_1` (each flipped `1 - v`).
- Lightmap-carrying materials export the lightmap as `occlusionTexture` with
  `texCoord: 1` - the closest standard-glTF stand-in for a baked
  light-add pass; consumers wanting the original look add the map over the
  diffuse themselves, exactly as the engine did.
- Faces within one primitive may disagree on chain length; a primitive gets
  `TEXCOORD_1` only if *some* face has a second set, others read it as the
  zero UV.

## 7. Known limits

- `hTexture_ptr` is dead on disk and stays unused (material id determines the
  texture).
- Materials with 3+ texture stages would need `TEXCOORD_2+`; none exist in
  shipped data.
- Animated textures (`AnimTexCounter`, `anim2:`..`anim16:` materials) are a
  separate gap - their frame lists live in the material blob's animation
  section and are not decoded yet (findings.md gap #3).
