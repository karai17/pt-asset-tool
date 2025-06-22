import math
import re
import types


VERSION = "0.1.0"

ANGLE_360 = 4096
TAU = 2 * math.pi
SCALE_INCH_TO_METER = 0.0254

STAGE_SIGNATURE = "SMD Stage data Ver 0.72"
ACTOR_SIGNATURE = "SMD Model data Ver 0.62"
OBJECT_HEAD = int.from_bytes(b"\xc1\x42\x43\x44")
OBJECT_HEAD_OLD = int.from_bytes(b"\x41\x42\x43\x44")
CONFIG_PATTERN = re.compile(rb'"[^"]*"|\S+')


# Spawn Monster
SPM = types.SimpleNamespace()
SPM.MAX_MONSTERS           = b"*\xc3\xd6\xb4\xeb\xb5\xbf\xbd\xc3\xc3\xe2\xc7\xf6\xbc\xf6"
SPM.SPAWN_INTERVAL         = b"*\xc3\xe2\xc7\xf6\xb0\xa3\xb0\xdd"
SPM.MAX_MONSTERS_PER_POINT = b"*\xc3\xe2\xc7\xf6\xbc\xf6"
SPM.MONSTER_SPAWN          = b"*\xc3\xe2\xbf\xac\xc0\xda"
SPM.BOSS_SPAWN             = b"*\xc3\xe2\xbf\xac\xc0\xda\xb5\xce\xb8\xf1"


# Character Definition
NPC = types.SimpleNamespace()
NPC._ACTIVE              = b"\xc0\xfb"
NPC._EMPTY               = b"\xbe\xf8\xc0\xbd"
NPC.State                = b"*\xbc\xd3\xbc\xba"
NPC.szModelName          = b"*\xb8\xf0\xbe\xe7\xc6\xc4\xc0\xcf"
NPC.Level                = b"*\xb7\xb9\xba\xa7"
NPC.szName               = b"*\xc0\xcc\xb8\xa7"
NPC.Name                 = b"*Name"
NPC.lpDialogMessage      = b"*\xb4\xeb\xc8"
NPC.SellAttackItem       = b"*\xb9\xab\xb1\xe2\xc6\xc7\xb8\xc5"
NPC.SellDefenceItem      = b"*\xb9\xe6\xbe\xee\xb1\xb8\xc6\xc7\xb8\xc5"
NPC.SellEtcItemCount     = b"*\xc0\xe2\xc8\xad\xc6\xc7\xb8\xc5"
NPC.SkillMaster          = b"*\xbd\xba\xc5\xb3\xbc\xf6\xb7\xc3"
NPC.SkillChangeJob       = b"*\xc1\xf7\xbe\xf7\xc0\xfc\xc8\xaf"
NPC.EventNPC             = b"*\xc0\xcc\xba\xa5\xc6\xae\xb8\xc5\xc7\xa5\xbc\xd2"
NPC.WareHouseMaster      = b"*\xbe\xc6\xc0\xcc\xc5\xdb\xba\xb8\xb0\xfc"
NPC.ItemMix              = b"*\xbe\xc6\xc0\xcc\xc5\xdb\xc1\xb6\xc7\xd5"
NPC.Smelting             = b"*\xbe\xc6\xc0\xcc\xc5\xdb\xc1\xa6\xb7\xc3"
NPC.Manufacture          = b"*\xbe\xc6\xc0\xcc\xc5\xdb\xc1\xa6\xc0\xdb"
NPC.ItemMix200           = b"*\xbe\xc6\xc0\xcc\xc5\xdb\xbf\xac\xb1\xdd"
NPC.ItemAging            = b"*\xbe\xc6\xc0\xcc\xc5\xdb\xbf\xa1\xc0\xcc\xc2\xa1"
NPC.MixtureReset         = b"*\xb9\xcd\xbd\xba\xc3\xb3\xb8\xae\xbc\xc2"
NPC.CollectMoney         = b"*\xb8\xf0\xb1\xdd\xc7\xd4"
NPC.WowEvent             = b"*\xb2\xce\xc0\xcc\xc1\xf6\xb7\xd5"
NPC.EventGift            = b"*\xb0\xe6\xc7\xb0\xc3\xdf\xc3\xb7"
NPC.ClanNPC              = b"*\xc5\xac\xb7\xa3\xb1\xe2\xb4\xc9"
NPC.GiftExpress          = b"*\xb0\xe6\xc7\xb0\xb9\xe8\xb4\xde"
NPC.WingQuestNpc1        = b"*\xc0\xae\xc4\xf9\xbd\xba\xc6\xae"
NPC.WingQuestNpc2        = b"*\xc4\xf9\xbd\xba\xc6\xae\xc0\xcc\xba\xa5\xc6\xae"
NPC.StarPointNpc         = b"*\xba\xb0\xc6\xf7\xc0\xce\xc6\xae\xc0\xfb\xb8\xb3"
NPC.GiveMoneyNpc         = b"*\xb1\xe2\xba\xce\xc7\xd4"
NPC.TelePortNpc          = b"*\xc5\xda\xb7\xb9\xc6\xf7\xc6\xae"
NPC.BlessCastleNPC       = b"*\xba\xed\xb7\xb9\xbd\xba\xc4\xb3\xbd\xbd"
NPC.PollingNpc           = b"*\xbc\xb3\xb9\xae\xc1\xb6\xbb\xe7"
NPC.szMediaPlayNPC_Title = b"*\xb5\xbf\xbf\xb5\xbb\xf3\xc1\xa6\xb8\xf1"
NPC.szMediaPlayNPC_Path  = b"*\xb5\xbf\xbf\xb5\xbb\xf3\xb0\xe6\xb7\xce"
NPC.OpenCount            = b"*\xc3\xe2\xc7\xf6\xb0\xa3\xb0\xdd"
NPC.QuestCode            = b"*\xc4\xf9\xbd\xba\xc6\xae\xc4\xda\xb5\xe5"
NPC.szNextFile           = b"*\xbf\xac\xb0\xe1\xc6\xc4\xc0\xcf"










