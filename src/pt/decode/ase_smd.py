"""ASE -> SMD/SMB conversion.

Mirrors the original pipeline end to end: smASE_Read / smASE_ReadBone
(smRead3d.cpp) parse the ASE, build smOBJ3D structures, convert them, and
serialize with smPAT3D::SaveFile (smObj3d.cpp:2852). Here the ASE parses into
the PT model structures (decode_ase) and those serialize to the binary formats
(save_actor_smd / save_bones_smb).

Round-trip contract with src/pt/encode/ase.py: the encoder emits exactly the
constructions this decoder (and the engine importers it mirrors) read back.
"""

import math
import os
import struct

import numpy as np
from ctypes import *

from pt.buffer import BufferReader
from pt.cdef import *
from pt.pdef import *
from pt.decode.ase import (
	parse_ase,
	quat_from_axisangle,
	FONE,
	SM_LIGHT_DYNAMIC
)
from pt.decode.smd import decode_mesh_state
from pt.const import (
	ACTOR_SIGNATURE,
	STAGE_SIGNATURE,
	OBJECT_HEAD,
	MTL_FORM_BLEND
)
from pt.utils import normalize_quaternion


MATS_SCRIPT_ANIM = { 2: 2, 4: 4, 8: 8, 16: 16 }


def to_fixed(v: float) -> int:
	"""(int)(atof * fONE) truncation toward zero, as in the ASE readers."""
	return int(v * FONE)


def encode_string(value: str) -> bytes:
	return value.encode("ascii", errors="ignore")


def string_field(value: str, size: int) -> bytes:
	data = encode_string(value)[:size-1]
	return data + b"\x00" * (size - len(data))


def sm_matrix_from_rows(rows: list[float]) -> smMATRIX:
	"""Authored *TM_ROW values into smMATRIX, stored verbatim like the
	importer's assignments (ReadASE_GEOMOBJECT, smRead3d.cpp:1199-1253):
	8.8 fixed point, _14/_24/_34 = 0, _44 = fONE. rows is the flat row-major
	list laid out like the importer's Tm array (12 = translation row)."""
	m = smMATRIX()
	m._11 = to_fixed(rows[0]); m._12 = to_fixed(rows[1]); m._13 = to_fixed(rows[2]); m._14 = 0
	m._21 = to_fixed(rows[4]); m._22 = to_fixed(rows[5]); m._23 = to_fixed(rows[6]); m._24 = 0
	m._31 = to_fixed(rows[8]); m._32 = to_fixed(rows[9]); m._33 = to_fixed(rows[10]); m._34 = 0
	m._41 = to_fixed(rows[12]); m._42 = to_fixed(rows[13]); m._43 = to_fixed(rows[14]); m._44 = FONE
	return m


def sm_matrix_from_ptmat(m: PTMat4) -> smMATRIX:
	return sm_matrix_from_rows([
		m._11, m._12, m._13, 0,
		m._21, m._22, m._23, 0,
		m._31, m._32, m._33, 0,
		m._41, m._42, m._43, 1
	])


