from ctypes import *

from pt.buffer import BufferReader
from pt.cdef import *
from pt.const import SCALE_INCH_TO_METER
from pt.pdef import *
from pt.utils import angles_to_quaternion, get_filename, decode_string


def decode(path: str) -> list[PTServerSpawnCharacter]:
	"""
	Decodes an SPC file which consists of a list of NPCs in a stage.

	SPC files have a fixed filesize of 50400 bytes which allows for a maximum of
	100 NPCs per stage. Some NPCs exist within the data but are disabled
	(code != 1212612720). If there are less than 100 NPCs, the tail end of the
	file is filled with zeros.

	Despite the fixed filesize, this decoder checks the size of the file in case
	future server developers want to create extra large stages with many more
	NPCs.

	Reference: `onserver.h::FIX_CHAR_MAX`
	"""
	sm_buffer = BufferReader(path)
	filesize = len(sm_buffer.data)
	num_points = int(filesize / sizeof(smTRNAS_PLAYERINFO))
	npcs = []

	for _ in range(num_points):
		sm_npc = sm_buffer.read(smTRNAS_PLAYERINFO)

		# code is checked against smTRANSCODE_ADD_NPC (0x48470070,
		# smPacket.h:117) by the server's NPC iteration (OnSever.cpp:7764:
		# "if ( TransCharFixed[cnt].code ) OpenNpc(...)").
		if sm_npc.size == 504:
			char, ext = get_filename(decode_string(sm_npc.smCharInfo.szModelName))
			npc, ext = get_filename(decode_string(sm_npc.smCharInfo.szModelName2))

			npcs.append(PTServerSpawnCharacter(
				active = True if sm_npc.code == 1212612720 else False,
				name = decode_string(sm_npc.smCharInfo.szName),
				char = char.casefold(),
				npc = npc.casefold(),
				# OpenNpc copies x/y/z verbatim into smCHAR::pX/pY/pZ which is
				# fixed point: inches << FLOATNS(8) (OnSever.cpp:6496-6498 vs
				# pX>>FLOATNS readers at 5330; SPP stores plain inches by
				# contrast). Contrast test: ruin-1 keeper raw x 4235537 ->
				# 16545 in = 420 m, inside the stage bounds; unscaled it would
				# be 107 km off-map.
				position = PTVector3(
					x = sm_npc.x / 256 * SCALE_INCH_TO_METER,
					y = sm_npc.y / 256 * SCALE_INCH_TO_METER,
					z = sm_npc.z / 256 * SCALE_INCH_TO_METER
				),
				# angle triple is applied verbatim to smCHAR::Angle by OpenNpc
				# (OnSever.cpp:6504-6506); the 4096-unit circle is defined in
				# smSin.h:25 (ANGLE_360).
				rotation = angles_to_quaternion(sm_npc.ax, sm_npc.ay, sm_npc.az),
				scale = PTVector3(1, 1, 1)
			))

	return npcs
