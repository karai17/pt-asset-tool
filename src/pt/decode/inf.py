from pt.pdef import *
from pt.utils import decode_string, split_config_tokens
from pt.const import (
	CHAR_SOUNDS_LOOKUP,
	CHAR_SIZE_NAMES,
	MONSTER_STATE_TRUE,
	MONSTER_NATURE_GOOD,
	MONSTER_NATURE_EVIL,
	MONSTER_BROODS,
	MONSTER_BROOD_UNDEAD,
	MONSTER_BROOD_YES,
	MONSTER_ACTIVE_DAY,
	MONSTER_ACTIVE_NIGHT,
	MONSTER_DROP_NONE,
	MONSTER_DROP_GOLD,
	INF,
	item_code
)


def parse_sound(name: bytes) -> str | None:
	"""Resolve a *효과음 name against dwCharSoundCode (case-insensitive
	lstrcmpi match, fileread.cpp:4631-4646). Unknown names stay None like the
	engine leaving dwCharSoundCode at 0."""
	return CHAR_SOUNDS_LOOKUP.get(decode_string(name).casefold())


def parse_size_level(value: bytes) -> int:
	"""*크기 index into szCharSizeCodeName (fileread.cpp:4603-4617); -1 when
	the value is a scale number instead (engine sets SizeLevel = -1 first)."""
	for i, name in enumerate(CHAR_SIZE_NAMES):
		if value == name:
			return i
	return -1


def parse_fall_item(segments: list[bytes]) -> PTServerFallItem:
	"""*아이템 / *추가아이템 value list: percent, then 없음 (drop nothing), or
	돈 [min] [max] (gold), or one or more item categories split evenly over the
	percentage (fileread.cpp:5060-5131)."""
	fall = PTServerFallItem(percent=int(segments[0]))
	rest = segments[1:]

	if rest and rest[0] == MONSTER_DROP_NONE:
		fall.kind = "none"
	elif rest and rest[0] == MONSTER_DROP_GOLD:
		fall.kind = "gold"
		fall.gold_min = int(rest[1]) if len(rest) > 1 else 0
		fall.gold_max = int(rest[2]) if len(rest) > 2 else fall.gold_min
	else:
		fall.kind = "item"
		fall.codes = [decode_string(code) for code in rest if item_code(decode_string(code)) is not None]

	return fall


