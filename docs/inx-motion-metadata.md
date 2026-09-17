# INX Motion Metadata - Animations, Facial Tables, and Chains

The INX is the actor entry point: besides referencing the shape (`.smd`) and
motion (`.smb`) files, it carries the per-animation tables the engine uses to
select and play motions - walk/run/attack variants, weapon and class
restrictions, NPC idle blending, and the facial (talk) animation table that
drives NPC expressions. This document describes everything
`src/pt/decode/inx.py` surfaces and how it is expressed in the glTF export.

The binary is a raw `smMODELINFO` struct (67084 bytes, or 95268 for the `EX`
variant with 16-bit item codes). The engine's loader is `smModelDecode`
(fileread.cpp:967); the runtime counterpart for motion selection is
`smCHAR::ChangeMotion` / `FindMotion` (character.cpp:2355-2440).

---

## 1. Slot convention

`MotionInfo[512]` is indexed in two ranges:

- Slots 0-9 are reserved for the old fixed-slot commands (`*걷는동작`,
  `*서있기동작`), which are commented out in the ini parser
  (fileread.cpp:601-610). Shipped files leave them zero.
- Real entries live at `[10, MotionCount)` - `MotionCount` counts the reserved
  slots, so `MotionCount - 10` is the number of authored animations. The
  engine walks exactly this range when decoding the motion keyword
  obfuscation (fileread.cpp:6481).

`TalkMotionInfo[30]` follows the same convention with `TalkMotionCount`.

`NpcMotionRate[30]` / `TalkMotionRate[30]` are parallel arrays indexed by the
same slot numbers, so rates only exist for the first 20 entries of each table.

## 2. Per-animation fields (`PTMotionMetadata`)

Decoded for both regular animations and talk animations.

| field | engine source | meaning |
|-------|---------------|---------|
| `name` | `State` | Motion state keyword match from the ini line, mapped through `CHRMOTION_STATE` (character.h:894-930): `stand`, `walk`, `run`, `attack`, `dead`, ... plus the `talk_*` expressions (see section 4). |
| `start_frame`, `end_frame` | `StartFrame` / `EndFrame` | Frame range in the motion file's frame space (160 ticks per frame, 30 fps). Obfuscated by `MotionKeyWordEncode` for regular motions and reversed by `decode_motion` (fileread.cpp:6474); talk motions are stored plain. |
| `repeat` | `Repeat` | Loop flag, set by the `반복` keyword or the run/stand keywords. |
| `motion_frame` | `MotionFrame` | Regular motions: 1-based index of the `*동작모음` (motion file list) entry whose frames were merged into `szMotionFile` for this animation (fileread.cpp:336; runtime reads `TmFrame[MotionFrame-1]`, character.cpp:591). 0 = the INX had no motion file list. Talk motions: which merged file the frames live in - 0 = `TALK_MOTION_FILE` (szMotionFile), 1 = `FACIAL_MOTION_FILE` (szTalkMotionFile) (smType.h:404-405). |
| `event_frames` | `EventFrame[3]` | Event trigger frames (sound effects, decals, ...) relative to the animation start; stored scaled by 160 ticks (fileread.cpp:236), divided back to frames. |
| `item_codes` | `ItemCodeCount` / `ItemCodeList[52]` | Weapon restriction (fileread.cpp:614-660): empty list = any weapon; otherwise `sItem[]` table indices (`0xFF`, or `0xFFFF` in the EX variant = bare-body sentinel). |
| `job_code_bit` | `dwJobCodeBit` | Class bitmask (fileread.cpp:666-683): 0 = every class, otherwise `BitMaskJobNames` bits (Fighter 0x1, Mechanician 0x2, Archer 0x4, Pikeman 0x8, ...). |
| `skill_codes` | `SkillCodeList[8]` | `SkillDataCode[]` indices (fileread.cpp:713-732); non-empty = the animation only plays while casting that skill. |
| `map_position` | `MapPosition` | Context mask from `*해당위치` (fileread.cpp:685-711): bit 1 = village, bit 2 = field; the runtime ANDs it with `StageVillage` (character.cpp:2355). |
| `key_code` | `KeyCode` | Single ASCII event key parsed from a trailing letter on the motion line (fileread.cpp:246), driving attack-followup behaviour (`character.cpp:3446+`: `'P'`, `'L'`, `'H'`, `'G'`, `'U'`, `'J'`, `'I'`, ...). |
| `rate` | `NpcMotionRate[i]` / `TalkMotionRate[i]` | Authored blend weight in percent. For regular motions it weights NPC idle random-motion selection (unused in shipped data); for talk motions it weights the facial expression lottery (section 4). |

### Restriction selection order

The engine's motion search (character.cpp:2355-2440) filters by `State` ==
requested state, then `MapPosition & StageVillage`, then `dwJobCodeBit &
jobMask`, then the skill list (when casting), then the item list (weapon in
hand, or the `0xFF` bare-body entry when empty-handed). An empty restriction
list always matches.

## 3. Model-level fields (`PTActorModel`)

