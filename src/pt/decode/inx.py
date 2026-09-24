import os

from ctypes import *

from pt.buffer import BufferReader
from pt.cdef import smMODELINFO, smMODELINFO_EX
from pt.decode import smd
from pt.pdef import *
from pt.utils import get_filename, decode_string, resolve_casepath
from pt.const import (
	CHRMOTION,
	CHRMOTION_STATE
)


# INX files are raw smMODELINFO structs obfuscated in two layers by the ini
# compiler (fileread.cpp::AddModelDecode -> smModelDecode saves the struct):
#
# 1. fileread.cpp::ModelKeyWordEncode xors a checksum of the file path into
#    FileTypeKeyWord / LinkFileKeyWord. The loader verifies it
#    (fileread.cpp::ModelKeyWordDecode) but nothing in the struct payload is
#    actually encrypted by it, so a decoder may ignore these fields.
# 2. fileread.cpp::MotionKeyWordEncode folds the same checksum into
#    StartFrame / MotionKeyWord_1 / EndFrame / MotionKeyWord_2 of every motion
#    entry from index CHRMOTION_EXT (10) up. This one must be reversed before
#    frames are readable.
#
# Reference: fileread.cpp:6474 MotionKeyWordDecode. The byte shuffles below
# are the exact inverses of the encoder's shifts/masks (dwCode is dropped
# because both encoder and decoder zero the keyword fields they touch).
def decode_motion(sm_motioninfo):
	sm_motioninfo.StartFrame = ((sm_motioninfo.StartFrame & int.from_bytes(b"\x00\x00\x00\xff")) << 24) | (sm_motioninfo.StartFrame & int.from_bytes(b"\x00\xff\x00\x00")) | ((sm_motioninfo.MotionKeyWord_1 & int.from_bytes(b"\x00\xff\x00\x00")) >> 8) | (sm_motioninfo.MotionKeyWord_1 & int.from_bytes(b"\x00\x00\x00\xff"))
	sm_motioninfo.MotionKeyWord_1 = 0
	sm_motioninfo.EndFrame = ((sm_motioninfo.MotionKeyWord_2 & int.from_bytes(b"\x00\xff\x00\x00")) << 8) | ((sm_motioninfo.MotionKeyWord_2 & int.from_bytes(b"\x00\x00\x00\xff")) << 16)| ((sm_motioninfo.EndFrame & int.from_bytes(b"\x00\xff\x00\x00")) >> 8) | (sm_motioninfo.EndFrame & int.from_bytes(b"\x00\x00\x00\xff"))
	sm_motioninfo.MotionKeyWord_2 = 0


def resolve_modelpath(dirpath: str, filename: str, root: str | None, ext: str) -> str:
	"""
	Resolve a model file reference the way the engine does (smRead3d.cpp
	smASE_Read -> smFindFile -> ChangeFileExt): the szModel/szMotion fields
	hold game-root-relative paths authored as szDirecotry + value (fileread.cpp
	:530), so the extension is swapped to the target type and the path is
	resolved against the game root, not the INX's own directory.
	"""
	rootname, _ = get_filename(filename)
	if root and "\\" in filename:
		relpath = os.path.splitext(filename.replace("\\", os.path.sep))[0]
		modelpath = os.path.join(root, relpath + ext)
		resolved = resolve_casepath(modelpath)
		if os.path.exists(resolved):
			return resolved
	return resolve_casepath(os.path.join(dirpath, rootname + ext))


def read_modelinfo(path: str):
	sm_buffer = BufferReader(path)
	size = len(sm_buffer.data)

	if size == 67084:
		return sm_buffer.read(smMODELINFO)
	elif size == 95268:
		return sm_buffer.read(smMODELINFO_EX)

	print(f"Invalid INX file size: {size}")
	return None


