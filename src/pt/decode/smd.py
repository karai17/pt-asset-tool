import os

from ctypes import *

from pt.buffer import BufferReader
from pt.cdef import *
from pt.pdef import *
from pt.utils import decode_string, get_filename, sm_tm_to_np, sm_tm_parent_local, decompose_rotation
from pt.const import (
	STAGE_SIGNATURE,
	ACTOR_SIGNATURE,
	OBJECT_HEAD,
	OBJECT_HEAD_OLD,
	STAGE_SCRIPT,
	FORM_SCRIPT,
	MTL_FORM_BLEND,
	MTL_FORM_SCRIPT
)


decoded_objects = [] # list of all objects (iterative)


# Actor files are smPAT3D files: smDFILE_HEADER, smDFILE_OBJINFO[ObjCounter],
# materials, then ObjCounter object blocks written by smOBJ3D::SaveFile
# (smObj3d.cpp:2856 SaveFile, :2937 LoadFile, :2110 smOBJ3D::SaveFile,
# :2146 smOBJ3D::LoadFile). Stage files are smSTAGE3D files written by
# smSTAGE3D::SaveFile (smStage3d.cpp:2291) / LoadFile (smStage3d.cpp:2362).


def decode_material_name(script_flags, blend_flag):
	name = ""

	for flag in MTL_FORM_SCRIPT:
		if script_flags & flag[1] == flag[1]:
			name = name + flag[0]

	for flag in MTL_FORM_BLEND:
		if blend_flag & flag[1] == flag[1]:
			name = name + flag[0]
			break

	return name


# Rebuild ASE texture map names from the flag bits parsed out of *MAP_NAME
# strings at import (smRead3d.cpp:367-384: BsStageScript values are D3DTOP_
# enums, BitmapFormState is the szMapFormScript table index).
def decode_texture_map_name(stage_flag, form_flag):
	name = ""

	for flag in STAGE_SCRIPT:
		if stage_flag & flag[1] == flag[1]:
			name = name + flag[0]
			break

	for flag in FORM_SCRIPT:
		if form_flag & flag[1] == flag[1]:
			name = name + flag[0]
			break

	return name


# The vertex color data is unrecoverable due to how PT tangles the data and
# averages it out. The best we can do is to pull the information out and leave
# it to the user to determine the value of this data.
# Reference: smStage3d.cpp:1055-1058 AddVertex initializes 255,255,255,255 via
# the SMC_ macros; smStage3d.cpp:1266-1277 averages neighbor colors at load.
def decode_stage_vertices(sm_modelbuffer: BufferReader, sm_stage: smSTAGE3D) -> tuple[list[PTVector3], list[PTColorVertex]]:
	vertices = []
	colors = []

	# Some objects have no vertices
	if sm_stage.nVertex <= 0:
		return vertices, colors

	for _ in range(sm_stage.nVertex):
		sm_vertex = sm_modelbuffer.read(smSTAGE_VERTEX)

		# swap Y and Z: the stage ASE importer maps *MESH_VERTEX (x,y,z) to
		# AddVertex(x,z,y) (smRead3d.cpp:2448-2460 smSTAGE3D_ReadASE_GEOMOBJECT).
		# Reference: smRead3d.cpp::smSTAGE3D_ReadASE_GEOMOBJECT
		vertices.append(PTVector3(
			x = sm_vertex.x / 256,
			y = sm_vertex.z / 256,
			z = sm_vertex.y / 256
		))

		# BGRA: sDef_Color is indexed with SMC_B=0, SMC_G=1, SMC_R=2, SMC_A=3
		# (smType.h:59-62), not the struct comment's "RGBA".
		# Reference: smType.h::SMC_A, SMC_R, SMC_G, SMC_B
		colors.append(PTColorVertex(
			r = sm_vertex.sDef_Color[2] / 255,
			g = sm_vertex.sDef_Color[1] / 255,
			b = sm_vertex.sDef_Color[0] / 255,
			a = 1
		))

	return vertices, colors


def decode_stage_faces(sm_modelbuffer: BufferReader, sm_stage: smSTAGE3D) -> list[PTObjectFace]:
	faces = []

	# Some objects have no faces
	if sm_stage.nFace <= 0:
		return faces

	for _ in range(sm_stage.nFace):
		sm_face = sm_modelbuffer.read(smSTAGE_FACE)
		faces.append(PTObjectFace(
			vertices = [
				sm_face.Vertex[0],
				sm_face.Vertex[1],
				sm_face.Vertex[2]
			],
			material_id = sm_face.Vertex[3]
		))

	return faces


# Faces store stale runtime addresses in lpTexLink_ptr / NextTex_ptr; the
# loaders rebase them into array indices by element difference against the
# first non-null address (smObj3d.cpp:2200-2221, smStage3d.cpp:2430-2453).
# AddTexLink appends links in face order, so TexLink[0] belongs to the first
# textured face and the smallest face pointer is TexLink[0]'s stale address.
# Each face owns a chain of smTEXLINKs linked by NextTex: link 0 carries the
# primary UV set, every further link one UV set for the material's secondary
# texture stages (lightmaps over diffuse in the *LM_ dungeon stages). The
# render loop walks the chain once per texture stage with the chain index as
# the D3D texcoord index (smRend3d.cpp:3216-3250 SetD3DRendBuff).
def decode_texlink_chain(texlinks: list, base: int, tex_index: int) -> list:
	sets = []
	seen = set()

	while 0 <= tex_index < len(texlinks) and tex_index not in seen:
		seen.add(tex_index)
		sets.append(texlinks[tex_index])

		if texlinks[tex_index].NextTex_ptr <= 0:
			break

		tex_index = int((texlinks[tex_index].NextTex_ptr - base) / sizeof(smTEXLINK))

	return sets


