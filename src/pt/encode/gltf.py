import base64
import math
import numpy as np
import os

from argparse import Namespace
from bisect import bisect_left, bisect_right
from ctypes import *
from dataclasses import asdict
from pathlib import Path
from PIL import Image as PILImage
from struct import pack
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
)


""" ANIMATIONS """


def encode_uv_animation(gltf: GLTF2, anim: dict, node_ids: list[int]) -> None:
	"""
	Export one flipbook as a KHR_animation_pointer uv animation walking the
	atlas rects in frame order (the engine swaps whole textures, not uv offsets;
	the pointer animates the material's KHR_texture_transform offset/scale, the
	portable glTF equivalent). smRend3d.cpp:3852-3854).
	"""
	if not node_ids:
		return None

	duration = (1 << anim["speed"]) * anim["count"] / 1000
	times = BufferReader(4 * (anim["count"] + 1))
	offsets = BufferReader(4 * 3 * (anim["count"] + 1))
	scales = BufferReader(4 * 3 * (anim["count"] + 1))

	for k in range(anim["count"]):
		times.write(c_float(k * (1 << anim["speed"]) / 1000))
		rect = anim["rects"][k]
		offsets.write((c_float*3)(rect[0], rect[1], 0))
		scales.write((c_float*3)(rect[2], rect[3], 0))

	times.write(c_float(duration))
	offsets.write((c_float*3)(anim["offset"][0], anim["offset"][1], 0))
	scales.write((c_float*3)(anim["scale"][0], anim["scale"][1], 0))

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

	def append_vec3_buffer(br: BufferReader) -> int:
		gltf.buffers.append(Buffer(
			uri = "data:application/octet-stream;base64," + base64.b64encode(br.get_data()).decode(),
			byteLength = len(br.data)
		))

		gltf.bufferViews.append(BufferView(
			buffer = len(gltf.buffers)-1,
			byteLength = len(br.data)
		))

		gltf.accessors.append(Accessor(
			bufferView = len(gltf.bufferViews)-1,
			componentType = FLOAT,
			count = anim["count"] + 1,
			type = "VEC3"
		))

		return len(gltf.accessors)-1

	offset_accessor = append_vec3_buffer(offsets)
	scale_accessor = append_vec3_buffer(scales)

	if "KHR_texture_transform" not in gltf.extensionsUsed:
		gltf.extensionsUsed.append("KHR_texture_transform")
	if "KHR_animation_pointer" not in gltf.extensionsUsed:
		gltf.extensionsUsed.append("KHR_animation_pointer")

	gltf_animation = next((ani for ani in gltf.animations if ani.name == "tex-anim"), None)
	if gltf_animation is None:
		gltf_animation = Animation(name = "tex-anim")
		gltf.animations.insert(0, gltf_animation)

	material_index = anim.get("gltf_material", anim["material"])
	pointers = (
		(offset_accessor, f"/materials/{material_index}/pbrMetallicRoughness/baseColorTexture/extensions/KHR_texture_transform/offset"),
		(scale_accessor, f"/materials/{material_index}/pbrMetallicRoughness/baseColorTexture/extensions/KHR_texture_transform/scale"),
	)

	for output_accessor, pointer in pointers:
		gltf_animation.samplers.append(Sampler(
			input = input_accessor,
			output = output_accessor,
			interpolation = "STEP",
			wrapS = None,
			wrapT = None
		))

		gltf_animation.channels.append(AnimationChannel(
			sampler = len(gltf_animation.samplers)-1,
			target = AnimationChannelTarget(
				path = "pointer",
				extensions = { "KHR_animation_pointer": { "pointer": pointer } }
			)
		))


