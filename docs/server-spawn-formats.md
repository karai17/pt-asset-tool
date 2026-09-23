# Server Data Formats: SPC / SPM / SPP

The GameServer keeps per-stage spawn data in three sidecar files that sit next
to the stage mesh (`.ase`) file in `bin/Server/GameServer/Field/`:

| file | meaning | count in shipped GameServer |
|------|---------|-----------------------------|
| `<stage>.ase.spm` | monster spawn configuration (what spawns, how often) | 43 |
| `<stage>.ase.spp` | monster spawn points (where they may appear) | 45 |
| `<stage>.ase.spc` | fixed NPCs (shopkeepers, guards, quest givers) | 20 |

The stage filename casing is inconsistent (`Ruin-1.ase.spm` vs
`ruin-1.ase.spp`) - the server's `SetFieldInfoPath` builds the sidecar name
from the `.ase` path it was given and the decoder matches case-insensitively.

Loading happens in `STG_AREA::LoadStage` (OnSever.cpp:7745): the `.ase` mesh is
read first, then `LoadStartPoint` (.spp), `LoadCharInfoFixed` (.spc), and
`DecodeOpenMonster` (.spm, fileread.cpp:5382) are called with the same root
name. All three formats are CP949-encoded or little-endian binary; nothing is
encrypted.

Decoders: `src/pt/decode/spm.py`, `src/pt/decode/spp.py`, `src/pt/decode/spc.py`.
Output dataclasses: `PTServerSpawnMonster`, `PTServerSpawnPoint`,
`PTServerSpawnCharacter` in `src/pt/pdef.py`.

---

## 1. SPM - monster spawn configuration (text)

CP949 text in the same `*key value` line format as INF/TXT/NPC files: lines
not starting with `*` are skipped (this also skips `//` comments), then each
line is tokenized with GetWord/GetString - quoted tokens keep their inner
spaces. Engine reference: `DecodeOpenMonster`, fileread.cpp:5382.

The full line format (Ruin-1.ase.spm):

```
//몬스터 출현 비율

*최대동시출현수		100
//출현간격 범위 9-1 1차이당 2배씩 빨라짐
*출현간격		5	17
*출현수			2

//		몬스터 이름          출현빈도
*출연자		"스켈레톤아처"		15
*출연자		"리치"			20

*출연자두목	"길티 고든"	"디코이"	7	11	14	17	20	23
```

The engine fills an `rsSTG_MONSTER_LIST` (fileread.h:45-60) from these keys.
Defaults when a key is absent: `LimitMax = 10` (applied at OnSever.cpp:7771,
not in the parser), `OpenInterval = 0x7F`, `OpenLimit = 3`.

### Key table

| key | alias | values | engine field | meaning |
|-----|-------|--------|--------------|---------|
| `*최대동시출현수` | `*MAX_ACTOR_POS` | int | `LimitMax` | Maximum monsters alive simultaneously for the whole stage. Spawn loop gates on `MonsterCount < LimitMax` (OnSever.cpp:7421). 100-200 in shipped files. |
| `*출현간격` | `*DELAY` | int [int] | `OpenInterval`, `dwIntervalTime` | Spawn cadence. First value n: engine evaluates `OpenInterval = 1 << n` then decrements while `> 1`, so n=0 stores 1 and n≥1 stores `(1 << n) - 1`; spawns when `(Counter & OpenInterval) == 0`, so each step of n halves the spawn frequency (the shipped comment says "1 차이당 2배씩 빨라짐" - each step of 1 doubles the speed). Optional second value: seconds between spawns at one point, stored as `value * 1000` ms and applied to `dwStartPoint_OpenTime` after a spawn (OnSever.cpp:7954). The decoder stores the converted `spawn_interval` and `spawn_interval_time` (ms), matching the engine fields. |
| `*출현수` | `*MAX_ACTOR` | int | `OpenLimit` | Maximum monsters allowed per spawn point (`StartPointMonCount[cnt] < OpenLimit`, OnSever.cpp:7871). 2 in shipped files. |
| `*출연자` | `*ACTOR` | quoted CP949 name, int | `rsMonster[i]` | One monster type eligible to spawn on this stage. The name is matched against the INF-loaded `smCHAR_INFO` list with `lstrcmp` (fileread.cpp:5414-5425). The int is the spawn weight: weights are prefix-summed into `NumOpenStart`/`PecetageCount` and a monster is picked by `rand() % PecetageCount` (OnSever.cpp:7435-7444). Up to 50 entries (`rsSTG_MONSTER_MAX`). |
| `*출연자두목` | `*BOSS_ACTOR` | quoted boss name, quoted minion name, int, 0-32 ints | `sBossMonsters[i]` | Boss encounter: master monster name, minion monster name, minion count (`SlaveCount` - the minion is spawned that many times, OnSever.cpp:17602), then up to 32 spawn hours (`bOpenTime[32]`). Hours are checked against the server clock once per hour (`st.wHour == bOpenTime[k]`, OnSever.cpp:6327). 26 encounters across the shipped files (`rsBOSS_MONSTER_MAX` = 16 per stage). Hours are plain 0-23 in shipped files; the decoder normalizes with `% 24` because `bOpenTime` is a single byte. Parsed at fileread.cpp:5434-5456. |