def decode_stage_texture_coords(sm_modelbuffer: BufferReader, sm_stage: smSTAGE3D) -> list[PTObjectTexture_Coord]:
	texture_coords = []

	# Some objects have no faces
	if sm_stage.nFace <= 0:
		return texture_coords

	texlink_offset = sm_modelbuffer.tell()
	texlinks = [sm_modelbuffer.read(smTEXLINK) for _ in range(sm_stage.nTexLink)]

	# faces sit before the texlink array in the stage layout too (the caller
	# has consumed vertices+faces); faces store stale addresses in file order
	face_offset = texlink_offset - (sm_stage.nFace * sizeof(smSTAGE_FACE))
	sm_modelbuffer.seek(face_offset)

	ptr = None
	for i in range(sm_stage.nFace):
		sm_face = sm_modelbuffer.read(smSTAGE_FACE)
		v = len(texture_coords) * 3

		if ptr is None and sm_face.lpTexLink_ptr > 0:
			ptr = sm_face.lpTexLink_ptr

		if sm_face.lpTexLink_ptr > 0:
			tex_index = int((sm_face.lpTexLink_ptr - ptr) / sizeof(smTEXLINK))
			uv_sets = [
				[
					PTTextureVertex(u=sm_texlink.u[0], v=-sm_texlink.v[0]),
					PTTextureVertex(u=sm_texlink.u[1], v=-sm_texlink.v[1]),
					PTTextureVertex(u=sm_texlink.u[2], v=-sm_texlink.v[2])
				]
				for sm_texlink in decode_texlink_chain(texlinks, ptr, tex_index)
			]
		else:
			uv_sets = []

		texture_coords.append(PTObjectTexture_Coord(
			face = PTObjectFace(
				vertices = [ v+0, v+1, v+2 ],
				material_id = sm_face.Vertex[3]
			),
			uv_sets = uv_sets
		))

	sm_modelbuffer.seek(texlink_offset + (sm_stage.nTexLink * sizeof(smTEXLINK)))

	return texture_coords


# only dungeons 1-5 (dun 1-3 sanc 1-2) have lightmaps (*LM_). no other
# stages seem to be light mapped!
# Light records are read by smSTAGE3D::LoadFile (smStage3d.cpp:2430-2433) as
# sizeof(smLIGHT3D) = 28-byte records; type flags are smLIGHT_TYPE_NIGHT =
# 0x1, LENS = 0x2, PULSE2 = 0x4, OBJ = 0x8, DYNAMIC = 0x80000 (smType.h:132-138).
# Only DYNAMIC lights reach the smLight array: the ASE importer bakes
# non-dynamic ones into vertex colors via AddVertexLightRound
# (smRead3d.cpp:3277-3310). type names come from the *NODE_NAME prefixes
# "night:"/"lens:"/"obj:" (smRead3d.cpp:2818-2840). Positions are inches
# (x,z,y at *TM_POS, smRead3d.cpp:2865-2871); Range is authored as v*16384
# for *LIGHT_MAPRANGE value v (smRead3d.cpp:2875-2877) and the engine falloff
# reaches zero at radius Range>>8 = v*64 engine units (AddVertexLightRound
# eLight, smStage3d.cpp:1303-1345), so range is stored here as that radius
# in inches.
def decode_stage_lights(sm_modelbuffer: BufferReader, sm_stage: smSTAGE3D) -> list[PTStageLight]:
	lights = []

	for _ in range(sm_stage.nLight):
		sm_light = sm_modelbuffer.read(smLIGHT3D)
		type_flags = sm_light.type & 0xFFFFFFFF
		lights.append(PTStageLight(
			type_flags = type_flags,
			dynamic = bool(type_flags & 0x80000),
			night = bool(type_flags & 0x1),
			lens = bool(type_flags & 0x2),
			obj = bool(type_flags & 0x8),
			position = PTVector3(
				x = sm_light.x / 256,
				y = sm_light.z / 256,
				z = sm_light.y / 256
			),
			range = sm_light.Range / 256,
			color = PTColorVertex(
				r = sm_light.r / 255,
				g = sm_light.g / 255,
				b = sm_light.b / 255,
				a = 1
			)
		))

	return lights


# Resolve the parent by NodeParent name. The engine matches parents with
# _stricmp (smPAT3D::LinkObject, smObj3d.cpp:2340-2355; bones also match by
# _stricmp in smPAT3D::GetObjectFromName, smObj3d.cpp:2383).
def decode_actor_parent(parent_name: str | None) -> smOBJ3D | None:
	if parent_name:
		for sm_object in decoded_objects:
			if parent_name == decode_string(sm_object.NodeName):
				return sm_object


