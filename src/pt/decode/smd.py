import os

from ctypes import *

from pt.buffer import BufferReader
from pt.cdef import *
from pt.pdef import *
from pt.utils import get_filename, decode_string
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
def decode_stage_vertices(sm_modelbuffer: BufferReader, sm_stage: smSTAGE3D) -> tuple[list[PTVector3], list[PTColorVertex]]:
	vertices = []
	colors = []

	# Some objects have no vertices
	if sm_stage.nVertex <= 0:
		return vertices, colors

	for _ in range(sm_stage.nVertex):
		sm_vertex = sm_modelbuffer.read(smSTAGE_VERTEX)

		# swap Y and Z
		# Reference: smRead3d.cpp::smSTAGE3D_ReadASE_GEOMOBJECT
		vertices.append(PTVector3(
			x = sm_vertex.x / 256,
			y = sm_vertex.z / 256,
			z = sm_vertex.y / 256
		))

		# BGRA
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


def decode_stage_texture_coords(sm_modelbuffer: BufferReader, sm_stage: smSTAGE3D) -> list[PTObjectTexture_Coord]:#, materials):
	texture_coords = []

	# Some objects have no faces
	if sm_stage.nFace <= 0:
		return texture_coords

	tlist = []
	ptr = None

	# We need to create a list of linked lists of textures that point to other
	# textures. This linked list is used for multi-texture faces.

	texlink_offset = sm_modelbuffer.tell()
	# for _ in range(sm_stage.nTexLink):
	# 	sm_texlink = sm_modelbuffer.read(smTEXLINK)

	# 	if sm_texlink.NextTex_ptr > 0:
	# 		ptr = sm_texlink.NextTex_ptr
	# 		break

	# sm_modelbuffer.seek(texlink_offset)
	# for _ in range(sm_stage.nTexLink):
	# 	sm_texlink = sm_modelbuffer.read(smTEXLINK)

	# 	if not ptr:
	# 		ptr = sm_texlink.NextTex_ptr

	# 	tlist.append(max(-1, int((sm_texlink.NextTex_ptr - ptr) / sizeof(smTEXLINK))))

	# ptr = None

	face_offset = texlink_offset - (sm_stage.nFace * sizeof(smSTAGE_FACE))
	for i in range(sm_stage.nFace):
		sm_modelbuffer.seek(face_offset + (i * sizeof(smSTAGE_FACE)))
		sm_face = sm_modelbuffer.read(smSTAGE_FACE)

		if sm_face.lpTexLink_ptr > 0:
			ptr = sm_face.lpTexLink_ptr
			break

	for i in range(sm_stage.nFace):
		sm_modelbuffer.seek(face_offset + (i * sizeof(smSTAGE_FACE)))
		sm_face = sm_modelbuffer.read(smSTAGE_FACE)

		if not ptr:
			ptr = sm_face.lpTexLink_ptr

		tex_id = max(-1, int((sm_face.lpTexLink_ptr - ptr) / sizeof(smTEXLINK)))
		v = len(texture_coords) * 3

		if tex_id >= 0:
			sm_modelbuffer.seek(texlink_offset + (tex_id * sizeof(smTEXLINK)))
			sm_texlink = sm_modelbuffer.read(smTEXLINK)

			# tex_id = tlist[tex_id] # TODO: multi textures via link list
			# materials tell us how many textures are expected.
			# light maps may be the texture after material textures
			# light maps are packed as the UV2 texture, probably!

			texture_coords.append(PTObjectTexture_Coord(
				face = PTObjectFace(
					vertices = [ v+0, v+1, v+2 ],
					material_id = sm_face.Vertex[3]
				),
				vertices = [
					PTTextureVertex(u=sm_texlink.u[0], v=-sm_texlink.v[0]),
					PTTextureVertex(u=sm_texlink.u[1], v=-sm_texlink.v[1]),
					PTTextureVertex(u=sm_texlink.u[2], v=-sm_texlink.v[2])
				]
			))
		else:
			texture_coords.append(PTObjectTexture_Coord(
				face = PTObjectFace(
					vertices = [ v+0, v+1, v+2 ],
					material_id = sm_face.Vertex[3]
				),
				vertices = [
					PTTextureVertex(u=0, v=-0),
					PTTextureVertex(u=0, v=-0),
					PTTextureVertex(u=0, v=-0)
				]
			))

	return texture_coords


