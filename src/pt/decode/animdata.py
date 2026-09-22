import os

from pt.pdef import *

# HoAnimData.cpp INI tables read via GetPrivateProfileString/Int:
# HoAnimSequenceData::Load (:48-207) fills an [ANIMATION] sequence whose
# comma-separated ImageNum/Delay/BlendValue (and optional Size/Angle) lists
# are per-frame; HoAnimImageData::Load (:279-299) fills an [IMAGE] texture
# table. Angle is authored in degrees, converted to engine angle units
# (ANGLE_360 * degrees / 360) at load; Size is the width and height is an
# extension that the shipped parser never reads.


def _split_csv(values: str) -> list[str]:
	return [value.strip() for value in values.split(",") if value.strip()]


def _parse_sections(path: str) -> dict[str, dict[str, str]]:
	sections: dict[str, dict[str, str]] = {}
	section = None

	with open(path, "r", encoding="cp949", errors="replace") as f:
		for line in f:
			line = line.strip()
			if not line or line.startswith("//") or line.startswith(";"):
				continue

			if line.startswith("[") and line.endswith("]"):
				section = line[1:-1].strip().upper()
				sections[section] = {}
			elif section is not None and "=" in line:
				key, value = line.split("=", 1)
				sections[section][key.strip().lower()] = value.strip()

	return sections


def _frames(image_nums: list[str], delays: list[str],
	blend_values: list[str], sizes: list[str], angles: list[str]) -> list[PTAnimFrame]:
	frames = []

	for index, image_num in enumerate(image_nums):
		frame = PTAnimFrame(
			image_num = int(image_num),
			delay = int(delays[index]) if index < len(delays) else 0,
			alpha = int(blend_values[index]) if index < len(blend_values) else 0
		)

		# INFO_SIZEWIDTH (HoAnimData.cpp:157-181); a width implies height
		# equal to it since only SizeWidth exists in the struct's base layout
		if index < len(sizes):
			frame.size_width = int(sizes[index])

		# INFO_ANGLE: degrees to engine angle units conversion is lossless
		# enough here to keep the authored degrees
		if index < len(angles):
			frame.angle = float(angles[index])

		frames.append(frame)

	return frames


def decode(path: str) -> PTAnimData:
	"""Decode an HoAnimData image/sequence INI."""
	animdata = PTAnimData()
	animdata.filename = os.path.basename(path)
	sections = _parse_sections(path)

	if "IMAGE" in sections:
		image = PTAnimImageData()
		image.texture_name = sections["IMAGE"].get("name")
		image.texture_count = int(sections["IMAGE"].get("count", 0))
		animdata.image_data.append(image)

	if "ANIMATION" in sections:
		sequence = PTAnimSequenceData()
		sequence.data_file = sections["ANIMATION"].get("datafile")
		sequence.blend_type = int(sections["ANIMATION"].get("blendtype", 0))
		sequence.start_blend_value = int(sections["ANIMATION"].get("startblendvalue", 0))

		image_nums = _split_csv(sections["ANIMATION"].get("imagenum", ""))
		delays = _split_csv(sections["ANIMATION"].get("delay", ""))
		blend_values = _split_csv(sections["ANIMATION"].get("blendvalue", ""))
		sizes = _split_csv(sections["ANIMATION"].get("size", ""))
		angles = _split_csv(sections["ANIMATION"].get("angle", ""))

		sequence.frames = _frames(image_nums, delays, blend_values, sizes, angles)
		animdata.sequences.append(sequence)

	return animdata
