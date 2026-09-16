from pt.pdef import *
from pt.utils import decode_string
from pt.const import (
	CONFIG_PATTERN,
	MONSTER_NAMES,
	SPM
)


def decode(path: str) -> PTServerSpawnMonster:
	"""
	Decode an SPM file which consists of monster spawn data for a stage.

	Engine counterpart: fileread.cpp:5382 DecodeOpenMonster, which fills an
	rsSTG_MONSTER_LIST (fileread.h:26-60) from the same keys. The file is
	CP949 text; only *-prefixed lines are commands (comment lines start with
	// and are skipped by the != b"*" test).
	"""
	config = PTServerSpawnMonster()

	with open(path, "rb") as f:
		for line in f.readlines():
			# Lines not beginning with * are skipped
			if line[0:1] != b"*":
				continue

			matches = CONFIG_PATTERN.findall(line)
			segments = [m.strip(b'"') for m in matches]
			key = segments.pop(0)

			match key:
				case SPM.MAX_MONSTERS:
					config.max_monsters = int(segments[0])
				case SPM.SPAWN_INTERVAL:
					# *출현간격: engine stores (1 << n) - 1 as a spawn-interval
					# backoff; the raw n and optional ms value are kept here
					# (fileread.cpp:5465-5474)
					config.spawn_interval_min = int(segments[0])

					# use same value for min and max if max not present
					if len(segments) > 1:
						config.spawn_interval_max = int(segments[1])
					else:
						config.spawn_interval_max = int(segments[0])
				case SPM.MAX_MONSTERS_PER_POINT:
					config.max_monsters_per_point = int(segments[0])
				# *출연자: monster name + spawn rate; the engine matches the name
				# against the INF-loaded smCHAR_INFO list with lstrcmp
				# (fileread.cpp:5406-5424)
				case SPM.MONSTER_SPAWN:
					for monster in MONSTER_NAMES:
						if segments[0] == monster["key"]:
							config.monsters.append(PTServerStageMonster(
								name = decode_string(segments[0]),
								name_en = monster["value"],
								spawn_rate = int(segments[1])
							))
							break
				# *출연자두목: boss, minion, minion count, then up to 32 spawn
				# hours into sBOSS_MONSTER.bOpenTime (fileread.cpp:5427-5451)
				case SPM.BOSS_SPAWN:
					for monster in MONSTER_NAMES:
						if segments[1] == monster["key"]:
							minion = decode_string(segments[1])
							minion_en = monster["value"]
							break

					for monster in MONSTER_NAMES:
						if segments[0] == monster["key"]:
							config.bosses.append(PTServerStageBoss(
								name = decode_string(segments[0]),
								name_en = monster["value"],
								minion = minion,
								minion_en = minion_en,
								num_minions = int(segments[2]),
								hours = sorted([int(item) % 24 for item in segments[3:]])
							))
							break
				case _:
					print(f"Unknown key: {key}")

	return config
