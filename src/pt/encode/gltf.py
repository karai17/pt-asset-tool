import base64
import numpy as np
import os

from argparse import Namespace
from ctypes import *
from dataclasses import asdict
from pathlib import Path
from PIL import Image as PILImage
from pygltflib import (
	GLTF2,
	Accessor,
	Animation,
	AnimationChannel,
	AnimationChannelTarget,
	Buffer,
	BufferView,
	Image,
	Material,
	Mesh,
	Node,
	PbrMetallicRoughness,
	Primitive,
	Sampler,
	Scene,
	Skin,
	Texture,
	TextureInfo,
	ARRAY_BUFFER,
	FLOAT,
	UNSIGNED_BYTE
)

from pt.cdef import *
from pt.pdef import *
from pt.const import EPSILON, SCALE_INCH_TO_METER
from pt.buffer import BufferReader
from pt.utils import (
	to_np_matrix,
	from_np_matrix,
	to_np_vector,
	from_np_vector,
	trs_to_np_matrix,
	matrix_to_quaternion,
	get_filename,
	normalize_face,
	multiply_quaternions,
	lerp_vector
)


""" ANIMATIONS """


def encode_uv_animation(gltf: GLTF2, anim: dict, node_ids: list[int]) -> None:
	"""
	Export one flipbook as a KHR_texture_transform uv animation walking the
	atlas rects in frame order (the engine swaps whole textures, not uv offsets;
	glTF uv animation is the portable equivalent). Base time matches the
	renderer: RendStatTime is the Win32 tick count in ms and Shift_FrameSpeed
	the right shift, so each frame lasts 2^speed ms. Mismatched per-frame
	durations would need non-uniform keys; all shipped data runs at a constant
	2^Shift_FrameSpeed ms (FrameMask = count-1 anim2..anim16,
	smRend3d.cpp:3852-3854).

	node_ids: mesh node ids carrying the animated primitive. The transform
	rides the channel target's KHR_texture_transform extension, which glTF
	defines only on TextureInfo.
	"""
	if not node_ids:
		return

	duration = (1 << anim["speed"]) * anim["count"] / 1000

	times = BufferReader(4 * (anim["count"] + 1))
	values = BufferReader(4 * 6 * (anim["count"] + 1))

	for k in range(anim["count"]):
		times.write(c_float(k * (1 << anim["speed"]) / 1000))
		rect = anim["rects"][k]
		values.write((c_float*6)(
			rect[0], 1 - rect[1] - rect[3],
			rect[2], rect[3],
			0, 0
		))

	times.write(c_float(duration))
	values.write((c_float*6)(
		anim["offset"][0], anim["offset"][1],
		anim["scale"][0], anim["scale"][1],
		0, 0
	))

	gltf.buffers.append(Buffer(
		uri = "data:application/octet-stream;base64," + base64.b64encode(times.get_data()).decode(),
		byteLength = len(times.data)
	))

	gltf.bufferViews.append(BufferView(
		buffer = len(gltf.buffers)-1,
		byteLength = len(times.data)
	))

	gltf.accessors.append(Accessor(
		bufferView = len(gltf.bufferViews)-1,
		componentType = FLOAT,
		count = anim["count"] + 1,
		type = "SCALAR",
		min = [ 0 ],
		max = [ duration ]
	))

	input_accessor = len(gltf.accessors)-1

	gltf.buffers.append(Buffer(
		uri = "data:application/octet-stream;base64," + base64.b64encode(values.get_data()).decode(),
		byteLength = len(values.data)
	))

	gltf.bufferViews.append(BufferView(
		buffer = len(gltf.buffers)-1,
		byteLength = len(values.data)
	))

	gltf.accessors.append(Accessor(
		bufferView = len(gltf.bufferViews)-1,
		componentType = FLOAT,
		count = anim["count"] + 1,
		type = "VEC3"
	))

	output_accessor = len(gltf.accessors)-1

	gltf.extensionsUsed.append("KHR_texture_transform")

	gltf_animation = next((ani for ani in gltf.animations if ani.name == "tex-anim"), None)
	if gltf_animation is None:
		gltf_animation = Animation(name = "tex-anim")
		gltf.animations.insert(0, gltf_animation)

	for node_id in node_ids:
		gltf_animation.samplers.append(Sampler(
			input = input_accessor,
			output = output_accessor
		))

		gltf_animation.channels.append(AnimationChannel(
			sampler = len(gltf_animation.samplers)-1,
			target = AnimationChannelTarget(
				node = node_id,
				path = "uv",
				extensions = { "KHR_texture_transform": { "index": anim["texture"] } }
			)
		))


# loop through list of key frames and fill in any frame gaps with new key frames
def fill_animation_frames(transform: PTActorAnimation) -> None:
	"""Fill in animation frames between key frames."""
	if len(transform.rotation) > 0:
		new_frames = []
		ptfm = None

		for tfm in transform.rotation:
			if ptfm:
				pframe = int(ptfm.frame / 160)
				cframe = int(tfm.frame / 160)

				# if there are gaps between frames, fill them in with origin transforms.
				# Each rotation frame is a delta from the previous so we just want to
				# pad out the frame count without changing the frame stack.
				if cframe > pframe+1:
					for f in range(pframe+1, cframe):
						new_frames.append(PTAnimationRotation(0, 0, 0, 1, f * 160))

			ptfm = tfm

		transform.rotation += new_frames
		transform.rotation.sort(key=lambda a: a.frame)


	if len(transform.position) > 0:
		new_frames = []
		ptfm = None

		for tfm in transform.position:
			if ptfm:
				pframe = int(ptfm.frame / 160)
				cframe = int(tfm.frame / 160)

				# if there are gaps between frames, fill them in
				if cframe > pframe+1:
					for f in range(pframe+1, cframe):
						ntfm = lerp_vector(ptfm, tfm, (f-pframe) / (cframe-pframe))
						ntfm.frame = f * 160
						new_frames.append(ntfm)

			ptfm = tfm

		transform.position += new_frames
		transform.position.sort(key=lambda a: a.frame)


	if len(transform.scale) > 0:
		new_frames = []
		ptfm = None

		for tfm in transform.scale:
			if ptfm:
				pframe = int(ptfm.frame / 160)
				cframe = int(tfm.frame / 160)

				# if there are gaps between frames, fill them in
				if cframe > pframe+1:
					for f in range(pframe+1, cframe):
						ntfm = lerp_vector(ptfm, tfm, (f-pframe) / (cframe-pframe))
						ntfm.frame = f * 160
						new_frames.append(ntfm)

			ptfm = tfm

		transform.scale += new_frames
		transform.scale.sort(key=lambda a: a.frame)