# Mirror of the engine's runtime TM handling. The authoritative static
# transform of a bone is its Tm matrix, which the engine treats as the bone's
# accumulated WORLD transform: smOBJ3D::TmAnimation composes the render
# matrix as qmat = Tm * pParent->TmInvert (static branch, smObj3d.cpp), then
# TmResult = qmat * pParent->TmResult; the product telescopes so the bone's
# world transform equals Tm exactly. The engine converts Tm to parent-local
# at runtime with a general matrix inverse (smMatrixInvert, smmatrix.cpp).
#
# The px/py/pz and qx..qw static fields are NOT trusted for the bind pose. A
# runtime audit of smObj3d.cpp finds exactly two uses, both animation-key
# fallbacks inside TmAnimation, and both covered by our animation decode:
#   px/py/pz -> animation position when the bone has NO position keys
#               (qmat._41 = float(px) / fONE)
#   qx..qw   -> baked into TmRotate at import (smRead3d.cpp:1268), used as
#               the animation rotation when the bone has NO rotation keys
#               (smFMatrixFromMatrix(qmat, TmRotate))
# sx/sy/sz feed only the ReformTM scale normalization (smObj3d.cpp:920-985).
# None of them participate in the static hierarchy.
#
# This matters because the static fields are not even self-consistent across
# files: the ASE exporters wrote either parent-relative data (Buma) or
# world-space NODE_TM data (Aragonian) into *TM_POS / *TM_ROTAXIS, and the
# converter copies them verbatim (smRead3d.cpp:1237-1268). Tm is the only
# consistent truth, so position/rotation below ALWAYS derive from
# qmat = Tm * inv(parentTm) - the engine's own math - never from px..qw.
#
# The PTObjectTransform matrix fields (_ij) keep the world Tm (with the
# ReformTM scale fixup mirrored): the glTF exporter's vertex bake and
# inverse-bind matrices pair against it.
def decode_actor_transform(sm_object: smOBJ3D, sm_object_parent: smOBJ3D | None, has_bones: bool = False):
	if sm_object_parent:
		scalei = PTVector3Int(
			x = sm_object_parent.sx,
			y = sm_object_parent.sy,
			z = sm_object_parent.sz
		)
	else:
		scalei = PTVector3Int(
			x = sm_object.sx,
			y = sm_object.sy,
			z = sm_object.sz
		)

	# rotation matrix needs some scale manipulation (ReformTM does
	# Tm._ij = (Tm._ij << FLOATNS) / scale, smObj3d.cpp:933-961; dividing by
	# scale/256 as float is algebraically equivalent for the /256 fixed point
	# used here)
	manipulated = int((scalei.x + scalei.y + scalei.z) / 3)

	if has_bones or manipulated == 0:
		manipulated = 256

	# TRS decomposition from Tm, the engine's authoritative matrix. qmat is the
	# engine's own static-branch math: local = Tm * inv(parentTm); for a root
	# bone the engine uses Tm directly (smOBJ3D::TmAnimation:
	# smFMatrixFromMatrix(qmat, Tm)). The ReformTM scale fixup is applied first
	# to mirror the order the engine runs in (ReformTM mutates Tm before any
	# animation matrix is built); for the unit-scale bipeds of every shipped
	# model it is the identity.
	cm = sm_tm_to_np(sm_object.Tm, manipulated)
	local = cm
	if sm_object_parent:
		local = sm_tm_parent_local(cm, sm_tm_to_np(sm_object_parent.Tm, manipulated))
		if local is None:
			local = cm

	# qmat's translation row is the parent-space offset already in inches
	# (fONE was divided out by sm_tm_to_np; the engine's 8.8 shift does not
	# apply twice), and its rotation matches the animation keys - verified
	# key0 == quat(qmat) on world-convention files such as Aragonian.
	position = PTVector3(
		x = local[3][0],
		y = local[3][1],
		z = local[3][2]
	)

	# The engine applies no TRS decomposition - it uses matrices directly - so
	# authored Tm matrices may carry baked uniform scale (Raeda clavicles,
	# det = 0.9925, i.e. 0.4% shorter bones) or a mirror (negative det).
	# Decompose the rotation block properly: normalize away the scale, flip a
	# column when det < 0 (recorded as negative node scale, the glTF
	# convention for mirrored chains), then extract the quaternion.
	rotation, fix_scale, flipped = decompose_rotation(local)

	scale = PTVector3(
		x = sm_object.sx / 256 * fix_scale[0],
		y = sm_object.sy / 256 * fix_scale[1],
		z = sm_object.sz / 256 * fix_scale[2] * (-1 if flipped else 1)
	)

	return PTObjectTransform(
		_11 = sm_object.Tm._11 / 256 * manipulated / 256,
		_12 = sm_object.Tm._12 / 256 * manipulated / 256,
		_13 = sm_object.Tm._13 / 256 * manipulated / 256,
		_14 = 0,
		_21 = sm_object.Tm._21 / 256 * manipulated / 256,
		_22 = sm_object.Tm._22 / 256 * manipulated / 256,
		_23 = sm_object.Tm._23 / 256 * manipulated / 256,
		_24 = 0,
		_31 = sm_object.Tm._31 / 256 * manipulated / 256,
		_32 = sm_object.Tm._32 / 256 * manipulated / 256,
		_33 = sm_object.Tm._33 / 256 * manipulated / 256,
		_34 = 0,
		_41 = sm_object.Tm._41 / 256,
		_42 = sm_object.Tm._42 / 256,
		_43 = sm_object.Tm._43 / 256,
		_44 = 1,

		rotation = rotation,

		position = position,

		scale = scale
	)


# Actor vertices come from the actor ASE importer which keeps *MESH_VERTEX
# (x,y,z) order unchanged, unlike the stage importer's x,z,y swap.
# Reference: smRead3d.cpp:1346-1361 ReadASE_GEOMOBJECT
def decode_actor_vertices(sm_modelbuffer: BufferReader, sm_object: smOBJ3D) -> list[PTVector3]:
	vertices = []

	# Some objects have no vertices
	if sm_object.nVertex <= 0:
		return vertices

	for _ in range(sm_object.nVertex):
		sm_vertex = sm_modelbuffer.read(smVERTEX)
		vertices.append(PTVector3(
			x = sm_vertex.x / 256,
			y = sm_vertex.y / 256,
			z = sm_vertex.z / 256
		))

	return vertices


