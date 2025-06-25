import struct
from pt.buffer import BufferReader


def patch(path: str) -> bytes:
	"""
	Priston Tale mangles the Waveform file header by replacing the four byte
	signature string `RIFF` with `JODO`.

	Reference: `Dxwav.h::WaveHeader0`, `WaveHeader1`, `WaveHeader2`
	"""
	buffer = BufferReader(path)
	id = buffer.data[0:4].decode("ascii")

	if id == "JODO":
		signature = struct.pack("<L", int.from_bytes(b"RIFF", "little"))
		buffer.data[0:4] = signature

	return buffer.get_data()