# this function is a little clunky because of the variances between the different transforms.
# however, the transforms are similar enough that the majority of the code is duplicate for each.
def get_animation_track(gltf: GLTF2, transforms: list[PTAnimationPosition] | list[PTAnimationRotation] | list[PTAnimationScale], name: str, has_bones: bool = False, animations: list[PTModelMetadata] | None = None) -> PTAnimationSampler:
	"""Get the animation sampler per transform, per animation."""
	rot = name == "rotation"
	pos = name == "position"
	scl = name == "scale"

	if len(transforms) > 0:
		orot = PTQuaternion()

		input_buffer = BufferReader(len(transforms)*4)

		if rot:
			output_buffer = BufferReader(len(transforms)*4*4)
		else:
			output_buffer = BufferReader(len(transforms)*3*4)

		for transform in transforms:
			if rot:
				orot = multiply_quaternions(orot, transform)

			# reset each animation's starting frame time to 0
			sframe = 0
			if animations:
				for animation in animations:
					if transform.frame / 160 >= animation.start_frame and transform.frame / 160 <= animation.end_frame:
						sframe = animation.start_frame
						break

			input_buffer.write(c_float(transform.frame / 160 / 30 - (sframe / 30)))

			if has_bones:
				if rot:
					output_buffer.write((c_float*4)(
						 orot.x,
						 orot.z,
						-orot.y,
						-orot.w
					))
				if pos:
					output_buffer.write((c_float*3)(
						 transform.x * SCALE_INCH_TO_METER,
						 transform.z * SCALE_INCH_TO_METER,
						-transform.y * SCALE_INCH_TO_METER
					))
				if scl:
					output_buffer.write((c_float*3)(
						transform.x,
						transform.z,
						transform.y
					))
			else:
				if rot:
					output_buffer.write((c_float*4)(
						-orot.x,
						 orot.z,
						 orot.y,
						-orot.w
					))
				if pos:
					output_buffer.write((c_float*3)(
						-transform.x * SCALE_INCH_TO_METER,
						 transform.z * SCALE_INCH_TO_METER,
						 transform.y * SCALE_INCH_TO_METER
					))
				if scl:
					output_buffer.write((c_float*3)(
						transform.x,
						transform.z,
						transform.y
					))

		gltf.buffers.append(Buffer(
			uri = "data:application/octet-stream;base64," + base64.b64encode(input_buffer.get_data()).decode(),
			byteLength = len(input_buffer.get_data())
		))

		gltf.buffers.append(Buffer(
			uri = "data:application/octet-stream;base64," + base64.b64encode(output_buffer.get_data()).decode(),
			byteLength = len(output_buffer.get_data())
		))

		return PTAnimationSampler(
			input = len(gltf.buffers)-2,
			output = len(gltf.buffers)-1
		)


def process_animation_transform(gltf: GLTF2, transform: list, name: str, gltf_animation: Animation, node: int, sampler: PTAnimationSampler, animation: PTMotionMetadata) -> None:
	"""Process animation transforms."""
	rot = name == "rotation"
	pos = name == "translation"
	scl = name == "scale"

	if len(transform) > 0:
		sframe = animation.start_frame if animation else 0
		eframe = animation.end_frame if animation else len(transform)-1
		nframe = eframe - sframe + 1

		fmin = 0
		fmax = (nframe-1) / 30

		gltf.bufferViews.append(BufferView(
			buffer = sampler.input,
			byteOffset = sframe * 4,
			byteLength = nframe * 4
		))

		gltf.accessors.append(Accessor(
			bufferView = len(gltf.bufferViews)-1,
			componentType = FLOAT,
			count = nframe,
			type = "SCALAR",
			min = [ fmin ],
			max = [ fmax ]
		))

		if rot:
			gltf.bufferViews.append(BufferView(
				buffer = sampler.output,
				byteOffset = sframe * 4 * 4,
				byteLength = nframe * 4 * 4
			))

			gltf.accessors.append(Accessor(
				bufferView = len(gltf.bufferViews)-1,
				componentType = FLOAT,
				count = nframe,
				type = "VEC4"
			))

		if pos or scl:
			gltf.bufferViews.append(BufferView(
				buffer = sampler.output,
				byteOffset = sframe * 4 * 3,
				byteLength = nframe * 4 * 3
			))

			gltf.accessors.append(Accessor(
				bufferView = len(gltf.bufferViews)-1,
				componentType = FLOAT,
				count = nframe,
				type = "VEC3"
			))

		gltf_animation.samplers.append(Sampler(
			input = len(gltf.accessors)-2,
			output = len(gltf.accessors)-1,
			wrapS = None,
			wrapT = None
		))

		gltf_animation.channels.append(AnimationChannel(
			sampler = len(gltf_animation.samplers)-1,
			target = AnimationChannelTarget(
				node = node,
				path = name
			)
		))


def process_animation(gltf: GLTF2, transform: PTObjectTransform, name: str, node: int, track, animation: PTMotionMetadata | None = None) -> None:
	"""Process an animation."""
	# NOTE: death animation has 8 more frames than listed in the inx file (for some reason)
	# This may not need to be added back for GLTF, but may be required for ASE.
	# Reference: fileread.cpp::AddModelDecode (Line ~420)
	# if name == "dead":
	# 	animation.end_frame = animation.end_frame + 8

	found = False
	sframe = animation.start_frame if animation else None
	eframe = animation.end_frame if animation else None

	for ani in gltf.animations:
		if ani.name == name and ani.extras["startFrame"] == sframe and ani.extras["endFrame"] == eframe:
			gltf_animation = ani
			found = True
			break

	if not found:
		gltf_animation = Animation(name=name)
		gltf_animation.extras["startFrame"] = sframe
		gltf_animation.extras["endFrame"] = eframe

		if animation:
			gltf_animation.extras["repeat"] = animation.repeat
			gltf_animation.extras["motionFrame"] = animation.motion_frame
			gltf_animation.extras["keyCode"] = animation.key_code
			gltf_animation.extras["itemCodes"] = animation.item_codes
			gltf_animation.extras["jobCodeBit"] = animation.job_code_bit
			gltf_animation.extras["skillCodes"] = animation.skill_codes
			gltf_animation.extras["mapPosition"] = animation.map_position
			gltf_animation.extras["rate"] = animation.rate

	process_animation_transform(gltf, transform.rotation, "rotation", gltf_animation, node, track.rotation, animation)
	process_animation_transform(gltf, transform.position, "translation", gltf_animation, node, track.position, animation)
	process_animation_transform(gltf, transform.scale, "scale", gltf_animation, node, track.scale, animation)

	if not found and len(gltf_animation.channels) > 0:
		gltf.animations.append(gltf_animation)