# Faces are consumed in file order; v[3] holds the per-face material id that
# ReadASE_GEOMOBJECT captured from *MESH_MTLID (smRead3d.cpp:1379-1394
# SetFaceMaterial).
def decode_actor_faces(sm_modelbuffer: BufferReader, sm_object: smOBJ3D) -> list[PTObjectFace]:
	faces = []

	# Some objects have no faces
	if sm_object.nFace <= 0:
		return faces

	for _ in range(sm_object.nFace):
		sm_face = sm_modelbuffer.read(smFACE)
		faces.append(PTObjectFace(
			vertices = [
				sm_face.v[0],
				sm_face.v[1],
				sm_face.v[2]
			],
			material_id = sm_face.v[3]
		))

	return faces


# smTEXLINK i holds the primary UV set of face i: ReadASE_GEOMOBJECT calls
# AddTexLink once per face in order (smRead3d.cpp:1543-1551) and AddTexLink
# appends and links Face[n].lpTexLink = &TexLink[nTexLink] (smObj3d.cpp:590-618).
# Faces with multiple textures chain extra links via NextTex
# (smObj3d.cpp:613-625); walk them into extra uv_sets.
# UV v was stored as 1-fv at import (smRead3d.cpp:1548), so 1-v undoes it.
def decode_actor_texture_coords(sm_modelbuffer: BufferReader, sm_object: smOBJ3D) -> list[PTObjectTexture_Coord]:
	texture_coords = []

	# Some objects have no texture links
	if sm_object.nTexLink <= 0 or sm_object.nFace <= 0:
		return texture_coords

	texlink_offset = sm_modelbuffer.tell()
	texlinks = [sm_modelbuffer.read(smTEXLINK) for _ in range(sm_object.nTexLink)]

	# faces sit before the texlink array in the actor layout
	face_offset = texlink_offset - (sm_object.nFace * sizeof(smFACE))
	sm_modelbuffer.seek(face_offset)

	ptr = None
	for i in range(sm_object.nFace):
		sm_face = sm_modelbuffer.read(smFACE)
		v = i * 3

		if ptr is None and sm_face.lpTexLink_ptr > 0:
			ptr = sm_face.lpTexLink_ptr

		if sm_face.lpTexLink_ptr > 0:
			tex_index = int((sm_face.lpTexLink_ptr - ptr) / sizeof(smTEXLINK))
			uv_sets = [
				[
					PTTextureVertex(u=sm_texlink.u[0], v=1-sm_texlink.v[0]),
					PTTextureVertex(u=sm_texlink.u[1], v=1-sm_texlink.v[1]),
					PTTextureVertex(u=sm_texlink.u[2], v=1-sm_texlink.v[2])
				]
				for sm_texlink in decode_texlink_chain(texlinks, ptr, tex_index)
			]
		else:
			uv_sets = []

		texture_coords.append(PTObjectTexture_Coord(
			face = PTObjectFace(
				vertices = [ v+0, v+1, v+2 ]
			),
			uv_sets = uv_sets
		))

	sm_modelbuffer.seek(texlink_offset + (sm_object.nTexLink * sizeof(smTEXLINK)))

	return texture_coords


def key_frame_window(sm_object: smOBJ3D, count: int, frames: list) -> tuple[int, int]:
	"""
	Engine key arrays are preallocated and only the window described by the first
	valid smFRAME_POS entry is written; the rest stays uninitialized in memory and
	is serialized as 0xCDCDCDCD garbage.
	Reference: smObj3d.cpp::GetTmFrameRot reads keys at [PosNum, PosNum+PosCnt)
	only when TmFrameCnt > 0 and PosCnt > 0.
	"""
	if sm_object.TmFrameCnt > 0:
		for f in frames:
			if f.PosCnt > 0 and 0 <= f.PosNum and f.PosNum + f.PosCnt <= count:
				return f.PosNum, f.PosNum + f.PosCnt
	return 0, count


def decode_actor_animation(sm_modelbuffer: BufferReader, sm_object: smOBJ3D) -> tuple[PTActorAnimation, int]:
	animation = PTActorAnimation()
	last_frame = None

	# Some objects have no transforms
	if sm_object.TmRotCnt + sm_object.TmPosCnt + sm_object.TmScaleCnt == 0:
		return animation, 100 # default value

	rot_window = key_frame_window(sm_object, sm_object.TmRotCnt, sm_object.TmRotFrame)
	pos_window = key_frame_window(sm_object, sm_object.TmPosCnt, sm_object.TmPosFrame)
	scl_window = key_frame_window(sm_object, sm_object.TmScaleCnt, sm_object.TmScaleFrame)

	# For each key group, keep only the keys inside the valid window and take
	# the last kept key's frame as the object's last frame. The engine samples
	# keys with the same window lookup (smObj3d.cpp:1252 GetTmFramePos,
	# :1272 GetTmFrameScale, :1292 GetTmFrameRot, called from TmAnimation at
	# smObj3d.cpp:1424-1426); the last position key also feeds MaxFrame in
	# smPAT3D::AddObject (smObj3d.cpp:2290-2293).
	rot_start, rot_end = rot_window
	pos_start, pos_end = pos_window
	scl_start, scl_end = scl_window

	for i in range(sm_object.TmRotCnt):
		sm_rotation = sm_modelbuffer.read(smTM_ROT)
		if rot_start <= i < rot_end:
			animation.rotation.append(PTAnimationRotation(
				frame = sm_rotation.frame,
				x = sm_rotation.x,
				y = sm_rotation.y,
				z = sm_rotation.z,
				w = sm_rotation.w
			))

			if not last_frame and i == rot_end-1:
				last_frame = sm_rotation.frame

	for i in range(sm_object.TmPosCnt):
		sm_position = sm_modelbuffer.read(smTM_POS)
		if pos_start <= i < pos_end:
			animation.position.append(PTAnimationPosition(
				frame = sm_position.frame,
				x = sm_position.x,
				y = sm_position.y,
				z = sm_position.z
			))

			if not last_frame and i == pos_end-1:
				last_frame = sm_position.frame

	for i in range(sm_object.TmScaleCnt):
		sm_scale = sm_modelbuffer.read(smTM_SCALE)
		if scl_start <= i < scl_end:
			animation.scale.append(PTAnimationScale(
				frame = sm_scale.frame,
				x = sm_scale.x / 256,
				y = sm_scale.y / 256,
				z = sm_scale.z / 256
			))

		if not last_frame and i == scl_end-1:
			last_frame = sm_scale.frame

	for _ in range(sm_object.TmRotCnt):
		# jump pointer ahead over the TmPrevRot matrix block written after the
		# keys (smObj3d.cpp:2127 SaveFile: sizeof(smMATRIX) * TmRotCnt)
		sm_modelbuffer.read(smFMATRIX)

	return animation, last_frame