| field | engine source | meaning |
|-------|---------------|---------|
| `link_file` | `szLinkFile` | `*파일연결` chain target (fileread.cpp:544-551). Game-root-relative INX reference. |
| `talk_link_file` | `szTalkLinkFile` | `*표정파일연결` chain target (fileread.cpp:738-747). |
| `talk_motion_file` | `szTalkMotionFile` | `*표정파일` (fileread.cpp:751-760): the face model the talk motions were merged into, authored as `.ASE`, shipped as `.smb`. |
| `sub_model_file` | `szSubModelFile` | `*보조동작파일` (fileread.cpp:559-566): auxiliary model loaded as a second character pattern at runtime (character.cpp:831-834). 59 shipped files, always another `.ini` (INX) in the same directory. |
| `npc_motion_rate_table` | `NpcMotionRateCnt[100]` | Precomputed `rand()%100` lookup for NPC idle blending. All zero in shipped data. |
| `talk_motion_rate_table` | `TalkMotionRateCnt[2][100]` | Precomputed `rand()%100` lookup per motion-file group (section 4). |

### Chain inheritance

The loader (fileread.cpp:996-1056) re-reads the linked INX files and inherits
their tables wholesale:

- `i=1` (`szLinkFile`): if the linked file has `MotionCount > 10`, the model
  inherits its `szMotionFile`, `MotionInfo`, `MotionCount`,
  `NpcMotionRate`, and `NpcMotionRateCnt`. This is how the 1646 clothing
  variants in `char/tmABCD` share the biped skeletons: a clothing INX (e.g.
  `B007.inx`) has no motions of its own and inherits everything (including
  the motion file `m1.smb`) from `M1Bip.inx`.
- `i=2` (`szTalkLinkFile`): if the linked file has `TalkMotionCount > 10`,
  the model inherits its `szTalkLinkFile`, `szTalkMotionFile`,
  `TalkMotionInfo`, `TalkMotionCount`, `TalkMotionRate`, and
  `TalkMotionRateCnt`. This is how base NPC models (e.g. `TN-011.inx`) get
  the facial table from their face variant (`TN-011f.inx`).

The stored link paths have their extension truncated (`M1Bip.in`); the engine
reconstructs the `.inx` name via `ChangeFileExt` (smRead3d.cpp:92), and the
decoder surfaces the reconstructed path. The decoder performs the same
one-level inheritance when a file lacks the corresponding table; file
resolution is case-insensitive to match the Win32 filesystem the engine runs
on (`resolve_casepath`, `pt/utils.py`).

## 4. Facial (talk) animations

`TalkMotionInfo` entries are facial expression clips played over the body of
an NPC while it talks (`smCHAR::AutoChangeTalkMotion`, character.cpp:2261).
The state constants (character.h:920-930) come from the `*표정` keyword
family (fileread.cpp:442-492):

| state | name | keyword |
|-------|------|---------|
| 0x400 | `talk_ar` | `*아표정` |
| 0x410 | `talk_e` | `*이표정` |
| 0x420 | `talk_oh` | `*오표정` |
| 0x430 | `talk_eye` | `*눈깜빡표정` (eye blink) |
| 0x0 | `talk_blank` | `*무표정` - explicitly marked "doesn't work" in the source |
| 0x440 | `talk_smile` | `*웃는표정` |
| 0x450 | `talk_grumble` | `*화난표정` |
| 0x460 | `talk_sorrow` | `*슬픈표정` |
| 0x470 | `talk_startled` | `*놀란표정` |
| 0x480 | `talk_nature` | `*고유표정` |
| 0x490 | `talk_special` | `*특별표정` |

`MotionFrame` splits the table into two groups by source file
(`TALK_MOTION_FILE` = 0, `FACIAL_MOTION_FILE` = 1). The engine normalizes each
group's rates to sum 100 (padding/trimming the largest weight,
fileread.cpp:852-902) and builds the `TalkMotionRateCnt[group][100]` lookup:
`TalkMotionRateCnt[group][rand()%100]` yields the talk-motion slot to play.
The decoder ships the table as stored.

90 shipped files carry talk data (46 face INXs with own tables, the rest via
chain inheritance), 637 talk animations total.

## 5. glTF expression

The glTF exporter (`src/pt/encode/gltf.py`) writes this data into the model
files themselves:

- **Regular and talk animations become glTF animations.** Talk animations are
  separate frame ranges in the same `.smb` frame space, so the exporter builds
  a second sampler pass per bone with timestamps resolved against the talk
  ranges (keeping each animation's time relative to its own start) and emits
  them as additional glTF animations named after the expression
  (`talk_smile`, `talk_eye`, ...).
- **Per-animation extras** on every glTF animation: `startFrame`, `endFrame`
  (existing), plus `repeat`, `motionFrame`, `keyCode`, `itemCodes`,
  `jobCodeBit`, `skillCodes`, `mapPosition`, and `rate`.
- **Model-level extras** on `asset.extras`: `linkFile`, `talkLinkFile`,
  `talkMotionFile`, `subModelFile` (when present), plus
  `npcMotionRateTable` / `talkMotionRateTable` when non-zero.

The JSON export (`-s` flag) mirrors the same fields via the dataclasses.
