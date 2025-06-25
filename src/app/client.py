import os

from argparse import Namespace
from pathlib import Path

from pt.patch import bmp, tga, wav
from pt.decode import inx, smd
from pt.encode import json, gltf
from pt.encode import png

from app.utils import ftime, now


def _encode(outpath: str, fdata: bytes, args: Namespace) -> None:
	if args.png:
		segments = outpath.split(os.path.sep)
		root, ext = os.path.splitext(segments[-1])
		segments[-1] = (root + ".png").lower()
		pngpath = Path(os.path.sep.join(segments))
		png.encode(pngpath, fdata)
	else:
		outpath = Path(outpath)
		outpath.parent.mkdir(exist_ok=True, parents=True)
		with outpath.open("wb") as f:
			f.write(fdata)


def patch_bmp(bucket: list, args: Namespace) -> None:
	"""Patch all of the BMP files."""
	print(f"Patching {len(bucket)} BMP files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(args.input, filepath)
		outpath = os.path.join(args.output, filepath)
		fdata = bmp.patch(inpath)
		_encode(outpath, fdata, args)

	t1 = now()
	print(f"Patched BMP files in {ftime(t0, t1)} seconds.")


def patch_tga(bucket: list, args: Namespace) -> None:
	"""Patch all of the TGA files."""
	print(f"Patching {len(bucket)} TGA files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(args.input, filepath)
		outpath = os.path.join(args.output, filepath)
		fdata = tga.patch(inpath)
		_encode(outpath, fdata, args)

	t1 = now()
	print(f"Patched TGA files in {ftime(t0, t1)} seconds.")


def patch_wav(bucket: list, args: Namespace) -> None:
	"""Patch all of the WAV files."""
	print(f"Patching {len(bucket)} WAV files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(args.input, filepath)
		outpath = os.path.join(args.output, filepath)
		fdata = wav.patch(inpath)

		root, ext = os.path.splitext(outpath)
		outpath = Path(root + ".wav")
		outpath.parent.mkdir(exist_ok=True, parents=True)
		with outpath.open("wb") as f:
			f.write(fdata)

	t1 = now()
	print(f"Patched WAV files in {ftime(t0, t1)} seconds.")


def decode_inx(bucket: list, args: Namespace) -> None:
	"""Decode INX config files."""
	print(f"Decoding {len(bucket)} INX files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(args.input, filepath)
		outpath = os.path.join(args.output, filepath)
		fdata = inx.decode(inpath)

		if args.json:
			root, ext = os.path.splitext(outpath)
			jsonpath = Path(root + ".json")
			json.encode(jsonpath, fdata)

		if args.gltf:
			root, ext = os.path.splitext(outpath)
			gltfpath = Path(root + ".gltf")
			gltf.encode(gltfpath, fdata, args)

	t1 = now()
	print(f"Decoded INX files in {ftime(t0, t1)} seconds.")


def decode_smd(smdbucket: list, inxbucket: list, args: Namespace) -> None:
	"""Decode SMD model files."""
	bucket = []

	# FIXME: instead of the name of the inx file we need to check the name of the
	# smd file that the inx file points to!

	for smdpath in smdbucket:
		found = False
		root, ext = os.path.splitext(smdpath)

		for inxpath in inxbucket:
			if root in inxpath:
				found = True
				break

		if not found:
			bucket.append(smdpath)

	print(f"Decoding {len(bucket)} SMD files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(args.input, filepath)
		outpath = os.path.join(args.output, filepath)
		fdata = smd.decode(inpath)

		if args.json:
			root, ext = os.path.splitext(outpath)
			jsonpath = Path(root + ".json")
			json.encode(jsonpath, fdata)

		if args.gltf:
			root, ext = os.path.splitext(outpath)
			gltfpath = Path(root + ".gltf")
			gltf.encode(gltfpath, fdata, args)

	t1 = now()
	print(f"Decoded SMD files in {ftime(t0, t1)} seconds.")