Shipped data notes:

- All 276 `*출연자` names resolve against `MONSTER_NAMES` (const.py), which
  maps the CP949 key to the English monster name.
- One file (ice_2.ASE.spm) carries `*//출연자두목` - a commented-out boss line
  whose leading `//` sits *after* the `*`. It starts with `*` so the parser
  sees it as a key; it matches nothing and is reported unknown.
- The English aliases (`*ACTOR` etc.) are accepted by the engine but appear in
  no shipped file.

---

## 2. SPP - monster spawn points (binary)

A flat array of exactly 200 `STG_START_POINT` records
(onserver.h:75-80), 8 bytes each, for a fixed file size of 2400 bytes. The
engine reads/writes the array in one `fread`/`fwrite`
(OnSever.cpp:7052-7074); the decoder divides the file size by the struct size
so oversized files would still load.

```c
struct STG_START_POINT {
    int state;   // slot-used flag
    int x, z;    // position, engine inches
};
```

| field | type | values | meaning |
|-------|------|--------|---------|
| `state` | int32 | 0 or 1 | 1 = slot in use. Set by `AddStartPoint` when an admin raycasts a point onto the terrain (OnSever.cpp:21280, then saved back to disk immediately). Spawning only considers slots with `state != 0` (OnSever.cpp:7871). |
| `x` | int32 | engine inches | World X of the spawn point. Raw inches: `SetStartPosChar` multiplies by `fONE` (256) to get fixed point (OnSever.cpp:7884). |
| `z` | int32 | engine inches | World Z of the spawn point. There is deliberately no `y` - the server drops monsters from above and lets gravity/raycast settle them. |

Empty slots are zero-filled, so `state == 0` entries are skipped. Note that
`DeleteStartPoint` (OnSever.cpp:7826) clears `state` but keeps the
coordinates, so 474 shipped slots are *deleted* points (state 0, plausible
position); the decoder emits those as inactive entries and only skips fully
zeroed tails. Shipped totals across all 45 files: 2474 active points, 474
deleted, 5902 empty. Points near the same X/Z as `.spc` NPC positions
confirm the coordinate space: e.g. ruin-2 spawn points span X 2821-9456,
Z 19486-23586 while its NPCs (see below) stand at X 5214-12794,
Z 23410-24935 inches.

At spawn time each point additionally enforces the per-point `OpenLimit` from
the SPM, a player-proximity test (`StartPointNearPlay`), and the
`dwIntervalTime` cooldown (OnSever.cpp:7871-7875).

---

## 3. SPC - fixed NPCs (binary)

A flat array of exactly 100 `smTRNAS_PLAYERINFO` records (smPacket.h:1863
[sic - the struct name is misspelled in the engine]), 504 bytes each, for a
fixed file size of 50400 bytes. Again one `fread`/`fwrite`
(OnSever.cpp:6443-6467, `FIX_CHAR_MAX = 100`, onserver.h:123).

