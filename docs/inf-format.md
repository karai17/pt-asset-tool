# The INF Format - Monster Definitions

Every monster in the game is defined by one INF file in
`bin/Server/GameServer/Monster/` (396 files shipped). The server loads all of
them at startup with `smCharDecode` (fileread.cpp:4279) - each file becomes one
`smCHAR_INFO` (character stats, smPacket.h:641) plus one `smCHAR_MONSTER_INFO`
(monster behaviour, smPacket.h:547) and a spawn-table entry keyed by name.
The same parser also reads `.npc` files; see `docs/server-npc-txt-formats.md`
for the NPC-specific keys.

A companion `name/*.zhoon` file (referenced by `*연결파일`) carries localized
names for foreign clients; the server itself never reads it.

Decoder: `src/pt/decode/inf.py`. Output dataclass: `PTServerMonster`.

---

## 1. File mechanics

- CP949 (EUC-KR superset) text, CRLF line endings.
- Only lines starting with `*` are commands; anything else (including `//`
  comments and blank lines) is skipped.
- Tokenization follows the engine's GetWord/GetString pair
  (fileread.cpp:81, smRead3d.cpp:4598): a token is a whitespace-delimited
  word, unless it opens with `"` in which case it runs to the closing quote
  and keeps inner spaces. Tabs are the usual separator.
- Numbers use C `atoi`/`atof` semantics: empty or malformed values parse as 0.
  A few shipped files abuse this (`*흡수율 5%`, `*블럭율 6%`, empty `*블럭율`).
- `*연결파일` switches the parser's input file mid-stream (the engine closes
  the current file and opens the zhoon file), so keys after it would be read
  from the next file. In shipped files it is always the last key.
- Keys unknown to `smCharDecode` are silently ignored by the engine. Four
  such keys appear in the shipped data and the decoder handles them
  explicitly (see the table): `*매직`, `*이동속도`, `*골드`, `*Name`.

## 2. Key table

Values are listed as `type [count]`. "min/max" means one or two integers; a
single value is duplicated into both slots by the engine. Percentages are
0-10000-ish integer weights, not normalized.

### Identity

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*이름` | quoted CP949 string | `smCHAR_INFO.szName` | Korean display name ("헤스트"). This name is the monster's spawn-table identity: SPM files and boss lists reference monsters by it. Also feeds `GetSpeedSum` to build the runtime checksum `dwAutoCharCode` (character.cpp:360). |
| `*Name` | ASCII string | (no engine case) | English display name ("Hest"). No case in `smCharDecode` for any language build - the ifdef family is `*E_NAME` etc. - yet present in all 396 shipped files. Decoded as `name_en`. |
| `*모양파일` | quoted CP949 path | `szModelName` | Client model INX path ("char\monster\Hest\Hest.INI"). |
| `*예비모델` | quoted CP949 path | `szModelName2`, `UseEventModel = TRUE` | Alternate ("event") model, swapped in by server events (e.g. decoys). 3 files. |
| `*속성` | `적` or `NPC` | `smCHAR_INFO.State` | Record type: `적` ("enemy") marks a monster. NPC files carry `NPC` instead. |
| `*연결파일` | quoted CP949 path | (parser input switch) | Localized-name sidecar ("name\Hest.zhoon"). Always last. |

### Level and class

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*레벨` | int | `Level` | Monster level. |
| `*두목` | (no values) | `wPlayClass[0] = 1` | Boss flag (`MONSTER_CLASS_BOSS`, smPacket.h:2759). 115 files. |
| `*계급` | int | `wPlayClass[0]` | Numeric rank override: 200 = hammer-class (decoy summons, `MONSTER_CLASS_HAMMER`), 300 = ghost-class (MrGhost quest, `MONSTER_CLASS_GHOST`). 4 files. |
| `*모델크기` | float | `wPlayClass[1]` | Model scale as `atof * 256` (fONE); a value of exactly 1.0 is reset to 0 (= default size). 207 files, range 0.3-2.5. |
| `*크기` | `소형` / `중형` / `중대형` / `대형` / scale float | `SizeLevel` | Shadow/hitbox tier index 0-3 from `szCharSizeCodeName` (fileread.cpp:4258). A numeric value leaves `SizeLevel = -1` (unmatched) and acts as an extra visual scale. All four names plus numerals appear. |
| `*구별코드` | int | `ClassCode` | Monster class distinguisher used by quest/event logic. 93 files. |

