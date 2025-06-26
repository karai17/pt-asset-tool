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


# Reference: fileread.cpp::MotionKeyWordDecode
def decode_motion(sm_motioninfo):
	sm_motioninfo.StartFrame = ((sm_motioninfo.StartFrame & int.from_bytes(b"\x00\x00\x00\xff")) << 24) | (sm_motioninfo.StartFrame & int.from_bytes(b"\x00\xff\x00\x00")) | ((sm_motioninfo.MotionKeyWord_1 & int.from_bytes(b"\x00\xff\x00\x00")) >> 8) | (sm_motioninfo.MotionKeyWord_1 & int.from_bytes(b"\x00\x00\x00\xff"))
	sm_motioninfo.MotionKeyWord_1 = 0
	sm_motioninfo.EndFrame = ((sm_motioninfo.MotionKeyWord_2 & int.from_bytes(b"\x00\xff\x00\x00")) << 8) | ((sm_motioninfo.MotionKeyWord_2 & int.from_bytes(b"\x00\x00\x00\xff")) << 16)| ((sm_motioninfo.EndFrame & int.from_bytes(b"\x00\xff\x00\x00")) >> 8) | (sm_motioninfo.EndFrame & int.from_bytes(b"\x00\x00\x00\xff"))
	sm_motioninfo.MotionKeyWord_2 = 0


def decode(path: str) -> PTActorModel | PTStageModel | None:
	"""Import an INX file as the entry point of loading a 3D model."""
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
	if modelfilename:
		modelroot, modelext = get_filename(modelfilename)
		modelpath = os.path.join(dirpath, modelroot + ".smd")

	motionfilename = decode_string(sm_modelinfo.szMotionFile)
	if motionfilename:
		motionroot, motionext = get_filename(motionfilename)
		motionpath = os.path.join(dirpath, motionroot + ".smb")

	# TODO: submodels
	# submodelfilename = decode_string(sm_modelinfo.szSubModelFile)
	# if submodelfilename:
	# 	submodelroot, submodelext = get_filename(submodelfilename)
	# 	submodelpath = os.path.join(dirpath, submodelroot + ".smd")

	metadata = PTModelMetadata()

	# collect only high quality model names, cull the rest in the smd importer
	for i in range(sm_modelinfo.HighModel.ModelNameCnt):
		metadata.model_names.append(decode_string(sm_modelinfo.HighModel.szModelName[i]))

	# loop through and decode motion info to build metadata
	for i in range(10, sm_modelinfo.MotionCount + 10):
		sm_motioninfo = sm_modelinfo.MotionInfo[i]
		if sm_motioninfo.State > 0:
			decode_motion(sm_motioninfo)

			animation = PTMotionMetadata()
			animation.name = CHRMOTION_STATE[sm_motioninfo.State]
			animation.start_frame = sm_motioninfo.StartFrame
			animation.end_frame = sm_motioninfo.EndFrame
			animation.repeat = True if sm_motioninfo.Repeat != 0 else False

			# event frames denote which frame relative to the beginning of the
			# animation some event occurs, such as playing a sound, displaying a
			# decal, or whatever else!
			for k in range(3):
				event_frame = sm_motioninfo.EventFrame[k]
				if event_frame > 0:
					animation.event_frames.append(event_frame / 160)

			# TODO: MotionFrame
			# TODO: talk info (see debug prints)

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
