import base64
import numpy as np
import os

from argparse import Namespace
from ctypes import *
from dataclasses import asdict
from pathlib import Path
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
from pt.const import SCALE_INCH_TO_METER
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

	process_animation_transform(gltf, transform.rotation, "rotation", gltf_animation, node, track.rotation, animation)
	process_animation_transform(gltf, transform.position, "translation", gltf_animation, node, track.position, animation)
	process_animation_transform(gltf, transform.scale, "scale", gltf_animation, node, track.scale, animation)

	if not found and len(gltf_animation.channels) > 0:
		gltf.animations.append(gltf_animation)


""" PRIMITIVES """


def make_primitives(object: PTActorObject | PTStageObject, nodes: list[Node]) -> list[dict[str,]]:
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
			"positionbuffer": BufferReader(vert_words*3),
			"normalbuffer": BufferReader(vert_words*3),
			"texcoord0buffer": BufferReader(vert_words*2),
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
			if hasattr(object, "texture_coords") and object.texture_coords:
				tc = object.texture_coords[iface[0]]

				prim["texcoord0buffer"].write((c_float*6)(
					tc.vertices[0].u, 1-tc.vertices[0].v,
					tc.vertices[1].u, 1-tc.vertices[1].v,
					tc.vertices[2].u, 1-tc.vertices[2].v
				))
			else:
				prim["texcoord0buffer"] = None

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

		if not prim["min"]:
			prim["min"] = PTVector3()

		if not prim["max"]:
			prim["max"] = PTVector3()

		if prim["count"] > 0:
			prims.append(prim)

	return prims


""" GLTF """


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
			np_w = np.linalg.inv(np_m) # lol it's an inverted m ;D

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

	for i, material in enumerate(model.materials):
		mtl = Material()
		gltf.materials.append(mtl)

		# Priston Tale's material names are delimited with : but that is invalid
		# for filesystems. Also remove the trailing delimiter.
		mtl.name = f"mtl_{i}-{material.name.replace("BLEND_ALPHA:", "").replace(":", "-")}"[:-1]
		mtl.alphaMode = "MASK"
		mtl.doubleSided = material.two_sided
		mtl.alphaCutoff = None

		# TODO: godot flag, otherwise move to extras
		# set non-colliders to not collide
		if not material.collide and not mtl.name.find("-pass") >= 0:
			mtl.name += "-pass"

		if mtl.name.find("-notpass") >= 0:
			mtl.name = mtl.name.replace("-pass", "")

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
					mtl.emissiveFactor = [ selfillum, selfillum, selfillum ]
					mtl.emissiveTexture = TextureInfo(index = len(gltf.textures)-1)

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

	""" MESHES """

	for object in model.objects:
		untangled_prims = make_primitives(object, gltf.nodes)
		prim_pass = []
		prim_col = []
		prim_colonly = []

		m = object.transform

		# swap Y and Z (smStgObj.cpp:82)
		position = PTVector3(
			x = -m._41 * SCALE_INCH_TO_METER,
			y =  m._43 * SCALE_INCH_TO_METER,
			z =  m._42 * SCALE_INCH_TO_METER
		)

		# Priston Tale stores but does not use the transform scale
		scale = PTVector3()
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
			p = Primitive(material = prim["material"])

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
			if prim["texcoord0buffer"]:
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

			# animated objects are not collidable
			if (hasattr(object, "animation") and object.animation) or gltf.materials[prim["material"]].name.find("-pass") >= 0:
				prim_pass.append(p)
			elif gltf.materials[prim["material"]].name.find("-wall") >= 0:
				prim_colonly.append(p)
			else:
				prim_col.append(p)

			# we want to limit the number of primitives per mesh to 256 (godot limit)
			if len(prim_col) >= 256:
				gltf.meshes.append(Mesh(
					name = object.name,
					primitives = prim_col
				))

				node = Node(
					name = f"{object.name}-{len(gltf.nodes)}-col", # import hint for godot's collision system
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
					name = f"{object.name}-{len(gltf.nodes)}-colonly", # import hint for godot's collision system
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
		if len(prim_col) > 0:
			gltf.meshes.append(Mesh(
				name = object.name,
				primitives = prim_col
			))

			node = Node(
				name = f"{object.name}-{len(gltf.nodes)}-col", # import hint for godot's collision system
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
				name = f"{object.name}-{len(gltf.nodes)}-colonly", # import hint for godot's collision system
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

			process_animation(gltf, object.animation, "ani-loop", len(gltf.nodes)-1, track)

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
				if animation.repeat:
					name += "-loop" # TODO: flag this for godot and instead put it in extras by default?

				process_animation(gltf, bone.animation, name, bone._id, track, animation)

	""" SCENE """

	scene = Scene()
	for i, node in enumerate(gltf.nodes):
		# armature will always start at 0
		# everything after the joint nodes is also a root
		if i == 0 or i >= (len(model.bones) if hasattr(model, "bones") else 0):
			scene.nodes.append(i)
	gltf.scenes.append(scene)

	path.parent.mkdir(exist_ok=True, parents=True)
	gltf.save(path)
