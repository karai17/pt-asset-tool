# ASE Round Trip

The ASE encoder/decoder pair converts decoded model data to 3ds Max Ascii Export
files and back to binary SMD/SMB, mirroring the original pipeline (the tools
authored `.ase`; `smASE_Read` / `smASE_ReadBone` / `smSTAGE3D_ReadASE` in
`smRead3d.cpp` converted them on load).

- `src/pt/encode/ase.py` - PTActorModel / PTStageModel -> ASE text
- `src/pt/decode/ase.py` - ASE text -> raw parse structures (GetWord/GetString
  tokenizer identical to the engine's)
- `src/pt/decode/ase_smd.py` - raw parse -> PTActorModel / PTStageModel, plus
  the binary writers (`save_actor_smd`, `save_bones_smb`, `save_stage_smd`)
  reproducing `smPAT3D::SaveFile` / `smSTAGE3D::SaveFile`
- CLI: `--ase` encodes every decoded INX/SMD model as `<name>.ase`

## Verified round-trip guarantees

Over the shipped corpus (150 sampled actors via INX, all 56 stage SMDs):

- object/bone names, hierarchy, physique assignments: exact
- vertices: exact (8-decimal output makes `int(atof * 256)` lossless)
- faces (indices + material ids): exact
- UV sets 0..2 (incl. `*MESH_MAPPINGCHANNEL` extra pools for stage second/third
  texture stages): exact
- bone static Tm matrices: exact
- position/scale keys: exact
- material scripts (blend type, script flags, MeshState, paths, transparency):
  exact (MeshState regenerated through `decode_mesh_state`, the exact inverse of
  the engine's AddMaterial state machine)
- stage lights: exact (type flags, positions, range, colors)
- binary SMD/SMB output decodes with `smd.decode` to identical model data

## Accepted lossy data

1. **Rotation keyframe quaternion normalization.** The engine stores rotation
   keys as quaternions converted from axis-angle by `smQuaternionFromAxis`
   (normalized by construction); some shipped SMDs carry slightly unnormalized
   quaternions (the original ASEs were authored with 4-decimal values). The
   round trip renormalizes them: quaternion components shift by up to ~7e-4
   (~0.04 degrees per key, visually identical, and the runtime slerp operates
   on rotations, not raw floats).
2. **Faces without texture links (stages).** A handful of stage faces (93 of
   60443 in ruin-2, 12 in dun-1, 5396 in mine-1) have no `smTEXLINK` at all.
   ASE cannot express "face without UVs"; they gain a zero-UV link.
3. **Junk materials.** A few dev files carry `0xCDCDCDCD`-filled materials
   (e.g. `1ani-09` material 122) whose texture path the engine's own blob
   reader rejects. They re-encode with `TextureCounter = 0`.
4. **Float32 fields stored as text.** SMD `Transparency`/colors are float32;
   the ASE carries the float64 text form (`0.20000000298023224` -> `0.2`).
   The binary re-encode rounds back to the identical float32.
5. **Not expressible in ASE / not reconstructed:** stage vertex-color shading
   gradients are carried verbatim in `*MESH_VERTCOL`-less form (the encoder
   writes white vertex colors; the SMD writer preserves the decoded
   `PTStageObject.vertex_colors` directly, so binary round trips keep them),
   `StageArea` partition data (rebuilt by `SetupPolyAreas` at engine import),
   `sum`/`CalcSum` render-sorting scratch values, and stale pointer fields
   (rebuilt by the loader's pointer-difference rebase).