def decode_metadata(sm_modelinfo, dirpath: str, root: str | None, chain: bool = True, lod: bool = False) -> tuple[PTModelMetadata, str]:
	metadata = PTModelMetadata()
	motionfilename = decode_string(sm_modelinfo.szMotionFile)

	# smMODELINFO.HighModel / DefaultModel / LowModel are _MODELGROUPs filled
	# from the *정밀모양 (high) / *보통모양 (default) / *저질모양 (low) ini keys
	# (fileread.cpp:624-634, AddModelDecode case 6/7/8). At render time the
	# engine picks one group by view distance (character.cpp:7349-7355:
	# default = DefaultModel, HighModel when dDist < VIEW_HIGH_DIST, LowModel
	# when dDist > VIEW_MID_DIST); lod keeps every quality group's objects
	# instead. All three groups are decoded regardless so the data is recorded.
	for group_name, group in (("high", sm_modelinfo.HighModel), ("default", sm_modelinfo.DefaultModel), ("low", sm_modelinfo.LowModel)):
		metadata.model_lod_groups[group_name] = [decode_string(group.szModelName[i]) for i in range(group.ModelNameCnt)]

	if lod:
		metadata.model_names = list(dict.fromkeys(
			name for names in metadata.model_lod_groups.values() for name in names
		))
	else:
		metadata.model_names = list(metadata.model_lod_groups["high"])

	# loop through and decode motion info to build metadata. The engine walks
	# the same range: for(i = CHRMOTION_EXT; i < MotionCount; i++)
	# (fileread.cpp:6481 MotionKeyWordDecode) - MotionCount counts the 10
	# reserved slots, so real entries live at [10, MotionCount). Slots 0-9 stay
	# zero: the ini parser only writes MotionInfo[10+] because the old
	# fixed-slot commands (*걷는동작 / *서있기동작) are commented out in
	# AddModelDecode (fileread.cpp:601-610).
	for i in range(10, sm_modelinfo.MotionCount):
		sm_motioninfo = sm_modelinfo.MotionInfo[i]
		if sm_motioninfo.State > 0:
			decode_motion(sm_motioninfo)

			animation = PTMotionMetadata()
			# State is set by the ini parser's keyword match on the motion line:
			# State 1 (TRUE) when no keyword matched (fileread.cpp:337), otherwise
			# CHRMOTION_STATE_* (character.h:893-931) such as CHRMOTION_STATE_STAND
			# = 0x40 or CHRMOTION_STATE_RUN = 0x60.
			animation.name = CHRMOTION_STATE.get(sm_motioninfo.State, "unknown")
			animation.start_frame = sm_motioninfo.StartFrame
			animation.end_frame = sm_motioninfo.EndFrame
			animation.repeat = True if sm_motioninfo.Repeat != 0 else False

			# MotionFrame is the 1-based index of the *동작모음 (motion file list)
			# entry whose frames were merged into szMotionFile for this animation
			# (fileread.cpp:336; runtime reads TmFrame[MotionFrame-1],
			# character.cpp:591). 0 means the INX had no motion file list.
			animation.motion_frame = sm_motioninfo.MotionFrame

			# event frames denote which frame relative to the beginning of the
			# animation some event occurs, such as playing a sound, displaying a
			# decal, or whatever else! The ini parser stores them scaled by 160
			# ticks (fileread.cpp:236 SetIniMotionInfo: (atoi - StartFrame) * 160);
			# divide by 160 to recover the frame number.
			for k in range(3):
				event_frame = sm_motioninfo.EventFrame[k]
				if event_frame > 0:
					animation.event_frames.append(event_frame / 160)

			# restrictions narrow when the engine plays this animation
			# (character.cpp:2355-2440): an empty item_codes list matches any
			# weapon, otherwise it holds sItem[] indices (0xFF / 0xFFFF in the
			# EX variant = bare body sentinel, fileread.cpp:645); job_code_bit is
			# a class bitmask where 0 matches every class (fileread.cpp:669-677);
			# skill_codes holds SkillDataCode[] indices and a non-empty list means
			# the animation only plays while casting that skill (fileread.cpp:714-732);
			# map_position is a bit mask of village (1) / field (2) contexts
			# (fileread.cpp:685-711, character.cpp StageVillage); key_code is a
			# single ASCII event key driving attack behaviour (fileread.cpp:246,
			# character.cpp:3446+).
			animation.item_codes = list(sm_motioninfo.ItemCodeList[:max(sm_motioninfo.ItemCodeCount, 0)])
			animation.job_code_bit = sm_motioninfo.dwJobCodeBit
			skill_codes = []
			for code in sm_motioninfo.SkillCodeList:
				if code == 0:
					break
				skill_codes.append(code)
			animation.skill_codes = skill_codes
			animation.map_position = sm_motioninfo.MapPosition
			if 32 <= sm_motioninfo.KeyCode <= 126:
				animation.key_code = chr(sm_motioninfo.KeyCode)
			if i < len(sm_modelinfo.NpcMotionRate):
				animation.rate = sm_modelinfo.NpcMotionRate[i]

			metadata.animations.append(animation)

	# the facial animation table (TalkMotionInfo) is written by the same tool in
	# the same slot convention (entries at [10, TalkMotionCount), TalkMotionCount
	# includes the 10 reserved slots) but is NOT obfuscated by MotionKeyWordEncode
	# (fileread.cpp:6474 only touches MotionInfo). State is a CHRMOTION_STATE_TALK_*
	# expression (character.h:920-930); MotionFrame discriminates which merged
	# motion file the frames live in: 0 = TALK_MOTION_FILE (szMotionFile),
	# 1 = FACIAL_MOTION_FILE (szTalkMotionFile) (smType.h:404-405). Rate is the
	# authored blend weight the engine normalizes into TalkMotionRateCnt
	# (fileread.cpp:831-902).
	for i in range(10, sm_modelinfo.TalkMotionCount):
		sm_talkinfo = sm_modelinfo.TalkMotionInfo[i]
		if sm_talkinfo.State > 0:
			animation = PTMotionMetadata()
			animation.name = CHRMOTION_STATE.get(sm_talkinfo.State, "unknown")
			animation.start_frame = sm_talkinfo.StartFrame
			animation.end_frame = sm_talkinfo.EndFrame
			animation.repeat = True if sm_talkinfo.Repeat != 0 else False
			animation.motion_frame = sm_talkinfo.MotionFrame
			if i < len(sm_modelinfo.TalkMotionRate):
				animation.rate = sm_modelinfo.TalkMotionRate[i]
			for k in range(3):
				event_frame = sm_talkinfo.EventFrame[k]
				if event_frame > 0:
					animation.event_frames.append(event_frame / 160)
			if 32 <= sm_talkinfo.KeyCode <= 126:
				animation.key_code = chr(sm_talkinfo.KeyCode)
			metadata.talk_animations.append(animation)

	metadata.npc_motion_rate_table = list(sm_modelinfo.NpcMotionRateCnt)
	metadata.talk_motion_rate_table = [list(rates) for rates in sm_modelinfo.TalkMotionRateCnt]

	# chain inheritance (fileread.cpp:996-1056): the loader re-reads the linked
	# INX and, when the LINKED file carries the table (its MotionCount /
	# TalkMotionCount > CHRMOTION_EXT), replaces our motion table (szLinkFile,
	# i==1) or facial table (szTalkLinkFile, i==2) wholesale, including the
	# referenced motion file and the table's rate tables - a local table does
	# not shield it (fileread.cpp:1031-1050 has no local-count condition).
	# Every shipped file that has both a local table and a link self-references
	# (the link points at the file's own .in), so on those the replacement is a
	# no-op; the rule still matters for cross-file chains. The stored extension
	# is truncated and reconstructed via ChangeFileExt(szFile, "inx")
	# (smRead3d.cpp:92), so links surface with the .inx extension restored.
	# szTalkMotionFile is the face model the talk motions were merged into
	# (authored as .ASE, shipped as .smb); szSubModelFile is an auxiliary model
	# loaded as a second character pattern (character.cpp:831-834).
	linkfile = decode_string(sm_modelinfo.szLinkFile)
	if linkfile:
		rootname, _ = get_filename(linkfile)
		metadata.link_file = rootname + ".inx"
	talklinkfile = decode_string(sm_modelinfo.szTalkLinkFile)
	if talklinkfile:
		rootname, _ = get_filename(talklinkfile)
		metadata.talk_link_file = rootname + ".inx"
	metadata.talk_motion_file = decode_string(sm_modelinfo.szTalkMotionFile) or None
	metadata.sub_model_file = decode_string(sm_modelinfo.szSubModelFile) or None

	# chain inheritance (fileread.cpp:996-1056): the loader re-reads the linked
	# INX and, when it carries the corresponding table, replaces our motion
	# table (szLinkFile) or facial table (szTalkLinkFile) wholesale, including
	# the referenced motion file - the *파일연결 chain is how clothing variants
	# share the biped's animations.
	if chain:
		if metadata.link_file:
			linkpath = resolve_modelpath(dirpath, metadata.link_file, root, ".inx")
			linked = read_modelinfo(linkpath) if os.path.exists(linkpath) else None
			if linked is not None and linked.MotionCount > 10:
				linked_metadata, linked_motionfile = decode_metadata(linked, dirpath, root, False)
				metadata.animations = linked_metadata.animations
				metadata.npc_motion_rate_table = linked_metadata.npc_motion_rate_table
				motionfilename = linked_motionfile
		if metadata.talk_link_file:
			linkpath = resolve_modelpath(dirpath, metadata.talk_link_file, root, ".inx")
			linked = read_modelinfo(linkpath) if os.path.exists(linkpath) else None
			if linked is not None and linked.TalkMotionCount > 10:
				linked_metadata, _ = decode_metadata(linked, dirpath, root, False)
				metadata.talk_animations = linked_metadata.talk_animations
				metadata.talk_motion_rate_table = linked_metadata.talk_motion_rate_table
				metadata.talk_motion_file = linked_metadata.talk_motion_file
				# the engine also copies the linked file's szTalkLinkFile over ours
				# (fileread.cpp:1040); szLinkFile is left alone in the i==1 branch.

	return metadata, motionfilename


