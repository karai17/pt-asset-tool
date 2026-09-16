from pt.pdef import *
from pt.utils import decode_string, split_config_tokens
from pt.const import (
	TXT
)


def parse_ints(segments: list[bytes]) -> list[int]:
	"""Empty value lists are legal; atoi/atof on the empty token = 0."""
	return [int(v) for v in segments]


def parse_floats(segments: list[bytes]) -> list[float]:
	return [float(v) for v in segments]


def decode(path: str) -> PTServerItem:
	"""
	Decode a TXT file which consists of item definition data.

	Engine counterpart: fileread.cpp:3328 DecodeItemInfo, which fills an
	sDEF_ITEMINFO / sITEMINFO from the same keys. The file is CP949 text; only
	*-prefixed lines are commands (comment lines start with // and are skipped
	by the != b"*" test). Most keys carry [min] [max] value pairs and empty
	values are legal ( atoi/atof on the empty token = 0). *연결파일 chains into
	a zhoon name file; the raw path is kept.
	"""
	item = PTServerItem()

	with open(path, "rb") as f:
		for line in f.readlines():
			# Lines not beginning with * are skipped
			if line[0:1] != b"*":
				continue

			segments = split_config_tokens(line)
			key = segments.pop(0)

			match key:
				case TXT.ItemName:
					item.name = decode_string(segments[0])
				case TXT.NameEnglish | TXT.NameUpper | TXT.C_Name | TXT.J_Name | TXT.T_Name | TXT.E_Name | TXT.TH_Name | TXT.V_Name | TXT.B_Name | TXT.A_Name:
					# romanized name keys; the active table entry wins
					item.name_en = decode_string(segments[0])
				case TXT.Code:
					item.code = decode_string(segments[0])
				case TXT.Integrity:
					item.durability = parse_ints(segments[:2])
				case TXT.Weight:
					item.weight = int(segments[0]) if segments else 0
				case TXT.Price:
					item.price = int(segments[0]) if segments else 0
				case TXT.sResistance_sITEMINFO_BIONIC:
					item.resistances["bionic"] = [int(v) for v in segments[:2]]
				case TXT.sResistance_sITEMINFO_EARTH:
					item.resistances["earth"] = [int(v) for v in segments[:2]]
				case TXT.sResistance_sITEMINFO_FIRE:
					item.resistances["fire"] = [int(v) for v in segments[:2]]
				case TXT.sResistance_sITEMINFO_ICE:
					item.resistances["ice"] = [int(v) for v in segments[:2]]
				case TXT.sResistance_sITEMINFO_LIGHTING:
					item.resistances["lighting"] = [int(v) for v in segments[:2]]
				case TXT.sResistance_sITEMINFO_POISON:
					item.resistances["poison"] = [int(v) for v in segments[:2]]
				case TXT.sResistance_sITEMINFO_WATER:
					item.resistances["water"] = [int(v) for v in segments[:2]]
				case TXT.sResistance_sITEMINFO_WIND:
					item.resistances["wind"] = [int(v) for v in segments[:2]]
				case TXT.sDamage:
					# base min/max then bonus min/max (fileread.cpp:3567-3578)
					item.damage = parse_ints(segments[:4])
				case TXT.Shooting_Range:
					item.shooting_range = int(segments[0]) if segments else 0
				case TXT.Attack_Speed:
					item.attack_speed = int(segments[0]) if segments else 0
				case TXT.sAttack_Rating:
					item.attack_rating = parse_ints(segments[:2])
				case TXT.Critical_Hit:
					item.critical_hit = int(segments[0]) if segments else 0
				case TXT.fAbsorb:
					item.absorb = parse_floats(segments[:2])
				case TXT.sDefence:
					item.defence = parse_ints(segments[:2])
				case TXT.fBlock_Rating:
					item.block_rating = parse_floats(segments[:2])
				case TXT.TransfereSpeed:
					item.speed = parse_floats(segments[:2])
				case TXT.Potion_Space:
					item.potion_space = int(segments[0]) if segments else 0
				case TXT.fMagic_Mastery | TXT.fMagic_Mastery2 | TXT.fMagic_Mastery3:
					item.magic_mastery = float(segments[0]) if segments else 0
				case TXT.fMana_Regen | TXT.fMana_Regen2:
					# either key overwrites the same sDEF_ITEMINFO slot
					item.mana_regen = parse_floats(segments[:2])
				case TXT.fLife_Regen | TXT.fLife_Regen2:
					item.life_regen = parse_floats(segments[:2])
				case TXT.fStamina_Regen | TXT.fStamina_Regen2:
					item.stamina_regen = parse_floats(segments[:2])
				case TXT.Increase_Mana | TXT.Increase_Mana2:
					item.increase_mana = parse_ints(segments[:2])
				case TXT.Increase_Life | TXT.Increase_Life2:
					item.increase_life = parse_ints(segments[:2])
				case TXT.Increase_Stamina | TXT.Increase_Stamina2:
					item.increase_stamina = parse_ints(segments[:2])
				case TXT.Level:
					item.level = int(segments[0]) if segments else 0
				case TXT.Strength:
					item.strength = int(segments[0]) if segments else 0
				case TXT.Spirit:
					item.spirit = int(segments[0]) if segments else 0
				case TXT.Talent:
					item.talent = int(segments[0]) if segments else 0
				case TXT.Agility_Dexterity:
					item.dexterity = int(segments[0]) if segments else 0
				case TXT.Health:
					item.health = int(segments[0]) if segments else 0
				case TXT.Stamina | TXT.Stamina2:
					item.stamina = parse_ints(segments[:2])
				case TXT.Mana | TXT.Mana2:
					item.mana = parse_ints(segments[:2])
				case TXT.Life | TXT.Life2:
					item.life = parse_ints(segments[:2])
				case TXT.UniqueItem:
					# bare key = TRUE, otherwise atoi (fileread.cpp:3441-3448)
					item.unique = True if not segments or not segments[0] else bool(int(segments[0]))
				case TXT.EffectColor:
					# R G B A [blink] (fileread.cpp:3452-3469)
					item.effect_color = parse_ints(segments[:5])
				case TXT.DispEffect:
					item.disp_effect = int(segments[0]) if segments else 0
				case TXT.JobCodeMask:
					item.job_code_mask = decode_string(segments[0]) if segments else None
				case TXT.dwJobBitCode_Random:
					item.job_code_random = [decode_string(v) for v in segments if v]
				case TXT.fSpecial_Absorb:
					item.special_absorb = parse_floats(segments[:2])
				case TXT.sSpecial_Defence:
					item.special_defence = parse_ints(segments[:2])
				case TXT.fSpecial_fSpeed:
					item.special_speed = parse_floats(segments[:2])
				case TXT.fSpecial_Magic_Mastery:
					item.special_magic_mastery = parse_floats(segments[:2])
				case TXT.fSpecial_Mana_Regen | TXT.fSpecial_Mana_Regen2:
					item.special_mana_regen = parse_floats(segments[:2])
				case TXT.JobItem_Per_Life_Regen | TXT.JobItem_Per_Life_Regen2:
					item.per_life_regen = float(segments[0]) if segments else 0
				case TXT.JobItem_Per_Stamina_Regen | TXT.JobItem_Per_Stamina_Regen2:
					item.per_stamina_regen = float(segments[0]) if segments else 0
				case TXT.JobItem_Add_fBlock_Rating:
					item.job_add_block_rating = float(segments[0]) if segments else 0
				case TXT.JobItem_Add_Attack_Speed:
					item.job_add_attack_speed = int(segments[0]) if segments else 0
				case TXT.JobItem_Add_Critical_Hit:
					item.job_add_critical_hit = int(segments[0]) if segments else 0
				case TXT.JobItem_Add_Shooting_Range:
					item.job_add_shooting_range = int(segments[0]) if segments else 0
				case TXT.JobItem_Lev_Mana | TXT.JobItem_Lev_Mana2:
					item.job_lev_mana = int(segments[0]) if segments else 0
				case TXT.JobItem_Lev_Life | TXT.JobItem_Lev_Life2:
					item.job_lev_life = int(segments[0]) if segments else 0
				case TXT.Lev_Attack_Rating:
					item.lev_attack_rating = parse_ints(segments[:2])
				case TXT.JobItem_Lev_Damage:
					item.job_lev_damage = parse_ints(segments[:2])
				case TXT.sGenDay | TXT.sGenDay2:
					item.gen_day = int(segments[0]) if segments else 0
				case TXT.szNextFile:
					item.next_file = decode_string(segments[0])
				case _:
					print(f"Unknown key: {key}")

	return item