# Monster Definition
INF = types.SimpleNamespace()
INF.wPlayClass                    = b"*\xb5\xce\xb8\xf1" # MONSTER_CLASS_BOSS (Boolean)
INF.Size                          = b"*\xb8\xf0\xb5\xa8\xc5\xa9\xb1\xe2" # wPlayClass[1] short 1 Value
INF.szName                        = b"*\xc0\xcc\xb8\xa7" # szName StringValue
INF.Level                         = b"*\xb7\xb9\xba\xa7" # Level integer 1 value
INF.wPlayClass2                   = b"*\xb0\xe8\xb1\xde" # wPlayClass Integer 1 Value (Rank)
INF.ClassCode                     = b"*\xb1\xb8\xba\xb0\xc4\xda\xb5\xe5" # ClassCode integer 1 Value
INF.GenerateGroup                 = b"*\xc1\xb6\xc1\xf7" # GenerateGroup integer 2 Values
INF.IQ                            = b"*\xc1\xf6\xb4\xc9" # IQ integer 1 Value
INF.Nature                        = b"*\xc7\xb0\xbc\xba" # Nature StringValue no "String" PossibleValues "good" "evil" ""                                   = neutral
INF.Real_Sight                    = b"*\xbd\xc3\xbe\xdf" # Sight integer 1 value
INF.Life                          = b"*\xbb\xfd\xb8\xed\xb7\xc2" #  Life integer 2 Values (Only first Value is used)
INF.Life2                         = b"*\xb6\xf3\xc0\xcc\xc7\xc1" #  Life integer 2 Values (Only first Value is used)
INF.Attack_Damage                 = b"*\xb0\xf8\xb0\xdd\xb7\xc2" #  Attack_Damage integer 2 values
INF.SkillDamage                   = b"*\xb1\xe2\xbc\xfa\xb0\xf8\xb0\xdd\xb7\xc2" # SkillDamage integer 2 Values
INF.SkillRating                   = b"*\xb1\xe2\xbc\xfa\xb0\xf8\xb0\xdd\xb7\xfc" # SkillRating integer 1 Value
INF.SkillDistance                 = b"*\xb1\xe2\xbc\xfa\xb0\xf8\xb0\xdd\xb0\xc5\xb8\xae" # SkillDistance integer 1 Value
INF.SkillRange                    = b"*\xb1\xe2\xbc\xfa\xb0\xf8\xb0\xdd\xb9\xfc\xc0\xa7" #  SkillRange integer 1 Value
INF.SkillCurse                    = b"*\xc0\xfa\xc1\xd6\xb1\xe2\xbc\xfa" # SkillCurse integer 1 Value
INF.Absorption                    = b"*\xc8\xed\xbc\xf6\xc0\xb2" #  Absorption integer 1 value
INF.Chance_Block                  = b"*\xba\xed\xb7\xb0\xc0\xb2" #  Chance_Block integer 1 Value
INF.Defence                       = b"*\xb9\xe6\xbe\xee\xb7\xc2" #  Defence integer 1 value
INF.Attack_Speed                  = b"*\xb0\xf8\xb0\xdd\xbc\xd3\xb5\xb5" #  Attack_Speed integer 2 values
INF.Attack_Rating                 = b"*\xb8\xed\xc1\xdf\xb7\xc2" # Attack_Rating integer 1 value
INF.SpAttackPercetage             = b"*\xc6\xaf\xbc\xf6\xb0\xf8\xb0\xdd\xb7\xfc" # SpAttackPercetage integer 1 Value
INF.Shooting_Range                = b"*\xb0\xf8\xb0\xdd\xb9\xfc\xc0\xa7" # Shooting_Range integer 1 value
INF.Resistance_sITEMINFO_BIONIC   = b"*\xbb\xfd\xc3\xbc" # Resistance[sITEMINFO_BIONIC] short integer 1 value
INF.Resistance_sITEMINFO_LIGHTING = b"*\xb9\xf8\xb0\xb3" # Resistance[sITEMINFO_LIGHTING] short integer 1 value
INF.Resistance_sITEMINFO_ICE      = b"*\xbe\xf3\xc0\xbd" # Resistance[sITEMINFO_ICE] short integer 1 value
INF.Resistance_sITEMINFO_FIRE     = b"*\xba\xd2" # Resistance[sITEMINFO_FIRE] short integer 1 value
INF.Resistance_sITEMINFO_POISON   = b"*\xb5\xb6" # Resistance[sITEMINFO_POISON] short integer 1 value
INF.Resistance_sITEMINFO_WATER    = b"*\xb9\xb0" # Resistance[sITEMINFO_WATER] short integer 1 value
INF.Resistance_sITEMINFO_WIND     = b"*\xb9\xd9\xb6\xf7" # Resistance[sITEMINFO_WIND] short integer 1 value
INF.Resistance_sITEMINFO_EARTH    = b"*\xc1\xf6\xb5\xbf\xb7\xc2" # Resistance[sITEMINFO_EARTH] short integer 1 value
INF.Type                          = b"*\xb8\xf3\xbd\xba\xc5\xcd\xc1\xbe\xc1\xb7" # Brood StringValue no "String" Possible Values "\xbe\xf0\xb5\xa5\xb5\xe5" = smCHAR_MONSTER_UNDEAD,                    "\xb9\xc2\xc5\xcf\xc6\xae" = smCHAR_MONSTER_MUTANT, "\xb5\xf0\xb8\xd5" = smCHAR_MONSTER_DEMON, "\xb8\xde\xc4\xab\xb4\xd0" = smCHAR_MONSTER_MECHANIC
INF.IsUndead                      = b"*\xbe\xf0\xb5\xa5\xb5\xe5" # Undead(Brood) StringValue no "String" ""                                                 = Neutral "\xc0\xaf" or "\xc0\xd6\xc0\xbd" = Undead
INF.MoveRange                     = b"*\xc0\xcc\xb5\xbf\xb9\xfc\xc0\xa7" #  MoveRange integer 1 Value
INF.MoveType                      = b"*\xc0\xcc\xb5\xbf\xc5\xb8\xc0\xd4" #  Not supported
INF.SoundEffect                   = b"*\xc8\xbf\xb0\xfa\xc0\xbd" # SoundCode StringValue no "String"
INF.SoundEffect2                  = b"*\xbc\xd2\xb8\xae" # SoundCode StringValue no "String"
INF.Exp                           = b"*\xb0\xe6\xc7\xe8\xc4\xa1" #  Exp integer 1 Value
INF.FallItemMax                   = b"*\xbe\xc6\xc0\xcc\xc5\xdb\xc4\xab\xbf\xee\xc5\xcd" #  FallItemMax integer 1 Value
INF.FallItems                     = b"*\xbe\xc6\xc0\xcc\xc5\xdb" # First Value Percent of Total,                                                             ItemCodes (Testserver mode different percent calculation)
INF.FallItems_Plus                = b"*\xc3\xdf\xb0\xa1\xbe\xc6\xc0\xcc\xc5\xdb" #  First Value Percent,                                                     ItemCode
INF.AllSeeItem                    = b"*\xbe\xc6\xc0\xcc\xc5\xdb\xb8\xf0\xb5\xce" # AllSeeItem Everyone can see Drops! Boolean
INF._DropGold                     = "\xb5\xb7" # \xb5\xb7                                                                                                   = Gold min max
INF._DropEmpty                    = "\xbe\xf8\xc0\xbd" # NoDrop
INF.State                         = b"*\xbc\xd3\xbc\xba" # State Value (\xc0\xfb = True) ("" = False)
INF.szModelName                   = b"*\xb8\xf0\xbe\xe7\xc6\xc4\xc0\xcf" # szModelName StringValue
INF.Name                          = b"*Name" # not supported
INF.ActiveHour                    = b"*\xc8\xb0\xb5\xbf\xbd\xc3\xb0\xa3" # String no "StringValue" 1 Value,                                                  3 Possible Values (""=0,"\xb3\xb7"=1,"\xb9\xe3"=-1)
INF.ArrowPosi                     = b"*\xc8\xad\xb8\xe9\xba\xb8\xc1\xa4" # ArrowPosi integer 2 value(keystone)
INF.SizeLevel                     = b"*\xc5\xa9\xb1\xe2" # StringValue no "String" Value Values "\xbc\xd2\xc7\xfc",                                          "\xc1\xdf\xc7\xfc",                        "\xc1\xdf\xb4\xeb\xc7\xfc", "\xb4\xeb\xc7\xfc",     ""
INF.PotionCount                   = b"*\xb9\xb0\xbe\xe0\xba\xb8\xc0\xaf\xbc\xf6" #  PotionCount integer 1 Value
INF.PotionPercent                 = b"*\xb9\xb0\xbe\xe0\xba\xb8\xc0\xaf\xb7\xfc" # PotionPercent integer 1 Value
INF.EventCode                     = b"*\xc0\xcc\xba\xa5\xc6\xae\xc4\xda\xb5\xe5" # EventCode integer 1 Value
INF.EventInfo                     = b"*\xc0\xcc\xba\xa5\xc6\xae\xc1\xa4\xba\xb8" # EventInfo integer 1 Value
INF.dwEvnetItem                   = b"*\xc0\xcc\xba\xa5\xc6\xae\xbe\xc6\xc0\xcc\xc5\xdb" # EventDrop Value 1 ItemCode
INF.szModelName2                  = b"*\xbf\xb9\xba\xf1\xb8\xf0\xb5\xa8" # szModelName2 (UseEventModel) StringValue
INF.ExtraGold                     = b"*\xb0\xf1\xb5\xe5" # not supportet?
INF.DamageStunPers                = b"*\xbd\xba\xc5\xcf\xc0\xb2" # DamageStunPers integer 1 Value
INF.DamageStunPers2               = b"*\xbd\xba\xc5\xcf\xb7\xfc" # DamageStunPers integer 1 Value
INF.Move_Speed                    = b"*\xc0\xcc\xb5\xbf\xb7\xc2" # Move_Speed float 1 value
INF.lpDialogMessage               = b"*\xb4\xeb\xc8\xad" # lpDialogMessage StringValue
INF.szNextFile                    = b"*\xbf\xac\xb0\xe1\xc6\xc4\xc0\xcf" # String Value "String"

