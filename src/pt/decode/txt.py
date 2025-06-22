from pt.pdef import *
from pt.utils import decode_string
from pt.const import (
	CONFIG_PATTERN,
	TXT
)


def decode(path: str) -> PTServerItem:
	""" Decode a TXT file which consists of item definition data. """

	item = PTServerItem()

	with open(path, "rb") as f:
		for line in f.readlines():
			# Lines not beginning with * are skipped
			if line[0:1] != b"*":
				continue

			matches = CONFIG_PATTERN.findall(line)
			segments = [m.strip(b'"') for m in matches]
			key = segments.pop(0)

			match key:



				case TXT.NameEnglish:
					pass
				case TXT.ItemName:
					pass
				case TXT.Code:
					pass
				case TXT.Integrity:
					pass
				case TXT.Weight:
					pass
				case TXT.Price:
					pass
				case TXT.sResistance_sITEMINFO_BIONIC:
					pass
				case TXT.sResistance_sITEMINFO_FIRE:
					pass
				case TXT.sResistance_sITEMINFO_ICE:
					pass
				case TXT.sResistance_sITEMINFO_LIGHTING:
					pass
				case TXT.sResistance_sITEMINFO_POISON:
					pass
				case TXT.sDamage:
					pass
				case TXT.sAttack_Rating:
					pass
				case TXT.sDefence:
					pass
				case TXT.fAbsorb:
					pass
				case TXT.fBlock_Rating:
					pass
				case TXT.Attack_Speed:
					pass
				case TXT.Critical_Hit:
					pass
				case TXT.Shooting_Range:
					pass
				case TXT.Potion_Space:
					pass
				case TXT.fLife_Regen:
					pass
				case TXT.fLife_Regen2:
					pass
				case TXT.fMana_Regen:
					pass
				case TXT.fMana_Regen2:
					pass
				case TXT.fStamina_Regen:
					pass
				case TXT.fStamina_Regen2:
					pass
				case TXT.Increase_Life:
					pass
				case TXT.Increase_Life2:
					pass
				case TXT.Increase_Mana:
					pass
				case TXT.Increase_Mana2:
					pass
				case TXT.Increase_Stamina:
					pass
				case TXT.Increase_Stamina2:
					pass
				case TXT.Level:
					pass
				case TXT.Strength:
					pass
				case TXT.Spirit:
					pass
				case TXT.Talent:
					pass
				case TXT.Agility_Dexterity:
					pass
				case TXT.Health:
					pass
				case TXT.DispEffect:
					pass
				case TXT.sResistance_sITEMINFO_EARTH:
					pass
				case TXT.sResistance_sITEMINFO_WATER:
					pass
				case TXT.sResistance_sITEMINFO_WIND:
					pass
				case TXT.TransfereSpeed:
					pass
				case TXT.UniqueItem:
					pass
				case TXT.dwJobBitCode_Random:
					pass
				case TXT.JobCodeMask:
					pass
				case TXT.fSpecial_Absorb:
					pass
				case TXT.sSpecial_Defence:
					pass
				case TXT.JobItem_Per_Life_Regen:
					pass
				case TXT.JobItem_Per_Life_Regen2:
					pass
				case TXT.fSpecial_Mana_Regen:
					pass
				case TXT.fSpecial_Mana_Regen2:
					pass
				case TXT.JobItem_Per_Stamina_Regen:
					pass
				case TXT.JobItem_Per_Stamina_Regen2:
					pass
				case TXT.fSpecial_fSpeed:
					pass
				case TXT.JobItem_Add_Attack_Speed:
					pass
				case TXT.JobItem_Add_fBlock_Rating:
					pass
				case TXT.Lev_Attack_Rating:
					pass
				case TXT.JobItem_Lev_Damage:
					pass
				case TXT.JobItem_Add_Critical_Hit:
					pass
				case TXT.fSpecial_Magic_Mastery:
					pass
				case TXT.JobItem_Add_Shooting_Range:
					pass
				case TXT.JobItem_Lev_Mana:
					pass
				case TXT.JobItem_Lev_Mana2:
					pass
				case TXT.JobItem_Lev_Life:
					pass
				case TXT.JobItem_Lev_Life2:
					pass
				case TXT.fMagic_Mastery:
					pass
				case TXT.Stamina:
					pass
				case TXT.Stamina2:
					pass
				case TXT.Mana:
					pass
				case TXT.Mana2:
					pass
				case TXT.Life:
					pass
				case TXT.Life2:
					pass
				case TXT.EffectColor:
					pass
				case TXT.sGenDay:
					pass
				case TXT.szNextFile:
					pass





				case _:
					print(f"Unknown key: {key}")

	return item