def fill_animation_frames(transform: PTActorAnimation) -> None:
	"""Fill in animation frames between key frames."""

	# encode may run twice over the same decoded model (gltf + glb in one pass);
	# filled frames are appended, so a second fill would corrupt the arrays
	if getattr(transform, "_filled", False):
		return
	transform._filled = True

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

				# if there are gaps between frames, fill them in (same
				# (1-t)*a + t*b arithmetic as lerp_vector, without the per-key
				# numpy arrays)
				if cframe > pframe+1:
					for f in range(pframe+1, cframe):
						t = (f-pframe) / (cframe-pframe)
						new_frames.append(PTAnimationPosition(
							frame = f * 160,
							x = (1-t) * ptfm.x + t * tfm.x,
							y = (1-t) * ptfm.y + t * tfm.y,
							z = (1-t) * ptfm.z + t * tfm.z
						))

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
						t = (f-pframe) / (cframe-pframe)
						new_frames.append(PTAnimationScale(
							frame = f * 160,
							x = (1-t) * ptfm.x + t * tfm.x,
							y = (1-t) * ptfm.y + t * tfm.y,
							z = (1-t) * ptfm.z + t * tfm.z
						))

			ptfm = tfm

		transform.scale += new_frames
		transform.scale.sort(key=lambda a: a.frame)


# this function is a little clunky because of the variances between the different transforms.
# however, the transforms are similar enough that the majority of the code is duplicate for each.
def get_animation_track(gltf: GLTF2, transforms: list[PTAnimationPosition] | list[PTAnimationRotation] | list[PTAnimationScale], name: str, has_bones: bool = False, animations: list[PTModelMetadata] | None = None) -> PTAnimationSampler:
	"""
	Get the animation values per transform. Times are resolved per clip in
	process_animation_transform against the clip's own frame window, mirroring
	the engine which only samples key arrays through a clip's window
	(smObj3d.cpp::GetTmFramePos).
	"""
	rot = name == "rotation"
	pos = name == "position"
	scl = name == "scale"

	if len(transforms) > 0:
		qx = qy = qz = qw = 0.0
		qw = 1.0
		composed = []
		frames = []
		times = []
		values = []

		# merged motion files can author two keys at a window boundary frame
		# (the incoming clip's first key re-based onto the previous clip's last
		# frame); a clip starting at that boundary samples the later window's
		# key, so keep the last key of each duplicated frame
		last_frame = None

		for transform in transforms:
			if last_frame is not None and transform.frame <= last_frame:
				del values[-4 if rot else -3:]
				if composed:
					composed.pop()
					# the dropped key's rotation delta must not leak into the
					# accumulated delta quaternion, so rewind to the kept key
					qx, qy, qz, qw = composed[-1] if composed else (0.0, 0.0, 0.0, 1.0)
				times.pop()
				frames.pop()
			last_frame = transform.frame

			if rot:
				# accumulate the delta quaternion chain in plain doubles
				# (multiply_quaternions with intermediate dataclass objects is
				# ~20x slower per key; the arithmetic here is identical)
				mx, my, mz, mw = transform.x, transform.y, transform.z, transform.w
				nx = qx * mw + qw * mx + qy * mz - qz * my
				ny = qy * mw + qw * my + qz * mx - qx * mz
				nz = qz * mw + qw * mz + qx * my - qy * mx
				nw = qw * mw - qx * mx - qy * my - qz * mz
				mag = math.sqrt(nw*nw + nx*nx + ny*ny + nz*nz)
				qx, qy, qz, qw = nx / mag, ny / mag, nz / mag, nw / mag
				composed.append((qx, qy, qz, qw))

			times.append(transform.frame / 160 / 30)
			frames.append(transform.frame)

			if has_bones:
				if rot:
					values += [ qx, qz, -qy, -qw ]
				if pos:
					values += [
						 transform.x * SCALE_INCH_TO_METER,
						 transform.z * SCALE_INCH_TO_METER,
						-transform.y * SCALE_INCH_TO_METER
					]
				if scl:
					values += [ transform.x, transform.z, transform.y ]
			else:
				if rot:
					values += [ -qx, qz, qy, -qw ]
				if pos:
					values += [
						-transform.x * SCALE_INCH_TO_METER,
						 transform.z * SCALE_INCH_TO_METER,
						 transform.y * SCALE_INCH_TO_METER
					]
				if scl:
					values += [ transform.x, transform.z, transform.y ]
		# one shared output buffer per track: per-clip accessors slice it with
		# byteOffset, exactly like the engine slices its key arrays per window
		values_bytes = pack(f"<{len(values)}f", *values)

		gltf.buffers.append(Buffer(
			uri = "data:application/octet-stream;base64," + base64.b64encode(values_bytes).decode(),
			byteLength = len(values_bytes)
		))

		return PTAnimationSampler(
			frames = frames,
			times = times,
			values = values,
			output = len(gltf.buffers)-1
		)
	return PTAnimationSampler()


