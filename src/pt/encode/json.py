from dataclasses import asdict, is_dataclass
from json import JSONEncoder, dump
from pathlib import Path


class CustomEncoder(JSONEncoder):
	def default(self, obj):
		if is_dataclass(obj):
			return asdict(obj)
		return super().default(obj)


def encode(path: Path, data) -> None:
	"""Encodes a data structure to a JSON file and writes it to disk."""
	path.parent.mkdir(exist_ok=True, parents=True)
	with path.open("w", encoding="utf-8") as f:
		dump(data, f, cls=CustomEncoder, ensure_ascii=False, indent=2)
