from ctypes import *


class BufferReader:
	def __init__(self, path: str | int):
		if type(path) == str:
			with open(path, "rb") as f:
				data = bytearray(f.read())
		elif type(path) == int:
			data = bytearray(path)
		else:
			raise Exception("Invalid initialization.")

		self.data = data
		self.offset = 0


	def read(self, struct_type):
		if not hasattr(struct_type, "_fields_") and not hasattr(struct_type, "_length_"):
			struct_type = struct_type * 1

		try:
			size = sizeof(struct_type)
		except Exception as e:
			raise TypeError("Expected a ctype or struct class.")

		if self.offset + size > len(self.data):
			raise ValueError("Not enough data left to read.")

		mv = memoryview(self.data)[self.offset:self.offset + size]
		struct = struct_type.from_buffer(mv)
		self.offset += size
		return struct


	def write(self, struct_data):
		try:
			size = sizeof(struct_data)
		except Exception as e:
			raise TypeError("Expected a ctype or struct instance.")

		if self.offset + size > len(self.data):
				raise ValueError("Not enough data left to write.")

		mv = memoryview(self.data)[self.offset:self.offset + size]
		memmove(addressof(c_char.from_buffer(mv)), addressof(struct_data), size)
		self.offset += size


	def seek(self, new_offset: int):
		self.offset = new_offset


	def tell(self):
		return self.offset


	def get_data(self):
		return bytes(self.data)