""" PRIMITIVES """


def make_primitives(object: PTActorObject | PTStageObject, nodes: list[Node], anim_material_ids: set[int] | None = None, overlay_material_ids: set[int] | None = None) -> list[dict[str,]]:
	"""Create a list of untangled primitives."""
	prims = []
	if not object.texture_coords or not object.vertices or not object.faces:
		return prims

	material_faces = {}
	for i, face in enumerate(object.faces):
		if not material_faces.get(face.material_id):
			material_faces[face.material_id] = []
		material_faces[face.material_id].append([i, face])

	for material_id, faces in material_faces.items():
		vert_words = len(faces)*3*4 # 3 vertices per face and we use 32bit (4byte) types
		prim = {
			"material": material_id,
			"count": len(faces)*3,
			"anim_material": material_id in anim_material_ids,
			"positionbuffer": BufferReader(vert_words*3),
			"normalbuffer": BufferReader(vert_words*3),
			"texcoord0buffer": BufferReader(vert_words*2),
			"texcoord1buffer": BufferReader(vert_words*2),
			"texcoord0": True,
			"texcoord1": True,
			"joints0buffer": BufferReader(vert_words),
			"weights0buffer": BufferReader(vert_words*4)
		}

		# the engine redraws these faces with the second stage texture alone in
		# an alpha pass (MapDualRend, smRend3d.cpp:3805-3809, 4105-4115); the
		# overlay prim mirrors that pass with an alpha-masked texture
		overlay_prim = None
		if overlay_material_ids and material_id in overlay_material_ids:
			# TEXCOORD_0 is written too: some importers (Blender) create no uv
			# layer at all for a primitive carrying only TEXCOORD_1
			overlay_prim = {
				"material": material_id,
				"count": 0,
				"anim_material": False,
				"min": None,
				"max": None,
				"positionbuffer": BufferReader(vert_words*3),
				"normalbuffer": BufferReader(vert_words*3),
				"texcoord0buffer": BufferReader(vert_words*2),
				"texcoord1buffer": BufferReader(vert_words*2),
				"texcoord0": True,
				"texcoord1": True,
				"joints0buffer": BufferReader(vert_words),
				"weights0buffer": BufferReader(vert_words*4)
			}

		for iface in faces:
			# POSITION
			vertices = []

			for j in range(3):
				face = iface[1]
				v = object.vertices[face.vertices[j]]

				if hasattr(object, "physique") and object.physique:
					vertex = PTVector3(
						x =  v.x * SCALE_INCH_TO_METER,
						y =  v.z * SCALE_INCH_TO_METER,
						z = -v.y * SCALE_INCH_TO_METER
					)
				else:
					vertex = PTVector3(
						x = -v.x * SCALE_INCH_TO_METER,
						y =  v.z * SCALE_INCH_TO_METER,
						z =  v.y * SCALE_INCH_TO_METER
					)
				vertices.append(vertex)

				if not prim.get("min") or not prim.get("max"):
					prim["min"] = PTVector3(
						x = vertex.x,
						y = vertex.y,
						z = vertex.z
					)

					prim["max"] = PTVector3(
						x = vertex.x,
						y = vertex.y,
						z = vertex.z
					)

				for key, value in asdict(vertex).items():
					setattr(prim["min"], key, min(getattr(prim["min"], key), value))
					setattr(prim["max"], key, max(getattr(prim["max"], key), value))

				prim["positionbuffer"].write((c_float*3)(vertex.x, vertex.y, vertex.z))

			# NORMAL
			v1, v2, v3 = vertices
			normal = normalize_face(v1, v2, v3)
			# TODO: zero length normals suggests that there are degenerate triangles
			# that need to be purged at some point.

			for _ in range(3):
				prim["normalbuffer"].write((c_float*3)(normal.x, normal.y, normal.z))

			# TEXCOORD_0
			# faces with a null lpTexLink_ptr have no texture link (nTexLink < nFace)
			if hasattr(object, "texture_coords") and object.texture_coords and iface[0] < len(object.texture_coords):
				tc = object.texture_coords[iface[0]]
				uv0 = tc.uv_sets[0] if len(tc.uv_sets) > 0 else [PTTextureVertex()] * 3
				uv1 = tc.uv_sets[1] if len(tc.uv_sets) > 1 else [PTTextureVertex()] * 3

				prim["texcoord0buffer"].write((c_float*6)(
					uv0[0].u, 1-uv0[0].v,
					uv0[1].u, 1-uv0[1].v,
					uv0[2].u, 1-uv0[2].v
				))

				# TEXCOORD_1: secondary texture stage UVs (lightmaps over
				# diffuse in the *LM_ dungeon stages) ride the NextTex chain
				prim["texcoord1buffer"].write((c_float*6)(
					uv1[0].u, 1-uv1[0].v,
					uv1[1].u, 1-uv1[1].v,
					uv1[2].u, 1-uv1[2].v
				))

				if len(tc.uv_sets) == 0:
					prim["texcoord0"] = False
					prim["texcoord1"] = False
				elif len(tc.uv_sets) == 1:
					prim["texcoord1"] = False
					prim["texcoord0"] = prim["texcoord0"] and True

				# the overlay pass only covers faces that actually carry a second
				# UV set; the engine alpha-passes exactly those (they ride the
				# NextTex chain). The same UVs fill both slots: glTF requires the
				# indexed semantic set to start at 0 and be continuous, and the
				# overlay material samples slot 1
				if overlay_prim and len(tc.uv_sets) > 1:
					uvs = [
						uv1[0].u, 1-uv1[0].v,
						uv1[1].u, 1-uv1[1].v,
						uv1[2].u, 1-uv1[2].v
					]
					overlay_prim["texcoord0buffer"].write((c_float*6)(*uvs))
					overlay_prim["texcoord1buffer"].write((c_float*6)(*uvs))
					overlay_prim["count"] += 3

					# the engine draws pass 2 at equal depth and wins by LESS-EQUAL
					# compare; depth buffers give no such guarantee for coplanar
					# primitives, so nudge the pass along the face normal instead
					overlay_positions = [
						(vertices[0].x + normal.x*EPSILON, vertices[0].y + normal.y*EPSILON, vertices[0].z + normal.z*EPSILON),
						(vertices[1].x + normal.x*EPSILON, vertices[1].y + normal.y*EPSILON, vertices[1].z + normal.z*EPSILON),
						(vertices[2].x + normal.x*EPSILON, vertices[2].y + normal.y*EPSILON, vertices[2].z + normal.z*EPSILON)
					]
					overlay_prim["positionbuffer"].write((c_float*9)(
						*overlay_positions[0], *overlay_positions[1], *overlay_positions[2]
					))
					for p in overlay_positions:
						if not overlay_prim["min"]:
							overlay_prim["min"] = PTVector3(x=p[0], y=p[1], z=p[2])
							overlay_prim["max"] = PTVector3(x=p[0], y=p[1], z=p[2])
						else:
							overlay_prim["min"].x = min(overlay_prim["min"].x, p[0])
							overlay_prim["min"].y = min(overlay_prim["min"].y, p[1])
							overlay_prim["min"].z = min(overlay_prim["min"].z, p[2])
							overlay_prim["max"].x = max(overlay_prim["max"].x, p[0])
							overlay_prim["max"].y = max(overlay_prim["max"].y, p[1])
							overlay_prim["max"].z = max(overlay_prim["max"].z, p[2])
					overlay_prim["normalbuffer"].write((c_float*9)(
						normal.x, normal.y, normal.z,
						normal.x, normal.y, normal.z,
						normal.x, normal.y, normal.z
					))
			else:
				prim["texcoord0"] = False
				prim["texcoord1"] = False

			# JOINTS_0
			if hasattr(object, "physique") and object.physique:
				for j in range(3):
					face = iface[1]
					bone = object.physique[face.vertices[j]]

					for n, node in enumerate(nodes):
						if bone == node.name:
							prim["joints0buffer"].write((c_ubyte*4)(n, 0, 0, 0))
							break

				# WEIGHTS_0
				prim["weights0buffer"].write((c_float*12)(
					1, 0, 0, 0,
					1, 0, 0, 0,
					1, 0, 0, 0
				))
			else:
				prim["joints0buffer"] = None
				prim["weights0buffer"] = None
				if overlay_prim:
					overlay_prim["joints0buffer"] = None
					overlay_prim["weights0buffer"] = None

		if not prim["min"]:
			prim["min"] = PTVector3()

		if not prim["max"]:
			prim["max"] = PTVector3()

		if prim["count"] > 0:
			prims.append(prim)

		if overlay_prim and overlay_prim["count"] > 0:
			overlay_prim["overlay_material"] = True
			prims.append(overlay_prim)

	return prims