# Structure Monster_SizeLevel
INF.Small  = b"\xbc\xd2\xc7\xfc"
INF.Medium = b"\xc1\xdf\xc7\xfc"
INF.Big    = b"\xc1\xdf\xb4\xeb\xc7\xfc"
INF.Bigger = b"\xb4\xeb\xc7\xfc"
INF.No     = ""

# Structure Monster_Nature
INF.good = "good"
INF.evil = "evil"

# Structure ActiveHours
INF.No    = "" # 0
INF.Day   = b"\xb3\xb7" # 1
INF.Night = b"\xb9\xe3" # -1

# Structure Monster_State
INF.State_True  = b"\xc0\xfb"
INF.State_False = ""

# Structure Monster_Type
INF.Normal   = ""
INF.Daemon   = b"\xb5\xf0\xb8\xd5"
INF.Undead   = b"\xbe\xf0\xb5\xa5\xb5\xe5"
INF.Mutant   = b"\xb9\xc2\xc5\xcf\xc6\xae"
INF.Mechanic = b"\xb8\xde\xc4\xab\xb4\xd0"
INF.Iron     = b"\xbe\xc6\xc0\xcc\xbe\xf0"

# Structure Monster_Undead
INF.Normal  = ""
INF.Undead  = b"\xc0\xaf"
INF.Undead2 = b"\xc0\xd6\xc0\xbd"










