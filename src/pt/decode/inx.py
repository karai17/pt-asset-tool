import os

from ctypes import *

from pt.buffer import BufferReader
from pt.cdef import smMODELINFO, smMODELINFO_EX
from pt.decode import smd
from pt.pdef import *
from pt.utils import get_filename, decode_string
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


def decode(path: str) -> PTActorModel | PTStageModel | None:
	"""
	Import an INX file as the entry point of loading a 3D model.

	The engine's counterpart is fileread.cpp:967 smModelDecode, which reads
	the ini/inx into an smMODELINFO and then loads the referenced smd/smb
	files via smPAT3D::LoadFile. Shipped INX files are raw sizeof(smMODELINFO)
	(67084) or sizeof(smMODELINFO_EX) (95268) byte structs; the size check
	stands in for the engine's smModelDecode dwFileLen == sizeof check
	(fileread.cpp:1019).
	"""
	sm_buffer = BufferReader(path)
	size = len(sm_buffer.data)

	if size == 67084:
		sm_modelinfo: smMODELINFO = sm_buffer.read(smMODELINFO)
	elif size == 95268:
		sm_modelinfo: smMODELINFO_EX = sm_buffer.read(smMODELINFO_EX)
	else:
		print(f"Invalid INX file size: {size}")
		return

	segments = path.split(os.path.sep)
	dirpath = os.path.sep.join(segments[:-1])

	modelfilename = decode_string(sm_modelinfo.szModelFile)
	modelpath = None
	if modelfilename:
		modelroot, modelext = get_filename(modelfilename)
		modelpath = os.path.join(dirpath, modelroot + ".smd")

	motionfilename = decode_string(sm_modelinfo.szMotionFile)
	motionpath = None
	if motionfilename:
		motionroot, motionext = get_filename(motionfilename)
		motionpath = os.path.join(dirpath, motionroot + ".smb")

	# TODO: submodels
	# submodelfilename = decode_string(sm_modelinfo.szSubModelFile)
	# if submodelfilename:
	# 	submodelroot, submodelext = get_filename(submodelfilename)
	# 	submodelpath = os.path.join(dirpath, submodelroot + ".smd")

	metadata = PTModelMetadata()

	# collect only high quality model names, cull the rest in the smd importer.
	# smMODELINFO.HighModel / DefaultModel / LowModel are _MODELGROUPs filled
	# from the *정밀모양 (high) / *보통모양 (default) / *저질모양 (low) ini keys
	# (fileread.cpp:624-634, AddModelDecode case 6/7/8).
	for i in range(sm_modelinfo.HighModel.ModelNameCnt):
		metadata.model_names.append(decode_string(sm_modelinfo.HighModel.szModelName[i]))

	# loop through and decode motion info to build metadata. The engine walks
	# the same range: for(i = CHRMOTION_EXT; i < MotionCount; i++)
	# (fileread.cpp:6482 MotionKeyWordDecode). Slots 0-9 stay zero: the ini
	# parser only writes MotionInfo[10+] because the old fixed-slot commands
	# (*걷는동작 / *서있기동작) are commented out in AddModelDecode
	# (fileread.cpp:601-610).
	for i in range(10, sm_modelinfo.MotionCount + 10):
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

			# event frames denote which frame relative to the beginning of the
			# animation some event occurs, such as playing a sound, displaying a
			# decal, or whatever else! The ini parser stores them scaled by 160
			# ticks (fileread.cpp:236 SetIniMotionInfo: (atoi - StartFrame) * 160);
			# divide by 160 to recover the frame number.
			for k in range(3):
				event_frame = sm_motioninfo.EventFrame[k]
				if event_frame > 0:
					animation.event_frames.append(event_frame / 160)

			# TODO: MotionFrame indexes the *동작모음 motion file list (set at
			# fileread.cpp:336); TODO: talk info (see debug prints), stored in
			# TalkMotionInfo via SetIniMotionInfo (fileread.cpp:446) from the
			# *표정 ini keywords (fileread.cpp:449-492).

			metadata.animations.append(animation)


	#----------- debug prints ---------------
	"""
	print("FileTypeKeyWord:", sm_model_info.FileTypeKeyWord)
	print("LinkFileKeyWord:", sm_model_info.LinkFileKeyWord)

	print("linkPath:", decode_string(sm_model_info.linkPath))
	print("talkLinkPath:", decode_string(sm_model_info.talkLinkPath))
	print("talkMotionPath:", decode_string(sm_model_info.talkMotionPath))

	print("numTalkMotion:", sm_model_info.numTalkMotion)
	for i in range(30):
		mi = sm_model_info.talkMotionInfo[i]
		decode_motion(mi)
		print_motioninfo(mi, "talkMotionInfo")
	end

	npcMotionRate = []
	for i in range(30):
		npcMotionRate.append(sm_model_info.npcMotionRate[i])
	end
	print_array(npcMotionRate, "npcMotionRate")

	numNpcMotionRate = []
	for i in range(100):
		numNpcMotionRate.append(sm_model_info.numNpcMotionRate[i])
	end
	print_array(numNpcMotionRate, "numNpcMotionRate")

	talkMotionRate = []
	for i in range(30):
		talkMotionRate.append(sm_model_info.talkMotionRate[i])
	end
	print_array(talkMotionRate, "talkMotionRate")

	numTalkMotionRate = []
	for i in range(2):
		x = []
		for k in range(100):
			x.append(sm_model_info.numTalkMotionRate[i][k])
			print("numTalkMotionRate:", i, k, sm_model_info.numTalkMotionRate[i][k])
		end
		numTalkMotionRate.append(x)
	end

	print()
	"""
	#---------------- debug end ----------------


	if modelpath and motionpath:
		return smd.decode(modelpath, motionpath, metadata)
	elif modelpath:
		return smd.decode(modelpath)
	else:
		print(f"Invalid Model: {path}")