""" GLTF """


ANIM_ATLAS_COLUMNS = 4


def next_pow2(value: int) -> int:
	return 1 << (value - 1).bit_length()


def pack_anim_atlas(paths: list[Path]) -> tuple[list[list[float]], tuple[int, int]]:
	"""Pack flipbook frames into a uniform grid (up to ANIM_ATLAS_COLUMNS per
	row) on a canvas whose width/height are each a power of two. Returns the
	normalized uv rects (x, y, w, h, origin top-left) in frame order plus the
	canvas size. Frame k sits at column k % columns, row k // columns; the uv
	animation walks the rects in the same order the engine walks its frame
	list (smRend3d.cpp:3852-3854). All rects share one size, so a
	KHR_texture_transform animation only needs a uniform scale."""
	sizes = [PILImage.open(path).size for path in paths]
	columns = min(len(paths), ANIM_ATLAS_COLUMNS)
	rows = (len(paths) + columns - 1) // columns
	cell_w = max(size[0] for size in sizes)
	cell_h = max(size[1] for size in sizes)

	width = next_pow2(columns * cell_w)
	height = next_pow2(rows * cell_h)

	rects = [
		[
			(k % columns) * cell_w / width,
			(k // columns) * cell_h / height,
			cell_w / width,
			cell_h / height
		]
		for k in range(len(paths))
	]

	return rects, (width, height)


def write_anim_atlas(path: Path, paths: list[Path], rects: list[list[float]], size: tuple[int, int]) -> None:
	atlas = PILImage.new("RGBA", size)
	for frame_path, rect in zip(paths, rects):
		frame = PILImage.open(frame_path).convert("RGBA")
		atlas.paste(frame, (round(rect[0] * size[0]), round(rect[1] * size[1])))
	path.parent.mkdir(exist_ok=True, parents=True)
	atlas.save(path)


def encode(path: Path, model: PTActorModel | PTStageModel, args: Namespace) -> None:
	"""Encodes the interal model structure to a GLTF file and writes it to disk."""
	# invalid model data
	if not model.materials and not model.objects:
		print(f"Model '{model.filename}' does not contain any data.")
		return

	gltf = GLTF2()
	gltf.scene = 0

	""" BONES """

	# if a model has bones, we add bone nodes first to make it a bit easier to do
	# the indexing
	if hasattr(model, "bones") and model.bones:
		# Priston Tale's model bones each link to their parent bone, but GLTF wants
		# a list of children so we have to flip how bones are linked together.
		for i, bone in enumerate(model.bones):
			bone._id = i
			if bone.parent:
				for parent in model.bones:
					if bone.parent == parent.name:
						bone._parent = parent
						parent._children.append(i)
						break

		# transform vertices to bone space
		for object in model.objects:
			for v, bonename in enumerate(object.physique):
				for bone in model.bones:
					if bonename == bone.name:
						np_m = to_np_matrix(bone.transform)
						np_v = to_np_vector(object.vertices[v])
						object.vertices[v] = from_np_vector(np_v @ np_m)
						break

		skin = Skin(name = "Armature")
		inverse_buffer = BufferReader(sizeof(smFMATRIX)*len(model.bones))
		inverse_base = []

		# inverse bind matrices
		for i, bone in enumerate(model.bones):
			skin.joints.append(i)
			t = bone.transform

			# NOTE: we are swapping Y and Z axes, but also negating Z for some reason
			# that I do not recall. Will update this note if/when I remember. May just
			# be a difference between the source data and glTF's expectations.
			position = PTVector3(
				x =  t.position.x * SCALE_INCH_TO_METER,
				y =  t.position.z * SCALE_INCH_TO_METER,
				z = -t.position.y * SCALE_INCH_TO_METER
			)

			rotation = PTQuaternion(
				x =  t.rotation.x,
				y =  t.rotation.z,
				z = -t.rotation.y,
				w =  t.rotation.w
			)

			scale =  PTVector3(
				x = t.scale.x,
				y = t.scale.z,
				z = t.scale.y
			)

			gltf.nodes.append(Node(
				name = bone.name,
				children = bone._children,
				translation = [ position.x, position.y, position.z ],
				rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ],
				scale = [ scale.x, scale.y, scale.z ]
			))

			np_m = trs_to_np_matrix(position, rotation, scale)
			try:
				np_w = np.linalg.inv(np_m) # lol it's an inverted m ;D
			except np.linalg.LinAlgError:
				# degenerate helper bones (zero Tm/scale) that no physique references;
				# the engine inverts them into garbage that is never sampled
				np_w = np.identity(4)

			if bone._parent:
				np_pw = inverse_base[bone._parent._id]
				inverse_base.append(np_w @ np_pw)
			else:
				inverse_base.append(np_w)

			w = from_np_matrix(inverse_base[i])
			inverse_buffer.write(smFMATRIX(
				w._11, w._12, w._13, w._14,
				w._21, w._22, w._23, w._24,
				w._31, w._32, w._33, w._34,
				w._41, w._42, w._43, w._44
			))

		gltf.buffers.append(Buffer(
			uri = "data:application/octet-stream;base64," + base64.b64encode(inverse_buffer.get_data()).decode(),
			byteLength = len(inverse_buffer.data)
		))

		gltf.bufferViews.append(BufferView(
			buffer = len(gltf.buffers)-1,
			byteLength = len(inverse_buffer.data)
		))

		gltf.accessors.append(Accessor(
			bufferView = len(gltf.bufferViews)-1,
			componentType = FLOAT,
			count = len(model.bones),
			type = "MAT4"
		))

		skin.inverseBindMatrices = len(gltf.accessors)-1
		gltf.skins.append(skin)

	""" MATERIALS """

	segments = str(path).split(os.path.sep)
	fs_dir = os.path.sep.join(segments[:-1])

	# Reference: smType.h:653
	overlay_material_ids = set()
	overlay_index_map = {}

	anim_materials = []
	for i, material in enumerate(model.materials):
		if material.texture_map.anim_frames:
			anim_materials.append((i, material))

	# flipbook frames become one atlas texture per material; KHR_texture_transform
	# uv animations walk the atlas slots at the engine's frame rate. Frames not
	# on disk are dropped (up to 16 distinct paths); the frame list is authored
	# with power-of-two counts (anim2..anim16), so a gap means the file is missing
	# on disk and the engine would have shown the same gap (SetTexture with a null
	# texture, smRend3d.cpp:3857).
	anim_atlas = []
	for i, material in anim_materials:
		frames = []
		for frame_path in material.texture_map.anim_frames:
			root, ext = get_filename(frame_path)

			if args.png:
				uri = (root + ".png").lower()
			else:
				uri = root + ext

			texpath = os.path.join(fs_dir, uri)

			if os.path.isfile(texpath):
				frames.append(Path(texpath))

		if len(frames) == 0:
			continue

		rects, atlas_size = pack_anim_atlas(frames)
		root, ext = get_filename(material.texture_map.anim_frames[0])
		atlas_name = (root + "-anim").lower()
		atlas_path = Path(os.path.join(fs_dir, atlas_name + ".png"))
		write_anim_atlas(atlas_path, frames, rects, atlas_size)

		anim_atlas.append({
			"material": i,
			"image": atlas_name + ".png",
			"rects": rects,
			"speed": material.anim_speed,
			"count": len(frames),
			"mask": material.anim_mask,
			"frame0": material.mat_frame
		})

	# atlas textures replace the static diffuse for flipbook materials; they are
	# registered before the material loop so the override below can reference
	# them by index, and the frame-`frame0` transform doubles as the animation's
	# base pose
	for anim in anim_atlas:
		gltf.images.append(Image(
			uri = anim["image"]
		))

		gltf.textures.append(Texture(
			source = len(gltf.images)-1
		))

		anim["texture"] = len(gltf.textures)-1
		rect = anim["rects"][anim["frame0"] % anim["count"]]
		anim["offset"] = [ rect[0], 1 - rect[1] - rect[3] ]
		anim["scale"] = [ rect[2], rect[3] ]

	material_index_map = {}
	for i, material in enumerate(model.materials):
		mtl = Material()
		gltf.materials.append(mtl)
		material_index_map[i] = len(gltf.materials)-1

		# Priston Tale's material names are delimited with : but that is invalid
		# for filesystems. Also remove the trailing delimiter.
		mtl.name = f"mtl_{i}-{material.name.replace("BLEND_ALPHA:", "").replace(":", "-")}"[:-1]
		mtl.alphaMode = "MASK"
		mtl.doubleSided = material.two_sided
		mtl.alphaCutoff = None

		# authored engine attributes as data, for any consumer
		mtl.extras["collide"] = material.collide
		mtl.extras["wall"] = (material.script_flags & 0x400) == 0x400
		mtl.extras["renderLatter"] = (material.mesh_flags & 0x2000) == 0x2000
		if material.wind_mesh_bottom:
			mtl.extras["windMeshBottom"] = material.wind_mesh_bottom

		# non-collidable materials are pass-through geometry
		if not material.collide and mtl.name.find("-pass") < 0:
			mtl.name += "-pass"

		# TODO: figure out how to add the map name / render flags (extras?)
		if material.texture_map:
			if material.texture_map.diffuse_path:
				root, ext = get_filename(material.texture_map.diffuse_path)

				if args.png:
					uri = (root + ".png").lower()
				else:
					uri = root + ext

				texpath = os.path.join(fs_dir, uri)

				if os.path.isfile(texpath):
					gltf.images.append(Image(
						uri = uri
					))

					gltf.textures.append(Texture(
						source = len(gltf.images)-1
					))

					mtl.pbrMetallicRoughness = PbrMetallicRoughness(
						baseColorTexture = TextureInfo(index = len(gltf.textures)-1),
						metallicFactor = 0
					)

				# animated materials show frame `frame0` at rest (the engine only
				# samples the anim list, smRend3d.cpp:3852-3854)
				for anim in (a for a in anim_atlas if a["material"] == i and a["texture"] is not None):
					mtl.pbrMetallicRoughness = PbrMetallicRoughness(
						baseColorTexture = TextureInfo(
							index = anim["texture"],
							extensions = {
								"KHR_texture_transform": {
									"offset": anim["offset"],
									"scale": anim["scale"],
									"rotation": 0
								}
							}
						),
						metallicFactor = 0
					)

			if material.texture_map.selfillum_path:
				root, ext = get_filename(material.texture_map.selfillum_path)

				if args.png:
					uri = (root + ".png").lower()
				else:
					uri = root + ext

				texpath = os.path.join(fs_dir, uri)

				if os.path.isfile(texpath):
					gltf.images.append(Image(
						uri = uri
					))

					gltf.textures.append(Texture(
						source = len(gltf.images)-1
					))

					selfillum = 1 if material.selfillum else 0

					# alpha-loaded second textures are the engine's dual-render
					# overlays (MapDualRend -> SetD3DRendStateOnlyAlpha,
					# smRend3d.cpp:3805-3809, 4124-4132): the faces are redrawn
					# with the second texture alone, alpha blended. glTF has no
					# second-diffuse slot, so the pass becomes its own
					# alpha-masked material directly after the base one; the
					# texture alpha cuts everything but the overlay art
					if material.texture_map.second_has_alpha:
						overlay_mtl = Material(
							name = mtl.name + "-overlay",
							alphaMode = "MASK",
							doubleSided = mtl.doubleSided,
							pbrMetallicRoughness = PbrMetallicRoughness(
								baseColorTexture = TextureInfo(index = len(gltf.textures)-1, texCoord = 1),
								metallicFactor = 0
							)
						)
						overlay_mtl.extras["collide"] = False
						overlay_mtl.extras["overlayFor"] = i
						gltf.materials.append(overlay_mtl)
						overlay_index_map[i] = len(gltf.materials)-1
						overlay_material_ids.add(i)
					# everything else modulates the stage over the diffuse
					# (MULTIMIX stage 1, smRend3d.cpp:3778-3789)
					else:
						mtl.emissiveFactor = [ selfillum, selfillum, selfillum ]
						mtl.emissiveTexture = TextureInfo(index = len(gltf.textures)-1, texCoord = 1)

			if material.texture_map.opacity_path:
				mtl.alphaMode = "BLEND"
				root, ext = get_filename(material.texture_map.opacity_path)

				if args.png:
					uri = (root + ".png").lower()
				else:
					uri = root + ext

				texpath = os.path.join(fs_dir, uri)

				if os.path.isfile(texpath):
					gltf.images.append(Image(
						uri = uri
					))

					gltf.textures.append(Texture(
						source = len(gltf.images)-1
					))

					mtl.occlusionTexture = TextureInfo(index = len(gltf.textures)-1)

			# lightmap: chained second texture of *LM_ dungeon stage materials,
			# exported as an occlusion map over TEXCOORD_1 (the engine adds the
			# second stage with D3DTOP_ADD, smRend3d.cpp:3628-3630); consumers
			# wanting baked-lighting previews can read it as AO
			if material.texture_map.lightmap_path:
				root, ext = get_filename(material.texture_map.lightmap_path)

				if args.png:
					uri = (root + ".png").lower()
				else:
					uri = (root + ext).lower()

				texpath = os.path.join(fs_dir, uri)

				if os.path.isfile(texpath):
					gltf.images.append(Image(
						uri = uri
					))

					gltf.textures.append(Texture(
						source = len(gltf.images)-1
					))

					mtl.occlusionTexture = TextureInfo(
						index = len(gltf.textures)-1,
						texCoord = 1
					)

	""" MESHES """

	anim_ids = { a["material"] for a in anim_atlas }

	for object in model.objects:
		untangled_prims = make_primitives(object, gltf.nodes, anim_ids, overlay_material_ids)
		prim_pass = []
		prim_col = []
		prim_colonly = []
		prim_anim = []
		anim_node_refs = []

		m = object.transform

		# swap Y and Z (smStgObj.cpp:82)
		position = PTVector3(
			x = -m._41 * SCALE_INCH_TO_METER,
			y =  m._43 * SCALE_INCH_TO_METER,
			z =  m._42 * SCALE_INCH_TO_METER
		)

		# Priston Tale stores but does not use the transform scale; node scale
		# must stay unit or the mesh collapses to a point
		scale = PTVector3(1, 1, 1)
		rotation = PTQuaternion()

		if hasattr(object, "transform_rotate"):
			q = matrix_to_quaternion(object.transform_rotate)
			rotation	= PTQuaternion(
				x = -q.x,
				y =  q.z,
				z =  q.y,
				w = -q.w
			)

		for prim in untangled_prims:
			if prim.get("overlay_material"):
				p = Primitive(material = overlay_index_map[prim["material"]])
			else:
				p = Primitive(material = material_index_map[prim["material"]])

			# POSITION
			gltf.buffers.append(Buffer(
				uri = "data:application/octet-stream;base64," + base64.b64encode(prim["positionbuffer"].get_data()).decode(),
				byteLength = len(prim["positionbuffer"].data)
			))

			gltf.bufferViews.append(BufferView(
				buffer = len(gltf.buffers)-1,
				byteLength = len(prim["positionbuffer"].data),
				target = ARRAY_BUFFER
			))

			gltf.accessors.append(Accessor(
				bufferView = len(gltf.bufferViews)-1,
				componentType = FLOAT,
				count = prim["count"],
				type = "VEC3",
				min = [ prim["min"].x, prim["min"].y, prim["min"].z ],
				max = [ prim["max"].x, prim["max"].y, prim["max"].z ]
			))

			p.attributes.POSITION = len(gltf.buffers)-1

			# NORMAL
			gltf.buffers.append(Buffer(
				uri = "data:application/octet-stream;base64," + base64.b64encode(prim["normalbuffer"].get_data()).decode(),
				byteLength = len(prim["normalbuffer"].data)
			))

			gltf.bufferViews.append(BufferView(
				buffer = len(gltf.buffers)-1,
				byteLength = len(prim["normalbuffer"].data),
				target = ARRAY_BUFFER
			))

			gltf.accessors.append(Accessor(
				bufferView = len(gltf.bufferViews)-1,
				componentType = FLOAT,
				count = prim["count"],
				type = "VEC3"
			))

			p.attributes.NORMAL = len(gltf.buffers)-1

			# TEXCOORD_0
			if prim["texcoord0"]:
				gltf.buffers.append(Buffer(
					uri = "data:application/octet-stream;base64," + base64.b64encode(prim["texcoord0buffer"].get_data()).decode(),
					byteLength = len(prim["texcoord0buffer"].data)
				))

				gltf.bufferViews.append(BufferView(
					buffer = len(gltf.buffers)-1,
					byteLength = len(prim["texcoord0buffer"].data),
					target = ARRAY_BUFFER
				))

				gltf.accessors.append(Accessor(
					bufferView = len(gltf.bufferViews)-1,
					componentType = FLOAT,
					count = prim["count"],
					type = "VEC2"
				))

				p.attributes.TEXCOORD_0 = len(gltf.buffers)-1

			# TEXCOORD_1
			if prim["texcoord1"]:
				gltf.buffers.append(Buffer(
					uri = "data:application/octet-stream;base64," + base64.b64encode(prim["texcoord1buffer"].get_data()).decode(),
					byteLength = len(prim["texcoord1buffer"].data)
				))

				gltf.bufferViews.append(BufferView(
					buffer = len(gltf.buffers)-1,
					byteLength = len(prim["texcoord1buffer"].data),
					target = ARRAY_BUFFER
				))

				gltf.accessors.append(Accessor(
					bufferView = len(gltf.bufferViews)-1,
					componentType = FLOAT,
					count = prim["count"],
					type = "VEC2"
				))

				p.attributes.TEXCOORD_1 = len(gltf.buffers)-1

			# JOINTS_0
			if prim["joints0buffer"]:
				gltf.buffers.append(Buffer(
					uri = "data:application/octet-stream;base64," + base64.b64encode(prim["joints0buffer"].get_data()).decode(),
					byteLength = len(prim["joints0buffer"].data)
				))

				gltf.bufferViews.append(BufferView(
					buffer = len(gltf.buffers)-1,
					byteLength = len(prim["joints0buffer"].data),
					target = ARRAY_BUFFER
				))

				gltf.accessors.append(Accessor(
					bufferView = len(gltf.bufferViews)-1,
					componentType = UNSIGNED_BYTE,
					count = prim["count"],
					type = "VEC4"
				))

				p.attributes.JOINTS_0 = len(gltf.buffers)-1

			# WEIGHTS_0
			if prim["weights0buffer"]:
				gltf.buffers.append(Buffer(
					uri = "data:application/octet-stream;base64," + base64.b64encode(prim["weights0buffer"].get_data()).decode(),
					byteLength = len(prim["weights0buffer"].data)
				))

				gltf.bufferViews.append(BufferView(
					buffer = len(gltf.buffers)-1,
					byteOffset = 0,
					byteLength = len(prim["weights0buffer"].data),
					target = ARRAY_BUFFER
				))

				gltf.accessors.append(Accessor(
					bufferView = len(gltf.bufferViews)-1,
					byteOffset = 0,
					componentType = FLOAT,
					count = prim["count"],
					type = "VEC4"
				))

				p.attributes.WEIGHTS_0 = len(gltf.buffers)-1

			material = model.materials[prim["material"]]
			is_wall = (material.script_flags & 0x400) == 0x400

			# flipbook prims get their own mesh so the uv animation only moves
			# their texture coordinates
			if prim["anim_material"]:
				prim_anim.append((prim["material"], p))
			# animated objects are not collidable
			elif (hasattr(object, "animation") and object.animation) or not material.collide:
				prim_pass.append(p)
			elif is_wall:
				prim_colonly.append(p)
			else:
				prim_col.append(p)

			if len(prim_anim) >= 256:
				gltf.meshes.append(Mesh(
					name = object.name,
					primitives = [ p for _, p in prim_anim ]
				))

				node = Node(
					name = f"{object.name}-{len(gltf.nodes)}" + ("-anim" if args.godot else ""),
					extras = { "role": "anim" },
					mesh = len(gltf.meshes)-1,
				)

				# nodes either have a local transform or a skin, never both
				if hasattr(object, "physique") and object.physique:
					node.skin = 0
				else:
					node.translation = [ position.x, position.y, position.z ]
					node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
					node.scale = [ scale.x, scale.y, scale.z ]

				gltf.nodes.append(node)
				anim_node_refs += [ (material_id, len(gltf.nodes)-1) for material_id, p in prim_anim ]
				prim_anim = []

			# we want to limit the number of primitives per mesh to 256 (godot limit)
			if len(prim_col) >= 256:
				gltf.meshes.append(Mesh(
					name = object.name,
					primitives = prim_col
				))

				node = Node(
					name = f"{object.name}-{len(gltf.nodes)}" + ("-col" if args.godot else ""), # -col: godot import hint (trimesh collision)
					extras = { "role": "col" },
					mesh = len(gltf.meshes)-1,
				)

				# nodes either have a local transform or a skin, never both
				if hasattr(object, "physique") and object.physique:
					node.skin = 0
				else:
					node.translation = [ position.x, position.y, position.z ]
					node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
					node.scale = [ scale.x, scale.y, scale.z ]

				gltf.nodes.append(node)
				prim_col = []

			if len(prim_colonly) >= 256:
				gltf.meshes.append(Mesh(
					name = object.name,
					primitives = prim_colonly
				))

				node = Node(
					name = f"{object.name}-{len(gltf.nodes)}" + ("-colonly" if args.godot else ""), # -colonly: godot import hint (invisible collision)
					extras = { "role": "colonly" },
					mesh = len(gltf.meshes)-1,
				)

				# nodes either have a local transform or a skin, never both
				if hasattr(object, "physique") and object.physique:
					node.skin = 0
				else:
					node.translation = [ position.x, position.y, position.z ]
					node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
					node.scale = [ scale.x, scale.y, scale.z ]

				gltf.nodes.append(node)
				prim_colonly = []

			if len(prim_pass) >= 256:
				gltf.meshes.append(Mesh(
					name = object.name,
					primitives = prim_pass
				))

				node = Node(
					name = f"{object.name}-{len(gltf.nodes)}",
					extras = { "role": "pass" },
					mesh = len(gltf.meshes)-1,
				)

				# nodes either have a local transform or a skin, never both
				if hasattr(object, "physique") and object.physique:
					node.skin = 0
				else:
					node.translation = [ position.x, position.y, position.z ]
					node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
					node.scale = [ scale.x, scale.y, scale.z ]

				gltf.nodes.append(node)
				prim_pass = []

		# any primitives left over get put into a final mesh and node
		if len(prim_anim) > 0:
			gltf.meshes.append(Mesh(
				name = object.name,
				primitives = [ p for _, p in prim_anim ]
			))

			node = Node(
				name = f"{object.name}-{len(gltf.nodes)}" + ("-anim" if args.godot else ""),
				extras = { "role": "anim" },
				mesh = len(gltf.meshes)-1,
			)

			# nodes either have a local transform or a skin, never both
			if hasattr(object, "physique") and object.physique:
				node.skin = 0
			else:
				node.translation = [ position.x, position.y, position.z ]
				node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
				node.scale = [ scale.x, scale.y, scale.z ]

			gltf.nodes.append(node)
			anim_node_refs += [ (material_id, len(gltf.nodes)-1) for material_id, p in prim_anim ]

		if len(prim_col) > 0:
			gltf.meshes.append(Mesh(
				name = object.name,
				primitives = prim_col
			))

			node = Node(
				name = f"{object.name}-{len(gltf.nodes)}" + ("-col" if args.godot else ""), # -col: godot import hint (trimesh collision)
				extras = { "role": "col" },
				mesh = len(gltf.meshes)-1,
			)

			# nodes either have a local transform or a skin, never both
			if hasattr(object, "physique") and object.physique:
				node.skin = 0
			else:
				node.translation = [ position.x, position.y, position.z ]
				node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
				node.scale = [ scale.x, scale.y, scale.z ]

			gltf.nodes.append(node)

		if len(prim_colonly) > 0:
			gltf.meshes.append(Mesh(
				name = object.name,
				primitives = prim_colonly
			))

			node = Node(
				name = f"{object.name}-{len(gltf.nodes)}" + ("-colonly" if args.godot else ""), # -colonly: godot import hint (invisible collision)
				extras = { "role": "colonly" },
				mesh = len(gltf.meshes)-1,
			)

			# nodes either have a local transform or a skin, never both
			if hasattr(object, "physique") and object.physique:
				node.skin = 0
			else:
				node.translation = [ position.x, position.y, position.z ]
				node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
				node.scale = [ scale.x, scale.y, scale.z ]

			gltf.nodes.append(node)

		if len(prim_pass) > 0:
			gltf.meshes.append(Mesh(
				name = object.name,
				primitives = prim_pass
			))

			node = Node(
				name = f"{object.name}-{len(gltf.nodes)}",
				extras = { "role": "pass" },
				mesh = len(gltf.meshes)-1,
			)

			# nodes either have a local transform or a skin, never both
			if hasattr(object, "physique") and object.physique:
				node.skin = 0
			else:
				node.translation = [ position.x, position.y, position.z ]
				node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
				node.scale = [ scale.x, scale.y, scale.z ]

			gltf.nodes.append(node)

		if hasattr(object, "animation") and (object.animation.position or object.animation.rotation or object.animation.scale):
			fill_animation_frames(object.animation)

			track = PTAnimationTrack()
			track.position = get_animation_track(gltf, object.animation.position, "position")
			track.rotation = get_animation_track(gltf, object.animation.rotation, "rotation")
			track.scale = get_animation_track(gltf, object.animation.scale, "scale")

			process_animation(gltf, object.animation, "ani" + ("-loop" if args.godot else ""), len(gltf.nodes)-1, track)

	""" ANIMATIONS """

	if hasattr(model, "bones") and hasattr(model, "animations") and model.animations:
		for bone in model.bones:
			fill_animation_frames(bone.animation)

			track = PTAnimationTrack()
			track.position = get_animation_track(gltf, bone.animation.position, "position", True, model.animations)
			track.rotation = get_animation_track(gltf, bone.animation.rotation, "rotation", True, model.animations)
			track.scale = get_animation_track(gltf, bone.animation.scale, "scale", True, model.animations)

			for animation in model.animations:
				name = animation.name
				if args.godot and animation.repeat:
					name += "-loop" # godot: keeps the imported animation looping; repeat stays in extras for everyone

				process_animation(gltf, bone.animation, name, bone._id, track, animation)

		# facial (talk) animations live in the same smb frame space as the regular
		# motions but are separate frame ranges, so they get their own sampler pass
		# per bone: get_animation_track resolves each key's timestamp against the
		# talk ranges, keeping times relative to the talk animation's own start.
		if model.talk_animations:
			for bone in model.bones:
				track = PTAnimationTrack()
				track.position = get_animation_track(gltf, bone.animation.position, "position", True, model.talk_animations)
				track.rotation = get_animation_track(gltf, bone.animation.rotation, "rotation", True, model.talk_animations)
				track.scale = get_animation_track(gltf, bone.animation.scale, "scale", True, model.talk_animations)

				for animation in model.talk_animations:
					name = animation.name
					if args.godot and animation.repeat:
						name += "-loop"

					process_animation(gltf, bone.animation, name, bone._id, track, animation)

	""" TEXTURE ANIMATIONS """

	for anim in anim_atlas:
		encode_uv_animation(gltf, anim, [ node_id for material_id, node_id in anim_node_refs if material_id == anim["material"] ])

	""" LIGHTS """

	# Stage dynamic lights (smLIGHT3D) as KHR_lights_punctual point lights.
	if hasattr(model, "lights") and model.lights:
		gltf.extensionsUsed.append("KHR_lights_punctual")

		punctual_lights = []

		for i, light in enumerate(model.lights):
			suffix = "".join(
				[ s for flag, s in (
					(light.dynamic, "-dynamic"),
					(light.night, "-night"),
					(light.lens, "-lens"),
					(light.pulse, "-pulse"),
					(light.obj, "-obj")
				) if flag ]
			)

			name = f"light_{i}{suffix}"
			punctual = {
				"name": name,
				"type": "point",
				"color": [ light.color.r, light.color.g, light.color.b ],
				"intensity": 1.0
			}

			if light.range > 0:
				punctual["range"] = light.range * SCALE_INCH_TO_METER

			punctual_lights.append(punctual)

			gltf.nodes.append(Node(
				name = name,
				translation = [
					-light.position.x * SCALE_INCH_TO_METER,
					 light.position.z * SCALE_INCH_TO_METER,
					 light.position.y * SCALE_INCH_TO_METER
				],
				extensions = {
					"KHR_lights_punctual": {
						"light": i
					}
				}
			))

		gltf.extensions = {
			"KHR_lights_punctual": {
				"lights": punctual_lights
			}
		}

	""" SCENE """

	scene = Scene()
	for i, node in enumerate(gltf.nodes):
		# armature will always start at 0
		# everything after the joint nodes is also a root
		if i == 0 or i >= (len(model.bones) if hasattr(model, "bones") else 0):
			scene.nodes.append(i)
	gltf.scenes.append(scene)

	""" MODEL METADATA """

	# chain files and rate tables are model level, so they live on the asset
	# extras; per-animation data (restrictions, key codes, blend rates) is on
	# each animation's extras.
	if hasattr(model, "link_file"):
		extras = {}
		if model.link_file:
			extras["linkFile"] = model.link_file
		if model.talk_link_file:
			extras["talkLinkFile"] = model.talk_link_file
		if model.talk_motion_file:
			extras["talkMotionFile"] = model.talk_motion_file
		if model.sub_model_file:
			extras["subModelFile"] = model.sub_model_file
		if model.npc_motion_rate_table and any(model.npc_motion_rate_table):
			extras["npcMotionRateTable"] = model.npc_motion_rate_table
		if model.talk_motion_rate_table and any(any(rates) for rates in model.talk_motion_rate_table):
			extras["talkMotionRateTable"] = model.talk_motion_rate_table
		if extras:
			gltf.asset.extras = extras

	path.parent.mkdir(exist_ok=True, parents=True)
	# pygltflib's save() resets self.asset with a fresh default Asset unless one
	# is passed, which would drop the asset extras above.
	gltf.save(path, gltf.asset)
