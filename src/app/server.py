import os

from argparse import Namespace
from collections.abc import Callable
from pathlib import Path

from pt.pdef import *
from pt.decode import spc, spm, spp, inf, npc, txt
from pt.encode import json

from app.utils import ftime, now


def _decode(bucket: list[str], args: Namespace, decode: Callable[[str], list]) -> tuple[dict[str, list], list[str]]:
	data = {}
	stages = []

	for filepath in bucket:
		segments = filepath.split(os.path.sep)
		aseroot, ext = os.path.splitext(segments[-1])
		root, ext = os.path.splitext(aseroot)
		stages.append(root.casefold())

		inpath = os.path.join(args.input, filepath)
		data[stages[-1]] = decode(inpath)

	return data, stages


def decode_spc(bucket: list[str], args: Namespace) -> tuple[dict[str, list[PTServerSpawnCharacter]], list[str]]:
	"""Decode SPC character spawn files."""
	print(f"Decoding {len(bucket)} SPC files...")
	t0 = now()
	data, stages = _decode(bucket, args, spc.decode)
	t1 = now()
	print(f"Decoded SPC files in {ftime(t0, t1)} seconds.")
	return data, stages


def decode_spm(bucket: list[str], args: Namespace) -> tuple[dict[str, PTServerSpawnMonster], list[str]]:
	"""Decode SPM monster spawn config files."""
	print(f"Decoding {len(bucket)} SPM files...")
	t0 = now()
	data, stages = _decode(bucket, args, spm.decode)
	t1 = now()
	print(f"Decoded SPM files in {ftime(t0, t1)} seconds.")
	return data, stages


def decode_spp(bucket: list[str], args: Namespace) -> tuple[dict[str, list[PTServerSpawnPoint]], list[str]]:
	"""Decode SPP spawn point files."""
	print(f"Decoding {len(bucket)} SPP files...")
	t0 = now()
	data, stages = _decode(bucket, args, spp.decode)
	t1 = now()
	print(f"Decoded SPP files in {ftime(t0, t1)} seconds.")
	return data, stages


def decode_inf(bucket: list[str], args: Namespace) -> None:
	"""Decode INF monster definition files and export each to JSON."""
	print(f"Decoding {len(bucket)} INF files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(args.input, filepath)
		outpath = os.path.join(args.output, filepath)
		data = inf.decode(inpath)

		root, ext = os.path.splitext(outpath)
		jsonpath = Path(root + ".json")
		json.encode(jsonpath, data)

	t1 = now()
	print(f"Decoded INF files in {ftime(t0, t1)} seconds.")


def decode_npc(bucket: list[str], args: Namespace) -> None:
	"""Decode NPC definition files and export each to JSON."""
	print(f"Decoding {len(bucket)} NPC files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(args.input, filepath)
		outpath = os.path.join(args.output, filepath)
		data = npc.decode(inpath)

		root, ext = os.path.splitext(outpath)
		jsonpath = Path(root + ".json")
		json.encode(jsonpath, data)

	t1 = now()
	print(f"Decoded NPC files in {ftime(t0, t1)} seconds.")


def decode_txt(bucket: list[str], args: Namespace) -> None:
	"""Decode TXT item definition files and export each to JSON."""
	print(f"Decoding {len(bucket)} TXT files...")
	t0 = now()

	for filepath in bucket:
		inpath = os.path.join(args.input, filepath)
		outpath = os.path.join(args.output, filepath)
		data = txt.decode(inpath)

		root, ext = os.path.splitext(outpath)
		jsonpath = Path(root + ".json")
		json.encode(jsonpath, data)

	t1 = now()
	print(f"Decoded TXT files in {ftime(t0, t1)} seconds.")


def decode_stages(spcbucket: list[str], spmbucket: list[str], sppbucket: list[str], args: Namespace) -> None:
		"""Decode server data for all stages and export to JSON file."""
		server = PTServerStages()

		# get data from stages
		spcdata, spcstages = decode_spc(spcbucket, args)
		spmdata, spmstages = decode_spm(spmbucket, args)
		sppdata, sppstages = decode_spp(sppbucket, args)

		# build full dataset
		allstages = sorted(list(dict.fromkeys(spcstages + spmstages + sppstages)))
		for stage in allstages:
			s = PTServerStage()

			if stage in spcdata:
				s.characters = spcdata[stage]

			if stage in spmdata:
				data = spmdata[stage]
				s.max_monsters = data.max_monsters
				s.spawn_interval = data.spawn_interval
				s.spawn_interval_time = data.spawn_interval_time
				s.max_monsters_per_point = data.max_monsters_per_point
				s.monsters = data.monsters
				s.bosses = data.bosses

			if stage in sppdata:
				s.spawn_points = sppdata[stage]

			server.stages[stage] = s

		# export to json file at root of outdir
		jsonpath = Path(os.path.join(args.output, "server_stages.json"))
		json.encode(jsonpath, server)