# Item Definition
TXT = types.SimpleNamespace()
TXT.NameEnglish                    = b"*Name" # Not supported/used in Server
TXT.ItemName                       = b"*\xc0\xcc\xb8\xa7" # \'ItemName StringValue
TXT.Code                           = b"*\xc4\xda\xb5\xe5" # ItemCode StringValue no "String"
TXT.Integrity                      = b"*\xb3\xbb\xb1\xb8\xb7\xc2" # sDurability Integer 2 Values
TXT.Weight                         = b"*\xb9\xab\xb0\xd4" # Weight Integer 1 Value
TXT.Price                          = b"*\xb0\xa1\xb0\xdd" # Price Integer 1 Value
TXT.sResistance_sITEMINFO_BIONIC   = b"*\xbb\xfd\xc3\xbc" # sResistance[sITEMINFO_BIONIC] Integer 2 Values
TXT.sResistance_sITEMINFO_FIRE     = b"*\xba\xd2" # sResistance[sITEMINFO_FIRE] Integer 2 Value
TXT.sResistance_sITEMINFO_ICE      = b"*\xb3\xc3\xb1\xe2" # sResistance[sITEMINFO_ICE] Integer 2 Value
TXT.sResistance_sITEMINFO_LIGHTING = b"*\xb9\xf8\xb0\xb3" # sResistance[sITEMINFO_LIGHTING] Integer 2 Value
TXT.sResistance_sITEMINFO_POISON   = b"*\xb5\xb6" # sResistance[sITEMINFO_POISON] Integer 2 Value
TXT.sDamage                        = b"*\xb0\xf8\xb0\xdd\xb7\xc2" # Damage Integer 4 Values
TXT.sAttack_Rating                 = b"*\xb8\xed\xc1\xdf\xb7\xc2" # sAttack_Rating Integer 2 Values
TXT.sDefence                       = b"*\xb9\xe6\xbe\xee\xb7\xc2" # \'sDefence Integer 2 Values (Something Special if Spec Defence follow?)
TXT.fAbsorb                        = b"*\xc8\xed\xbc\xf6\xb7\xc2" # fAbsorb Float 2 Values
TXT.fBlock_Rating                  = b"*\xba\xed\xb7\xb0\xc0\xb2" # fBlock_Rating float 2 Values
TXT.Attack_Speed                   = b"*\xb0\xf8\xb0\xdd\xbc\xd3\xb5\xb5" # Attack_Speed word 1 value
TXT.Critical_Hit                   = b"*\xc5\xa9\xb8\xae\xc6\xbc\xc4\xc3" # Critical_Hit Integer 1 Value
TXT.Shooting_Range                 = b"*\xbb\xe7\xc1\xa4\xb0\xc5\xb8\xae" # Shooting_Range Integer 1 Value
TXT.Potion_Space                   = b"*\xba\xb8\xc0\xaf\xb0\xf8\xb0\xa3" # Potion_Space Integer 1 Value
TXT.fLife_Regen                    = b"*\xbb\xfd\xb8\xed\xb7\xc2\xc0\xe7\xbb\xfd" # fLife_Regen float 2 values (will overwrite fLife_Regen2)
TXT.fLife_Regen2                   = b"*\xb6\xf3\xc0\xcc\xc7\xc1\xc0\xe7\xbb\xfd" # fLife_Regen2 float 2 values (will overwrite fLife_Regen)
TXT.fMana_Regen                    = b"*\xb1\xe2\xb7\xc2\xc0\xe7\xbb\xfd" # fMana_Regen float 2 values (will overwrite fMana_Regen2)
TXT.fMana_Regen2                   = b"*\xb8\xb6\xb3\xaa\xc0\xe7\xbb\xfd" # fMana_Regen2 float 2 Values (will overwrite fMana_Regen)
TXT.fStamina_Regen                 = b"*\xb1\xd9\xb7\xc2\xc0\xe7\xbb\xfd" # fStamina_Regen float 2 values (will overwrite fStamina_Regen2)
TXT.fStamina_Regen2                = b"*\xbd\xba\xc5\xd7\xb9\xcc\xb3\xaa\xc0\xe7\xbb\xfd" # fStamina_Regen2 float 2 values (will overwrite fStamina_Regen)
TXT.Increase_Life                  = b"*\xbb\xfd\xb8\xed\xb7\xc2\xc3\xdf\xb0\xa1" # \'Increase_Life Integer 2 values (will overwrite Increase_Life2)
TXT.Increase_Life2                 = b"*\xb6\xf3\xc0\xcc\xc7\xc1\xc3\xdf\xb0\xa1" # \'Increase_Life2 Integer 2 values (will overwrite Increase_Life)
TXT.Increase_Mana                  = b"*\xb1\xe2\xb7\xc2\xc3\xdf\xb0\xa1" # Increase_Mana Integer 2 values (will overwrite Increase_Mana2)
TXT.Increase_Mana2                 = b"*\xb8\xb6\xb3\xaa\xc3\xdf\xb0\xa1" # Increase_Mana2 Integer 2 Values (will overwrite Increase_Mana)
TXT.Increase_Stamina               = b"*\xb1\xd9\xb7\xc2\xc3\xdf\xb0\xa1" # Increase_Stamina Integer 2 values (will overwrite Increase_Stamina2)
TXT.Increase_Stamina2              = b"*\xbd\xba\xc5\xd7\xb9\xcc\xb3\xaa\xc3\xdf\xb0\xa1" # Increase_Stamina Integer 2 values (will overwrite Increase_Stamina)
TXT.Level                          = b"*\xb7\xb9\xba\xa7" # Level Integer 1 value
TXT.Strength                       = b"*\xc8\xfb" # Strength Integer 1 value
TXT.Spirit                         = b"*\xc1\xa4\xbd\xc5\xb7\xc2" # Spirit Integer 1 value
TXT.Talent                         = b"*\xc0\xe7\xb4\xc9" # Talent Integer 1 value
TXT.Agility_Dexterity              = b"*\xb9\xce\xc3\xb8\xbc\xba" # Dexterity Integer 1 value
TXT.Health                         = b"*\xb0\xc7\xb0\xad" # Health Integer 1 value
TXT.DispEffect                     = b"*\xc0\xcc\xc6\xe5\xc6\xae\xbc\xb3\xc1\xa4" # DispEffect Integer 1 Value
TXT.sResistance_sITEMINFO_EARTH    = b"*\xb4\xeb\xc0\xda\xbf\xac" # sResistance[sITEMINFO_EARTH] Integer 2 Values
TXT.sResistance_sITEMINFO_WATER    = b"*\xb9\xb0" # sResistance[sITEMINFO_WATER] Integer 2 Values
TXT.sResistance_sITEMINFO_WIND     = b"*\xb9\xd9\xb6\xf7" # sResistance[sITEMINFO_WIND] Integer 2 Values
TXT.TransfereSpeed                 = b"*\xc0\xcc\xb5\xbf\xbc\xd3\xb5\xb5" # fSpeed float 2 Values
TXT.UniqueItem                     = b"*\xc0\xaf\xb4\xcf\xc5\xa9" # UniqueItem Word 1 Value
TXT.dwJobBitCode_Random            = b"**\xc6\xaf\xc8\xad\xb7\xa3\xb4\xfd" # dwJobBitCode_Random
TXT.JobCodeMask                    = b"**\xc6\xaf\xc8\xad" # \' JobCodeMask (Primary Spec)
TXT.fSpecial_Absorb                = b"**\xc8\xed\xbc\xf6\xb7\xc2" # fSpecial_Absorb float 2 values
TXT.sSpecial_Defence               = b"**\xb9\xe6\xbe\xee\xb7\xc2" # sSpecial_Defence Integer 2 values
TXT.JobItem_Per_Life_Regen         = b"**\xbb\xfd\xb8\xed\xb7\xc2\xc0\xe7\xbb\xfd" # Per_Life_Regen float 1 value
TXT.JobItem_Per_Life_Regen2        = b"**\xb6\xf3\xc0\xcc\xc7\xc1\xc0\xe7\xbb\xfd" # Per_Life_Regen float 1 value
TXT.fSpecial_Mana_Regen            = b"**\xb1\xe2\xb7\xc2\xc0\xe7\xbb\xfd" # fSpecial_Mana_Regen float 2 values
TXT.fSpecial_Mana_Regen2           = b"**\xb8\xb6\xb3\xaa\xc0\xe7\xbb\xfd" # fSpecial_Mana_Regen float 2 values
TXT.JobItem_Per_Stamina_Regen      = b"**\xb1\xd9\xb7\xc2\xc0\xe7\xbb\xfd" # Per_Stamina_Regen float 1 value
TXT.JobItem_Per_Stamina_Regen2     = b"**\xbd\xba\xc5\xd7\xb9\xcc\xb3\xaa\xc0\xe7\xbb\xfd" # Per_Stamina_Regen float 1 value
TXT.fSpecial_fSpeed                = b"**\xc0\xcc\xb5\xbf\xbc\xd3\xb5\xb5" # fSpecial_fSpeed float 2 values
TXT.JobItem_Add_Attack_Speed       = b"**\xb0\xf8\xb0\xdd\xbc\xd3\xb5\xb5" # Add_Attack_Speed Integer 1 value
TXT.JobItem_Add_fBlock_Rating      = b"**\xba\xed\xb7\xb0\xc0\xb2" # Add_fBlock_Rating float 1 value
TXT.Lev_Attack_Rating              = b"**\xb8\xed\xc1\xdf\xb7\xc2" # Lev_Attack_Rating Integer 2 values
TXT.JobItem_Lev_Damage             = b"**\xb0\xf8\xb0\xdd\xb7\xc2" # Lev_Damage Integer 2 values
TXT.JobItem_Add_Critical_Hit       = b"**\xc5\xa9\xb8\xae\xc6\xbc\xc4\xc3" # Add_Critical_Hit Integer 1 value
TXT.fSpecial_Magic_Mastery         = b"**\xb8\xb6\xb9\xfd\xbc\xf7\xb7\xc3\xb5\xb5" # fSpecial_Magic_Mastery float 2 values
TXT.JobItem_Add_Shooting_Range     = b"**\xbb\xe7\xc1\xa4\xb0\xc5\xb8\xae" # Add_Shooting_Range Integer 1 value
TXT.JobItem_Lev_Mana               = b"**\xb8\xb6\xb3\xaa\xc3\xdf\xb0\xa1" # JobItem_Lev_Mana Integer 1 value (will overwite JobItem_Lev_Mana2)
TXT.JobItem_Lev_Mana2              = b"**\xb1\xe2\xb7\xc2\xc3\xdf\xb0\xa1" # JobItem_Lev_Mana2 Integer 1 value (will overwite JobItem_Lev_Mana)
TXT.JobItem_Lev_Life               = b"**\xb6\xf3\xc0\xcc\xc7\xc1\xc3\xdf\xb0\xa1" # JobItem_Lev_Life Integer 1 value (will overwite JobItem_Lev_Life2)
TXT.JobItem_Lev_Life2              = b"**\xbb\xfd\xb8\xed\xb7\xc2\xc3\xdf\xb0\xa1" # JobItem_Lev_Life2 Integer 1 value (will overwite JobItem_Lev_Life)
TXT.fMagic_Mastery                 = b"*\xb8\xb6\xb9\xfd\xbc\xf7\xb7\xc3\xb5\xb5" # fMagic_Mastery float 1 Value
TXT.Stamina                        = b"*\xb1\xd9\xb7\xc2\xbb\xf3\xbd\xc2" # Stamina Integer 2 values
TXT.Stamina2                       = b"*\xbd\xba\xc5\xd7\xb9\xcc\xb3\xca\xbb\xf3\xbd\xc2" # Stamina Integer 2 values
TXT.Mana                           = b"*\xb1\xe2\xb7\xc2\xbb\xf3\xbd\xc2" # Mana Integer 2 values
TXT.Mana2                          = b"*\xb8\xb6\xb3\xaa\xbb\xf3\xbd\xc2" # Mana Integer 2 values
TXT.Life                           = b"*\xbb\xfd\xb8\xed\xb7\xc2\xbb\xf3\xbd\xc2" # Life Integer 2 values
TXT.Life2                          = b"*\xb6\xf3\xc0\xcc\xc7\xc1\xbb\xf3\xbd\xc2" # Life Integer 2 values
TXT.EffectColor                    = b"*\xc0\xaf\xb4\xcf\xc5\xa9\xbb\xf6\xbb\xf3" # EffectColor[0-3] EffectBlink[0] Integer 5 Values R, G, B, A, Blink
TXT.sGenDay                        = b"*\xb9\xdf\xbb\xfd\xc1\xa6\xc7\xd1" # sGenDay Integer 1 value
TXT.szNextFile                     = b"*\xbf\xac\xb0\xe1\xc6\xc4\xc0\xcf" # szNextFile StringValue










# Reference: character.h::CHRMOTION_EXT
CHRMOTION = {
	int.from_bytes(b"\x00\x01"): "hvPOSI_RHAND",
	int.from_bytes(b"\x00\x02"): "hvPOSI_LHAND",
	int.from_bytes(b"\x00\x0a"): "EXT"
}

