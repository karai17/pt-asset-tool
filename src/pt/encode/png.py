import io

import numpy as np
from pathlib import Path
from PIL import Image


def encode(filepath: Path, filedata: bytes) -> None:
	"""Encodes texture data to a PNG file and writes it to disk."""
	try:
			filepath.parent.mkdir(exist_ok=True, parents=True)
			with Image.open(io.BytesIO(filedata)) as img:
				img.load()
				img.save(filepath, format="PNG")
	except Exception as e:
			print(f"Failed to encode image: {str(e)}")


def compose(diffuse_path: Path, alpha_path: Path, out_path: Path) -> bool:
	"""
	Writes the PNG a glTF should bind for a diffuse whose engine load
	path runs through LoadDibSurfaceAlpha (smTexture.cpp:2247): the diffuse
	with the *MAP_OPACITY bitmap as its alpha channel. A 32bpp diffuse keeps
	its own alpha and the alpha file is never read; a 24-bit one takes the
	alpha file's raw 8-bit byte, or (r+g+b)/3 of 24/32-bit files. A missing,
	unloadable or wrong-sized alpha file leaves alpha at 255
	(AlphaBitCnt = 0 matches no case) — declining the composite is the
	engine's own graceful degradation, and the caller keeps the plain PNG.
	"""
	try:
		diffuse = Image.open(diffuse_path)
		diffuse.load()
	except Exception:
		return False
	if "A" in diffuse.getbands():
		return False
	try:
		alpha = Image.open(alpha_path)
		alpha.load()
	except Exception:
		return False
	if alpha.size != diffuse.size:
		return False
	rgb = np.array(diffuse.convert("RGB"))
	raw = np.array(alpha)
	if alpha.mode in ("P", "L"):
		a = raw
	elif alpha.mode in ("RGB", "RGBA"):
		a = (raw[..., :3].astype(np.uint32).sum(axis = 2) // 3).astype(np.uint8)
	else:
		a = np.array(alpha.convert("L"))
	out_path.parent.mkdir(exist_ok=True, parents=True)
	Image.fromarray(np.dstack([rgb, a]), "RGBA").save(out_path, format="PNG")
	return True
