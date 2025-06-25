from ctypes import *
from typing import TypeVar


CType = TypeVar("CType")


class BufferReader:
	"""Read a file as a bytearray to be read from and written to."""
	def __init__(self, path: str | int) -> None:
		if type(path) == str:
			with open(path, "rb") as f:
				data = bytearray(f.read())
		elif type(path) == int:
			data = bytearray(path)
		else:
			raise Exception("Invalid initialization.")

		self.data = data
		self.offset = 0


	def read(self, struct_type: type[CType]) -> CType:
		"""
		Read from the bytearray at the current offset location. Progresses the
		offset location forward by the size of the read.
		"""
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


	def write(self, struct_data: CType) -> None:
		"""
		Write to the bytearray at the current offset location. Progresses the
		offset location forward by the size of the write.
		"""
		try:
			size = sizeof(struct_data)
		except Exception as e:
			raise TypeError("Expected a ctype or struct instance.")

		if self.offset + size > len(self.data):
				raise ValueError("Not enough data left to write.")

		mv = memoryview(self.data)[self.offset:self.offset + size]
		memmove(addressof(c_char.from_buffer(mv)), addressof(struct_data), size)
		self.offset += size


	def seek(self, new_offset: int) -> None:
		"""Progress the offset to a new location."""
		self.offset = new_offset


	def tell(self) -> int:
		"""Current offset location."""
		return self.offset


	def get_data(self) -> bytes:
		"""Get bytearray data as immutable bytes."""
		return bytes(self.data)
