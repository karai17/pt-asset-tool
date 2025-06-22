import os

from pathlib import Path

from pt.patch import bmp, tga, wav
from pt.decode import inx, smd
from pt.encode import json, gltf
from pt.encode import png

from app.utils import ftime, now


def _encode(outpath: str, fdata, encode_png: bool):
	if encode_png:
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


def patch_bmp(bucket: list, indir: str, outdir: str, encode_png: bool):
	""" Patch all of the BMP files. """

	print(f"Patching {len(bucket)} BMP files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(indir, filepath)
		outpath = os.path.join(outdir, filepath)
		fdata = bmp.patch(inpath)
		_encode(outpath, fdata, encode_png)

	t1 = now()
	print(f"Patched BMP files in {ftime(t0, t1)} seconds.")


def patch_tga(bucket: list, indir: str, outdir: str, encode_png: bool):
	""" Patch all of the TGA files. """

	print(f"Patching {len(bucket)} TGA files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(indir, filepath)
		outpath = os.path.join(outdir, filepath)
		fdata = tga.patch(inpath)
		_encode(outpath, fdata, encode_png)

	t1 = now()
	print(f"Patched TGA files in {ftime(t0, t1)} seconds.")


def patch_wav(bucket: list, indir: str, outdir: str):
	""" Patch all of the WAV files. """

	print(f"Patching {len(bucket)} WAV files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(indir, filepath)
		outpath = os.path.join(outdir, filepath)

		fdata = wav.patch(inpath)

		root, ext = os.path.splitext(outpath)
		outpath = Path(root + ".wav")
		outpath.parent.mkdir(exist_ok=True, parents=True)
		with outpath.open("wb") as f:
			f.write(fdata)

	t1 = now()
	print(f"Patched WAV files in {ftime(t0, t1)} seconds.")


def decode_inx(bucket: list, indir: str, outdir: str, encode_json: bool, encode_gltf: bool, encode_png: bool):
	""" Decode INX config files. """

	print(f"Decoding {len(bucket)} INX files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(indir, filepath)
		outpath = os.path.join(outdir, filepath)

		fdata = inx.decode(inpath)

		if encode_json:
			root, ext = os.path.splitext(outpath)
			jsonpath = Path(root + ".json")
			json.encode(jsonpath, fdata)

		if encode_gltf:
			root, ext = os.path.splitext(outpath)
			gltfpath = Path(root + ".gltf")
			gltf.encode(gltfpath, fdata, encode_png)

	t1 = now()
	print(f"Decoded INX files in {ftime(t0, t1)} seconds.")


def decode_smd(smdbucket: list, inxbucket: list, indir: str, outdir: str, encode_json: bool, encode_gltf: bool, encode_png: bool):
	""" Decode SMD model files. """

	bucket = []

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
		inpath = os.path.join(indir, filepath)
		outpath = os.path.join(outdir, filepath)

		fdata = smd.decode(inpath)

		if encode_json:
			root, ext = os.path.splitext(outpath)
			jsonpath = Path(root + ".json")
			json.encode(jsonpath, fdata)

		if encode_gltf:
			root, ext = os.path.splitext(outpath)
			gltfpath = Path(root + ".gltf")
			gltf.encode(gltfpath, fdata, encode_png)

	t1 = now()
	print(f"Decoded SMD files in {ftime(t0, t1)} seconds.")
