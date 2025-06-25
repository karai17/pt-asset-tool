import struct
from pt.buffer import BufferReader


def patch(path: str) -> bytes:
	"""
	Priston Tale mangles the whole 14 byte Bitmap file header in an unknown way.
	The two byte signature string is always mangled by replacing `BM` with `A8`.
	Luckily, constructing a new file header is pretty simple.

	Reference: `smTexture.cpp::LoadDib`
	"""
	buffer = BufferReader(path)
	id = buffer.data[0:2].decode("ascii")

	if id == "A8":
		signature = struct.pack("<H", int.from_bytes(b"BM", "little"))
		size = struct.pack("<L", len(buffer.data))
		reserved = struct.pack("<L", 0)
		offset = struct.pack("<L", int.from_bytes(b"\x36", "little")) # Priston Tale's textures always have an offset of 0x36
		buffer.data[0:14] = signature + size + reserved + offset

	return buffer.get_data()