def tm_invert(m: smMATRIX) -> smMATRIX:
	"""General 4x4 inverse in float math; TmInvert is runtime scratch that
	smOBJ3D::LoadFile overwrites, so the precision difference against the
	engine's fixed-point smMatrixInvert (smmatrix.cpp:140) is irrelevant."""
	a = np.array([
		[m._11 / FONE, m._12 / FONE, m._13 / FONE, 0],
		[m._21 / FONE, m._22 / FONE, m._23 / FONE, 0],
		[m._31 / FONE, m._32 / FONE, m._33 / FONE, 0],
		[m._41 / FONE, m._42 / FONE, m._43 / FONE, 1]
	], dtype=np.float64)

	q = smMATRIX()
	try:
		inv = np.linalg.inv(a)
	except np.linalg.LinAlgError:
		return q

	for i, field in enumerate((
		"_11", "_12", "_13", "_14", "_21", "_22", "_23", "_24",
		"_31", "_32", "_33", "_34", "_41", "_42", "_43", "_44"
	)):
		setattr(q, field, int(inv[i // 4][i % 4] * 65536))

	return q


def default_frame_table(pos: int, count: int) -> list[smFRAME_POS]:
	"""One readable window over the whole key array (GetTmFrameRot's
	StartFrame <= frame < EndFrame && PosCnt > 0 test, smObj3d.cpp:1296)."""
	entry = smFRAME_POS()
	entry.StartFrame = 0
	entry.EndFrame = 0x7FFFFFFF
	entry.PosNum = pos
	entry.PosCnt = count
	return [entry] + [smFRAME_POS() for _ in range(31)]


def set_frame_table(table, pos: int, count: int) -> None:
	for i, entry in enumerate(default_frame_table(pos, count)):
		table[i] = entry


def quat_to_matrix(q: PTQuaternion) -> np.ndarray:
	xx, yy, zz = q.x*q.x, q.y*q.y, q.z*q.z
	xy, xz, yz = q.x*q.y, q.x*q.z, q.y*q.z
	wx, wy, wz = q.w*q.x, q.w*q.y, q.w*q.z
	return np.array([
		[1-2*(yy+zz), 2*(xy-wz), 2*(xz+wy), 0],
		[2*(xy+wz), 1-2*(xx+zz), 2*(yz-wx), 0],
		[2*(xz-wy), 2*(yz+wx), 1-2*(xx+yy), 0],
		[0, 0, 0, 1]
	], dtype=np.float64)


def prev_rot_matrices(rotations: list[PTAnimationRotation]) -> list:
	"""TmPrevRot[cnt] = accumulated product of the per-key quaternion matrices
	(smRead3d.cpp:1616-1628); the SMD decoders skip this block."""
	matrices = []
	acc = np.identity(4, dtype=np.float64)

	for rot in rotations:
		acc = quat_to_matrix(rot) @ acc
		matrices.append(acc)

	return matrices


def register_materials(ase_materials: list) -> int:
	"""AddMaterial equivalent: ReadASE_MATERIAL registers every material in the
	flattened array in index order (only byte-identical duplicates share a
	slot), including the no-bitmap wrapper material. The shipped
	death_knight pair pins this: ASE MTLIDs 0..5 land on SMD material ids
	1..6 because the wrapper takes slot 0. Registration stops at the
	material count the ASE itself declared (aseMaterialCnt = last index + 1
	in ReadASE_MATERIAL, smRead3d.cpp:558)."""
	regist = 0

	for material in ase_materials:
		material.RegistNum = regist
		regist += 1

	return regist


def decode_ase_materials(ase_materials: list) -> list[PTModelMaterial]:
	"""smMATERIAL fields from the parsed ASE material (AddMaterial,
	smTexture.cpp:780-1010): MeshState from the script/gradient machine
	(decode_mesh_state), WindMeshBottom from the wind/water/blink scripts."""
	materials = []

	for material in ase_materials:
		if material.RegistNum < 0:
			continue

		while len(materials) <= material.RegistNum:
			materials.append(PTModelMaterial())

		target = materials[material.RegistNum]
		target.name = ""
		target.num_textures = material.TextureCounter
		target.ambient = [material.Diffuse.x, material.Diffuse.y, material.Diffuse.z]
		target.diffuse = [material.Diffuse.x, material.Diffuse.y, material.Diffuse.z]
		target.specular = [0.9, 0.9, 0.9]
		target.transparency = material.Transparency
		target.selfillum = material.SelfIllum > 0
		target.two_sided = material.TwoSide > 0
		target.script_flags = material.ScriptState
		target.blend_type = material.BlendType
		target.mesh_flags = decode_mesh_state(material.ScriptState, material.Transparency)
		target.collide = (target.mesh_flags & 1) == 1

		# plain "wind:" maps to WINDZ1 (AddMaterial, smTexture.cpp:884-887)
		if material.ScriptState & 0x1: target.wind_mesh_bottom = 0x20
		if material.ScriptState & 0x20: target.wind_mesh_bottom = 0x20
		if material.ScriptState & 0x40: target.wind_mesh_bottom = 0x40
		if material.ScriptState & 0x80: target.wind_mesh_bottom = 0x80
		if material.ScriptState & 0x100: target.wind_mesh_bottom = 0x100
		if material.ScriptState & 0x200: target.wind_mesh_bottom = 0x200

		if material.BITMAP:
			target.texture_map.diffuse_path = material.BITMAP[0]

		if len(material.BITMAP) > 1:
			path = material.BITMAP[1]
			name = material.BitmapFormState[1]
			if "lightingmap" in path.lower():
				target.texture_map.lightmap_path = path
			else:
				target.texture_map.selfillum_path = path

		if len(material.BITMAP) > 2:
			target.texture_map.thirdstage_path = material.BITMAP[2]

		if material.MAP_OPACITY:
			target.texture_map.opacity_path = material.MAP_OPACITY

	return materials


def uv_from_transform(material, stage: int, u: float, v: float) -> tuple[float, float]:
	"""The importer's texlink UV transform, applied when reading the TVERT
	pool (ReadASE_GEOMOBJECT, smRead3d.cpp:1478-1511): offset/tiling/angle of
	the material's bitmap for this stage, plus the 1-fv flip."""
	if not material or not material.UVW_ANGLE:
		return u, v

	stage = min(stage, len(material.UVW_ANGLE) - 1)
	radians = material.UVW_ANGLE[stage]
	cos, sin = math.cos(radians), math.sin(radians)
	fu = (u - 0.5) * cos + (v - 0.5) * sin
	fv = (v - 0.5) * cos - (u - 0.5) * sin
	fu -= material.UVW_U_OFFSET[stage]
	fv -= material.UVW_V_OFFSET[stage]
	fu *= material.UVW_U_TILING[stage]
	fv *= material.UVW_V_TILING[stage]
	return fu + 0.5, fv + 0.5


def decode_texlink_sets(obj, material, face_index: int) -> list[list[PTTextureVertex]]:
	"""One uv_sets entry per texture stage: the importer adds one link per
	face per stage (ReadASE_GEOMOBJECT tail, smRead3d.cpp:1455-1560), the
	lightmap link coming from the second TVERT pool when *MESH_MAPPINGCHANNEL
	switched pools."""
	sets = []

	if not obj.tface or face_index >= len(obj.tface):
		return sets

	count = material.TextureCounter if material else 0

	# Pool 1 carries the primary UV set for every face. The second pool
	# (after *MESH_MAPPINGCHANNEL) holds the additional texture-stage UVs of
	# faces whose material has more than one texture; one-texture materials
	# wrote zeros there and get no extra set.
	corner = []
	for k in range(3):
		tindex = obj.tface[face_index][k]
		u, v = obj.tvertex[tindex]
		fu, fv = uv_from_transform(material, 0, u, v)
		corner.append(PTTextureVertex(u = fu, v = fv))
	sets.append(corner)

	# the extra pools carry uv set j (j >= 1) of every face; one-texture
	# materials wrote zeros there and their faces get no extra set
	if obj.bLightMap:
		extra_pool = [ (obj.lightmap_tvertex, obj.lightmap_tface, 1) ]
		extra_pool += [ (obj.extra_tvertex, obj.extra_tface, j) for j in range(2, count) ]

		for tverts, tfaces, set_index in extra_pool:
			if not tfaces or face_index >= len(tfaces) or set_index >= count:
				continue
			corner = []
			for k in range(3):
				tindex = tfaces[face_index][k]
				u, v = tverts[tindex]
				fu, fv = uv_from_transform(material, min(set_index, len(material.UVW_ANGLE) - 1) if material else 0, u, v)
				corner.append(PTTextureVertex(u = fu, v = fv))
			if any(abs(c.u) > 1e-9 or abs(c.v) > 1e-9 for c in corner):
				sets.append(corner)

	return sets


def make_animation(obj) -> tuple[PTActorAnimation, int | None]:
	animation = PTActorAnimation()
	last = None

	if obj.TmRot:
		animation.rotation = [
			PTAnimationRotation(
				frame = frame,
				x = x * math.sin(w / 2),
				y = y * math.sin(w / 2),
				z = z * math.sin(w / 2),
				w = math.cos(w / 2)
			)
			for frame, x, y, z, w in obj.TmRot
		]
		animation.rotation_windows = [(0, len(obj.TmRot))]
		last = obj.TmRot[-1][0]

	if obj.TmPos:
		animation.position = [
			PTAnimationPosition(frame = frame, x = x, y = y, z = z)
			for frame, x, y, z in obj.TmPos
		]
		last = obj.TmPos[-1][0]

	if obj.TmScale:
		animation.scale = [
			PTAnimationScale(frame = frame, x = x, y = y, z = z)
			for frame, x, y, z in obj.TmScale
		]

	return animation, last


def make_transform(obj) -> PTObjectTransform:
	return PTObjectTransform(
		_11 = obj.Tm[0], _12 = obj.Tm[1], _13 = obj.Tm[2], _14 = 0,
		_21 = obj.Tm[4], _22 = obj.Tm[5], _23 = obj.Tm[6], _24 = 0,
		_31 = obj.Tm[8], _32 = obj.Tm[9], _33 = obj.Tm[10], _34 = 0,
		_41 = obj.Tm[12], _42 = obj.Tm[13], _43 = obj.Tm[14], _44 = 1,
		position = PTVector3(obj.px, obj.py, obj.pz),
		rotation = quat_from_axisangle((obj.qx, obj.qy, obj.qz), obj.qw) if obj.has_qrot else PTQuaternion(),
		scale = PTVector3(obj.sx / FONE, obj.sy / FONE, obj.sz / FONE)
	)


def make_object_transform_rotate(obj) -> PTMat4:
	"""TmRotate from *TM_ROTAXIS/*TM_ROTANGLE (smMatrixFromQuaternion,
	smmatrix.cpp:190); the identity axis-angle (z, 0) decodes to identity."""
	q = quat_from_axisangle((obj.qx, obj.qy, obj.qz), obj.qw)
	m = PTMat4()
	m._11 = 1 - 2*(q.y**2 + q.z**2)
	m._12 = 2*(q.x*q.y - q.w*q.z)
	m._13 = 2*(q.x*q.z + q.w*q.y)
	m._21 = 2*(q.x*q.y + q.w*q.z)
	m._22 = 1 - 2*(q.x**2 + q.z**2)
	m._23 = 2*(q.y*q.z - q.w*q.x)
	m._31 = 2*(q.x*q.z - q.w*q.y)
	m._32 = 2*(q.y*q.z + q.w*q.x)
	m._33 = 1 - 2*(q.x**2 + q.y**2)
	return m


def fill_object(object: PTActorObject | PTActorBone, obj, material_ref) -> None:
	object.name = obj.NodeName
	object.parent = obj.NodeParent or None
	object.num_vertices = len(obj.vertices)
	object.num_faces = len(obj.faces)
	object.num_texture_links = len(obj.tface)
	object.num_tfm_rotations = len(obj.TmRot)
	object.num_tfm_positions = len(obj.TmPos)
	object.num_tfm_scales = len(obj.TmScale)
	object.vertices = [ PTVector3(x, y, z) for x, y, z in obj.vertices ]
	object.faces = [
		PTObjectFace(vertices = [a, b, c], material_id = obj.FaceMatrial[i])
		for i, (a, b, c) in enumerate(obj.faces)
	]
	object.transform = make_transform(obj)
	animation, _ = make_animation(obj)
	object.animation = animation

	if isinstance(object, PTActorObject):
		object.transform_rotate = make_object_transform_rotate(obj)


def decode_ase_stage(path: str) -> PTStageModel | None:
	"""smSTAGE3D_ReadASE (smRead3d.cpp:3123-3290): every GEOMOBJECT appends
	into one stage; vertices map (x,z,y); TVERTs negate v; the mesh carries
	per-face MTLIDs resolved through the flattened material array."""
	ase = parse_ase(path)
	register_materials(ase["materials"])

	model = PTStageModel()
	model.filename = os.path.splitext(os.path.basename(path))[0]
	model.materials = decode_ase_materials(ase["materials"])

	object = PTStageObject()
	vertices = []
	faces = []
	texture_coords = []

	for obj in ase["objects"]:
		base = len(vertices)
		face_base = len(faces)
		material = ase["materials"][obj.MatrialRef] if obj.MatrialRef < len(ase["materials"]) else None

		# AddVertex(x, z, y) stores (x, z_ase, y_ase) and decode_stage_vertices
		# swaps back to (x, z, y) - the two swaps cancel, so the PT vertex
		# equals the ASE vertex verbatim
		vertices.extend(PTVector3(x, y, z) for x, y, z in obj.vertices)

		for i, (a, b, c) in enumerate(obj.faces):
			fmat = obj.MatrialRef + obj.FaceMatrial[i]
			if material and material.SubPoint:
				fmat = material.SubPoint + obj.FaceMatrial[i]
			registered = ase["materials"][fmat] if fmat < len(ase["materials"]) else None
			material_id = registered.RegistNum if registered and registered.RegistNum >= 0 else 0

			faces.append(PTObjectFace(vertices = [base + a, base + b, base + c], material_id = material_id))

			sets = decode_texlink_sets(obj, registered, i)
			texture_coords.append(PTObjectTexture_Coord(
				face = PTObjectFace(vertices = [face_base + i, 0, 0]),
				uv_sets = sets
			))

	object.vertices = vertices
	object.faces = faces
	object.num_vertices = len(vertices)
	object.num_faces = len(faces)
	object.num_texture_links = sum(len(t.uv_sets) for t in texture_coords)

	for i, tex in enumerate(texture_coords):
		tex.face.vertices = [i * 3, i * 3 + 1, i * 3 + 2]
		object.texture_coords.append(tex)

	model.objects.append(object)
	model.lights = [
		PTStageLight(
			type_flags = light.Type,
			dynamic = bool(light.Type & SM_LIGHT_DYNAMIC),
			night = bool(light.Type & 0x1),
			lens = bool(light.Type & 0x2),
			pulse = bool(light.Type & 0x4),
			obj = bool(light.Type & 0x8),
			# *TM_POS reads (x, z, y) into the engine struct, so the stored
			# (x, y, z) here is the ASE order; swap like decode_stage_lights
			position = PTVector3(light.x / FONE, light.z / FONE, light.y / FONE),
			range = light.Range / FONE,
			color = PTColorVertex(light.r / 255, light.g / 255, light.b / 255, 1)
		)
		for light in ase["lights"]
	]

	# engine defaults (smStage3d.cpp:365-370)
	model.contrast = 300
	model.bright = 130
	model.vect_light = PTVector3(1.0, -1.0, 0.5)

	return model


def decode_ase(path: str, dirpath: str | None = None) -> PTActorModel | None:
	"""smASE_Read + smASE_ReadBone: one ASE carries the biped bones (Bip*
	nodes, saved to .smb) and the meshes (saved to .smd)."""
	ase = parse_ase(path)
	register_materials(ase["materials"])

	model = PTActorModel()
	model.filename = os.path.splitext(os.path.basename(path))[0]
	model.materials = decode_ase_materials(ase["materials"])
	model.scene.ticks_per_frame = ase["ticks"]

	bones = []
	objects = []

	for obj in ase["objects"]:
		is_bone = obj.NodeName.lower().startswith("bip")

		if is_bone:
			bone = PTActorBone()
			fill_object(bone, obj, obj.MatrialRef)
			bones.append(bone)
		elif obj.vertices:
			object = PTActorObject()
			fill_object(object, obj, obj.MatrialRef)
			object.physique = list(obj.Physique)

			material = ase["materials"][obj.MatrialRef] if obj.MatrialRef < len(ase["materials"]) else None
			for i, face in enumerate(object.faces):
				# fmat = SubPoint + MTLID when the *MATERIAL_REF carries
				# submaterials, else MatrialRef (ReadASE_GEOMOBJECT,
				# smRead3d.cpp:1455-1460); the registered material then comes
				# from the flattened array's RegistNum
				# fmat resolves MTLID against the flattened array; with no
				# submaterial wrapper (SubPoint 0) the flat layout indexes
				# materials directly from MTLID
				fmat = obj.MatrialRef + obj.FaceMatrial[i]
				if material and material.SubPoint:
					fmat = material.SubPoint + obj.FaceMatrial[i]
				registered = ase["materials"][fmat] if fmat < len(ase["materials"]) else None
				face.material_id = registered.RegistNum if registered and registered.RegistNum >= 0 else 0

				sets = decode_texlink_sets(obj, registered, i)
				object.texture_coords.append(PTObjectTexture_Coord(face = face, uv_sets = sets))

			objects.append(object)

	model.bones = bones
	model.objects = objects

	# MaxFrame: AddObject keeps the max over last pos/rot keys
	last_frame = 0
	for object in bones + objects:
		animation = object.animation
		if animation.position:
			last_frame = max(last_frame, animation.position[-1].frame)
		elif animation.rotation:
			last_frame = max(last_frame, animation.rotation[-1].frame)

	model.scene.last_frame = last_frame // model.scene.ticks_per_frame

	return model


def write_actor_object(object: PTActorObject | PTActorBone, has_physique: bool) -> tuple[smOBJ3D, bytes]:
	sm_object = smOBJ3D()
	sm_object.Head = OBJECT_HEAD
	sm_object.Physique_ptr = 1 if has_physique else 0
	sm_object.nVertex = object.num_vertices
	sm_object.nFace = object.num_faces
	sm_object.nTexLink = sum(len(tex.uv_sets) for tex in object.texture_coords)
	sm_object.TmRotCnt = object.num_tfm_rotations
	sm_object.TmPosCnt = object.num_tfm_positions
	sm_object.TmScaleCnt = object.num_tfm_scales
	for i, byte in enumerate(string_field(object.name or "", 32)):
		sm_object.NodeName[i] = byte
	for i, byte in enumerate(string_field(object.parent or "", 32)):
		sm_object.NodeParent[i] = byte

	sm_object.Tm = sm_matrix_from_ptmat(object.transform)
	sm_object.TmInvert = tm_invert(sm_object.Tm)
	sm_object.TmRotate = sm_matrix_from_ptmat(getattr(object, "transform_rotate", PTMat4()))

	sm_object.px = to_fixed(object.transform.position.x)
	sm_object.py = to_fixed(object.transform.position.y)
	sm_object.pz = to_fixed(object.transform.position.z)
	sm_object.sx = to_fixed(object.transform.scale.x)
	sm_object.sy = to_fixed(object.transform.scale.y)
	sm_object.sz = to_fixed(object.transform.scale.z)

	q = object.transform.rotation
	sm_object.qx = q.x; sm_object.qy = q.y; sm_object.qz = q.z; sm_object.qw = q.w

	set_frame_table(sm_object.TmRotFrame, 0, sm_object.TmRotCnt)
	set_frame_table(sm_object.TmPosFrame, 0, sm_object.TmPosCnt)
	set_frame_table(sm_object.TmScaleFrame, 0, sm_object.TmScaleCnt)
	sm_object.TmFrameCnt = 1 if sm_object.TmRotCnt + sm_object.TmPosCnt + sm_object.TmScaleCnt else 0

	payload = b""

	for vertex in object.vertices:
		sm_vertex = smVERTEX()
		sm_vertex.x = to_fixed(vertex.x)
		sm_vertex.y = to_fixed(vertex.y)
		sm_vertex.z = to_fixed(vertex.z)
		payload += bytes(sm_vertex)

	# face lpTexLink_ptr / NextTex_ptr hold stale runtime addresses on disk;
	# loaders convert pointer differences into element indices
	# (smObj3d.cpp:2200-2216). Links append in face order (AddTexLink), so a
	# base of 32 with ptr = 32 * (element + 1) makes element_index resolve
	# exactly; 0 keeps meaning "no texture link".
	face_ptrs = []
	ptr = 0

	for tex in object.texture_coords:
		face_ptrs.append((ptr + 1) * 32 if tex.uv_sets else 0)
		ptr += len(tex.uv_sets)

	for i, face in enumerate(object.faces):
		sm_face = smFACE()
		sm_face.v[0] = face.vertices[0]
		sm_face.v[1] = face.vertices[1]
		sm_face.v[2] = face.vertices[2]
		sm_face.v[3] = face.material_id or 0
		sm_face.lpTexLink_ptr = face_ptrs[i] if i < len(face_ptrs) else 0
		payload += bytes(sm_face)

	ptr = 0
	for tex in object.texture_coords:
		for j, uv_set in enumerate(tex.uv_sets):
			sm_texlink = smTEXLINK()
			for k, uv in enumerate(uv_set):
				sm_texlink.u[k] = uv.u
				sm_texlink.v[k] = uv.v
			if j + 1 < len(tex.uv_sets):
				sm_texlink.NextTex_ptr = (ptr + 1) * 32
			payload += bytes(sm_texlink)
			ptr += 1

	animation = object.animation

	for rot in animation.rotation:
		sm_rot = smTM_ROT()
		sm_rot.frame = rot.frame
		sm_rot.x = rot.x; sm_rot.y = rot.y; sm_rot.z = rot.z; sm_rot.w = rot.w
		payload += bytes(sm_rot)

	for pos in animation.position:
		sm_pos = smTM_POS()
		sm_pos.frame = pos.frame
		sm_pos.x = pos.x; sm_pos.y = pos.y; sm_pos.z = pos.z
		payload += bytes(sm_pos)

	for scl in animation.scale:
		sm_scl = smTM_SCALE()
		sm_scl.frame = scl.frame
		sm_scl.x = to_fixed(scl.x); sm_scl.y = to_fixed(scl.y); sm_scl.z = to_fixed(scl.z)
		payload += bytes(sm_scl)

	for matrix in prev_rot_matrices(animation.rotation):
		sm_fmatrix = smFMATRIX()
		for i, field in enumerate((
			"_11", "_12", "_13", "_14", "_21", "_22", "_23", "_24",
			"_31", "_32", "_33", "_34", "_41", "_42", "_43", "_44"
		)):
			setattr(sm_fmatrix, field, float(matrix[i // 4][i % 4]))
		payload += bytes(sm_fmatrix)

	if has_physique:
		for name in object.physique:
			payload += bytes(string_field(name, 32))

	return sm_object, payload


def material_texture_paths(material: PTModelMaterial) -> list[str]:
	tm = material.texture_map
	paths = []

	if tm.diffuse_path:
		paths.append(tm.diffuse_path)
	if tm.selfillum_path or tm.lightmap_path:
		paths.append(tm.selfillum_path or tm.lightmap_path)
	if tm.thirdstage_path:
		paths.append(tm.thirdstage_path)

	return paths


def write_material_blob(material: PTModelMaterial, paths: list[str]) -> bytes:
	"""smMATERIAL + path blob exactly as smMATERIAL_GROUP::SaveFile writes it
	(smTexture.cpp:603): 320 bytes, then the (Name, NameA) NUL-string pairs
	only when InUse; each pair is Name + '\\0' + NameA + '\\0'."""
	sm_material = smMATERIAL()
	sm_material.InUse = 1
	sm_material.TextureCounter = len(paths)
	sm_material.TextureStageState[0] = 4  # D3DTOP_MODULATE
	sm_material.BlendType = material.blend_type
	sm_material.Transparency = material.transparency
	sm_material.SelfIllum = 1.0 if material.selfillum else 0.0
	sm_material.TwoSide = 1 if material.two_sided else 0
	sm_material.UseState = material.script_flags
	sm_material.MeshState = material.mesh_flags
	sm_material.WindMeshBottom = material.wind_mesh_bottom
	sm_material.Diffuse[0] = material.diffuse[0]
	sm_material.Diffuse[1] = material.diffuse[1]
	sm_material.Diffuse[2] = material.diffuse[2]

	blob = b""

	for path in paths:
		blob += string_field(path, len(path) + 1)
		blob += b"\x00" # NameA stays empty

	return bytes(sm_material) + struct.pack("<I", len(blob)) + blob


def write_bytes(buffer: BufferReader, data: bytes) -> None:
	"""Raw bytes at the current cursor (BufferReader.write only takes ctypes)."""
	buffer.data[buffer.offset:buffer.offset + len(data)] = data
	buffer.offset += len(data)


def save_actor(model: PTActorModel, path: str, bones: bool) -> None:
	"""smPAT3D::SaveFile layout: header, objinfo table, material group +
	blobs, then the per-object blocks (MatFilePoint = 556 + 40*ObjCounter)."""
	objects = model.bones if bones else model.objects
	has_physique = not bones and any(object.physique for object in objects)
	materials = model.materials if not bones else []

	object_payloads = [ write_actor_object(object, has_physique) for object in objects ]
	material_blobs = [
		write_material_blob(material, material_texture_paths(material))
		for material in materials
	]

	mat_file_point = 556 + 40 * len(objects)
	first_obj_point = mat_file_point + (88 if materials else 0) + sum(len(blob) for blob in material_blobs)
	total = first_obj_point + sum(sizeof(smOBJ3D) + len(payload) for sm_object, payload in object_payloads)

	buffer = BufferReader(total)
	buffer.seek(0)

	header = smDFILE_HEADER()
	for i, byte in enumerate(encode_string(ACTOR_SIGNATURE)[:23]):
		header.szHeader[i] = byte
	header.ObjCounter = len(objects)
	header.MatCounter = len(materials)
	header.MatFilePoint = mat_file_point
	header.First_ObjInfoPoint = first_obj_point
	header.TmFrameCounter = 0
	buffer.write(header)

	offset = first_obj_point

	for (sm_object, payload), object in zip(object_payloads, objects):
		info = smDFILE_OBJINFO()
		for i, byte in enumerate(string_field(object.name or "", 32)):
			info.szNodeName[i] = byte
		info.Length = sizeof(smOBJ3D) + len(payload)
		info.ObjFilePoint = offset
		buffer.write(info)
		offset += info.Length

	if materials:
		group = smMATERIAL_GROUP()
		group.Head = 0x41424344
		group.MaterialCount = len(materials)
		buffer.write(group)

		for blob in material_blobs:
			write_bytes(buffer, blob)

	for sm_object, payload in object_payloads:
		buffer.write(sm_object)
		write_bytes(buffer, payload)

	with open(path, "wb") as f:
		f.write(buffer.get_data())


def save_actor_smd(model: PTActorModel, path: str) -> None:
	save_actor(model, path, bones=False)


def save_bones_smb(model: PTActorModel, path: str) -> None:
	save_actor(model, path, bones=True)


def write_stage(model: PTStageModel) -> bytes:
	"""smSTAGE3D::SaveFile (smStage3d.cpp:2291): header, smSTAGE3D, material
	group + blobs, vertices, faces, texlinks, lights, area partitions. The
	StageArea draw-partition grid is engine batching data rebuilt at import
	(SetupPolyAreas), so it is written empty."""
	vertices = 0
	faces = 0
	texlinks = 0
	for object in model.objects:
		vertices += object.num_vertices
		faces += object.num_faces
		texlinks += sum(len(t.uv_sets) for t in object.texture_coords)

	material_blobs = [
		write_material_blob(material, material_texture_paths(material))
		for material in model.materials
	]

	header_size = sizeof(smDFILE_HEADER)
	stage_size = sizeof(smSTAGE3D)
	mat_size = (88 if model.materials else 0) + sum(len(blob) for blob in material_blobs)
	total = header_size + stage_size + mat_size
	total += vertices * sizeof(smSTAGE_VERTEX)
	total += faces * sizeof(smSTAGE_FACE)
	total += texlinks * sizeof(smTEXLINK)
	total += len(model.lights) * sizeof(smLIGHT3D)

	buffer = BufferReader(total)
	buffer.seek(0)

	header = smDFILE_HEADER()
	for i, byte in enumerate(encode_string(STAGE_SIGNATURE)[:23]):
		header.szHeader[i] = byte
	header.ObjCounter = 0
	header.MatCounter = len(model.materials)
	header.MatFilePoint = header_size
	header.First_ObjInfoPoint = header_size + stage_size + mat_size
	buffer.write(header)

	stage = smSTAGE3D()
	stage.nVertex = vertices
	stage.nFace = faces
	stage.nTexLink = texlinks
	stage.nLight = len(model.lights)
	stage.nVertColor = vertices
	stage.Contrast = model.contrast
	stage.Bright = model.bright
	stage.VectLight.x = int(model.vect_light.x * FONE)
	stage.VectLight.y = int(model.vect_light.y * FONE)
	stage.VectLight.z = int(model.vect_light.z * FONE)
	stage.StageMapRect.left = 0
	stage.StageMapRect.top = 0
	stage.StageMapRect.right = 0
	stage.StageMapRect.bottom = 0
	buffer.write(stage)

	if model.materials:
		group = smMATERIAL_GROUP()
		group.Head = 0x41424344
		group.MaterialCount = len(model.materials)
		buffer.write(group)
		for blob in material_blobs:
			write_bytes(buffer, blob)

	for object in model.objects:
		for i, vertex in enumerate(object.vertices):
			# decode_stage_vertices swaps (x, z, y); the writer swaps back
			sm_vertex = smSTAGE_VERTEX()
			sm_vertex.x = to_fixed(vertex.x)
			sm_vertex.y = to_fixed(vertex.z)
			sm_vertex.z = to_fixed(vertex.y)
			if i < len(object.vertex_colors):
				color = object.vertex_colors[i]
				sm_vertex.sDef_Color[0] = int(color.b * 255)  # SMC_B
				sm_vertex.sDef_Color[1] = int(color.g * 255)  # SMC_G
				sm_vertex.sDef_Color[2] = int(color.r * 255)  # SMC_R
				sm_vertex.sDef_Color[3] = 255                 # SMC_A
			else:
				sm_vertex.sDef_Color[0] = 255
				sm_vertex.sDef_Color[1] = 255
				sm_vertex.sDef_Color[2] = 255
				sm_vertex.sDef_Color[3] = 255
			payload = bytes(sm_vertex)
			write_bytes(buffer, payload)

	ptr = 0
	face_ptrs = []
	for tex in object.texture_coords:
		face_ptrs.append((ptr + 1) * 32 if tex.uv_sets else 0)
		ptr += len(tex.uv_sets)

	for object in model.objects:
		for i, face in enumerate(object.faces):
			sm_face = smSTAGE_FACE()
			sm_face.Vertex[0] = face.vertices[0]
			sm_face.Vertex[1] = face.vertices[1]
			sm_face.Vertex[2] = face.vertices[2]
			sm_face.Vertex[3] = face.material_id or 0
			sm_face.lpTexLink_ptr = face_ptrs[i] if i < len(face_ptrs) else 0
			write_bytes(buffer, bytes(sm_face))

	for object in model.objects:
		for tex in object.texture_coords:
			for j, uv_set in enumerate(tex.uv_sets):
				sm_texlink = smTEXLINK()
				for k, uv in enumerate(uv_set):
					sm_texlink.u[k] = uv.u
					sm_texlink.v[k] = uv.v
				if j + 1 < len(tex.uv_sets):
					sm_texlink.NextTex_ptr = (ptr + 1) * 32
				write_bytes(buffer, bytes(sm_texlink))
				ptr += 1

	for light in model.lights:
		sm_light = smLIGHT3D()
		sm_light.type = light.type_flags
		# decode_stage_lights reads (x, z, y) from the engine struct
		sm_light.x = to_fixed(light.position.x)
		sm_light.y = to_fixed(light.position.z)
		sm_light.z = to_fixed(light.position.y)
		sm_light.Range = to_fixed(light.range)
		sm_light.r = int(light.color.r * 255)
		sm_light.g = int(light.color.g * 255)
		sm_light.b = int(light.color.b * 255)
		write_bytes(buffer, bytes(sm_light))

	return buffer.get_data()


def save_stage_smd(model: PTStageModel, path: str) -> None:
	data = write_stage(model)
	with open(path, "wb") as f:
		f.write(data)
