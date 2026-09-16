# The NPC and TXT Formats - NPC and Item Definitions

Two more consumers of the same `*key value` line parser:

- **NPC** files (`bin/Server/GameServer/NPC/*.npc`, 110 shipped) define what
  an NPC *does*: which shops it runs, which quests it handles, its dialogue.
  The client loads them via playmain.cpp:1452; the server loads the file an
  SPC record points at with `smCharDecode` (fileread.cpp:4279) to get the
  function flags, sell lists and dialogue.
- **TXT** files (`bin/Server/GameServer/OpenItem/*.txt`, 981 shipped) define
  one item each: base stats, requirements, and specialization bonuses. The
  server loads all of them into its `DefaultItems` table at startup
  (OnSever.cpp:1824) - drop rolls instantiate items from this table.

A companion `name/*.zhoon` file (referenced by `*연결파일`) carries localized
names/chat for foreign clients; neither server path reads it.

Decoders: `src/pt/decode/npc.py`, `src/pt/decode/txt.py`. Output dataclasses:
`PTServerCharacter`, `PTServerItem`. The shared file mechanics (CP949, `*`
lines, GetWord/GetString tokenization, `atoi("") == 0`) are described in
`docs/inf-format.md` §1 and apply here unchanged.

---

## 1. NPC key table

Every active NPC record starts with `*속성 NPC`; the remaining keys select its
functions. Boolean function keys take no value.

### Identity

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*속성` | `NPC` | `State = FALSE` | Record type. `적` would mark a monster; NPC files carry `NPC`. |
| `*모양파일` | quoted CP949 path | `szModelName` | Client model INX ("char\npc\arad\arad.INI"). |
| `*이름` | quoted CP949 string | `szName` | Korean display name ("제련마스터 아라드"). |
| `*Name` | ASCII string | (language ifdef) | English display name; 12 files. |
| `*레벨` | int | `Level` | Displayed level (32 files, mostly 100). |
| `*대화` | quoted CP949 string | `lpNpcMessage[n]` | Chat line; repeats append (10 files, 1-5 lines). One file spells it `*댜화` (typo) - the engine's exact match also misses it; the decoder accepts both. |
| `*연결파일` | quoted CP949 path | `zhoon_path` | Localized sidecar ("name\arad.zhoon"). Always last. |

### Functions

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*스킬수련` | (none) | `SkillMaster = TRUE` | Teaches/upgrades skills. |
| `*직업전환` | [int] | `SkillChangeJob` | Job-change master. Optional int = required job id (shipped values 2, 3). Bare key = TRUE. |
| `*아이템보관` | (none) | `WareHouseMaster = TRUE` | Warehouse keeper. |
| `*아이템조합` | (none) | `ItemMix = TRUE` | Item mixing. |
| `*아이템제련` | (none) | `Smelting = TRUE` | Ore smelting (Arad). |
| `*아이템제작` | (none) | `Manufacture = TRUE` | Item manufacture. |
| `*아이템연금` | (none) | `ItemMix = 200` | 200-mixing (alchemy). |
| `*아이템에이징` | (none) | `ItemAging = TRUE` | Item aging. |
| `*믹스쳐리셋` | (none) | `MixtureReset = TRUE` | Mixture reset (석지용 - "for Seokji" per the engine comment). |
| `*모금함` | (none) | `CollectMoney = TRUE` | Donation box. |
| `*경품추첨` | (none) | `EventGift = TRUE` | Prize lottery (Eventgirl). |
| `*경품배달` | (none) | `GiftExpress = TRUE` | Prize delivery. |
| `*클랜기능` | (none) | `ClanNPC = TRUE` | Clan management. |
| `*기부함` | (none) | `GiveMoneyNpc = TRUE` | Money collection. |
| `*꽝이지롱` | (none) | `WowEvent = TRUE` | Vietnam-only wow event (veitnam ifdef). |