# Physique name table: written when the runtime Physique pointer is non-null
# (smObj3d.cpp:2129-2137 SaveFile), 32-byte NodeName of the bound bone per
# vertex. LoadFile gates on the same pointer read back from disk
# (smObj3d.cpp:2223-2236).
def decode_actor_physique(sm_modelbuffer: BufferReader, sm_object: smOBJ3D, has_bones: bool) -> list[str]:
	physique = []

	if has_bones:
		for _ in range(sm_object.nVertex):
			# each string is 32 bytes
			sm_physique = sm_modelbuffer.read(c_ubyte * 32)
			physique.append(decode_string(sm_physique))

	return physique


# Reference: smTexture.cpp:713 smMATERIAL_GROUP::LoadFile. Each material is a
# 320-byte smMATERIAL followed by the texture path blob only when InUse != 0
# (smTexture.cpp:731). The blob holds (Name, NameA) NUL-string pairs for
# TextureCounter textures then again for AnimTexCounter animation textures
# (smTexture.cpp:738-764); NameA non-empty selects an alternate pixel format
# and is usually a duplicate or empty in shipped data.
def decode_material(sm_modelbuffer: BufferReader) -> PTModelMaterial | None:
	sm_material = sm_modelbuffer.read(smMATERIAL)

	# The engine loads the blob for InUse != 0 and then overlays it at
	# smMaterial[MatNum] only on success (smTexture.cpp:735). A partial decode
	# here would desync face material ids, so bail out entirely instead.
	if sm_material.InUse == 0:
		return None

	material = PTModelMaterial()
	material.name = decode_material_name(sm_material.UseState, sm_material.BlendType)
	material.num_textures = sm_material.TextureCounter
	material.num_anim_textures = sm_material.AnimTexCounter
	material.anim_speed = sm_material.Shift_FrameSpeed
	material.anim_mask = sm_material.FrameMask
	material.mat_frame = sm_material.MatFrame
	material.ambient = [ sm_material.Diffuse[0], sm_material.Diffuse[1], sm_material.Diffuse[2] ] # not in SMD, defaulting to diffuse
	material.diffuse = [ sm_material.Diffuse[0], sm_material.Diffuse[1], sm_material.Diffuse[2] ]
	material.specular = [ 0.9, 0.9, 0.9 ]
	material.transparent = True if sm_material.Transparency > 0 else False
	material.selfillum = True if sm_material.SelfIllum > 0 else False
	material.two_sided = True if sm_material.TwoSide > 0 else False
	# MeshState / UseState are built from the material script flags at
	# import (smTexture.cpp:941-1013 AddMaterial) using sMATS_SCRIPT_*
	# (smRead3d.h:44-77) and SMMAT_STAT_CHECK_FACE = 0x1
	# (smType.h:649).
	material.mesh_flags = sm_material.MeshState # Reference: smTexture.cpp::smMATERIAL_GROUP::AddMaterial (line ~944)
	material.collide = True if (sm_material.MeshState % 2) == 1 else False

	# FIXME: wrong but convenient (for now)
	if not material.collide:
		material.collide = sm_material.MeshState & int.from_bytes(b"\x01\x00\x00") == int.from_bytes(b"\x01\x00\x00") # orgwater flag

	"""
	if ( smMaterial[MatNum].Transparency==0 )
		smMaterial[MatNum].MeshState = SMMAT_STAT_CHECK_FACE;

	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WIND) ) {
		smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDZ1;
		smMaterial[MatNum].MeshState = 0;
	}
	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDX1) ) {
		smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDX1;
		smMaterial[MatNum].MeshState = 0;
	}
	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDX2) ) {
		smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDX2;
		smMaterial[MatNum].MeshState = 0;
	}
	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDZ1) ) {
		smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDZ1;
		smMaterial[MatNum].MeshState = 0;
	}
	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDZ2) ) {
		smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDZ2;
		smMaterial[MatNum].MeshState = 0;
	}
	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDZ2) ) {
		smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDZ2;
		smMaterial[MatNum].MeshState = 0;
	}
	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WATER) ) {
		smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WATER;
		smMaterial[MatNum].MeshState = 0;
	}

	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_NOTPASS) ) {
		smMaterial[MatNum].MeshState = SMMAT_STAT_CHECK_FACE;
	} else {
		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_PASS) ) {
			smMaterial[MatNum].MeshState = 0;
		}
	}

	if ( (aseMaterial->ScriptState&sMATS_SCRIPT_RENDLATTER) ) {
		smMaterial[MatNum].MeshState |= sMATS_SCRIPT_RENDLATTER;
	}
	if( (aseMaterial->ScriptState & sMATS_SCRIPT_CHECK_ICE) )
		smMaterial[MatNum].MeshState |= sMATS_SCRIPT_CHECK_ICE;
	if( (aseMaterial->ScriptState & sMATS_SCRIPT_ORG_WATER) )
		smMaterial[MatNum].MeshState = sMATS_SCRIPT_ORG_WATER;
	"""


	# If we have textures and paths to those textures, we need to add
	# texture mapping data.
	texpaths_len = int.from_bytes(sm_modelbuffer.read(c_uint32), byteorder="little")

	if sm_material.TextureCounter > 0 and texpaths_len > 0:
		texpaths = []

		sm_texpaths = sm_modelbuffer.read(c_uint8 * texpaths_len)
		sm_texpaths = bytes(sm_texpaths).split(b"\x00")

		for j in range(sm_material.TextureCounter):
			if sm_texpaths[j*2][-1] > int.from_bytes(b"\x7F", byteorder="little"): # invalid data
				break

			texpath = decode_string(sm_texpaths[j*2])
			texpaths.append(texpath)

		if len(texpaths) > 0:
			material.texture_map.diffuse_name = decode_texture_map_name(
				sm_material.TextureStageState[0],
				sm_material.TextureFormState[0]
			)
			material.texture_map.diffuse_path = texpaths[0] # diffuse texture is the first texture

		# The second texture stage rides the NextTex chain as TEXCOORD_1 and is
		# added on top of the diffuse (D3DTOP_ADD, smRend3d.cpp:3628-3630):
		# baked *LightingMap.bmp lightmaps in the *LM_ dungeon stages, or
		# selfillum maps elsewhere (e.g. actor glow maps)
		if len(texpaths) == 2:
			if "lightingmap" in texpaths[1].casefold():
				material.texture_map.lightmap_name = decode_texture_map_name(
					sm_material.TextureStageState[1],
					sm_material.TextureFormState[1]
				)
				material.texture_map.lightmap_path = texpaths[1]
			else:
				material.texture_map.selfillum_name = decode_texture_map_name(
					sm_material.TextureStageState[1],
					sm_material.TextureFormState[1]
				)
				material.texture_map.selfillum_path = texpaths[1] # self illumination texture is the second texture

		# anim2:..anim16: flipbook frames: the (Name, NameA) pairs after the
		# TextureCounter textures (smTexture.cpp:759-764). Rendered as a texture
		# swap: frame = (RendStatTime>>Shift_FrameSpeed)&FrameMask, SMTEX_AUTOANIMATION = 0x100
		# (smRend3d.cpp:3852-3854).
		if sm_material.AnimTexCounter > 0:
			material.texture_map.anim_frames = [
				decode_string(sm_texpaths[(sm_material.TextureCounter + k) * 2])
				for k in range(sm_material.AnimTexCounter)
			]

		# MapOpacity != 0 means *MAP_OPACITY in the ASE; the engine loads the
		# diffuse bitmap with the opacity map as its NameA (smTexture.cpp:874-912)
		if len(texpaths) > 0 and sm_material.MapOpacity == 1:
			material.texture_map.opacity_name = ""
			material.texture_map.opacity_path = texpaths[0] # opacity uses the diffuse texture
	return material