CHRMOTION_STATE = {
	int.from_bytes(b"\x00\x40"): "stand",
	int.from_bytes(b"\x00\x50"): "walk",
	int.from_bytes(b"\x00\x60"): "run",
	int.from_bytes(b"\x00\x80"): "falldown",
	int.from_bytes(b"\x01\x00"): "attack",
	int.from_bytes(b"\x01\x10"): "damage",
	int.from_bytes(b"\x01\x20"): "dead",
	int.from_bytes(b"\x01\x30"): "sometime",
	int.from_bytes(b"\x01\x40"): "eat",
	int.from_bytes(b"\x01\x50"): "skill",
	int.from_bytes(b"\x01\x70"): "fallstand",
	int.from_bytes(b"\x01\x80"): "falldamage",
	int.from_bytes(b"\x02\x00"): "restart",
	int.from_bytes(b"\x02\x10"): "warp",
	int.from_bytes(b"\x02\x20"): "yahoo",
	int.from_bytes(b"\x03\x00"): "hammer",
	int.from_bytes(b"\x00\x00"): "talk_blank",
	int.from_bytes(b"\x04\x00"): "talk_ar",
	int.from_bytes(b"\x04\x10"): "talk_e",
	int.from_bytes(b"\x04\x20"): "talk_oh",
	int.from_bytes(b"\x04\x30"): "talk_eye",
	int.from_bytes(b"\x04\x40"): "talk_smile",
	int.from_bytes(b"\x04\x50"): "talk_grumble",
	int.from_bytes(b"\x04\x60"): "talk_sorrow",
	int.from_bytes(b"\x04\x70"): "talk_startled",
	int.from_bytes(b"\x04\x80"): "talk_nature",
	int.from_bytes(b"\x04\x90"): "talk_special"
}


STAGE_SCRIPT = [                                         # szMapStageScript, BsStageScript
	[ "BS_MODULATE:",     4 ],
	[ "BS_MODULATE2X:",   5 ],
	[ "BS_MODULATE4X:",   6 ],
	[ "BS_ADD:",          7 ],
	[ "BS_ADDSIGNED:",    8 ],
	[ "BS_ADDSIGNED2X:",  9 ],
	[ "BS_SUBTRACT:",    10 ]
]

FORM_SCRIPT = [                                          # szMapFormScript
	[ "FS_NONE:",         1 ],
	[ "FS_FORMX:",        2 ],
	[ "FS_FORMY:",        3 ],
	[ "FS_FORMZ:",        4 ],
	[ "FS_SCROLL:",       5 ],
	[ "FS_REFLEX:",       6 ],
	[ "FS_SCROLL2:",      7 ],
	[ "FS_SCROLL3:",      8 ],
	[ "FS_SCROLL4:",      9 ],
	[ "FS_SCROLL5:",     10 ],
	[ "FS_SCROLL6:",     11 ],
	[ "FS_SCROLL7:",     12 ],
	[ "FS_SCROLL8:",     13 ],
	[ "FS_SCROLL9:",     14 ],
	[ "FS_SCROLL10:",    15 ],
	[ "FS_SCROLLSLOW1:", 16 ],
	[ "FS_SCROLLSLOW2:", 17 ],
	[ "FS_SCROLLSLOW3:", 18 ],
	[ "FS_SCROLLSLOW4:", 19 ]
]

MTL_FORM_SCRIPT = [                                      # MaterialFormScript
	[ "wind:",                  int.from_bytes(b"\x01") ],
	[ "anim2:",                 int.from_bytes(b"\x02") ],
	[ "anim4:",                 int.from_bytes(b"\x04") ],
	[ "anim8:",                 int.from_bytes(b"\x08") ],
	[ "anim16:",                int.from_bytes(b"\x10") ],
	[ "wind_z1:",               int.from_bytes(b"\x20") ],
	[ "wind_z2:",               int.from_bytes(b"\x40") ],
	[ "wind_x1:",               int.from_bytes(b"\x80") ],
	[ "wind_x2:",           int.from_bytes(b"\x01\x00") ],
	[ "water:",             int.from_bytes(b"\x02\x00") ],
	[ "wall:",              int.from_bytes(b"\x04\x00") ],
	[ "pass:",              int.from_bytes(b"\x08\x00") ],
	[ "notpass:",           int.from_bytes(b"\x10\x00") ],
	[ "render_latter:",     int.from_bytes(b"\x20\x00") ],
	[ "BLINK_COLOR:",       int.from_bytes(b"\x40\x00") ],
	[ "ice:",               int.from_bytes(b"\x80\x00") ],
	[ "orgwater:",      int.from_bytes(b"\x01\x00\x00") ]
]

MTL_FORM_BLEND = [                                       # MaterialFormBlend
	[ "BLEND_ALPHA:",    1 ],
	[ "BLEND_COLOR:",    2 ],
	[ "BLEND_ADDCOLOR:", 5 ],
	[ "BLEND_SHADOW:",   3 ],
	[ "BLEND_LAMP:",     4 ]
]