### Functions with values

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*이벤트매표소` | [int] | `EventNPC` | Event ticket booth (SOD entry). Optional int = booth id, default 1. |
| `*윙퀘스트` | [int] | `WingQuestNpc` | Wing quest giver; default 1. |
| `*퀘스트이벤트` | [int] | `WingQuestNpc` | Second wing-quest variant; default 2 (shipped files carry explicit ids 3-18). |
| `*별포인트적립` | [int] | `StarPointNpc` | Star-point collection; default 20. |
| `*텔레포트` | [int] | `TelePortNpc` | Teleport service; int = gate id (shipped 2, 3). |
| `*블레스캐슬` | [int] | `BlessCastleNPC` | Bless Castle function; default 1. |
| `*설문조사` | [int] | `PollingNpc` | Survey/polling; default 1. |
| `*무기판매` | item categories | `SellAttackItem[32]` | Weapon stock, up to 32 categories resolved case-insensitively against the item table ("ws108 ws109 ..."). |
| `*방어구판매` | item categories | `SellDefenceItem[32]` | Armor stock, same encoding. |
| `*잡화판매` | item categories | `SellEtcItem[32]` | Misc stock (potions, orbs), same encoding. |
| `*효과음` | sound name | `dwCharSoundCode` | Same sound table as monsters (4 files). |
| `*크기` | size name | `SizeLevel` | Same shadow tier as monsters (4 files). |
| `*모델크기` | float | `wPlayClass[1]` | Model scale (1 file). |
| `*계급` | int | `wPlayClass[0]` | Numeric rank - NPC quest chains use ids like 1012 (derik), 1004 (25 files). `*두목` (boss flag) is the monster-side sibling. |
| `*이벤트코드` / `*이벤트정보` | int | `EventCode` / `EventInfo` | Event hooks (3 files). |
| `*출현간격` | int, int | `OpenCount[2]` | Conditional appearance: `OpenNpc` shows the NPC only while `rsOpenNPC_RandomPos % OpenCount[1] == OpenCount[0]` (OnSever.cpp:6527-6529) - a lottery across server instances. 2 files. |
| `*퀘스트코드` | int, int | `QuestCode`, `QuestParam` | Quest hook (2 files). |
| `*동영상제목` | quoted string | `szMediaPlayNPC_Title` | Media player title (BC-Reporter). |
| `*동영상경로` | quoted string | `szMediaPlayNPC_Path` | Media URL ("mms://media.pristontale.com/siegewartest"). |

Notes:

- Several function keys are optional-valued in the engine (the `GetWord`
  leaves the buffer empty and the code substitutes a default). Shipped files
  contain both bare (`*블레스캐슬`, `*이벤트매표소`, `*윙퀘스트`,
  `*설문조사`, `*텔레포트`) and valued forms; both parse.
- `snowboard.NPC` writes `*퀘스트 이벤트` with a space inside the key - an
  exact `lstrcmp` in the engine would miss it too. The decoder reassembles
  the split key.
- Localized chat keys (`*C_CHAT`, `*J_CHAT`, `*T_CHAT`, `*E_CHAT`, `*TH_CHAT`,
  `*V_CHAT`, `*B_CHAT`, `*A_CHAT`; fileread.cpp:4438-4505) exist in the
  parser but only inside language ifdefs, and no shipped `.npc` uses them.
  They do appear inside zhoon files, which are not decoded.

## 2. TXT key table

One item per file; the file name is the item's category code ("WP123.txt").
All stat keys accept empty values (= 0) and most carry `[min] [max]` pairs.
Range keys where the engine stores floats are marked *float*.

### Identity

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*이름` | quoted CP949 string | `ItemName` | Korean item name ("리퍼 사이드"). |
| `*Name` / `*NAME` | ASCII string | `ItemName` (language ifdefs) | English name. 948 files use `*Name`, 32 use `*NAME` (uppercase has no engine case - the effective English name for those comes from the zhoon; decoded as `name_en` regardless). |
| `*C_NAME` .. `*A_NAME` | ASCII string | `ItemName` (language ifdefs) | Chinese/Japanese/Taiwanese/English/Thai/Vietnamese/Brazilian/Argentinian name variants. None in shipped files. |
| `*코드` | quoted category | `CODE` | Item category code ("WP123"). Case-insensitively matched against `sItem[].LastCategory`; file-name casing is inconsistent (170 files differ only in case). |
| `*연결파일` | quoted CP949 path | (parser input switch) | Localized-name sidecar ("name\WP123.zhoon"). Always last. |