# only dungeons 1-5 (dun 1-3 sanc 1-2) have lightmaps (*LM_). no other
# stages seem to be light mapped!
# TODO: lights need to actually do something
def decode_stage_lights(sm_modelbuffer: BufferReader, sm_stage: smSTAGE3D) -> list:
	lights = []
	print(f"Contrast: {sm_stage.Contrast}")
	print(f"Bright: {sm_stage.Bright}")
	print(f"VectLight: [{sm_stage.VectLight.x},{sm_stage.VectLight.y},{sm_stage.VectLight.z}]")
	print(f"nLight: {sm_stage.nLight}")
	for _ in range(sm_stage.nLight):
		sm_light = sm_modelbuffer.read(smLIGHT3D)
		print(f"type: 0x{sm_light.type.to_bytes()}")
		print(f"xyz: [{sm_light.x},{sm_light.y},{sm_light.z}]")
		print(f"Range: {sm_light.Range}")
		print(f"rgb: [{sm_light.r},{sm_light.g},{sm_light.b}]")
	return lights


def decode_actor_parent(parent_name: str | None) -> smOBJ3D | None:
	if parent_name:
		for sm_object in decoded_objects:
			if parent_name == decode_string(sm_object.NodeName):
				return sm_object


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

	# rotation matrix needs some scale manipulation
	manipulated = int((scalei.x + scalei.y + scalei.z) / 3)

	if has_bones or manipulated == 0:
		manipulated = 256

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

		rotation = PTQuaternion(
			x = sm_object.qx,
			y = sm_object.qy,
			z = sm_object.qz,
			w = sm_object.qw
		),

		position = PTVector3(
			x = sm_object.px / 256,
			y = sm_object.py / 256,
			z = sm_object.pz / 256
		),

		scale = PTVector3(
			x = sm_object.sx / 256,
			y = sm_object.sy / 256,
			z = sm_object.sz / 256
		)
	)


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


def decode_actor_texture_coords(sm_modelbuffer: BufferReader, sm_object: smOBJ3D) -> list[PTObjectTexture_Coord]:
	texture_coords = []

	# Some objects have no texture links
	if sm_object.nTexLink <= 0:
		return texture_coords

	for i in range(sm_object.nTexLink):
		v = i * 3
		sm_texlink = sm_modelbuffer.read(smTEXLINK)
		texture_coords.append(PTObjectTexture_Coord(
			face = PTObjectFace(
				vertices = [ v+0, v+1, v+2 ]
			),
			vertices = [
				PTTextureVertex(u=sm_texlink.u[0], v=1-sm_texlink.v[0]),
				PTTextureVertex(u=sm_texlink.u[1], v=1-sm_texlink.v[1]),
				PTTextureVertex(u=sm_texlink.u[2], v=1-sm_texlink.v[2])
			]
		))

	return texture_coords


def decode_actor_animation(sm_modelbuffer: BufferReader, sm_object: smOBJ3D) -> tuple[PTActorAnimation, int]:
	animation = PTActorAnimation()
	last_frame = None

	# Some objects have no transforms
	if sm_object.TmRotCnt + sm_object.TmPosCnt + sm_object.TmScaleCnt == 0:
		return animation, 100 # default value

	for i in range(sm_object.TmRotCnt):
		sm_rotation = sm_modelbuffer.read(smTM_ROT)
		animation.rotation.append(PTAnimationRotation(
			frame = sm_rotation.frame,
			x = sm_rotation.x,
			y = sm_rotation.y,
			z = sm_rotation.z,
			w = sm_rotation.w
		))

		if not last_frame and i == sm_object.TmRotCnt-1:
			last_frame = sm_rotation.frame

	for i in range(sm_object.TmPosCnt):
		sm_position = sm_modelbuffer.read(smTM_POS)
		animation.position.append(PTAnimationPosition(
			frame = sm_position.frame,
			x = sm_position.x,
			y = sm_position.y,
			z = sm_position.z
		))

		if not last_frame and i == sm_object.TmPosCnt-1:
			last_frame = sm_position.frame

	for i in range(sm_object.TmScaleCnt):
		sm_scale = sm_modelbuffer.read(smTM_SCALE)
		animation.scale.append(PTAnimationScale(
			frame = sm_scale.frame,
			x = sm_scale.x / 256,
			y = sm_scale.y / 256,
			z = sm_scale.z / 256
		))

		if not last_frame and i == sm_object.TmScaleCnt-1:
			last_frame = sm_scale.frame

	for _ in range(sm_object.TmRotCnt):
		# jump pointer ahead
		sm_modelbuffer.read(smFMATRIX)

	return animation, last_frame


