import multiprocessing as mp
import os

from argparse import Namespace
from pathlib import Path

from pt.decode import inx, smd, part, luascript, animdata
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


def _resolve_output_png(args: Namespace, model_path: str) -> Path | None:
	"""Locates the PNG the texture stage wrote for a model-referenced texture.
	Texture files mirror their input-tree location under args.output with a
	lowercased .png name, while model texture paths are the engine's own
	(possibly differently-cased) strings - the engine resolved them
	case-insensitively on Windows, so the lookup does too, falling back to a
	flat output root for fixture layouts."""
	rel = (os.path.splitext(model_path.replace("\\", os.path.sep))[0] + ".png")
	candidate = Path(os.path.join(args.output, rel))
	if candidate.is_file():
		return candidate

	segs = Path(rel).parts
	cur = Path(args.output)
	for seg in segs[:-1]:
		match = [d for d in cur.iterdir() if d.is_dir() and d.name.lower() == seg.lower()]
		if not match:
			cur = None
			break
		cur = match[0]
	if cur is not None:
		match = [f for f in cur.iterdir() if f.is_file() and f.name.lower() == segs[-1].lower()]
		if match:
			return match[0]

	for f in Path(args.output).iterdir():
		if f.is_file() and f.name.lower() == segs[-1].lower():
			return f
	return None


def _compose_model_opacity(fdata, args: Namespace) -> None:
	"""Pre-computes the PNGs the engine would build at texture load time for
	materials whose diffuse runs through LoadDibSurfaceAlpha (smTexture.cpp:
	2247): the diffuse composited with its *MAP_OPACITY bitmap as the alpha
	channel. png.compose encodes the engine's own graceful degradation (a
	32bpp diffuse keeps its own alpha, a missing/wrong-sized alpha file stays
	opaque), so only diffuse-derivable outputs are rewritten - over the
	diffuse's own name, because the glTF encoder binds textures by name and
	must not care whether the PNG's alpha is authored or composited. The
	source .bmp/.tga outputs stay untouched for ASE round-tripping."""
	if not args.png or not fdata.materials:
		return

	for material in fdata.materials:
		tm = material.texture_map
		if not tm or not tm.opacity_name:
			continue

		pairs = []
		if tm.diffuse_path:
			pairs.append((tm.diffuse_path, tm.opacity_path))
		for k, frame in enumerate(tm.anim_frames or []):
			alpha = tm.anim_alphas[k] if k < len(tm.anim_alphas or []) and tm.anim_alphas[k] else frame
			pairs.append((frame, alpha))

		for diffuse, alpha in pairs:
			png_out = _resolve_output_png(args, diffuse)
			if png_out is None:
				continue

			if alpha and alpha.lower() != diffuse.lower():
				src = _resolve_output_png(args, alpha)
				if src is None:
					continue
			else:
				src = png_out

			png.compose(png_out, src, png_out)


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
	_compose_model_opacity(fdata, args)
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
	_compose_model_opacity(fdata, args)
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


def _decode_part_file(job: tuple) -> None:
	filepath, args = job
	inpath = os.path.join(args.input, filepath)
	outpath = os.path.join(args.output, filepath)
	fdata = part.decode(inpath)

	root, _ = os.path.splitext(outpath)

	if args.json:
		json.encode(Path(root + ".json"), fdata)


def decode_part(bucket: list, args: Namespace) -> None:
	"""Decode .part particle scripts."""
	print(f"Decoding {len(bucket)} particle scripts...")
	t0 = now()

	_parallel_map(_decode_part_file, [(filepath, args) for filepath in bucket], args.jobs)

	t1 = now()
	print(f"Decoded particle scripts in {ftime(t0, t1)} seconds.")


def _decode_luascript_file(job: tuple) -> None:
	filepath, args = job
	inpath = os.path.join(args.input, filepath)
	outpath = os.path.join(args.output, filepath)
	fdata = luascript.decode(inpath)

	root, _ = os.path.splitext(outpath)

	if args.json:
		json.encode(Path(root + ".json"), fdata)


def decode_luascript(bucket: list, args: Namespace) -> None:
	"""Decode NewEffect .lua effect scripts."""
	print(f"Decoding {len(bucket)} effect scripts...")
	t0 = now()

	_parallel_map(_decode_luascript_file, [(filepath, args) for filepath in bucket], args.jobs)

	t1 = now()
	print(f"Decoded effect scripts in {ftime(t0, t1)} seconds.")


def _decode_animdata_file(job: tuple) -> None:
	filepath, args = job
	inpath = os.path.join(args.input, filepath)
	outpath = os.path.join(args.output, filepath)
	fdata = animdata.decode(inpath)

	root, _ = os.path.splitext(outpath)

	if args.json:
		json.encode(Path(root + ".json"), fdata)


def decode_animdata(bucket: list, args: Namespace) -> None:
	"""Decode HoAnimData image/sequence INI files."""
	print(f"Decoding {len(bucket)} animation data files...")
	t0 = now()

	_parallel_map(_decode_animdata_file, [(filepath, args) for filepath in bucket], args.jobs)

	t1 = now()
	print(f"Decoded animation data files in {ftime(t0, t1)} seconds.")
