from pt.pdef import *
from pt.utils import decode_string
from pt.const import (
	CONFIG_PATTERN,
	NPC
)


def decode(path: str) -> PTServerCharacter:
	"""
	Decode an NPC file which consists of NPC definition data.

	NPC files are parsed by the same engine line parser used for INF files:
	fileread.cpp:4279 smCharDecode (the client's .npc loader is
	playmain.cpp:1452; GetWord/GetString at fileread.cpp:81/:46 do the
	tokenizing that CONFIG_PATTERN approximates). Only *-prefixed lines are
	commands; // lines are comments.
	"""
	character = PTServerCharacter()

	with open(path, "rb") as f:
		for line in f.readlines():
			# Lines not beginning with * are skipped
			if line[0:1] != b"*":
				continue

			matches = CONFIG_PATTERN.findall(line)
			segments = [m.strip(b'"') for m in matches]
			key = segments.pop(0)

			match key:
				# *속성: NPC marks an NPC record (smCharDecode also accepts 적,
				# the monster value; fileread.cpp:4338)
				case NPC.State:
					character.active = True if segments[0] == NPC._ACTIVE else False
				case NPC.szModelName:
					character.model = segments[0]
				case NPC.Level:
					character.level = int(segments[0])
				case NPC.szName:
					character.name = decode_string(segments[0])
				case NPC.Name:
					character.name_en = segments[0]
				case NPC.lpDialogMessage:
					character.dialogue.append(decode_string(segments[0]))
				case NPC.SellAttackItem:
					# *무기판매: item names resolved against the item table
					# (smCharDecode case at fileread.cpp:5162-5177)
					character.sell_weapons = [decode_string(s) for s in segments if segments[0] != NPC._EMPTY]
				case NPC.SellDefenceItem:
					# *방어구판매 (fileread.cpp:5178-5193)
					character.sell_defences = [decode_string(s) for s in segments if segments[0] != NPC._EMPTY]
				case NPC.SellEtcItemCount:
					# *잡화판매 (fileread.cpp:5194-5209); key fixed: was an
					# AttributeError before (const only defines SellEtcItemCount)
					character.sell_misc = [decode_string(s) for s in segments if segments[0] != NPC._EMPTY]
				case NPC.SkillMaster:
					character.skill_master = True
				case NPC.SkillChangeJob:
					# *직업전환; no argument = rank 0 (smCharDecode also maps the
					# rank keywords *두목 / *계급 to wPlayClass[0],
					# fileread.cpp:126278-126300)
					character.job_master = 0 if len(segments) == 0 else segments[0]
				case NPC.EventNPC:
					character.event = int(segments[0])
				case NPC.WareHouseMaster:
					character.warehouse_master = True
				case NPC.ItemMix:
					character.item_mixing = True
				case NPC.Smelting:
					character.item_smelting = True
				case NPC.Manufacture:
					character.item_crafting = True
				case NPC.ItemMix200:
					character.item_mixing_200 = True
				case NPC.ItemAging:
					character.item_aging = True
				case NPC.MixtureReset:
					character.item_reset = True
				case NPC.CollectMoney:
					character.CollectMoney = True
				case NPC.WowEvent:
					character.WowEvent = True
				case NPC.EventGift:
					character.EventGift = True
				case NPC.ClanNPC:
					character.clan_master = True
				case NPC.GiftExpress:
					character.GiftExpress = True
				case NPC.WingQuestNpc1:
					character.WingQuestNpc1 = int(segments[0])
				case NPC.WingQuestNpc2:
					character.WingQuestNpc2 = int(segments[0])
				case NPC.StarPointNpc:
					character.StarPointNpc = int(segments[0])
				case NPC.GiveMoneyNpc:
					character.GiveMoneyNpc = True
				case NPC.TelePortNpc:
					character.teleport_master = int(segments[0])
				case NPC.BlessCastleNPC:
					character.BlessCastleNPC = int(segments[0])
				case NPC.PollingNpc:
					character.PollingNpc = int(segments[0])
				case NPC.szMediaPlayNPC_Title:
					character.media_title = segments[0]
				case NPC.szMediaPlayNPC_Path:
					character.media_path = segments[0]
				case NPC.OpenCount:
					character.find_word = int(segments[0])
					character.exit_number = int(segments[1])
				case NPC.QuestCode:
					character.quest_code = int(segments[0])
					character.quest_param = int(segments[1])
				case NPC.szNextFile:
					character.zhoon_path = segments[0]
				case _:
					print(f"Unknown key: {key}")

	return character
