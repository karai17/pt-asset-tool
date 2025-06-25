import os

from collections.abc import Callable
from pathlib import Path

from pt.pdef import *
from pt.decode import spc, spm, spp
from pt.encode import json

from app.utils import ftime, now


def _decode(bucket: list[str], indir: str, decode: Callable[[str], list]) -> tuple[dict[str, list], list[str]]:
	data = {}
	stages = []

	for filepath in bucket:
		segments = filepath.split(os.path.sep)
		aseroot, ext = os.path.splitext(segments[-1])
		root, ext = os.path.splitext(aseroot)
		stages.append(root.casefold())

		inpath = os.path.join(indir, filepath)
		data[stages[-1]] = decode(inpath)

	return data, stages


def decode_spc(bucket: list[str], indir: str) -> tuple[dict[str, list[PTServerSpawnCharacter]], list[str]]:
	"""Decode SPC character spawn files."""
	print(f"Decoding {len(bucket)} SPC files...")
	t0 = now()
	data, stages = _decode(bucket, indir, spc.decode)
	t1 = now()
	print(f"Decoded SPC files in {ftime(t0, t1)} seconds.")
	return data, stages


def decode_spm(bucket: list[str], indir: str) -> tuple[dict[str, PTServerSpawnMonster], list[str]]:
	"""Decode SPM monster spawn config files."""
	print(f"Decoding {len(bucket)} SPM files...")
	t0 = now()
	data, stages = _decode(bucket, indir, spm.decode)
	t1 = now()
	print(f"Decoded SPM files in {ftime(t0, t1)} seconds.")
	return data, stages


def decode_spp(bucket: list[str], indir: str) -> tuple[dict[str, list[PTServerSpawnPoint]], list[str]]:
	"""Decode SPP spawn point files."""
	print(f"Decoding {len(bucket)} SPP files...")
	t0 = now()
	data, stages = _decode(bucket, indir, spp.decode)
	t1 = now()
	print(f"Decoded SPP files in {ftime(t0, t1)} seconds.")
	return data, stages


def decode_stages(spcbucket: list[str], spmbucket: list[str], sppbucket: list[str], indir: str, outdir: str) -> None:
		"""Decode server data for all stages and export to JSON file."""
		server = PTServerStages()

		# get data from stages
		spcdata, spcstages = decode_spc(spcbucket, indir)
		spmdata, spmstages = decode_spm(spmbucket, indir)
		sppdata, sppstages = decode_spp(sppbucket, indir)

		# build full dataset
		allstages = sorted(list(dict.fromkeys(spcstages + spmstages + sppstages)))
		for stage in allstages:
			s = PTServerStage()

			if stage in spcdata:
				s.characters = spcdata[stage]

			if stage in spmdata:
				data = spmdata[stage]
				s.max_monsters = data.max_monsters
				s.spawn_interval_min = data.spawn_interval_min
				s.spawn_interval_max = data.spawn_interval_max
				s.max_monsters_per_point = data.max_monsters_per_point
				s.monsters = data.monsters
				s.bosses = data.bosses

			if stage in sppdata:
				s.spawn_points = sppdata[stage]

			server.stages[stage] = s

		# export to json file at root of outdir
		jsonpath = Path(os.path.join(outdir, "server_stages.json"))
		json.encode(jsonpath, server)
