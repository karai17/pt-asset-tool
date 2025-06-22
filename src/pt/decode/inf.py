from pt.pdef import *
from pt.utils import decode_string
from pt.const import (
	CONFIG_PATTERN,
	INF
)


def decode(path: str) -> PTServerMonster:
	""" Decode an INF file which consists of monster definition data. """

	monster = PTServerMonster()

	with open(path, "rb") as f:
		for line in f.readlines():
			# Lines not beginning with * are skipped
			if line[0:1] != b"*":
				continue

			matches = CONFIG_PATTERN.findall(line)
			segments = [m.strip(b'"') for m in matches]
			key = segments.pop(0)

			match key:




				case INF.wPlayClass:
					pass
				case INF.Size:
					pass
				case INF.szName:
					pass
				case INF.Level:
					pass
				case INF.wPlayClass2:
					pass
				case INF.ClassCode:
					pass
				case INF.GenerateGroup:
					pass
				case INF.IQ:
					pass
				case INF.Nature:
					pass
				case INF.Real_Sight:
					pass
				case INF.Life:
					pass
				case INF.Life2:
					pass
				case INF.Attack_Damage:
					pass
				case INF.SkillDamage:
					pass
				case INF.SkillRating:
					pass
				case INF.SkillDistance:
					pass
				case INF.SkillRange:
					pass
				case INF.SkillCurse:
					pass
				case INF.Absorption:
					pass
				case INF.Chance_Block:
					pass
				case INF.Defence:
					pass
				case INF.Attack_Speed:
					pass
				case INF.Attack_Rating:
					pass
				case INF.SpAttackPercetage:
					pass
				case INF.Shooting_Range:
					pass
				case INF.Resistance_sITEMINFO_BIONIC:
					pass
				case INF.Resistance_sITEMINFO_LIGHTING:
					pass
				case INF.Resistance_sITEMINFO_ICE:
					pass
				case INF.Resistance_sITEMINFO_FIRE:
					pass
				case INF.Resistance_sITEMINFO_POISON:
					pass
				case INF.Resistance_sITEMINFO_WATER:
					pass
				case INF.Resistance_sITEMINFO_WIND:
					pass
				case INF.Resistance_sITEMINFO_EARTH:
					pass
				case INF.Type:
					pass
				case INF.IsUndead:
					pass
				case INF.MoveRange:
					pass
				case INF.MoveType:
					pass
				case INF.SoundEffect:
					pass
				case INF.SoundEffect2:
					pass
				case INF.Exp:
					pass
				case INF.FallItemMax:
					pass
				case INF.FallItems:
					pass
				case INF.FallItems_Plus:
					pass
				case INF.AllSeeItem:
					pass
				case INF._DropGold:
					pass
				case INF._DropEmpty:
					pass
				case INF.State:
					pass
				case INF.szModelName:
					pass
				case INF.Name:
					pass
				case INF.ActiveHour:
					pass
				case INF.ArrowPosi:
					pass
				case INF.SizeLevel:
					pass
				case INF.PotionCount:
					pass
				case INF.PotionPercent:
					pass
				case INF.EventCode:
					pass
				case INF.EventInfo:
					pass
				case INF.dwEvnetItem:
					pass
				case INF.szModelName2:
					pass
				case INF.ExtraGold:
					pass
				case INF.DamageStunPers:
					pass
				case INF.DamageStunPers2:
					pass
				case INF.Move_Speed:
					pass
				case INF.lpDialogMessage:
					pass
				case INF.szNextFile:
					pass

				case INF.Small:
					pass
				case INF.Medium:
					pass
				case INF.Big:
					pass
				case INF.Bigger:
					pass
				case INF.No:
					pass

				case INF.good:
					pass
				case INF.evil:
					pass

				case INF.No:
					pass
				case INF.Day:
					pass
				case INF.Night:
					pass

				case INF.State_True:
					pass
				case INF.State_False:
					pass

				case INF.Normal:
					pass
				case INF.Daemon:
					pass
				case INF.Undead:
					pass
				case INF.Mutant:
					pass
				case INF.Mechanic:
					pass
				case INF.Iron:
					pass

				case INF.Normal:
					pass
				case INF.Undead:
					pass
				case INF.Undead2:
					pass




				case _:
					print(f"Unknown key: {key}")

	return monster