# entry point of loading a 3D model; the engine's counterpart is
# fileread.cpp:967 smModelDecode, which reads the ini/inx into an smMODELINFO
# and then loads the referenced smd/smb files via smPAT3D::LoadFile. Shipped
# INX files are raw sizeof(smMODELINFO) (67084) or sizeof(smMODELINFO_EX)
# (95268) byte structs; the size check stands in for the engine's
# smModelDecode dwFileLen == sizeof check (fileread.cpp:1019).
def decode(path: str, root: str | None = None, lod: bool = False) -> PTActorModel | PTStageModel | None:
	sm_modelinfo = read_modelinfo(path)
	if sm_modelinfo is None:
		return

	segments = path.split(os.path.sep)
	dirpath = os.path.sep.join(segments[:-1])

	metadata, motionfilename = decode_metadata(sm_modelinfo, dirpath, root, lod=lod)

	modelfilename = decode_string(sm_modelinfo.szModelFile)
	modelpath = resolve_modelpath(dirpath, modelfilename, root, ".smd") if modelfilename else None
	motionpath = resolve_modelpath(dirpath, motionfilename, root, ".smb") if motionfilename else None

	if modelpath and motionpath:
		return smd.decode(modelpath, motionpath, metadata)
	elif modelpath:
		return smd.decode(modelpath)
	else:
		print(f"Invalid Model: {path}")