def decode(path: str) -> PTServerMonster:
	"""
	Decode an INF file which consists of monster definition data.

	Engine counterpart: fileread.cpp:4279 smCharDecode, which fills an
	smCHAR_INFO plus an smCHAR_MONSTER_INFO from the same keys. The file is
	CP949 text; only *-prefixed lines are commands (comment lines start with
	// and are skipped by the != b"*" test). *연결파일 chains into a zhoon
	name file; the raw path is kept.
	"""
	monster = PTServerMonster()

	with open(path, "rb") as f:
		for line in f.readlines():
			# Lines not beginning with * are skipped
			if line[0:1] != b"*":
				continue

			segments = split_config_tokens(line)
			key = segments.pop(0)

			match key:
				case INF.szName:
					monster.name = decode_string(segments[0])
				case INF.Name:
					monster.name_en = decode_string(segments[0])
				case INF.szModelName:
					monster.model = decode_string(segments[0])
				case INF.szModelName2:
					monster.model_alt = decode_string(segments[0])
					monster.event_model = True
				case INF.State:
					# *속성: 적 marks a monster record (NPC files carry NPC)
					monster.active = segments[0] == MONSTER_STATE_TRUE
				case INF.Level:
					monster.level = int(segments[0])
				case INF.wPlayClass:
					monster.is_boss = True
				case INF.wPlayClass2:
					monster.rank = int(segments[0])
				case INF.Size:
					# *모델크기: atof * fONE, 1.0 reset to 0
					monster.model_scale = float(segments[0])
				case INF.SizeLevel:
					monster.size = decode_string(segments[0])
					monster.size_level = parse_size_level(segments[0])
				case INF.SoundEffect | INF.SoundEffect2:
					monster.sound = parse_sound(segments[0])
				case INF.Move_Speed | INF.MoveSpeed:
					# *이동력 / *이동속도: ConvMoveSpeed, (speed - 9) * 16 + fONE
					monster.move_speed = float(segments[0])
				case INF.MoveType:
					# *이동타입: parsed but discarded by the engine
					monster.move_type = int(segments[0])
				case INF.MoveRange:
					# *이동범위: atof * fONE (default 64 * fONE)
					monster.move_range = float(segments[0])
				case INF.Attack_Damage:
					monster.attack_damage = [int(v) for v in segments[:2]]
				case INF.Attack_Speed:
					# atof * fONE; second value overwrites the first in the
					# engine (fileread.cpp:4696-4705)
					monster.attack_speed = float(segments[0]) if segments else 0
				case INF.Shooting_Range:
					monster.shooting_range = int(segments[0]) if segments else 0
				case INF.Attack_Rating:
					monster.attack_rating = int(segments[0]) if segments else 0
				case INF.Defence:
					monster.defence = int(segments[0]) if segments else 0
				case INF.Absorption:
					# stray "5%" unit suffixes appear in a few older files
					monster.absorption = int(segments[0].rstrip(b"%")) if segments else 0
				case INF.Chance_Block:
					# stray "6%" unit suffixes appear in a few older files
					monster.chance_block = int(segments[0].rstrip(b"%")) if segments else 0
				case INF.Life | INF.Life2:
					# single value, copied into both Life slots
					monster.life = int(segments[0])
				case INF.Resistance_sITEMINFO_BIONIC:
					monster.resistances["bionic"] = int(segments[0])
				case INF.Resistance_sITEMINFO_WATER:
					monster.resistances["water"] = int(segments[0])
				case INF.Resistance_sITEMINFO_LIGHTING:
					monster.resistances["lighting"] = int(segments[0])
				case INF.Resistance_sITEMINFO_ICE:
					monster.resistances["ice"] = int(segments[0])
				case INF.Resistance_sITEMINFO_WIND:
					monster.resistances["wind"] = int(segments[0])
				case INF.Resistance_sITEMINFO_EARTH:
					monster.resistances["earth"] = int(segments[0])
				case INF.Resistance_sITEMINFO_FIRE:
					monster.resistances["fire"] = int(segments[0])
				case INF.Resistance_sITEMINFO_POISON:
					monster.resistances["poison"] = int(float(segments[0]))
				case INF.Resistance_sITEMINFO_MAGIC:
					monster.resistances["magic"] = int(segments[0])
				case INF.Real_Sight:
					# stored as-is; the engine squares it for the radius test
					monster.sight = int(segments[0])
				case INF.ArrowPosi:
					monster.arrow_position = [int(v) for v in segments[:2]]
				case INF.SkillDamage:
					monster.skill_damage = [int(v) for v in segments[:2]]
				case INF.SkillDistance:
					monster.skill_distance = int(segments[0])
				case INF.SkillRange:
					monster.skill_range = int(segments[0])
				case INF.SkillRating:
					monster.skill_rating = int(segments[0])
				case INF.SkillCurse:
					monster.skill_curse = int(segments[0])
				case INF.ActiveHour:
					if segments[0] == MONSTER_ACTIVE_DAY:
						monster.active_hour = 1
					elif segments[0] == MONSTER_ACTIVE_NIGHT:
						monster.active_hour = -1
				case INF.GenerateGroup:
					monster.generate_group = [int(v) for v in segments[:2]]
				case INF.IQ:
					monster.iq = int(segments[0])
				case INF.ClassCode:
					monster.class_code = int(segments[0])
				case INF.DamageStunPers | INF.DamageStunPers2:
					monster.damage_stun_percent = int(segments[0])
				case INF.Nature:
					if segments[0] == MONSTER_NATURE_GOOD:
						monster.nature = "good"
					elif segments[0] == MONSTER_NATURE_EVIL:
						monster.nature = "evil"
				case INF.EventCode:
					monster.event_code = int(segments[0])
				case INF.EventInfo:
					monster.event_info = int(segments[0])
				case INF.dwEvnetItem:
					monster.event_item = decode_string(segments[0])
				case INF.SpAttackPercetage:
					# engine converts percent to 8.8 fixed (ConvPercent8)
					monster.special_attack_percent = int(segments[0])
				case INF.Type:
					monster.brood = MONSTER_BROODS.get(segments[0])
					# convenience only: the engine's Undead boolean is set solely
					# by *언데드; gameplay checks read Brood (OnSever.cpp:8432)
					monster.undead = segments[0] == MONSTER_BROOD_UNDEAD
				case INF.IsUndead:
					monster.undead = segments[0] in MONSTER_BROOD_YES
				case INF.Exp:
					monster.exp = int(segments[0])
				case INF.PotionCount:
					monster.potion_count = int(segments[0])
				case INF.PotionPercent:
					monster.potion_percent = int(segments[0])
				case INF.AllSeeItem:
					monster.all_see_item = True
				case INF.FallItemMax:
					monster.fall_item_max = int(segments[0])
				case INF.FallItems:
					monster.fall_items.append(parse_fall_item(segments))
				case INF.FallItems_Plus:
					monster.fall_items_plus.append(parse_fall_item(segments))
				case INF.ExtraGold:
					# *골드: gold min max percent (server-side only key)
					if len(segments) >= 2:
						monster.fall_items.append(PTServerFallItem(
							kind = "gold",
							percent = int(segments[2]) if len(segments) > 2 else 0,
							gold_min = int(segments[0]),
							gold_max = int(segments[1])
						))
				case INF.lpDialogMessage:
					monster.dialogue.append(decode_string(segments[0]))
				case INF.szNextFile:
					monster.next_file = decode_string(segments[0])
				case _:
					print(f"Unknown key: {key}")

	return monster