def decode_bones(sm_motionbuffer: BufferReader) -> tuple[list[PTActorBone], int]:
	""""Decode an SMB bone file.

	SMB files are actor-layout SMDs written by smPAT3D::SaveFile: the ASE
	biped pass keeps only Bip* objects (smRead3d.cpp:1966-1975
	smASE_ReadBone) and saves them under the smb extension via
	ChangeFileExt + SaveFile (smRead3d.cpp:1983-1985).
	"""
	bones = []
	sm_fileheader = sm_motionbuffer.read(smDFILE_HEADER)

	if sm_fileheader.MatCounter != 0:
		print("Bone objects should not have materials.")
		return bones, 100

	if sm_fileheader.ObjCounter <= 0:
		print("Bone objects not detected.")
		return bones, 100

	sm_motionbuffer.seek(sm_fileheader.First_ObjInfoPoint)

	for i in range(sm_fileheader.ObjCounter):
		sm_object = sm_motionbuffer.read(smOBJ3D)

		# Verify that the object is valid.
		# Head = 0x41424344 | OBJ_HEAD_TYPE_NEW_NORMAL = 0x80000000
		# (smObj3d.cpp:2115-2119, smObj3d.h:10).
		# Reference: smObj3d.cpp::smOBJ3D::SaveFile (lines ~2117 -> 2121)
		if sm_object.Head != OBJECT_HEAD and sm_object.Head != OBJECT_HEAD_OLD:
			print(f"Bone object #{i} has an invalid header: {sm_object.Head}")
			return bones, 100

		if sm_object.Physique_ptr != 0:
			print(f"Bone object #{i} has bones.")
			return bones, 100

		bone = PTActorBone()
		bone.name = decode_string(sm_object.NodeName)

		parent = decode_string(sm_object.NodeParent)
		bone.parent = parent if len(parent) > 0 else None
		sm_object_parent = decode_actor_parent(bone.parent)

		bone.num_vertices = sm_object.nVertex
		bone.num_faces = sm_object.nFace
		bone.num_tfm_rotations = sm_object.TmRotCnt
		bone.num_tfm_positions = sm_object.TmPosCnt
		bone.num_tfm_scales = sm_object.TmScaleCnt

		bone.vertices = decode_actor_vertices(sm_motionbuffer, sm_object)
		bone.faces = decode_actor_faces(sm_motionbuffer, sm_object)
		bone.texture_coords = decode_actor_texture_coords(sm_motionbuffer, sm_object)
		bone.animation, last_frame = decode_actor_animation(sm_motionbuffer, sm_object)
		bone.transform = decode_actor_transform(sm_object, sm_object_parent)
		bones.append(bone)

		decoded_objects.append(sm_object)
	return bones, last_frame


