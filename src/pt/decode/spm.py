from pt.pdef import *
from pt.utils import atoi, decode_string
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
					config.max_monsters = atoi(segments[0])
				case SPM.SPAWN_INTERVAL:
					# *출현간격 [n] [ms]: the engine evaluates OpenInterval = (1 << n)
					# with the special case (1 << n) > 1 -> (1 << n) - 1, i.e.
					# (1 << n) - 1 for n >= 1 but 1 for n = 0 (fileread.cpp:5474-5476);
					# the runtime gates spawning on (Counter & OpenInterval) == 0
					# (OnSever.cpp:7422). The optional second value is a plain wait
					# time in ms, dwIntervalTime = atoi * 1000 (fileread.cpp:5478-5480)
					interval = 1 << atoi(segments[0])
					config.spawn_interval = interval - 1 if interval > 1 else interval

					if len(segments) > 1:
						config.spawn_interval_time = atoi(segments[1]) * 1000
				case SPM.MAX_MONSTERS_PER_POINT:
					config.max_monsters_per_point = atoi(segments[0])
				# *출연자: monster name + spawn rate; the engine matches the name
				# against the INF-loaded smCHAR_INFO list with lstrcmp
				# (fileread.cpp:5406-5424)
				case SPM.MONSTER_SPAWN:
					for monster in MONSTER_NAMES:
						if segments[0] == monster["key"]:
							config.monsters.append(PTServerStageMonster(
								name = decode_string(segments[0]),
								name_en = monster["value"],
								spawn_rate = atoi(segments[1])
							))
							break
				# *출연자두목: boss, minion, minion count, then up to 32 spawn
				# hours into sBOSS_MONSTER.bOpenTime (fileread.cpp:5427-5451)
				case SPM.BOSS_SPAWN:
					# the engine appends the boss record unconditionally: a name
					# that does not resolve against the INF character list leaves
					# the Master/Slave pointer null but BossMonsterCount++ still
					# runs (fileread.cpp:5427-5451), so unmatched names fall back
					# to the raw token instead of dropping the record
					name = decode_string(segments[0])
					name_en = None
					minion = decode_string(segments[1])
					minion_en = None
					for monster in MONSTER_NAMES:
						if segments[1] == monster["key"]:
							minion_en = monster["value"]
							break

					for monster in MONSTER_NAMES:
						if segments[0] == monster["key"]:
							name_en = monster["value"]
							break
					config.bosses.append(PTServerStageBoss(
						name = name,
						name_en = name_en,
						minion = minion,
						minion_en = minion_en,
						num_minions = atoi(segments[2]),
						hours = sorted([atoi(item) % 24 for item in segments[3:]])
					))
				case _:
					print(f"Unknown key: {key}")

	return config
