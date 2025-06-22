import io

from pathlib import Path
from PIL import Image


def encode(filepath: Path, filedata: bytes):
	try:
			filepath.parent.mkdir(exist_ok=True, parents=True)
			with Image.open(io.BytesIO(filedata)) as img:
				img.load()
				img.save(filepath, format="PNG")
	except Exception as e:
			print(f"Failed to encode image: {str(e)}")
