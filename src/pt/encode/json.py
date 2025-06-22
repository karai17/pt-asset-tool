from dataclasses import asdict, is_dataclass
from json import JSONEncoder, dumps
from pathlib import Path


class CustomEncoder(JSONEncoder):
	def default(self, obj):
		if is_dataclass(obj):
			return asdict(obj)
		return super().default(obj)


def encode(path: Path, data: bytes):
	jsondata = dumps(data, cls=CustomEncoder, ensure_ascii=False, indent=2)
	path.parent.mkdir(exist_ok=True, parents=True)
	with open(path, "w") as f:
		f.write(jsondata)