### Common

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*내구력` | int [2] | `sDurability[2]` | Durability min/max. |
| `*무게` | int | `Weight` | Weight. |
| `*가격` | int | `Price` | Base price. |

### Elemental resistances (int [2], min/max)

| key | engine target |
|-----|---------------|
| `*생체` | `sResistance[sITEMINFO_BIONIC]` |
| `*대자연` | `sResistance[sITEMINFO_EARTH]` |
| `*불` | `sResistance[sITEMINFO_FIRE]` |
| `*냉기` | `sResistance[sITEMINFO_ICE]` (note: monsters use `*얼음` for the same slot) |
| `*번개` | `sResistance[sITEMINFO_LIGHTING]` |
| `*독` | `sResistance[sITEMINFO_POISON]` |
| `*물` | `sResistance[sITEMINFO_WATER]` |
| `*바람` | `sResistance[sITEMINFO_WIND]` |

Empty resistance lines are common and mean "no elemental spread" - the base
item's variance comes from elsewhere.

### Offensive

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*공격력` | int x4 | `sDamage[4]` | Damage: base min, base max, bonus min, bonus max (fileread.cpp:3567-3578). |
| `*사정거리` | int | `Shooting_Range` | Range (bows/guns). |
| `*공격속도` | int | `Attack_Speed` | Attack speed grade. |
| `*명중력` | int [2] | `sAttack_Rating[2]` | Accuracy min/max. |
| `*크리티컬` | int | `Critical_Hit` | Critical chance (%). |

### Defensive

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*흡수력` | float [2] | `fAbsorb[2]` | Absorption min/max (decimals like 5.899 occur). |
| `*방어력` | int [2] | `sDefence[2]` | Defense min/max. |
| `*블럭율` | float [2] | `fBlock_Rating[2]` | Block rating min/max. |
| `*이동속도` | float [2] | `fSpeed[2]` | Movement speed (boots). |

### Inventory

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*보유공간` | int | `Potion_Space` | Potion socket space. |

### Regeneration / bonuses (pairs unless noted)

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*마법숙련도` | float | `fMagic_Mastery` | Magic mastery. Two synonym keys exist in shipped files with no engine case: `*마법기술숙련도` (809 files) and `*기술숙련도` (47) - both decoded to the same field. |
| `*마나재생` / `*기력재생` | float [2] | `fMana_Regen[2]` | Mana regen (two accepted spellings). |
| `*라이프재생` / `*생명력재생` | float [2] | `fLife_Regen[2]` | Life regen (two spellings). |
| `*스테미나재생` / `*근력재생` | float [2] | `fStamina_Regen[2]` | Stamina regen (two spellings). |
| `*마나추가` / `*기력추가` | int [2] | `Increase_Mana[2]` | Mana bonus. |
| `*라이프추가` / `*생명력추가` | int [2] | `Increase_Life[2]` | Life bonus. |
| `*스테미나추가` / `*근력추가` | int [2] | `Increase_Stamina[2]` | Stamina bonus. |

The pairs of spellings map to the same `sDEF_ITEMINFO` slot, so whichever
line comes last wins - the shipped files use exactly one of each pair.

### Requirements

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*레벨` | int | `Level` | Required level. |
| `*힘` | int | `Strength` | Required strength. |
| `*정신력` | int | `Spirit` | Required spirit. |
| `*재능` | int | `Talent` | Required talent. |
| `*민첩성` | int | `Dexterity` | Required dexterity. |
| `*건강` | int | `Health` | Required health. |