```c
struct smTRNAS_PLAYERINFO {
    int size;               // 504 for an in-use slot, 0 for empty
    int code;               // smTRANSCODE_ADD_NPC (0x48470070) when in use
    smCHAR_INFO smCharInfo; // full character record, 472 bytes
    DWORD dwObjectSerial;   // runtime object id (reassigned on load)
    int x, y, z;            // position, fixed point (inches << 8)
    int ax, ay, az;         // facing angles, 4096-unit circle
    int state;              // spare (0 in all shipped files)
};
```

The server iterates the array and calls `OpenNpc` for every slot with a
nonzero `code` (OnSever.cpp:7762-7766).

### Slot header fields

| field | type | values | meaning |
|-------|------|--------|---------|
| `size` | int32 | 504 / 0 | `sizeof(smTRNAS_PLAYERINFO)` written by the tool that created the NPC; the de-facto in-use flag. 123 active slots across the 20 shipped files, everything else zero-filled. |
| `code` | int32 | `0x48470070` (= decimal 1212612720) | `smTRANSCODE_ADD_NPC` (smPacket.h:117) - marks the record as an "add NPC" transaction. |
| `dwObjectSerial` | uint32 | runtime id | Overwritten with a fresh serial by `OpenNpc` on every load, so the on-disk value is stale. |
| `x`, `y`, `z` | int32 | fixed point | Position copied verbatim into `smCHAR::pX/pY/pZ`, which is fixed point: inches left-shifted by `FLOATNS = 8`, i.e. raw / 256 = inches. Contrast with SPP, whose values are plain inches. |
| `ax`, `ay`, `az` | int32 | 0-4095 | Facing angles on the engine's 4096-unit circle (smSin.h:25 `ANGLE_360`), applied directly to `smCHAR::Angle` by `OpenNpc` (OnSever.cpp:6504-6506). Shipped NPCs usually carry only `ay` (yaw); 2608 ≈ 229°. |
| `state` | int32 | 0 | `smCHAR::state` placeholder; never nonzero in shipped files. |

### The embedded `smCHAR_INFO` (472 bytes)

A full character record (smPacket.h:641-790). Only the fields the NPC loader
actually consumes are meaningful here; the rest arrive zeroed. The ones that
matter:

| field | type | meaning |
|-------|------|---------|
| `szName[32]` | CP949 string | Display name ("던전 키퍼"). If the linked .npc file sets a localized name it overrides this at load (OnSever.cpp:6533-6536). |
| `szModelName[64]` | CP949 path | Client-side model INX ("char\npc\TN-001\TN-001.INI") - what the NPC looks like. |
| `szModelName2[60]` | CP949 path | Server-side .npc definition path ("GameServer\npc\dungeon-keeper.npc"). `OpenNpc` runs `smCharDecode` on it to load the NPC's functions, dialogue, sell lists and quest hooks (OnSever.cpp:6525). Every active slot in shipped files carries one. |
| `State` | int32 | `smCHAR_STATE_NPC` marker as set by the NPC editor tool. |

The remaining fields (stats, resistances, `wPlayClass`, sound code, ...) are
populated by the .npc decode or left zeroed; see the INF/NPC documentation for
their semantics.

The decoder (`spc.py`) treats a record as an NPC when `size == 504`, then
emits `active` (`code == 1212612720`), the display name, the model and npc
basenames (casefolded, matching how the tool keys stage data), position in
meters (raw / 256 inches, then * 0.0254), and a quaternion built from the
4096-unit angle triple.

---

## 4. How the three interact

1. `LoadStage("Field/Ruin-1.ase")` reads the mesh, then the three sidecars.
2. The SPC NPCs are placed immediately at their exact fixed positions.
3. The SPM config says how many monsters may exist (100), how fast they
   spawn (interval 5 ≈ every 31 ticks, optional 17 s per-point cooldown) and
   the weighted monster pool.
4. Every spawn tick the server picks a random pool entry by weight, then
   `SetStartPosChar` walks the SPP list for an eligible point (active, player
   nearby, under `*출현수`, cooldown expired) and drops the monster there.
5. Boss sets (`*출연자두목`) ignore the tick loop: at each listed hour the
   master spawns once plus `SlaveCount` minions at a spawn point.
