import struct
from pt.buffer import BufferReader


def u8(n: int):
	return n % 256


def patch(path: str):
	"""
	Priston Tale mangles the whole 18 byte Targa file header by using a counter
	and a simple key product to add a junk value to each byte in the header.

	We need to perform the same operation, instead negating the junk value.

	Reference: smTexture.cpp::cTGA::LoadTga
	"""

	buffer = BufferReader(path)

	id = bytes(buffer.data[0:1]).decode("ascii")
	color_map_type = bytes(buffer.data[1:2]).decode("ascii")
	image_type = buffer.data[2] - 2

	if id == "G" and color_map_type == "8" and image_type % 4 == 0:
		# initialize magic numbers
		key = int(image_type / 4)
		crypt_count = 3
		crypt_key = 4

		# initialize header
		header = buffer.data[0:18]
		magic = struct.pack("<BBB", 0, 0, 2)
		header[0:3] = magic

		# loop through rest of header
		for i in range(3, 18):
			# increment crypt values by magic numbers
			crypt_count = u8(crypt_count + 2)
			crypt_key = u8(crypt_key + crypt_count)

			# get byte, multiply keys, negate junk value
			b = header[i]
			tmp = u8(crypt_key * key)
			new_b = u8(b - tmp)

			# set byte
			header[i] = new_b

		buffer.data[0:18] = header

	return buffer.get_data()