def decode_stage(sm_modelbuffer: BufferReader) -> PTStageModel:
	"""Decode a stage SMD.

	Reference: smSTAGE3D::LoadFile (smStage3d.cpp:2362). Layout: header,
	smSTAGE3D, materials (if MatCounter), then vertex/face/texlink/light
	arrays. The loader never seeks with MatFilePoint (which the writer
	hardcodes to 556, smStage3d.cpp:2310) - it reads sequentially.
	"""
	model = PTStageModel()

	sm_modelbuffer.seek(0)
	sm_fileheader = sm_modelbuffer.read(smDFILE_HEADER)
	sm_stage = sm_modelbuffer.read(smSTAGE3D)

	if sm_fileheader.MatCounter > 0:
		# jump pointer ahead over smMATERIAL_GROUP (written by
		# smMATERIAL_GROUP::SaveFile, smTexture.cpp:663)
		sm_modelbuffer.read(smMATERIAL_GROUP)

		for _ in range(sm_fileheader.MatCounter):
			material = decode_material(sm_modelbuffer)
			if material:
				model.materials.append(material)

	object = PTStageObject()
	object.num_vertices = sm_stage.nVertex
	object.num_faces = sm_stage.nFace
	object.num_texture_links = sm_stage.nTexLink
	# sm_stage.nVertColor
	# after the lights the file carries the 256x256 StageArea draw-partition
	# records (smStage3d.cpp:2340-2349 SaveFile, :2476-2491 LoadFile); engine
	# batching data, not needed to reconstruct the mesh

	object.vertices, object.vertex_colors = decode_stage_vertices(sm_modelbuffer, sm_stage)
	object.faces = decode_stage_faces(sm_modelbuffer, sm_stage)
	object.texture_coords = decode_stage_texture_coords(sm_modelbuffer, sm_stage) #, model.materials)
	object.lights = decode_stage_lights(sm_modelbuffer, sm_stage)

	# global vertex-shade sun parameters; the engine folds these into vertex
	# colors at import (SetVertexShade, smStage3d.cpp:1183-1290) and only
	# dynamic lights are serialized to the SMD
	model.lights = object.lights
	model.contrast = sm_stage.Contrast
	model.bright = sm_stage.Bright
	model.vect_light = PTVector3(
		x = sm_stage.VectLight.x / 256,
		y = sm_stage.VectLight.y / 256,
		z = sm_stage.VectLight.z / 256
	)

	model.objects.append(object)
	return model