### Combat stats

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*생명력` / `*라이프` | int [2] | `Life[0..1]` | HP. First value is used and copied to the max slot. |
| `*공격력` | int min, int max | `Attack_Damage[2]` | Base damage range. |
| `*공격속도` | float | `Attack_Speed` | Attack speed, stored `atof * 256`. Practically an int 5-9; the second value on the line overwrites the first (engine quirk, fileread.cpp:4696-4705). |
| `*공격범위` | int | `Shooting_Range` | Attack reach in engine units, stored `value * 256`. |
| `*명중력` | int | `Attack_Rating` | Accuracy rating. |
| `*방어력` | int | `Defence` | Defense. |
| `*흡수율` | int [%] | `Absorption` | Damage absorption percent. Stray `%` suffix in 3 files. |
| `*블럭율` | int [%] | `Chance_Block` | Block chance percent. Stray `%` suffix in 1 file; empty in 2. |
| `*특수공격률` | int | `SpAttackPercetage` | Chance to use the special attack, stored `value * 256 / 100` (ConvPercent8). |

### Skills

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*기술공격력` | int min, int max | `SkillDamage[2]` | Skill damage range. |
| `*기술공격거리` | int | `SkillDistance` | Skill cast distance. |
| `*기술공격범위` | int | `SkillRange` | Skill area-of-effect radius. |
| `*기술공격률` | int | `SkillRating` | Skill use chance/rating. |
| `*저주기술` | int | `SkillCurse` | Curse id applied by the skill (1 = absorb debuff, 2 = monster buff, 3 = player attack down per in-file comments). 12 files. |

### Elemental resistances

Shorts indexed by `sITEMINFO_*` (sinItem.h). All optional; missing = 0.

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*생체` | int | `Resistance[sITEMINFO_BIONIC]` | Bionic (biological) resistance. |
| `*대자연` | int | `Resistance[sITEMINFO_EARTH]` | Earth/nature resistance. |
| `*불` | int | `Resistance[sITEMINFO_FIRE]` | Fire resistance. |
| `*얼음` | int | `Resistance[sITEMINFO_ICE]` | Ice resistance. |
| `*번개` | int | `Resistance[sITEMINFO_LIGHTING]` | Lightning resistance. |
| `*독` | int (atof) | `Resistance[sITEMINFO_POISON]` | Poison resistance (the engine reads this one with atof). |
| `*물` | int | `Resistance[sITEMINFO_WATER]` | Water resistance. |
| `*바람` | int | `Resistance[sITEMINFO_WIND]` | Wind resistance. |
| `*매직` | int | (no engine case) | Magic resistance. Present in **all 396** shipped files but `smCharDecode` has no case for it; the client's resistance array has no magic slot. Decoded into `resistances["magic"]`. |

Negative values are legal (e.g. `-15` = weakness).

### Movement and perception

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*시야` | int | `Sight`, `Real_Sight` | Aggro sight radius in engine units. The engine keeps `Real_Sight = value` and squares `Sight` for cheap distance tests. |
| `*화면보정` | int [2] | `ArrowPosi[2]` | Screen/arrow offset tweak for the camera ("화면보정" = screen correction); two optional ints, empty slots skipped. 282 files. |
| `*이동력` | float 1-6 | `Move_Speed` | Movement speed through ConvMoveSpeed: `(v - 9) * 16 + 256`. |
| `*이동속도` | float | (no engine case) | Synonym of `*이동력` used by 278 newer files instead of 118 older ones; `smCharDecode` has no case for it. Decoded into the same `move_speed`. |
| `*이동범위` | float | `MoveRange` | Wander radius from the spawn point, stored `atof * 256`. Default 64 * 256 when absent. |
| `*이동타입` | int | (parsed, discarded) | Movement AI type; the engine reads and drops the value. All files carry `0`. |