def process_animation_transform(gltf: GLTF2, name: str, gltf_animation: Animation, node: int, sampler: PTAnimationSampler, animation: PTMotionMetadata, input_accessors: dict) -> None:
	"""Process animation transforms."""
	rot = name == "rotation"

	if sampler.times:
		# each clip samples only the keys inside its frame window
		# (smObj3d.cpp::GetTmFramePos); slice the track to that window and make
		# times relative to the clip's own start. Windowing uses the sampler's
		# own frames so the time and value slices always stay in sync, even when
		# the rotation and position tracks have different key counts. Frames are
		# strictly increasing (get_animation_track drops duplicate keys), so the
		# window bounds are a binary search instead of a full scan.
		if animation:
			sidx = bisect_left(sampler.frames, animation.start_frame * 160)
			eidx = bisect_right(sampler.frames, animation.end_frame * 160) - 1
			if sidx > eidx:
				return
			tbase = animation.start_frame / 30
		else:
			sidx, eidx = 0, len(sampler.times)-1
			tbase = 0

		sz = 4 if rot else 3
		count = eidx - sidx + 1

		# every bone of a clip walks the same dense frame grid, so the rebased
		# times repeat verbatim across thousands of channels; the packed bytes
		# are the sharing key, which makes a hit exact by construction
		times_bytes = pack(f"<{count}f", *( t - tbase for t in sampler.times[sidx:eidx+1] ))

		input_accessor = input_accessors.get(times_bytes)
		if input_accessor is None:
			gltf.buffers.append(Buffer(
				uri = "data:application/octet-stream;base64," + base64.b64encode(times_bytes).decode(),
				byteLength = count * 4
			))

			gltf.bufferViews.append(BufferView(
				buffer = len(gltf.buffers)-1,
				byteLength = count * 4
			))

			# times are strictly increasing, so the ends are the extremes
			gltf.accessors.append(Accessor(
				bufferView = len(gltf.bufferViews)-1,
				componentType = FLOAT,
				count = count,
				type = "SCALAR",
				min = [ sampler.times[sidx] - tbase ],
				max = [ sampler.times[eidx] - tbase ]
			))

			input_accessor = len(gltf.accessors)-1
			input_accessors[times_bytes] = input_accessor

		gltf.bufferViews.append(BufferView(
			buffer = sampler.output,
			byteOffset = sidx * sz * 4,
			byteLength = count * sz * 4
		))

		gltf.accessors.append(Accessor(
			bufferView = len(gltf.bufferViews)-1,
			componentType = FLOAT,
			count = count,
			type = "VEC4" if rot else "VEC3"
		))

		gltf_animation.samplers.append(Sampler(
			input = input_accessor,
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


def process_animation(gltf: GLTF2, name: str, node: int, track: PTAnimationTrack, animation: PTMotionMetadata | None = None, input_accessors: dict | None = None) -> None:
	"""Process an animation."""
	# NOTE: death animation has 8 more frames than listed in the inx file (for some reason)
	# This may not need to be added back for GLTF, but may be required for ASE.
	# Reference: fileread.cpp::AddModelDecode (Line ~420)
	# if name == "dead":
	# 	animation.end_frame = animation.end_frame + 8

	found = False
	sframe = animation.start_frame if animation else None
	eframe = animation.end_frame if animation else None

	# duplicate INX motions (same clip, different event frames/item/weapon
	# restrictions, e.g. Hest attack G/H) point at the SAME merged motion file
	# window (motion_frame), so their tracks are the same keys of the same bones
	# and the engine just picks between the restriction variants at runtime
	# (SetMotionFromCode, character.cpp:2352-2455). Their glTF samplers would be
	# identical, which the validator rejects (ANIMATION_DUPLICATE_TARGETS).
	# The same animation name is shared across all bones of a clip and across
	# stage objects, so only skip when this node already has channels in it;
	# otherwise the new channels merge into the existing animation.
	for ani in gltf.animations:
		if ani.name == name and ani.extras["startFrame"] == sframe and ani.extras["endFrame"] == eframe:
			if any(c.target.node == node for c in ani.channels):
				# corpus survey: duplicate (name, window) rows always share
				# motion_frame (38,003 groups, 0 exceptions), so the existing
				# track already holds this key content; keep the first row's
				# variant metadata and record the extras of later variants
				if animation and ani.extras.get("motionFrame") != animation.motion_frame:
					gltf_animation = Animation(name = f"{name}.{animation.motion_frame}")
					gltf_animation.extras["startFrame"] = sframe
					gltf_animation.extras["endFrame"] = eframe
					gltf_animation.extras["motionFrame"] = animation.motion_frame
					gltf_animation.extras["repeat"] = animation.repeat
					gltf_animation.extras["keyCode"] = animation.key_code
					gltf_animation.extras["itemCodes"] = animation.item_codes
					gltf_animation.extras["jobCodeBit"] = animation.job_code_bit
					gltf_animation.extras["skillCodes"] = animation.skill_codes
					gltf_animation.extras["mapPosition"] = animation.map_position
					gltf_animation.extras["rate"] = animation.rate
					process_animation_transform(gltf, "rotation", gltf_animation, node, track.rotation, animation, input_accessors)
					process_animation_transform(gltf, "translation", gltf_animation, node, track.position, animation, input_accessors)
					process_animation_transform(gltf, "scale", gltf_animation, node, track.scale, animation, input_accessors)
					if len(gltf_animation.channels) > 0:
						gltf.animations.append(gltf_animation)
				return
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

	process_animation_transform(gltf, "rotation", gltf_animation, node, track.rotation, animation, input_accessors)
	process_animation_transform(gltf, "translation", gltf_animation, node, track.position, animation, input_accessors)
	process_animation_transform(gltf, "scale", gltf_animation, node, track.scale, animation, input_accessors)

	if not found and len(gltf_animation.channels) > 0:
		gltf.animations.append(gltf_animation)


""" PRIMITIVES """


def make_primitives(object: PTActorObject | PTStageObject, nodes: list[Node], anim_material_ids: set[int] | None = None, overlay_material_ids: set[int] | None = None, has_bones: bool = False) -> list[dict[str,]]:
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
			"joints0buffer": BufferReader(vert_words) if has_bones else None,
			"weights0buffer": BufferReader(vert_words*4) if has_bones else None
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
			overlay_face = False

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

			if hasattr(object, "vertex_normals") and object.vertex_normals:
				authored = [object.vertex_normals[i] for i in iface[1].vertices]
				flipped = False
			elif iface[1].normal is not None:
				authored = [iface[1].normal, iface[1].normal, iface[1].normal]
				flipped = True
			else:
				authored = None

			corner_normals = []
			for j in range(3):
				if authored is None:
					corner_normals.append((normal.x, normal.y, normal.z))
					continue

				# same component mapping as the positions above
				if hasattr(object, "physique") and object.physique:
					nx, ny, nz = authored[j].x, authored[j].z, -authored[j].y
				else:
					nx, ny, nz = -authored[j].x, authored[j].z, authored[j].y
				if flipped:
					nx, ny, nz = -nx, -ny, -nz
				corner_normals.append((nx, ny, nz))

			for nx, ny, nz in corner_normals:
				prim["normalbuffer"].write((c_float*3)(nx, ny, nz))

			# TEXCOORD_0
			# faces with a null lpTexLink_ptr have no texture link (nTexLink < nFace)
			if hasattr(object, "texture_coords") and object.texture_coords and iface[0] < len(object.texture_coords):
				tc = object.texture_coords[iface[0]]
				uv0 = tc.uv_sets[0] if len(tc.uv_sets) > 0 else [PTTextureVertex()] * 3
				uv1 = tc.uv_sets[1] if len(tc.uv_sets) > 1 else [PTTextureVertex()] * 3

				# texlink v is exported verbatim: the engine samples the stored
				# value directly (smRead3d.cpp:1548 actors, :2646 stages)
				prim["texcoord0buffer"].write((c_float*6)(
					uv0[0].u, uv0[0].v,
					uv0[1].u, uv0[1].v,
					uv0[2].u, uv0[2].v
				))

				# TEXCOORD_1: secondary texture stage UVs (lightmaps over
				# diffuse in the *LM_ dungeon stages) ride the NextTex chain
				prim["texcoord1buffer"].write((c_float*6)(
					uv1[0].u, uv1[0].v,
					uv1[1].u, uv1[1].v,
					uv1[2].u, uv1[2].v
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
					overlay_face = True
					uvs = [
						uv1[0].u, uv1[0].v,
						uv1[1].u, uv1[1].v,
						uv1[2].u, uv1[2].v
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
						*corner_normals[0], *corner_normals[1], *corner_normals[2]
					))
			else:
				prim["texcoord0"] = False
				prim["texcoord1"] = False

			# JOINTS_0
			if prim["joints0buffer"] and hasattr(object, "physique") and object.physique:
				for j in range(3):
					face = iface[1]
					bone = object.physique[face.vertices[j]]

					for n, node in enumerate(nodes):
						if bone == node.name:
							prim["joints0buffer"].write((c_ubyte*4)(n, 0, 0, 0))
							if overlay_face:
								overlay_prim["joints0buffer"].write((c_ubyte*4)(n, 0, 0, 0))
							break
					else:
						# the engine resolves every physique name at load
						# (smRead3d.cpp:1448 GetObjectFromName) so this is a safety
						# net; binding to bone 0 keeps the stream aligned
						prim["joints0buffer"].write((c_ubyte*4)(0, 0, 0, 0))
						if overlay_face:
							overlay_prim["joints0buffer"].write((c_ubyte*4)(0, 0, 0, 0))

				# WEIGHTS_0
				prim["weights0buffer"].write((c_float*12)(
					1, 0, 0, 0,
					1, 0, 0, 0,
					1, 0, 0, 0
				))
				if overlay_face:
					overlay_prim["weights0buffer"].write((c_float*12)(
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


def build(model: PTActorModel | PTStageModel, args: Namespace, path: Path) -> GLTF2 | None:
	"""Builds the glTF document for a model."""
	# invalid model data
	if not model.materials and not model.objects:
		print(f"Model '{model.filename}' does not contain any data.")
		return None

	gltf = GLTF2()
	gltf.scene = 0

	# input (time) accessors are content-shared across all channels whose
	# rebased key times match byte for byte
	input_accessors = {}

	""" BONES """

	# if a model has bones, we add bone nodes first to make it a bit easier to do
	# the indexing
	if hasattr(model, "bones") and model.bones:
		# encode may run twice over the same decoded model (gltf + glb in one
		# pass), so the link state has to be reset to stay idempotent
		for bone in model.bones:
			bone._children = []

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

		# transform vertices to bone space (once; the vertices of an already
		# encoded model are already in bone space and the transform is not
		# idempotent)
		if not getattr(model, "_bone_space", False):
			for object in model.objects:
				for v, bonename in enumerate(object.physique):
					for bone in model.bones:
						if bonename == bone.name:
							np_m = to_np_matrix(bone.transform)
							np_v = to_np_vector(object.vertices[v])
							object.vertices[v] = from_np_vector(np_v @ np_m)
							# the engine transforms skinned normals with the same
							# bone matrix (smObj3d.cpp:1888-1910); w=0 drops the
							# translation, which unpacked normals must not inherit
							if v < len(object.vertex_normals):
								n = object.vertex_normals[v]
								np_n = np.array([ n.x, n.y, n.z, 0 ], dtype=np.float32) @ np_m
								object.vertex_normals[v] = PTVector3(np_n[0], np_n[1], np_n[2])
							break
			model._bone_space = True

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

	fs_dir = str(path.parent)

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

			# '#' in a filename is a URI fragment delimiter (golem#2.png)
			texpath = os.path.join(fs_dir, uri.replace("#", "%23"))

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
			uri = anim["image"].replace("#", "%23")
		))

		gltf.textures.append(Texture(
			source = len(gltf.images)-1
		))

		anim["texture"] = len(gltf.textures)-1
		# the renderer samples cells from the global clock alone
		# (RendStatTime >> Shift_FrameSpeed) & FrameMask (smRend3d.cpp:3852-3854);
		# the serialized MatFrame sync flag is dead code (ReSwapMaterial returns
		# early, smTexture.cpp:1223-1226), so the rest pose is frame 0
		anim["offset"] = [ anim["rects"][0][0], anim["rects"][0][1] ]
		anim["scale"] = [ anim["rects"][0][2], anim["rects"][0][3] ]

	material_index_map = {}
	for i, material in enumerate(model.materials):
		mtl = Material()
		gltf.materials.append(mtl)
		material_index_map[i] = len(gltf.materials)-1

		# Priston Tale's material names are delimited with : but that is invalid
		# for filesystems. Also remove the trailing delimiter.
		mtl.name = f"mtl_{i}-{material.name.replace("BLEND_ALPHA:", "").replace(":", "-")}"[:-1]
		mtl.alphaMode = "OPAQUE"
		mtl.doubleSided = material.two_sided
		mtl.alphaCutoff = None

		# The engine alpha-tests whenever any texture in the chain loads with an
		# alpha channel: every TGA does (new_smCreateTexture sets MapOpacity for
		# TGAs unconditionally, smTexture.cpp:4206-4210; BMPs never do,
		# smTexture.cpp:4192-4194), and an ASE *MAP_OPACITY forces an alpha load
		# even on BMPs (LoadDibSurfaceAlpha, smTexture.cpp:862, 3574-3581).
		# SetD3DRendState enables ALPHATESTENABLE at AlphaTestDepth and
		# D3DCMP_GREATEREQUAL with depth-write ON while Transparency <= 0.2
		# (ZWriteAuto, playmain.cpp:976; smRend3d.cpp:3981-3994): MASK with the
		# engine's own test depth as alphaCutoff. Above 0.2 the engine turns
		# Z-write off (true translucency): BLEND
		alpha_textures = [
			material.texture_map.diffuse_path,
			material.texture_map.selfillum_path,
			*material.texture_map.anim_frames,
		]
		if (material.texture_map.opacity_name
			or any(material.texture_map.anim_alphas)
			or any(path is not None and path.lower().endswith(".tga") for path in alpha_textures)
		):
			if material.transparency > 0.2:
				mtl.alphaMode = "BLEND"
			else:
				mtl.alphaMode = "MASK"
				mtl.alphaCutoff = 60 / 255

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

				texpath = os.path.join(fs_dir, uri.replace("#", "%23"))

				if os.path.isfile(texpath):
					gltf.images.append(Image(
						uri = uri.replace("#", "%23")
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
					if "KHR_texture_transform" not in gltf.extensionsUsed:
						gltf.extensionsUsed.append("KHR_texture_transform")

					# overlay materials are inserted before this point, so the gltf
					# material index can drift from the model's; uv animations need
					# the gltf index for their document pointers
					anim["gltf_material"] = material_index_map[i]

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

				texpath = os.path.join(fs_dir, uri.replace("#", "%23"))

				if os.path.isfile(texpath):
					gltf.images.append(Image(
						uri = uri.replace("#", "%23")
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
							alphaCutoff = 60 / 255,
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

				texpath = os.path.join(fs_dir, uri.replace("#", "%23"))

				if os.path.isfile(texpath):
					gltf.images.append(Image(
						uri = uri.replace("#", "%23")
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
		untangled_prims = make_primitives(object, gltf.nodes, anim_ids, overlay_material_ids, bool(getattr(model, "bones", None)))
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

			p.attributes.POSITION = len(gltf.accessors)-1

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

			p.attributes.NORMAL = len(gltf.accessors)-1

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

				p.attributes.TEXCOORD_0 = len(gltf.accessors)-1

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

				p.attributes.TEXCOORD_1 = len(gltf.accessors)-1

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

				p.attributes.JOINTS_0 = len(gltf.accessors)-1

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

				p.attributes.WEIGHTS_0 = len(gltf.accessors)-1

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
			if getattr(model, "bones", None) and hasattr(object, "physique") and object.physique:
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
			if getattr(model, "bones", None) and hasattr(object, "physique") and object.physique:
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
			if getattr(model, "bones", None) and hasattr(object, "physique") and object.physique:
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
			if getattr(model, "bones", None) and hasattr(object, "physique") and object.physique:
				node.skin = 0
			else:
				node.translation = [ position.x, position.y, position.z ]
				node.rotation = [ rotation.x, rotation.y, rotation.z, rotation.w ]
				node.scale = [ scale.x, scale.y, scale.z ]

			gltf.nodes.append(node)

		if hasattr(object, "animation") and (object.animation.position or object.animation.rotation or object.animation.scale):
			# animated TRS has no effect on a skinned mesh node (the skin's joint
			# transforms drive it), and the validator rejects the channel target;
			# skip before building the tracks so no unused buffers land between
			# the primitives of this and the next object
			if getattr(object, "physique", None):
				continue

			fill_animation_frames(object.animation)

			track = PTAnimationTrack()
			track.position = get_animation_track(gltf, object.animation.position, "position")
			track.rotation = get_animation_track(gltf, object.animation.rotation, "rotation")
			track.scale = get_animation_track(gltf, object.animation.scale, "scale")

			process_animation(gltf, "ani" + ("-loop" if args.godot else ""), len(gltf.nodes)-1, track, None, input_accessors)

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

				process_animation(gltf, name, bone._id, track, animation, input_accessors)

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

					process_animation(gltf, name, bone._id, track, animation, input_accessors)

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
			# engine colors are byte values that may exceed 255 (overbright, e.g.
			# dun-1 r=382); glTF clamps color to [0,1] so the overbright headroom
			# moves into intensity (color normalized to the max channel instead)
			peak = max(light.color.r, light.color.g, light.color.b, 1e-6)
			punctual = {
				"name": name,
				"type": "point",
				"color": [ light.color.r / peak, light.color.g / peak, light.color.b / peak ],
				"intensity": peak
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

	if hasattr(model, "bones") and model.bones:
		# a synthetic identity root keeps the engine's flat hierarchy (joint roots
		# and sibling weapon bones like 'Bip01 sword') while giving every skin's
		# joints one common scene ancestor, which glTF requires; skinned mesh
		# nodes stay scene roots because parent transforms would not affect them.
		# Marked as the skin's skeleton: without it the root node inserts an
		# unlisted level between the dummy import root and Bip01, which breaks
		# Blender's inverse-bind-matrix bind pose guess and rotates actors 180°
		root = Node(name = "root")
		gltf.nodes.append(root)
		root_index = len(gltf.nodes)-1
		skin.skeleton = root_index
		parented = { c for n in gltf.nodes for c in (n.children or []) }
		# a skinned mesh node must stay a scene root (parent transforms would not
		# affect it), everything else joins the synthetic root
		root.children = [
			i for i in range(root_index)
			if i not in parented and not (gltf.nodes[i].mesh is not None and gltf.nodes[i].skin is not None)
		]
		scene.nodes.append(root_index)
		scene.nodes += [
			i for i in range(root_index)
			if i not in parented and gltf.nodes[i].mesh is not None and gltf.nodes[i].skin is not None
		]
	else:
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

	return gltf


def write(path: Path, gltf: GLTF2) -> None:
	"""Writes a built glTF document to disk as .gltf or .glb."""
	path.parent.mkdir(exist_ok=True, parents=True)

	if path.suffix != ".glb":
		gltf.save(path, gltf.asset)
		return

	# pygltflib's buffers_to_binary_blob base64-decodes a buffer's URI once per
	# bufferView, so a shared buffer (one per bone track, sliced by hundreds of
	# per-clip views) is re-decoded hundreds of times; decode each buffer once
	# here and hand pygltflib the pre-assembled binary blob instead
	parts = []
	offsets = []
	total = 0
	for buffer in gltf.buffers:
		offsets.append(total)
		raw = base64.b64decode(buffer.uri.split(",", 1)[1])
		parts.append(raw)
		pad = -len(raw) % 4
		parts.append(b"\0" * pad)
		total += len(raw) + pad

	for view in gltf.bufferViews:
		view.byteOffset = (view.byteOffset or 0) + offsets[view.buffer]
		view.buffer = 0

	buffers = gltf.buffers
	views = gltf.bufferViews
	gltf.buffers = [Buffer(byteLength = total)]
	gltf.set_binary_blob(b"".join(parts))

	try:
		gltf.save_binary(path)
	finally:
		gltf.set_binary_blob(None)
		gltf.buffers = buffers
		gltf.bufferViews = views
