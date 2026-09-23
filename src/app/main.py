import argparse
import os

from app.client import *
from app.server import *
from app.utils import trailing_slash


buckets = {
	# texture
	".bmp": [],
	".tga": [],
	# audio
	".wav": [],
	# model
	".inx": [],
	".smd": [],
	# effect
	".part": [],
	".lua": [],
	".ini": [],
	# server
	".spc": [],
	".spm": [],
	".spp": [],
	".inf": [],
	".npc": [],
	".txt": [],
}


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("-i", "--input")
	parser.add_argument("-o", "--output")
	parser.add_argument("-t", "--texture", action="store_true")
	parser.add_argument("-a", "--audio", action="store_true")
	parser.add_argument("-m", "--model", action="store_true")
	parser.add_argument("-s", "--server", action="store_true")
	parser.add_argument("-e", "--effect", action="store_true")
	parser.add_argument("-p", "--png", action="store_true")
	parser.add_argument("-j", "--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
	parser.add_argument("-g", "--gltf", action="store_true")
	parser.add_argument("-b", "--glb", action="store_true")
	parser.add_argument("--ase", action="store_true")
	parser.add_argument("--godot", action="store_true")
	parser.add_argument("--debug", action="store_true")
	args = parser.parse_args()

	if args.input:
		args.input = trailing_slash(args.input)

	if args.output:
		args.output = trailing_slash(args.output)

	# walk through all of the files in the game client and bucket them by filetype
	for dirpath, dirnames, filenames in os.walk(args.input):
		for filename in filenames:
			relpath = dirpath[len(args.input):]
			filepath = os.path.join(relpath, filename)

			base, ext = os.path.splitext(filename)
			filetype = ext.casefold()

			if filetype in buckets.keys():
				buckets[filetype].append(filepath)
			elif filetype == ".bgm":
				buckets[".wav"].append(filepath)

	if args.texture:
		patch_bmp(buckets[".bmp"], args)
		patch_tga(buckets[".tga"], args)
	if args.audio:
		patch_wav(buckets[".wav"], args)
	if args.model:
		decode_inx(buckets[".inx"], args)
		decode_smd(buckets[".smd"], buckets[".inx"], args)
	if args.ase:
		encode_ase(buckets[".inx"], buckets[".smd"], args)
	if args.effect:
		decode_part(buckets[".part"], args)
		decode_luascript([f for f in buckets[".lua"]], args)
		decode_animdata(
			[f for f in buckets[".ini"] if f.startswith("Effect") and
				("AnimationData" in f or "ImageData" in f or "ObjAnimationData" in f or "Etc" in f)],
			args)
	if args.server:
		decode_stages(buckets[".spc"], buckets[".spm"], buckets[".spp"], args)
		decode_inf(buckets[".inf"], args)
		decode_npc(buckets[".npc"], args)
		decode_txt(buckets[".txt"], args)
