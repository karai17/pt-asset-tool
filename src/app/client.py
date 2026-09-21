import multiprocessing as mp
import os

from argparse import Namespace
from pathlib import Path

from pt.decode import inx, smd
from pt.encode import json, gltf, png
from pt.patch import bmp, tga, wav
from pt.utils import decode_string

from app.utils import ftime, now


def _encode_image(outpath: str, fdata: bytes, args: Namespace) -> None:
	if args.png:
		segments = outpath.split(os.path.sep)
		root, ext = os.path.splitext(segments[-1])
		segments[-1] = (root + ".png").lower()
		pngpath = Path(os.path.sep.join(segments))
		png.encode(pngpath, fdata)
	else:
		dstpath = Path(outpath)
		dstpath.parent.mkdir(exist_ok=True, parents=True)
		with dstpath.open("wb") as f:
			f.write(fdata)


def _referenced_models(inxbucket: list, args: Namespace) -> set[str]:
	"""Collect the SMD files referenced by the INX bucket via szModelFile."""
	referenced = set()

	for filepath in inxbucket:
		inpath = os.path.join(args.input, filepath)
		with open(inpath, "rb") as f:
			modelfilename = decode_string(f.read(64))
		if not modelfilename:
			continue
		modelpath, _ = os.path.splitext(modelfilename.replace("\\", os.path.sep))
		referenced.add((modelpath + ".smd").casefold())

	return referenced


def _parallel_map(worker, jobs: list[tuple], processes: int) -> None:
	if processes <= 1 or len(jobs) < 2:
		for job in jobs:
			worker(job)
		return

	try:
		context = mp.get_context("fork")
	except ValueError:
		context = mp.get_context()

	with context.Pool(processes=processes) as pool:
		for _ in pool.imap_unordered(worker, jobs, chunksize=1):
			pass


def _patch_bmp_file(job: tuple) -> None:
	filepath, args = job
	inpath = os.path.join(args.input, filepath)
	outpath = os.path.join(args.output, filepath)
	fdata = bmp.patch(inpath)
	_encode_image(outpath, fdata, args)


def patch_bmp(bucket: list, args: Namespace) -> None:
	"""Patch all of the BMP files."""
	print(f"Patching {len(bucket)} BMP files...")
	t0 = now()

	_parallel_map(_patch_bmp_file, [(filepath, args) for filepath in bucket], args.jobs)

	t1 = now()
	print(f"Patched BMP files in {ftime(t0, t1)} seconds.")


def _patch_tga_file(job: tuple) -> None:
	filepath, args = job
	inpath = os.path.join(args.input, filepath)
	outpath = os.path.join(args.output, filepath)
	fdata = tga.patch(inpath)
	_encode_image(outpath, fdata, args)


def patch_tga(bucket: list, args: Namespace) -> None:
	"""Patch all of the TGA files."""
	print(f"Patching {len(bucket)} TGA files...")
	t0 = now()

	_parallel_map(_patch_tga_file, [(filepath, args) for filepath in bucket], args.jobs)

	t1 = now()
	print(f"Patched TGA files in {ftime(t0, t1)} seconds.")


def _patch_wav_file(job: tuple) -> None:
	filepath, args = job
	inpath = os.path.join(args.input, filepath)
	outpath = os.path.join(args.output, filepath)
	fdata = wav.patch(inpath)

	root, ext = os.path.splitext(outpath)
	outpath = Path(root + ".wav")
	outpath.parent.mkdir(exist_ok=True, parents=True)
	with outpath.open("wb") as f:
		f.write(fdata)


def patch_wav(bucket: list, args: Namespace) -> None:
	"""Patch all of the WAV files."""
	print(f"Patching {len(bucket)} WAV files...")
	t0 = now()

	_parallel_map(_patch_wav_file, [(filepath, args) for filepath in bucket], args.jobs)

	t1 = now()
	print(f"Patched WAV files in {ftime(t0, t1)} seconds.")


def _decode_inx_file(job: tuple) -> None:
	filepath, args = job
	inpath = os.path.join(args.input, filepath)
	outpath = os.path.join(args.output, filepath)
	fdata = inx.decode(inpath, args.input)

	if not fdata:
		print(f"Invalid INX file: {filepath}")
		return

	root, _ = os.path.splitext(outpath)

	if args.json:
		json.encode(Path(root + ".json"), fdata)
	if args.gltf or args.glb:
		doc = gltf.build(fdata, args, Path(outpath))

		if doc is not None:
			if args.gltf:
				gltf.write(Path(root + ".gltf"), doc)
			if args.glb:
				gltf.write(Path(root + ".glb"), doc)


def decode_inx(bucket: list, args: Namespace) -> None:
	"""Decode INX config files."""
	print(f"Decoding {len(bucket)} INX files...")
	t0 = now()

	_parallel_map(_decode_inx_file, [(filepath, args) for filepath in bucket], args.jobs)

	t1 = now()
	print(f"Decoded INX files in {ftime(t0, t1)} seconds.")


def _decode_smd_file(job: tuple) -> None:
	filepath, args = job
	inpath = os.path.join(args.input, filepath)
	outpath = os.path.join(args.output, filepath)
	fdata = smd.decode(inpath)

	if not fdata:
		print(f"Invalid SMD file: {filepath}")
		return

	root, _ = os.path.splitext(outpath)

	if args.json:
		json.encode(Path(root + ".json"), fdata)
	if args.gltf or args.glb:
		doc = gltf.build(fdata, args, Path(outpath))

		if doc is not None:
			if args.gltf:
				gltf.write(Path(root + ".gltf"), doc)
			if args.glb:
				gltf.write(Path(root + ".glb"), doc)


def decode_smd(smdbucket: list, inxbucket: list, args: Namespace) -> None:
	"""Decode SMD model files."""
	referenced = _referenced_models(inxbucket, args)
	bucket = [filepath for filepath in smdbucket if filepath.casefold() not in referenced]
	print(f"Decoding {len(bucket)} SMD files...")
	t0 = now()

	_parallel_map(_decode_smd_file, [(filepath, args) for filepath in bucket], args.jobs)

	t1 = now()
	print(f"Decoded SMD files in {ftime(t0, t1)} seconds.")