### Behaviour

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*활동시간` | `제한없음` / `낮` / `밤` | `ActiveHour` | Activity window: unrestricted / day (+1) / night (-1). All shipped files use `제한없음`. |
| `*조직` | int [2] | `GenerateGroup[2]` | Pack size min/max spawned together (the spawn loop rolls `GetRandomPos(min, max)`). One value = fixed pack. |
| `*지능` | int 1-10 | `IQ` | AI aggressiveness rating. |
| `*품성` | `Evil` / `Neutral` / `good` (case-insensitive; empty = neutral) | `Nature` | Temper: `smCHAR_MONSTER_EVIL` (0x82) / `NATURAL` (0x80) / `GOOD` (0x81). Affects targeting (good monsters attack monsters). |
| `*몬스터종족` | `언데드` / `뮤턴트` / `디먼` / `메카닉` / `노멀` / `아이언` | `Brood` | Kinship: `smCHAR_MONSTER_UNDEAD/MUTANT/DEMON/MECHANIC` (0x90-0x93), `smCHAR_MONSTER_NORMAL` (0x00) for `노멀`. Note this key touches `Brood` only - the separate `Undead` boolean is set by `*언데드`. `아이언` has no engine case (leaves the previous/default value) - the "Iron monster" files just reuse the sound table. |
| `*언데드` | `유` / `있음` / anything else | `Undead`, `Brood` | Legacy undead flag: yes/yes → `Undead = TRUE` + `Brood = UNDEAD`, anything else resets both. 1 file (most use `*몬스터종족`). |
| `*스턴율` / `*스턴률` | int | `DamageStunPers` | Chance to stun on hit, percent. Default 100. The engine accepts both spellings; shipped data only uses `*스턴율` (150 files). |
| `*효과음` / `*소리` | sound-table name (case-insensitive) | `dwCharSoundCode` | Voice/footstep set, resolved against `dwCharSoundCode[]` (fileread.cpp:4008-4253, 198 names with aliases like `ARMADIL`→ARMA, `GOLEM`→STONEGIANT). Unknown names leave the code 0. `*소리` is the legacy spelling. |
| `*경험치` | int | `GetExp`, `Exp` | Experience awarded on kill (quadrupled on test servers). |

### Events

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*이벤트코드` | int | `EventCode` | Event hook id (100 = wolverine quest on the three wolverine files). |
| `*이벤트정보` | int | `EventInfo` | Event parameter. |
| `*이벤트아이템` | item category | `dwEvnetItem` | Item code required by the event, resolved against the item table ("QT102"). Case-insensitive. |

### Consumables and loot

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*물약보유수` | int | `PotionCount` | Number of potions the monster may drink in combat. |
| `*물약보유률` | int | `PotionPercent` | Chance (%) the monster spawns carrying them. |
| `*아이템모두` | (no values) | `AllSeeItem = TRUE` | Drops are visible to everyone (no per-player ownership window). 8 files. |
| `*아이템카운터` | int | `FallItemMax` | Maximum drops per kill (how many times the drop loop runs; premium items can raise it, OnSever.cpp:8868-8930). |
| `*아이템` | see below | `FallItems[n]` | One weighted loot entry; 2822 lines across all files. |
| `*추가아이템` | percent, category | `FallItems_Plus[n]` | Bonus drop rolled independently (rune/ore style, "pr101"). Up to 3 (`FALLITEM2_MAX`). |
| `*골드` | int min, int max, int percent | (no engine case) | Server-side-only gold drop line ("200 220 80"); 31 files carry it but `smCharDecode` ignores it. Decoded as a `gold` fall item. |

`*아이템` value grammar (fileread.cpp:5060-5131):

```
*아이템  <percent>  없음              -- "nothing" entry: consuming it drops nothing
*아이템  <percent>  돈 min [max]      -- gold drop; max defaults to min
*아이템  <percent>  cat1 [cat2 ...]   -- item drop; percent is split evenly
```

- `percent` weights accumulate into `FallItemPerMax`; a roll of
  `rand() % FallItemPerMax` walks the entries in order (OnSever.cpp:2994-3010).
- Item codes are 5-character categories ("da112", "OS107"), matched
  case-insensitively against `sItem[].LastCategory`. The numeric code is
  `base | index << 8` where base is the two-letter+tier table (sinItem.h,
  e.g. `sinDA2 = 0x02050000`) - reproduced by `item_code()` in const.py.
- On a hit the item is instantiated from the server's item table
  (`DefaultItems`, loaded from OpenItem TXTs) with the drop's stats.

### Dialogue (NPC-only in practice)

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*대화` | quoted CP949 string | `lpNpcMessage[n]` | Chat line. Stored only when the caller passes a dialog buffer (NPC loads pass one; the monster load passes NULL so monster INFs never keep it). Repeats append up to `NPC_MESSAGE_MAX` = 20. |

## 3. Census

Across the 396 shipped files every file carries the same core block (이름,
Name, 모양파일, 레벨, 활동시간, 조직, 지능, 품성, 시야, 생명력, 공격 stats,
resistances, 크기, 효과음, 경험치, 연결파일). The rare keys: `*언데드` (1),
`*이벤트코드`/`*이벤트정보` (3), `*예비모델` (3), `*계급` (4), `*아이템모두`
(8), `*저주기술` (12), `*골드` (31). The decoder resolves all of them; the
only keys it reports unknown are malformed comment lines in one SPM file
(not INF).