def decode_actor(sm_modelbuffer: BufferReader, sm_motionbuffer: BufferReader, metadata: PTModelMetadata) -> PTActorModel:
	model = PTActorModel()

	sm_modelbuffer.seek(0)
	sm_fileheader = sm_modelbuffer.read(smDFILE_HEADER)

	### MOTION DATA ###

	# If there is bone data, get the last frame from the bone data.
	if sm_motionbuffer:
		bones, last_frame = decode_bones(sm_motionbuffer)
		model.bones = bones
		model.scene.last_frame = int(last_frame / model.scene.ticks_per_frame)

	# If there is not bone data, get the last frame from the model data.
	elif sm_fileheader.ObjCounter > 0:
		sm_modelbuffer.seek(sm_fileheader.First_ObjInfoPoint)
		max_frame = 0

		for _ in range(sm_fileheader.ObjCounter):
			sm_object = sm_modelbuffer.read(smOBJ3D)
			frame = 0

			# Reference: smObj3d.cpp::smPAT3D::AddObject computes MaxFrame as the
			# maximum over objects of the last position key frame, which overwrites
			# the last rotation key frame when present; scale keys are ignored.
			for _ in range(sm_object.nVertex): sm_modelbuffer.read(smVERTEX)
			for _ in range(sm_object.nFace): sm_modelbuffer.read(smFACE)
			for _ in range(sm_object.nTexLink): sm_modelbuffer.read(smTEXLINK)

			for _ in range(sm_object.TmRotCnt):
				sm_rotation = sm_modelbuffer.read(smTM_ROT)
				frame = sm_rotation.frame

			for _ in range(sm_object.TmPosCnt):
				sm_position = sm_modelbuffer.read(smTM_POS)
				frame = sm_position.frame

			max_frame = max(max_frame, frame)

			# jump pointer ahead over the rest of this object's payload
			for _ in range(sm_object.TmScaleCnt): sm_modelbuffer.read(smTM_SCALE)
			for _ in range(sm_object.TmRotCnt): sm_modelbuffer.read(smFMATRIX)

			if sm_object.Physique_ptr > 0:
				for _ in range(sm_object.nVertex): sm_modelbuffer.read(c_ubyte * 32)

		model.scene.last_frame = int(max_frame / model.scene.ticks_per_frame)

	""" MATERIAL """

	if sm_fileheader.MatCounter > 0:
		# jump pointer ahead
		sm_modelbuffer.seek(sm_fileheader.MatFilePoint)
		sm_modelbuffer.read(smMATERIAL_GROUP)

		for _ in range(sm_fileheader.MatCounter):
			material = decode_material(sm_modelbuffer)
			if material:
				model.materials.append(material)

	""" MESH """

	if sm_fileheader.ObjCounter > 0:
		sm_modelbuffer.seek(sm_fileheader.First_ObjInfoPoint)

		for i in range(sm_fileheader.ObjCounter):
			sm_object = sm_modelbuffer.read(smOBJ3D)

			# Verify that the object is valid.
			# Head = 0x41424344 | OBJ_HEAD_TYPE_NEW_NORMAL = 0x80000000
			# (smObj3d.cpp:2115-2119, smObj3d.h:10).
			# Reference: smObj3d.cpp::smOBJ3D::SaveFile (lines ~2117 -> 2121)
			if sm_object.Head != OBJECT_HEAD and sm_object.Head != OBJECT_HEAD_OLD:
				print(f"Mesh object #{i} has an invalid header: {sm_object.Head}")
				return model

			object = PTActorObject()
			object.name = decode_string(sm_object.NodeName)

			# filter out objects we don't want such as low quality meshes.
			# The engine resolves one model per name from the inx model groups;
			# name matching is case-insensitive (_stricmp in
			# smPAT3D::LinkObject / GetObjectFromName, smObj3d.cpp:2346 / 2389).
			# Reference: smObj3d.cpp uses lstrcmpi / _stricmp: case-insensitive
			found = False
			if metadata:
				for model_name in metadata.model_names:
					if model_name.casefold() == object.name.casefold():
						found = True
						break
			else:
				found = True

			# the object payload must always be consumed to keep the cursor in sync
			# Reference: smObj3d.cpp::smOBJ3D::LoadFile reads the payload of every
			# object regardless of which objects the caller keeps
			has_bones = True if sm_object.Physique_ptr > 0 else False

			parent = decode_string(sm_object.NodeParent)
			object.parent = parent if len(parent) > 0 else None
			sm_object_parent = decode_actor_parent(object.parent)

			object.num_vertices = sm_object.nVertex
			object.num_faces = sm_object.nFace
			object.num_texture_links = sm_object.nTexLink
			object.num_tfm_rotations = sm_object.TmRotCnt
			object.num_tfm_positions = sm_object.TmPosCnt
			object.num_tfm_scales = sm_object.TmScaleCnt

			object.vertices = decode_actor_vertices(sm_modelbuffer, sm_object)
			object.faces = decode_actor_faces(sm_modelbuffer, sm_object)
			object.texture_coords = decode_actor_texture_coords(sm_modelbuffer, sm_object)
			object.animation, _ = decode_actor_animation(sm_modelbuffer, sm_object)
			object.physique = decode_actor_physique(sm_modelbuffer, sm_object, has_bones)
			object.transform = decode_actor_transform(sm_object, sm_object_parent, has_bones)

			if found:
				# static rotation fallback for objects without rotation keys,
				# matching TmAnimation's else branch
				# (smFMatrixFromMatrix(qmat, TmRotate), smObj3d.cpp:1345).
				# NOTE: this is used on objects without rotation frames
				# Reference: @Rovug from RageZone Priston Tale Discord
				object.transform_rotate._11 = sm_object.TmRotate._11 / 256
				object.transform_rotate._12 = sm_object.TmRotate._12 / 256
				object.transform_rotate._13 = sm_object.TmRotate._13 / 256
				object.transform_rotate._21 = sm_object.TmRotate._21 / 256
				object.transform_rotate._22 = sm_object.TmRotate._22 / 256
				object.transform_rotate._23 = sm_object.TmRotate._23 / 256
				object.transform_rotate._31 = sm_object.TmRotate._31 / 256
				object.transform_rotate._32 = sm_object.TmRotate._32 / 256
				object.transform_rotate._33 = sm_object.TmRotate._33 / 256
				object.transform_rotate._41 = sm_object.TmRotate._41 / 256
				object.transform_rotate._42 = sm_object.TmRotate._42 / 256
				object.transform_rotate._43 = sm_object.TmRotate._43 / 256
				model.objects.append(object)
			decoded_objects.append(sm_object)
	return model


def decode(modelpath: str, motionpath: str | None = None, metadata: PTModelMetadata | None = None) -> PTActorModel | PTStageModel | None:
	"""Decode an actor SMD (and its optional SMB bones) into the internal model structure."""

	# Reference: smPAT3D::LoadFile (smObj3d.cpp:2937): validate szHeader with
	# lstrcmp, read the header, materials, then every object block.
	if not os.path.exists(modelpath):
		print(f"Model file not found: {modelpath}")
		return

	decoded_objects.clear()
	sm_modelbuffer = BufferReader(modelpath)
	modelroot, modelext = get_filename(modelpath, os.path.sep)
	sm_fileheader = sm_modelbuffer.read(smDFILE_HEADER)
	signature = decode_string(sm_fileheader.szHeader)

	print(modelroot)

	if signature == STAGE_SIGNATURE:
		model = decode_stage(sm_modelbuffer)
		model.filename = modelroot + modelext
		# single stage pseudo-object; the engine keeps smSTAGE3D whole
		model.objects[0].name = modelroot
		return model

	if signature == ACTOR_SIGNATURE:
		if not motionpath:
			motionroot, motionext = os.path.splitext(modelpath)
			motionpath = motionroot + ".smb"

		if os.path.exists(motionpath):
			sm_motionbuffer = BufferReader(motionpath)
		else:
			sm_motionbuffer = None

		model = decode_actor(sm_modelbuffer, sm_motionbuffer, metadata)
		model.filename = modelroot + modelext
		model.animations = metadata.animations if metadata else None
		model.talk_animations = metadata.talk_animations if metadata else None
		model.link_file = metadata.link_file if metadata else None
		model.talk_link_file = metadata.talk_link_file if metadata else None
		model.talk_motion_file = metadata.talk_motion_file if metadata else None
		model.sub_model_file = metadata.sub_model_file if metadata else None
		model.npc_motion_rate_table = metadata.npc_motion_rate_table if metadata else None
		model.talk_motion_rate_table = metadata.talk_motion_rate_table if metadata else None
		return model

	print(f"Unknown file signature: {signature}")
	return