def decode_actor_physique(sm_modelbuffer: BufferReader, sm_object: smOBJ3D, has_bones: bool) -> list[str]:
	physique = []

	if has_bones:
		# jump pointer ahead
		for _ in range(sm_object.TmRotCnt): # TODO: are these needed anywhere?
			sm_modelbuffer.read(smFMATRIX)

		for _ in range(sm_object.nVertex):
			# each string is 32 bytes
			sm_physique = sm_modelbuffer.read(c_ubyte * 32)
			physique.append(decode_string(sm_physique))

	return physique


def decode_material(sm_modelbuffer: BufferReader) -> PTModelMaterial | None:
	sm_material = sm_modelbuffer.read(smMATERIAL)

	# If the material is not flagged to be used, we skip it entirely.
	if sm_material.InUse > 0:
		material = PTModelMaterial()
		material.name = decode_material_name(sm_material.UseState, sm_material.BlendType)
		material.num_textures = sm_material.TextureCounter
		material.ambient = [ sm_material.Diffuse[0], sm_material.Diffuse[1], sm_material.Diffuse[2] ] # not in SMD, defaulting to diffuse
		material.diffuse = [ sm_material.Diffuse[0], sm_material.Diffuse[1], sm_material.Diffuse[2] ]
		material.specular = [ 0.9, 0.9, 0.9 ]
		material.transparent = True if sm_material.Transparency > 0 else False
		material.selfillum = True if sm_material.SelfIllum > 0 else False
		material.two_sided = True if sm_material.TwoSide > 0 else False
		material.mesh_flags = sm_material.MeshState # Reference: smTexture.cpp::smMATERIAL_GROUP::AddMaterial (line ~944)
		material.collide = True if (sm_material.MeshState % 2) == 1 else False

		# FIXME: wrong but convenient (for now)
		if not material.collide:
			material.collide = sm_material.MeshState & int.from_bytes(b"\x01\x00\x00") == int.from_bytes(b"\x01\x00\x00") # orgwater flag


		"""
		if ( smMaterial[MatNum].Transparency==0 )
			smMaterial[MatNum].MeshState		= SMMAT_STAT_CHECK_FACE;

		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WIND) ) {
			smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDZ1;
			smMaterial[MatNum].MeshState		= 0;
		}
		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDX1) ) {
			smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDX1;
			smMaterial[MatNum].MeshState		= 0;
		}
		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDX2) ) {
			smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDX2;
			smMaterial[MatNum].MeshState		= 0;
		}
		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDZ1) ) {
			smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDZ1;
			smMaterial[MatNum].MeshState		= 0;
		}
		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDZ2) ) {
			smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDZ2;
			smMaterial[MatNum].MeshState		= 0;
		}
		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WINDZ2) ) {
			smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WINDZ2;
			smMaterial[MatNum].MeshState		= 0;
		}
		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_WATER) ) {
			smMaterial[MatNum].WindMeshBottom = sMATS_SCRIPT_WATER;
			smMaterial[MatNum].MeshState		= 0;
		}

		if ( (aseMaterial->ScriptState&sMATS_SCRIPT_NOTPASS) ) {
			smMaterial[MatNum].MeshState		= SMMAT_STAT_CHECK_FACE;	//허가
		} else {
			if ( (aseMaterial->ScriptState&sMATS_SCRIPT_PASS) ) {
				smMaterial[MatNum].MeshState		= 0;					//불가
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

			if len(texpaths) == 2:
				material.texture_map.selfillum_name = decode_texture_map_name(
					sm_material.TextureStageState[1],
					sm_material.TextureFormState[1]
				)
				material.texture_map.selfillum_path = texpaths[1] # self illumination texture is the second texture

			if len(texpaths) > 0 and sm_material.MapOpacity == 1:
				material.texture_map.opacity_name = ""
				material.texture_map.opacity_path = texpaths[0] # opacity uses the diffuse texture
		return material


def decode_bones(sm_motionbuffer: BufferReader) -> tuple[list[PTActorBone], int]:
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
	model = PTStageModel()

	sm_modelbuffer.seek(0)
	sm_fileheader = sm_modelbuffer.read(smDFILE_HEADER)
	sm_stage = sm_modelbuffer.read(smSTAGE3D)

	if sm_fileheader.MatCounter > 0:
		# jump pointer ahead
		sm_modelbuffer.read(smMATERIAL_GROUP)

		for _ in range(sm_fileheader.MatCounter):
			material = decode_material(sm_modelbuffer)
			if material:
				model.materials.append(material)

	object = PTStageObject()
	object.num_vertices = sm_stage.nVertex
	object.num_faces = sm_stage.nFace
	object.num_texture_links = sm_stage.nTexLink
	# sm_stage.nLight
	# sm_stage.nVertColor

	object.vertices, object.vertex_colors = decode_stage_vertices(sm_modelbuffer, sm_stage)
	object.faces = decode_stage_faces(sm_modelbuffer, sm_stage)
	object.texture_coords = decode_stage_texture_coords(sm_modelbuffer, sm_stage) #, model.materials)
	# object.lights = decode_stage_lights(sm_modelbuffer, sm_stage)

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

		for i in range(sm_fileheader.ObjCounter):
			sm_object = sm_modelbuffer.read(smOBJ3D)

			# If the object has transform data, get the last frame from this object.
			if sm_object.TmRotCnt + sm_object.TmPosCnt + sm_object.TmScaleCnt > 0:
				# jump pointer ahead
				for _ in range(sm_object.nVertex): sm_modelbuffer.read(smVERTEX)
				for _ in range(sm_object.nFace): sm_modelbuffer.read(smFACE)
				for _ in range(sm_object.nTexLink): sm_modelbuffer.read(smTEXLINK)

				# jump pointer ahead to last rotation
				if sm_object.TmRotCnt > 0:
					for _ in range(sm_object.TmRotCnt):
						sm_rotation = sm_modelbuffer.read(smTM_ROT)
					model.scene.last_frame = int(sm_rotation.frame / model.scene.ticks_per_frame)
					break

				# jump pointer ahead to last position
				if sm_object.TmPosCnt > 0:
					for _ in range(sm_object.TmPosCnt):
						sm_position = sm_modelbuffer.read(smTM_POS)
					model.scene.last_frame = int(sm_position.frame / model.scene.ticks_per_frame)
					break

				# jump pointer ahead to last scale
				if sm_object.TmScaleCnt > 0:
					for _ in range(sm_object.TmScaleCnt):
						sm_scale = sm_modelbuffer.read(smTM_SCALE)
					model.scene.last_frame = int(sm_scale.frame / model.scene.ticks_per_frame)
					break

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
			# Reference: smObj3d.cpp::smOBJ3D::SaveFile (lines ~2117 -> 2121)
			if sm_object.Head != OBJECT_HEAD and sm_object.Head != OBJECT_HEAD_OLD:
				print(f"Mesh object #{i} has an invalid header: {sm_object.Head}")
				return

			object = PTActorObject()
			object.name = decode_string(sm_object.NodeName)

			# filter out objects we don't want such as low quality meshes
			found = False
			if metadata:
				for model_name in metadata.model_names:
					if model_name == object.name:
						found = True
						break
			else:
				found = True

			if found:
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
	""" Decodes an SMD file into the internal model structure. """

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
		return model

	print(f"Unknown file signature: {signature}")
	return