MONSTER_NAMES = [
	# MONSTERS
	{ "key": b"\xBA\xED\xB8\xAE\xC0\xDA\xB5\xE5\x20\xC0\xDA\xC0\xCC\xBE\xF0\xC6\xAE", "value": "Blizzard Giant" },
	{ "key": b"\xC0\xCE\xC5\xA5\xB9\xF6\xBD\xBA\x20\xBC\xAD\xB8\xD3\xB3\xCA", "value": "Incubus Summoner" },
	{ "key": b"\xBD\xCE\xC0\xCC\xC5\xAC\xB7\xD3\xBD\xBA\x20\xBF\xF6\xB8\xAE\xBE\xEE", "value": "Cyclops Warrior" },
	{ "key": b"\xB5\xA5\xBA\xED\x20\xB9\xF6\xB5\xE5", "value": "Devil Bird" },
	{ "key": b"\xC5\xCD\xC6\xB2\x20\xC4\xB3\xB3\xED", "value": "Turtle Cannon" },
	{ "key": b"\xC7\xC1\xB7\xCE\xBD\xBA\xC6\xAE\x20\xBF\xA1\xC0\xCC\xBC\xC7\xC6\xAE", "value": "Frost Ancient" },
	{ "key": b"\xBE\xC6\xC0\xCC\xBD\xBA\x20\xB0\xED\xB7\xBD", "value": "Ice Golem" },
	{ "key": b"\xB9\xCC\xBD\xBA\xC6\xBD\x20\xBD\xBA\xC7\xC7\xB3\xDA", "value": "Mystic Spinel" },
	{ "key": b"\xC4\xAB\xBF\xC0\xBD\xBA\x20\xC4\xAB\xB6\xF3", "value": "Chaos Kara" },
	{ "key": b"\xC0\xA7\xC4\xA1", "value": "Location" },
	{ "key": b"\xBD\xF0\x20\xC5\xA9\xB7\xCE\xBF\xEF\xB7\xAF", "value": "Torn Crowler" },
	{ "key": b"\xB8\xB6\xC0\xCC\xBE\xEE\x20\xC5\xB0\xC6\xDb", "value": "Mayer Kiefer" },
	{ "key": b"\xB3\xAA\xC0\xCC\xC6\xAE\xB8\xDE\xBE\xEE", "value": "Nightmare" },
	{ "key": b"\xB4\xD9\xC5\xA9\x20\xB3\xAA\xC0\xCC\xC6\xAE", "value": "The Dark Knight" },
	{ "key": b"\xB5\xD2\x20\xB0\xA1\xB5\xE5", "value": "Doom Guard" },
	{ "key": b"\xC7\xEC\xBA\xF1\x20\xB0\xED\xBA\xED\xB8\xB0", "value": "Heavy Goblin" },
	{ "key": b"\xBD\xBA\xC5\xE6\x20\xB0\xED\xB7\xBD", "value": "Stone Golem" },
	{ "key": b"\xB9\xD9\xB0\xEF", "value": "Bagon" },
	{ "key": b"\xBA\xCE\xB8\xB6", "value": "Buma" },
	{ "key": b"\xBD\xCE\xC0\xCC\xC5\xAC\xB7\xD3\xBD\xBA", "value": "Cyclops" },
	{ "key": b"\xB1\xB8\xBF\xEF", "value": "Ghoul" },
	{ "key": b"\xC5\xA9\xB8\xB3\xC6\xAE", "value": "Crypt" },
	{ "key": b"\xBD\xBA\xC4\xCC\xB7\xB9\xC5\xE6\xBE\xC6\xC3\xB3", "value": "Skeleton Archer" },
	{ "key": b"\xBE\xC6\xB8\xD3\xB5\xE5\x20\xBA\xF1\xC6\xB2", "value": "Armored Beetle" },
	{ "key": b"\xC5\xB8\xC0\xCC\xC5\xBA", "value": "Titan" },
	{ "key": b"\xB8\xB6\xC0\xCC\xC6\xBC\xB0\xED\xBA\xED\xB8\xB0", "value": "Mighty Goblin" },
	{ "key": b"\xBD\xCE\xC0\xCC\xC5\xAC\xB7\xD3\xBD\xBA\x20\xB3\xAA\xC0\xCC\xC6\xAE", "value": "Cyclops Knight" },
	{ "key": b"\xBD\xBA\xC4\xCC\xB7\xB9\xC5\xE6\xB7\xB9\xC0\xCE\xC0\xFA", "value": "Skeleton Ranger" },
	{ "key": b"\xC7\xEC\xB5\xE5\xC4\xBF\xC5\xCD", "value": "Headcutter" },
	{ "key": b"\xBE\xC6\xBA\xA7\xB8\xAE\xBD\xBA\xC5\xA9\x2D\x53", "value": "Abelisk-S" },
	{ "key": b"\xB1\xD7\xB8\xAE\xBA\xEC", "value": "Griven" },
	{ "key": b"\xBD\xBA\xC5\xE6\xC0\xDA\xC0\xCC\xBE\xF0\xC6\xAE", "value": "Stone Giant" },
	{ "key": b"\xBB\xF7\xB5\xE5\xB7\xA5", "value": "Sandram" },
	{ "key": b"\xBE\xC6\xBA\xA7\xB8\xAE\xBD\xBA\xC5\xA9\x2D\x4C", "value": "Abelisk-L" },
	{ "key": b"\xBD\xBD\xB7\xAF\xC5\xCD", "value": "Slaughter" },
	{ "key": b"\xC6\xC4\xC0\xCC\xB0\xEF", "value": "Pygon" },
	{ "key": b"\xBD\xBA\xC4\xCC\xB7\xB9\xC5\xE6\xBF\xF6\xB8\xAE\xBE\xEE", "value": "Skeleton Warrior" },
	{ "key": b"\xC0\xA5", "value": "WeB" },
	{ "key": b"\xBD\xBA\xC4\xCC\xB7\xB9\xC5\xE6\xB3\xAA\xC0\xCC\xC6\xAE", "value": "Skeleton Knight" },
	{ "key": b"\xB8\xD3\xB9\xCC", "value": "Mummy" },
	{ "key": b"\xC5\xB7\xC8\xA3\xC7\xC7", "value": "King Hopy" },
	{ "key": b"\xC0\xCF\xB7\xE7\xC1\xAF\xB3\xAA\xC0\xCC\xC6\xAE", "value": "Illusion Night" },
	{ "key": b"\xBD\xBD\xB8\xAE\xB9\xF6", "value": "Sliver" },
	{ "key": b"\xB3\xAA\xC1\xEE", "value": "Naz" },
	{ "key": b"\xC7\xEB\xC5\xB0", "value": "Hunky" },
	{ "key": b"\xBD\xBA\xC6\xBC\xC1\xF6\xBE\xF0", "value": "Stygian" },
	{ "key": b"\xB4\xD9\xBF\xEC\xB8\xB0", "value": "Daurin" },
	{ "key": b"\xBE\xC6\xBA\xA7\xB8\xAE\xBD\xBA\xC5\xA9\x20\xB7\xCE\xB5\xE5", "value": "Abelisk Road" },
	{ "key": b"\xBD\xA6\xB5\xB5\xBF\xEC", "value": "Shadow" },
	{ "key": b"\xBD\xE1\xC5\xA5\xB9\xF6\xBD\xBA", "value": "Succubus" },
	{ "key": b"\xB4\xF5\xBD\xBA\xC5\xA9", "value": "Dusk" },
	{ "key": b"\xC0\xCE\xC5\xA5\xB9\xF6\xBD\xBA", "value": "Incubus" },
	{ "key": b"\xB6\xF3\xC5\xF5", "value": "Ratu" },
	{ "key": b"\xBF\xC0\xB9\xCC\xC5\xA9\xB7\xD0", "value": "Omicron" },
	{ "key": b"\xB4\xD9\xC5\xA9\x20\xBD\xBA\xC6\xE5\xC5\xCD", "value": "Dark Specter" },
	{ "key": b"\xB4\xCF\xC4\xCb", "value": "Niken" },
	{ "key": b"\xB9\xCC\xB9\xCD", "value": "Mimic" },
	{ "key": b"\xC5\xB7\x20\xB9\xEE", "value": "King Bat" },
	{ "key": b"\xB0\xED\xBA\xED\xB8\xB0\xBB\xFE\xB8\xD5", "value": "Goblin Shaman" },
	{ "key": b"\xC7\xEC\xBD\xBA\xC6\xAE", "value": "Hest" },
	{ "key": b"\xC6\xC4\xC0\xCC\xC5\xCD\xC0\xC7\x20\xBF\xF8\xC8\xA5", "value": "Fighter's Vengeful Spirit" },
	{ "key": b"\xC6\xC4\xC0\xCC\xC5\xA9\xB8\xC7\xC0\xC7\x20\xBF\xF8\xC8\xA5", "value": "Pikeman's Vengeful Spirit" },
	{ "key": b"\xBE\xC6\xC3\xB3\xC0\xC7\x20\xBF\xF8\xC8\xA5", "value": "Archer's Vengeful Spirit" },
	{ "key": b"\xB8\xDE\xC4\xAB\xB4\xCF\xBC\xC7\xC0\xC7\x20\xBF\xF8\xC8\xA5", "value": "Mechanism's Vengeful Spirit" },
	{ "key": b"\xBE\xF0\xB5\xA5\xB5\xE5\x20\xC8\xA3\xC7\xC7", "value": "Undead Hopy" },
	{ "key": b"\xC8\xA3\xBA\xB8\xB0\xED\xB7\xBD", "value": "Hobogorem" },
	{ "key": b"\xB3\xAA\xC0\xCC\xC6\xAE\xC0\xC7\x20\xBF\xF8\xC8\xA5", "value": "Knight's Vengeful Spirit" },
	{ "key": b"\xC7\xC1\xB8\xAE\xBD\xBA\xC6\xBC\xBD\xBA\xC0\xC7\x20\xBF\xF8\xC8\xA5", "value": "Princess's Vengeful Spirit" },
	{ "key": b"\xB8\xDE\xC1\xF6\xBC\xC7\xC0\xC7\x20\xBF\xF8\xC8\xA5", "value": "Magician's Vengeful Spirit" },
	{ "key": b"\xBE\xC6\xC5\xBB\xB6\xF5\xC5\xB8\xC0\xC7\x20\xBF\xF8\xC8\xA5", "value": "Atalanta's Vengeful Spirit" },
	{ "key": b"\xB0\xED\xB8\xA3\xB0\xEF", "value": "Gorgon" },
	{ "key": b"\xB7\xE7\xC4\xAb", "value": "Luca" },
	{ "key": b"\xB3\xAA\xC1\xEE\x20\xBD\xC3\xB4\xCF\xBE\xEE", "value": "Naz Senior" },
	{ "key": b"\xC0\xCC\xB0\xF1\xB6\xF3\xC6\xBC\xBF\xC2", "value": "Igolation" },
	{ "key": b"\xC4\xAB\xC4\xDA\xBE\xC6", "value": "Cacoa" },
	{ "key": b"\xBD\xBA\xC7\xC1\xB8\xB0", "value": "Sprint" },
	{ "key": b"\xBE\xF0\xB5\xA5\xB5\xE5\x20\xB8\xDE\xC0\xCC\xC7\xC3", "value": "Undead Maple" },
	{ "key": b"\xC1\xA6\xC5\xBA", "value": "Coal Fire" },
	{ "key": b"\xB7\xA1\xBA\xF1", "value": "Ravi" },
	{ "key": b"\xC5\xE4\xBA\xF1", "value": "Toby" },
	{ "key": b"\xB8\xD3\xBD\xAC", "value": "Mush" },
	{ "key": b"\xC1\xA9\xB5\xF0", "value": "Zeldie" },
	{ "key": b"\xB3\xEB\xBE\xB2\xB0\xED\xBA\xED\xB8\xB0", "value": "North Goblin" },
	{ "key": b"\xC8\xA3\xC7\xC7", "value": "Hopy" },
	{ "key": b"\xC5\xA5\xC7\xC7", "value": "Cupy" },
	{ "key": b"\xBE\xC6\xB8\xA3\xB8\xB6", "value": "Arma" },
	{ "key": b"\xB9\xF6\xBC\xB8\xB1\xCD\xBD\xC5", "value": "Mushroom Ghost" },
	{ "key": b"\xC8\xA9\xB0\xED\xBA\xED\xB8\xB0", "value": "Hobgoblin" },
	{ "key": b"\xC8\xA3\xC7\xC7\x20\xC5\xB0\xB5\xE5", "value": "Hopy Kid" },
	{ "key": b"\xB9\xCC\xB4\xCF\xB1\xD7", "value": "Minig" },
	{ "key": b"\xC0\xD3\xC7\xC1", "value": "Imp" },
	{ "key": b"\xB0\xED\xBD\xBA\xC6\xAE", "value": "Ghost" },
	{ "key": b"\xC7\xE5\xC6\xC3\x20\xC7\xC3\xB7\xA3\xC6\xAE", "value": "Hunting Plant" },
	{ "key": b"\xB5\xB5\xB6\xF6", "value": "Doral" },
	{ "key": b"\xC1\xBB\xBA\xF1", "value": "Zombie" },
	{ "key": b"\xBD\xEb", "value": "Shen" },
	{ "key": b"\xC7\xE5\xC6\xC3\x20\xB8\xDE\xC0\xCC\xC7\xC3", "value": "Hunting Maple" },
	{ "key": b"\xC0\xCC\xB0\xA3", "value": "Lee Gan" },
	{ "key": b"\xB9\xC2\xC5\xCF\xC6\xAE\x20\xC6\xAE\xB8\xAE", "value": "Mutant Tree" },
	{ "key": b"\xBA\xAF\xC0\xCC\xBD\xC4\xB9\xB0", "value": "Mutant Plant" },
	{ "key": b"\xB9\xC2\xC5\xCF\xC6\xAE\x20\xB7\xA1\xBA\xF1", "value": "Mutant Rabbit" },
	{ "key": b"\xC4\xBF\xB7\xB4\xC6\xAE", "value": "Cut" },
	{ "key": b"\xB5\xA5\xB9\xFA\xB8\xAE\xBD\xAC\x20\xC6\xAE\xB8\xAE", "value": "Devilish Tree" },
	{ "key": b"\xBA\xF1\xB5\xB6", "value": "Beedog" },
	{ "key": b"\xBD\xBA\xC6\xC4\xC0\xCC\xB4\xF5\x20\xC6\xAE\xB7\xE7\xC6\xDb", "value": "Spider Trooper" },
	{ "key": b"\xB8\xAE\xC0\xDA\xB5\xE5\xC6\xF7\xC5\xA9", "value": "Lizard Fork" },
	{ "key": b"\xBD\xBA\xC6\xC3\xB7\xB9\xC0\xCC", "value": "Stingray" },
	{ "key": b"\xB8\xD3\xB9\xCC\xB7\xCE\xB5\xE5", "value": "Mummy Road" },
	{ "key": b"\xBF\xC0\xB9\xC7", "value": "Orb" },
	{ "key": b"\xB1\xD7\xB7\xB9\xC0\xCC\xC6\xAE\x20\xB1\xD7\xB8\xAE\xBA\xEC", "value": "Great Griven" },
	{ "key": b"\xBD\xBA\xC6\xAE\xB6\xF3\xC0\xCC\xB4\xF5", "value": "Strider" },
	{ "key": b"\xB1\xBC\xB0\xA1\xB8\xA3", "value": "Gulgar" },
	{ "key": b"\xC7\xC1\xB7\xCE\xC1\xF0\x20\xB9\xCC\xBD\xBA\xC6\xAE", "value": "Frozen Mist" },
	{ "key": b"\xC4\xDD\xB5\xE5\xBE\xC6\xC0\xCC", "value": "Cold Eye" },
	{ "key": b"\xBE\xC6\xBA\xA7\xB8\xB0", "value": "Abeline" },
	{ "key": b"\xC3\xBC\xC0\xCE\x20\xB0\xED\xB7\xBD", "value": "Chain Golem" },
	{ "key": b"\xB5\xA5\xB5\xE5\xC1\xB8", "value": "Dead Zone" },
	{ "key": b"\xB1\xD7\xB7\xCE\xC5\xD7\xBD\xBA\xC5\xA9", "value": "Grotesque" },
	{ "key": b"\xC7\xCF\xC0\xCC\xC6\xDB\x20\xB8\xD3\xBD\xC5", "value": "Hyper Machine" },
	{ "key": b"\xB9\xEC\xC7\xC7\xB8\xAF\x20\xB8\xD3\xBD\xC5", "value": "Vampiric Machine" },
	{ "key": b"\xB7\xA5\xC6\xE4\xC0\xCC\xC1\xF6", "value": "Rampage" },
	{ "key": b"\xBE\xC6\xC0\xCC\xBE\xF0\x20\xB0\xA1\xB5\xE5", "value": "Iron Guard" },
	{ "key": b"\xB7\xE7\xB4\xD0\x20\xB0\xA1\xB5\xF0\xBE\xC8", "value": "Runik Guardian" },
	{ "key": b"\xBE\xC6\xBA\xA7\xB8\xB0\x20\xC4\xFD", "value": "Abeline Quinn" },
	{ "key": b"\xB8\xB6\xBF\xEE\xC6\xBE", "value": "Mountain" },
	{ "key": b"\xBB\xF5\xB5\xE5\xB4\xCF\xBD\xBA", "value": "Sadness" },
	{ "key": b"\xBE\xC6\xC0\xCC\xBE\xF0\x20\xC7\xC7\xBD\xBA\xC6\xAE", "value": "Iron Fist" },
	{ "key": b"\xB8\xF0\xB8\xA3\xB0\xEF", "value": "Morgon" },
	{ "key": b"\xB5\xF0\x2D\xB8\xD3\xBD\xC5", "value": "D-Machine" },
	{ "key": b"\xB8\xDE\xC6\xAE\xB7\xD0", "value": "Metron" },
	{ "key": b"\xBA\xED\xB7\xAF\xB5\xF0\x20\xB3\xAA\xC0\xCC\xC6\xAE", "value": "Bloody Night" },
	{ "key": b"\xC5\xDB\xC7\xC3\xB0\xA1\xB5\xE5", "value": "Temple Guard" },
	{ "key": b"\xC5\xB7\x20\xBD\xBA\xC6\xC4\xC0\xCC\xB4\xF5", "value": "King Spider" },
	{ "key": b"\xBC\xBC\xC5\xE4", "value": "Seto" },
	{ "key": b"\xC5\xB0\xB8\xDE\xB6\xF3", "value": "Chimera" },
	{ "key": b"\xB4\xD9\xC5\xA9\x20\xB0\xA1\xB5\xE5", "value": "Dark Guard" },
	{ "key": b"\xB4\xD9\xC5\xA9\x20\xC6\xC8\xB6\xFB\xC5\xA9\xBD\xBA", "value": "Dark Phalanx" },
	{ "key": b"\xB4\xD9\xC5\xA9\x20\xB8\xDE\xC0\xCC\xC1\xF6", "value": "Dark Mage" },
	{ "key": b"\xC6\xC4\xC0\xCC\xBE\xEE\x20\xBF\xFA", "value": "Fire Worm" },
	{ "key": b"\xC7\xEF\x20\xC7\xCF\xBF\xEE\xB5\xE5", "value": "Hellhound" },
	{ "key": b"\xB4\xD9\xC0\xCC\xBE\xEE\x20\xBA\xF1", "value": "Diabee" },
	{ "key": b"\xB8\xD3\xB5\xF0\x20\xB0\xED\xB7\xBD", "value": "Muddy Golem" },
	{ "key": b"\xBC\xD6\xB8\xAE\xB5\xE5\x20\xBD\xBA\xB3\xD7\xC0\xCF", "value": "Solid Snail" },
	{ "key": b"\xC0\xCC\xBA\xED\x20\xC7\xC3\xB7\xA3\xC6\xAE", "value": "Evil Plant" },
	{ "key": b"\xBA\xF1\xBA\xED", "value": "Bible" },
	{ "key": b"\xB8\xAE\xC4\xA1", "value": "Rich" },
	{ "key": b"\xBD\xBA\xC4\xDD\xC7\xC7\xBF\xC2", "value": "Scorpion" },
	{ "key": b"\xB5\xF0\xC4\xDA\xC0\xCC", "value": "Decoy" },
	{ "key": b"\xC4\xDA\xC5\xA9\xB8\xAE\xBD\xBA", "value": "Cokris" },
	{ "key": b"\xC1\xF8\xB3\xAA\xB9\xAB\xB1\xAB\xB9\xB0", "value": "Jinnamu Monster" },
	{ "key": b"\xB8\xDE\xC7\xCD", "value": "Mefit" },
	{ "key": b"\xBD\xBA\xC4\xCC\xB7\xB9\xC5\xE6", "value": "Skeleton" },
	{ "key": b"\xC0\xCC\xBA\xED\x20\xBD\xBA\xB3\xD7\xC0\xCF", "value": "Evil Snail" },
	{ "key": b"\xB8\xD3\xC7\xC9", "value": "Muffin" },
	{ "key": b"\xB9\xEC\xC7\xC7\xB8\xAF\x20\xB9\xEE", "value": "Vampiric Bat" },
	{ "key": b"\xB9\xCC\xB4\xCF\xB1\xD7\x20\xBD\xC7\xB9\xF6", "value": "Minig Silver" },
	# BOSSES
	{ "key": b"\xB9\xDF\xB7\xBB\xC5\xE4", "value": "Valento" },
	{ "key": b"\xC4\xCC\xBA\xA3\xC1\xEA", "value": "Kelbeju" },
	{ "key": b"\xC4\xCC\xBA\xA3\xC1\xEA\x31", "value": "Kelbeju 1" },
	{ "key": b"\xBE\xEE\xC6\xC4\xBD\xBA\xC5\xCD\xBD\xC3", "value": "Apastasy" },
	{ "key": b"\xC7\xC1\xB6\xF3\xC0\xCC\xC6\xAE\x20\xB3\xD7\xB9\xC3", "value": "Fright Nemune" },
	{ "key": b"\xBF\xA4\x20\xB6\xF3\xBD\xC3\x20\xC4\xEF", "value": "El Rashi Kun" },
	{ "key": b"\xBA\xA3\xB0\xA1\x20\xB5\xE5\xB9\xCC\xB8\xA3", "value": "Vega Demir" },
	{ "key": b"\xBD\xBD\xB7\xB9\xC0\xCC\xBF\xC2", "value": "Slayon" },
	{ "key": b"\xC7\xEF\xBD\xCC", "value": "Hellsing" },
	{ "key": b"\xBA\xA3\xB8\xA3\xB9\xAE\x20\xBE\xC7\xC5\xB8\xB7\xE9", "value": "Vermun Aktarun" },
	{ "key": b"\xBA\xA3\xB0\xA1\x20\xB5\xE5\xB9\xCC\xC6\xAE\xB8\xAE", "value": "Vega Dmitry" },
	{ "key": b"\xBE\xF0\xC8\xA6\xB8\xAE\x20\xB3\xAA\xC0\xCC\xC6\xAE", "value": "Unholy Night" },
	{ "key": b"\xBA\xED\xB7\xAF\xB5\xF0\x20\xB7\xCE\xC1\xEE", "value": "Bloody Rose" },
	{ "key": b"\xBD\xBA\xC6\xBD\xBD\xBA\x20\xBE\xC6\xB8\xA3\xC4\xAD", "value": "Styx Arkan" },
	{ "key": b"\xB6\xF3\xBB\xFE\x27\xBD\xBA", "value": "Lasha's" },
	{ "key": b"\xBF\xC0\xB8\xDE\xB0\xA1", "value": "Omega" },
	{ "key": b"\xC7\xBB\xB8\xAE", "value": "Fury" },
	{ "key": b"\xC2\xAF\xC7\xC7", "value": "Jjangpi" },
	{ "key": b"\xC0\xCC\xB5\xE5", "value": "Id" },
	{ "key": b"\xC7\xC3\xB7\xA1\xC6\xBE\x20\xB8\xB6\xBA\xEA", "value": "Platin Marv" },
	{ "key": b"\xB9\xD9\xBA\xA7", "value": "Babel" },
	{ "key": b"\xB8\xF0\xC4\xDA\xB9\xD9", "value": "Mokoba" },
	{ "key": b"\xB1\xE6\xC6\xBC\x20\xB0\xED\xB5\xE7", "value": "Guilty Gordon" },
	{ "key": b"\xB1\xD7\xB7\xB9\xC0\xCC\xBA\xEA\x20\xBB\xFE\xC5\xB2\xBD\xBA", "value": "Grave Sharkins" },
	{ "key": b"\xB9\xD9\xBF\xEC\xC5\xE6", "value": "Boughton" },
	{ "key": b"\xBD\xCE\xC0\xCC\xC5\xAC\xB7\xD0", "value": "Cyclone" },
	{ "key": b"\xB8\xDE\xC5\xB0\xBD\xBA\xC6\xAE", "value": "Mekist" },
	# EVENT
	{ "key": b"\xB9\xCC\xB4\xCF\xBB\xEA\xC5\xB8\xB0\xED\xBA\xED\xB8\xB0", "value": "Mini Santa Goblin" },
	{ "key": b"\xBB\xEA\xC5\xB8\xB0\xED\xBA\xED\xB8\xB0", "value": "Santa Goblin" },
	{ "key": b"\xBA\xF2\xBB\xEA\xC5\xB8\xB0\xED\xBA\xED\xB8\xB0", "value": "Big Santa Goblin" },
	{ "key": b"\xB0\xC5\xB4\xEB\xC7\xD1\x21\xBB\xEA\xC5\xB8\xB0\xED\xBA\xED\xB8\xB0", "value": "Giant! Santa Goblin" }
]