### Recovery (potions)

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*생명력상승` / `*라이프상승` | int [2] | `Life[2]` | Life restored min/max (two spellings). |
| `*기력상승` / `*마나상승` | int [2] | `Mana[2]` | Mana restored. |
| `*근력상승` / `*스테미너상승` | int [2] | `Stamina[2]` | Stamina restored. |

### Uniqueness / visual

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*유니크` | [int] | `UniqueItem` | Bare key = TRUE; an int sets the grade. 44 files. |
| `*유니크색상` | int x4 [x2] | `EffectColor[4]`, `EffectBlink[0]`, `ScaleBlink[0]` | Unique glow: R, G, B, A, blink rate, optional blink scale (stored `atof * 256`). 29 files. |
| `*이펙트설정` | int | `DispEffect` | Display effect id (8 files). |

### Specialization (`**` keys)

The `**` prefix marks per-job specialization stats that apply only while the
item's designated job uses it. Job names are matched case-insensitively
against `JobDataBase` (e_JobCode.h): Mechanician, Fighter, Pikeman, Archer,
Knight, Atalanta, Priestess, Magician (plus the tier-2/3/4 evolution names).

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `**특화` | job names | `JobCodeMask` | The job(s) this item is designed for (a single name in shipped files; 1 file has an empty value). Note the engine assignment is `=` not `\|=`, so multiple names keep only the last. |
| `**특화랜덤` | job names | `dwJobBitCode_Random[12]` | Jobs eligible when the item's specialization is rolled at drop time (up to `SPECIAL_JOB_RANDOM_MAX` = 12). 441 files. Shipped names include two typos ("Atalanter", "Atalantar") that match no table entry and are skipped by the engine. |
| `**흡수력` | float [2] | `fSpecial_Absorb[2]` | Specialized absorption. |
| `**방어력` | int [2] | `sSpecial_Defence[2]` | Specialized defense. |
| `**이동속도` | float [2] | `fSpecial_fSpeed[2]` | Specialized speed. |
| `**마법숙련도` | float [2] | `fSpecial_Magic_Mastery[2]` | Specialized magic mastery. |
| `**마나재생` / `**기력재생` | float [2] | `fSpecial_Mana_Regen[2]` | Specialized mana regen. |
| `**라이프재생` / `**생명력재생` | float | `Per_Life_Regen` | Specialized life regen (single value). |
| `**스테미나재생` / `**근력재생` | float | `Per_Stamina_Regen` | Specialized stamina regen (single value). |
| `**블럭율` | float | `JobItem.Add_fBlock_Rating` | Specialized block rating (single value). |
| `**공격속도` | int | `JobItem.Add_Attack_Speed` | Specialized attack speed. |
| `**크리티컬` | int | `JobItem.Add_Critical_Hit` | Specialized critical. |
| `**사정거리` | int | `JobItem.Add_Shooting_Range` | Specialized range. |
| `**마나추가` / `**기력추가` | int | `JobItem.Lev_Mana` | Level-scaled mana add (single value). |
| `**라이프추가` / `**생명력추가` | int | `JobItem.Lev_Life` | Level-scaled life add. |
| `**명중력` | int [2] | `Lev_Attack_Rating[2]` | Level-scaled accuracy min/max. |
| `**공격력` | int [2] | `JobItem.Lev_Damage[2]` | Level-scaled damage min/max. |

### Spawn limiting

| key | values | engine target | meaning |
|-----|--------|---------------|---------|
| `*발생제한` | int | `sGenDay[0]` | Max spawns of this item per day (unique/world-drop throttle: the drop is refused while `sGenDay[1] >= sGenDay[0]`, OnSever.cpp:3039-3048; the counter resets at midnight, OnSever.cpp:6297-6305). 2 files. |
| `*최대수량` | int | (no engine case) | Synonym of `*발생제한` used by 27 shipped files ("max quantity"); decoded to the same field. |

## 3. Relationship to the drop table

Monster INF `*아이템` lines and NPC `*판매` lines reference items by the same
5-character category the TXT `*코드` declares. The server's `DefaultItems`
table is exactly the parsed TXT corpus, so an INF drop code whose TXT is
missing falls through the item lookup and the entry is skipped.
