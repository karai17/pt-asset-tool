from ctypes import *

from pt.buffer import BufferReader
from pt.cdef import *
from pt.const import SCALE_INCH_TO_METER
from pt.pdef import *


def decode(path: str) -> list[PTServerSpawnPoint]:
	"""
	Decodes an SPP file which consists of a list of monster spawn points.

	SPP files have a fixed filesize of 2400 bytes which allows for a maximum of
	200 spawn points per stage. Some spawn points exist within the data but are
	disabled (state == 0). If there are less than 200 spawn points, the tail end
	of the file is filled with zeros.

	Despite the fixed filesize, this decoder checks the size of the file in case
	future server developers want to create extra large stages with many more
	spawn points.

	Reference: `onserver.h::STG_START_POINT_MAX`
	"""
	sm_buffer = BufferReader(path)
	filesize = len(sm_buffer.data)
	num_points = int(filesize / sizeof(STG_START_POINT))
	points = []

	for i in range(0, num_points):
		sm_point = sm_buffer.read(STG_START_POINT)

		if sm_point.state + sm_point.x + sm_point.z != 0:
			points.append(PTServerSpawnPoint(
				active = True if sm_point.state == 1 else False,
				position = PTVector3(
					x = sm_point.x * SCALE_INCH_TO_METER,
					y = 0, # y value determined via raycast
					z = sm_point.z * SCALE_INCH_TO_METER
				)
			))

	return points
