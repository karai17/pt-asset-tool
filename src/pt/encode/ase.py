import io
import math

from pt.pdef import *
from pt.const import (
	STAGE_SCRIPT,
	FORM_SCRIPT,
	MTL_FORM_SCRIPT,
	MTL_FORM_BLEND
)
from pt.utils import normalize_quaternion


# The ASE file is the intermediate the original pipeline shipped through: the
# tools authored *.ASE (3ds Max Ascii Export format), and the engine's importers
# (smRead3d.cpp smASE_Read / smASE_ReadBone / smSTAGE3D_ReadASE) converted them
# to SMD/SMB. This writer produces the same shape of file from the decoded
# model structures so the conversion can be run in reverse.
#
# Floating point values are serialized with %0.5f, matching the 3ds Max exporter
# output the engine was built to read (e.g. the shipped
# char/monster/death_knight/*.ASE files).

ENDL = "\n"
TAB = "\t"
ASE_MATERIAL_CLASS = "Multi/Sub-Object"
ASE_MAP_CLASS = "Bitmap"


def f(n: float) -> str:
	return "%0.8f" % n


def mi(t: list) -> str:
	return "\t".join(str(n) for n in t)


def mf(t: list) -> str:
	return "\t".join(f(n) for n in t)


def material_script_name(material: PTModelMaterial) -> str:
	"""The engine parsed every material property out of the material's name
	string (ReadASE_MATERIAL, smRead3d.cpp:326-352: script flags via strstr,
	blend type via strstr). decode_material_name is the exact-value inverse of
	those lookups, so reassembling the name from the stored flags reproduces
	what the original ASE carried; defaults (empty name) stay empty."""
	name = ""

	for flag in MTL_FORM_SCRIPT:
		if material.script_flags & flag[1] == flag[1]:
			name = name + flag[0]

	for flag in MTL_FORM_BLEND:
		if material.blend_type == flag[1]:
			name = name + flag[0]
			break

	return name


def texture_map_name(stage_flag: int, form_flag: int) -> str:
	"""Map names carry the same kind of script (szMapStageScript /
	szMapFormScript, smRead3d.cpp:367-384): stage flags are stored as the
	D3DTOP enum (exact match), form flags as the script array index."""
	name = ""

	for flag in STAGE_SCRIPT:
		if stage_flag == flag[1]:
			name = name + flag[0]
			break

	for flag in FORM_SCRIPT:
		if form_flag == flag[1]:
			name = name + flag[0]
			break

	return name


def quaternion_to_axisangle(q: PTQuaternion) -> tuple[PTVector3, float]:
	"""The engine reads rotations as axis + angle (ReadASE_GEOMOBJECT
	*TM_ROTAXIS/*TM_ROTANGLE, smRead3d.cpp:1255-1271) and converts with
	smQuaternionFromAxis (smmatrix.cpp:233): x/y/z stay the axis, w becomes
	the angle around it in radians. The inverse of that conversion is
	angle = 2*atan2(|v|, w)."""
	axis = PTVector3(q.x, q.y, q.z)
	magnitude = math.sqrt(q.x**2 + q.y**2 + q.z**2)
	angle = 2 * math.atan2(magnitude, q.w)

	if angle > math.pi:
		angle -= 2 * math.pi

	if magnitude > 0:
		axis = PTVector3(q.x / magnitude, q.y / magnitude, q.z / magnitude)
	else:
		axis = PTVector3(0, 0, 1)

	return axis, angle


def ase_header(buffer: io.StringIO) -> None:
	buffer.write(f"*3DSMAX_ASCIIEXPORT\t200{ENDL}")
	buffer.write(f"*COMMENT \"AsciiExport Version  2.00 - Mon Dec 01 00:00:00 2808\"{ENDL}")


def ase_scene(buffer: io.StringIO, scene: PTModelScene, filename: str, first_frame: int = 0) -> None:
	buffer.write(f"*SCENE {{{ENDL}")
	buffer.write(f"{TAB}*SCENE_FILENAME \"{filename}.max\"{ENDL}")
	buffer.write(f"{TAB}*SCENE_FIRSTFRAME {first_frame}{ENDL}")
	buffer.write(f"{TAB}*SCENE_LASTFRAME {scene.last_frame}{ENDL}")
	buffer.write(f"{TAB}*SCENE_FRAMESPEED {scene.frame_speed}{ENDL}")
	buffer.write(f"{TAB}*SCENE_TICKSPERFRAME {scene.ticks_per_frame}{ENDL}")
	buffer.write(f"{TAB}*SCENE_BACKGROUND_STATIC {mf([0, 0, 0])}{ENDL}")
	buffer.write(f"{TAB}*SCENE_AMBIENT_STATIC {mf([0, 0, 0])}{ENDL}")
	buffer.write(f"}}{ENDL}")


def ase_map(buffer: io.StringIO, level: str, block: str, subno: int, map_name: str, path: str) -> None:
	buffer.write(f"{level}*MAP_{block} {{{ENDL}")
	buffer.write(f"{level}{TAB}*MAP_NAME \"{map_name}\"{ENDL}")
	buffer.write(f"{level}{TAB}*MAP_CLASS \"{ASE_MAP_CLASS}\"{ENDL}")
	buffer.write(f"{level}{TAB}*MAP_SUBNO {subno}{ENDL}")
	buffer.write(f"{level}{TAB}*MAP_AMOUNT {f(1)}{ENDL}")
	buffer.write(f"{level}{TAB}*BITMAP \"{path}\"{ENDL}")
	buffer.write(f"{level}{TAB}*MAP_TYPE Screen{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_U_OFFSET {f(0)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_V_OFFSET {f(0)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_U_TILING {f(1)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_V_TILING {f(1)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_ANGLE {f(0)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_BLUR {f(1)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_BLUR_OFFSET {f(0)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_NOUSE_AMT {f(1)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_NOISE_SIZE {f(1)}{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_NOISE_LEVEL 1{ENDL}")
	buffer.write(f"{level}{TAB}*UVW_NOISE_PHASE {f(0)}{ENDL}")
	buffer.write(f"{level}{TAB}*BITMAP_FILTER Pyramidal{ENDL}")
	buffer.write(f"{level}}}{ENDL}")


def ase_materials(buffer: io.StringIO, materials: list[PTModelMaterial]) -> None:
	buffer.write(f"*MATERIAL_LIST {{{ENDL}")

	if not materials:
		buffer.write(f"{TAB}*MATERIAL_COUNT 0{ENDL}")
		buffer.write(f"}}{ENDL}")
		return

	# A flat material list: every smMATERIAL is a top-level *MATERIAL with the
	# face MTLID equal to its array index (SubPoint stays 0, so the importer's
	# fmat = MatrialRef + MTLID resolves 1:1; smRead3d.cpp:1455-1460). The
	# original tools shipped both layouts - the multi/sub wrapper layout maps
	# MTLIDs through SubPoint - and this is the one that keeps the decoded
	# material ids stable.
	buffer.write(f"{TAB}*MATERIAL_COUNT {len(materials)}{ENDL}")

	for i, material in enumerate(materials):
		name = material_script_name(material)
		tm = material.texture_map
		level = f"{TAB}"
		buffer.write(f"{level}*MATERIAL {i} {{{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_NAME \"{name}\"{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_CLASS \"Standard\"{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_AMBIENT {mf(material.ambient)}{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_DIFFUSE {mf(material.diffuse)}{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_SPECULAR {mf(material.specular)}{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_SHINE {f(0.1)}{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_SHINESTRENGTH {f(0)}{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_TRANSPARENCY {f(material.transparency)}{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_WIRESIZE {f(1)}{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_SHADING Blinn{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_XP_FALLOFF {f(0)}{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_SELFILLUM {f(1 if material.selfillum else 0)}{ENDL}")
		if material.two_sided:
			buffer.write(f"{level}{TAB}*MATERIAL_TWOSIDED{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_FALLOFF In{ENDL}")
		buffer.write(f"{level}{TAB}*MATERIAL_XP_TYPE Filter{ENDL}")

		# Texture stage 0 is the diffuse map (AddMaterial BITMAP[0],
		# smTexture.cpp:812-821); stage 1+ ride the face texlink chain.
		# *MAP_OPACITY bumps the engine's per-material TextureCounter
		# (ReadASE_MATERIAL BitmapDiffuse=0, smRead3d.cpp:432-441, and the
		# stage-1 handling in ReadASE_GEOMOBJECT), which is how the second
		# texture path reaches the buffer.
		# every texture stage exports as its own *MAP_DIFFUSE block: the
		# importer counts one texture per *BITMAP under diffuse (BitmapCnt++,
		# smRead3d.cpp:432-441), which reproduces the shipped TextureCounter
		# of 2/3 for glow + lightmap materials (a *MAP_OPACITY emission would
		# instead route through the engine's opacity path and stay at 1)
		stage_flags = [(0, tm.diffuse_name, tm.diffuse_path)]

		if tm.selfillum_path:
			stage_flags.append((1, tm.selfillum_name, tm.selfillum_path))
		elif tm.lightmap_path:
			stage_flags.append((1, tm.lightmap_name, tm.lightmap_path))

		if tm.thirdstage_path:
			stage_flags.append((2, tm.thirdstage_name, tm.thirdstage_path))

		for stage, name, path in stage_flags:
			if not path:
				continue

			if name is None:
				name = texture_map_name(
					material.script_flags if stage == 0 else 0,
					0
				)

			ase_map(buffer, f"{level}{TAB}", "DIFFUSE", 1, name, path)

		buffer.write(f"{level}}}{ENDL}")

	buffer.write(f"}}{ENDL}")


def ase_node_tm(buffer: io.StringIO, name: str, transform: PTObjectTransform) -> None:
	buffer.write(f"{TAB}*NODE_TM {{{ENDL}")
	buffer.write(f"{TAB}{TAB}*NODE_NAME \"{name}\"{ENDL}")
	buffer.write(f"{TAB}{TAB}*INHERIT_POS 0 0 0{ENDL}")
	buffer.write(f"{TAB}{TAB}*INHERIT_ROT 0 0 0{ENDL}")
	buffer.write(f"{TAB}{TAB}*INHERIT_SCL 1 1 1{ENDL}")

	# TM rows are the world transform verbatim: the importer copies the three
	# rotation rows and the translation row straight into smOBJ3D.Tm
	# (ReadASE_GEOMOBJECT, smRead3d.cpp:1199-1253).
	buffer.write(f"{TAB}{TAB}*TM_ROW0 {f(transform._11)}\t{f(transform._12)}\t{f(transform._13)}{ENDL}")
	buffer.write(f"{TAB}{TAB}*TM_ROW1 {f(transform._21)}\t{f(transform._22)}\t{f(transform._23)}{ENDL}")
	buffer.write(f"{TAB}{TAB}*TM_ROW2 {f(transform._31)}\t{f(transform._32)}\t{f(transform._33)}{ENDL}")
	buffer.write(f"{TAB}{TAB}*TM_ROW3 {f(transform._41)}\t{f(transform._42)}\t{f(transform._43)}{ENDL}")

	buffer.write(f"{TAB}{TAB}*TM_POS {mf([transform.position.x, transform.position.y, transform.position.z])}{ENDL}")

	axis, angle = quaternion_to_axisangle(normalize_quaternion(transform.rotation))
	buffer.write(f"{TAB}{TAB}*TM_ROTAXIS {mf([axis.x, axis.y, axis.z])}{ENDL}")
	buffer.write(f"{TAB}{TAB}*TM_ROTANGLE {f(angle)}{ENDL}")

	buffer.write(f"{TAB}{TAB}*TM_SCALE {mf([transform.scale.x, transform.scale.y, transform.scale.z])}{ENDL}")
	buffer.write(f"{TAB}{TAB}*TM_SCALEAXIS {mf([0, 0, 0])}{ENDL}")
	buffer.write(f"{TAB}{TAB}*TM_SCALEAXISANG {f(0)}{ENDL}")
	buffer.write(f"{TAB}}}{ENDL}")


def ase_mesh(buffer: io.StringIO, object: PTActorObject | PTActorBone | PTStageObject) -> None:
	num_tvertex = sum(1 for t in object.texture_coords if t.uv_sets) * 3
	buffer.write(f"{TAB}*MESH {{{ENDL}")
	buffer.write(f"{TAB}{TAB}*TIMEVALUE 0{ENDL}")
	buffer.write(f"{TAB}{TAB}*MESH_NUMVERTEX {object.num_vertices}{ENDL}")
	buffer.write(f"{TAB}{TAB}*MESH_NUMFACES {object.num_faces}{ENDL}")

	if object.num_vertices > 0:
		buffer.write(f"{TAB}{TAB}*MESH_VERTEX_LIST {{{ENDL}")
		for i, vertex in enumerate(object.vertices):
			buffer.write(f"{TAB}{TAB}{TAB}*MESH_VERTEX{i:10d}\t{mf([vertex.x, vertex.y, vertex.z])}{ENDL}")
		buffer.write(f"{TAB}{TAB}}}{ENDL}")

	if object.num_faces > 0:
		buffer.write(f"{TAB}{TAB}*MESH_FACE_LIST {{{ENDL}")
		for i, face in enumerate(object.faces):
			# face indices are written 0-based; the flat material list makes
			# the face MTLID equal to the smMATERIAL array index (fmat =
			# MatrialRef + MTLID with SubPoint 0, smRead3d.cpp:1455-1460)
			material_id = max(face.material_id or 0, 0)
			buffer.write(
				f"{TAB}{TAB}{TAB}*MESH_FACE{i:10d}:\tA:{face.vertices[0]:10d}\tB:{face.vertices[1]:10d}\t"
				f"C:{face.vertices[2]:10d}\tAB:    1 BC:    1 CA:    1\t*MESH_SMOOTHING 1 \t*MESH_MTLID {material_id}{ENDL}"
			)
		buffer.write(f"{TAB}{TAB}}}{ENDL}")

	buffer.write(f"{TAB}{TAB}*MESH_NUMTVERTEX {num_tvertex}{ENDL}")

	if any(t.uv_sets for t in object.texture_coords):
		# the actor importer stores v = 1 - fv (smRead3d.cpp:1548), the stage
		# importer negates v (smRead3d.cpp:2535-2540); the encoder writes the
		# ASE value each reader's own transform restores to the stored link
		buffer.write(f"{TAB}{TAB}*MESH_TVERTLIST {{{ENDL}")
		for tex in object.texture_coords:
			for j, corner in enumerate(tex.face.vertices):
				uv = tex.uv_sets[0][j] if tex.uv_sets else PTTextureVertex()
				v = -uv.v if isinstance(object, PTStageObject) else uv.v
				buffer.write(f"{TAB}{TAB}{TAB}*MESH_TVERT {corner}\t{mf([uv.u, v, 0])}{ENDL}")
		buffer.write(f"{TAB}{TAB}}}{ENDL}")

		# UV sets 1+ export as extra full pools: *MESH_MAPPINGCHANNEL marks
		# the switch and the next *MESH_NUMTVERTEX (re)allocates the active
		# tvertex/tface pool (smRead3d.cpp:1160-1174); uv_sets[0] stays the
		# first pool, every additional set gets its own pool
		num_uv_sets = max((len(t.uv_sets) for t in object.texture_coords), default=1)

		for pool in range(1, num_uv_sets):
			buffer.write(f"{TAB}{TAB}*MESH_NUMTVFACES {object.num_faces}{ENDL}")
			buffer.write(f"{TAB}{TAB}*MESH_TFACELIST {{{ENDL}")
			for i, tex in enumerate(object.texture_coords):
				buffer.write(
					f"{TAB}{TAB}{TAB}*MESH_TFACE {i}\t{tex.face.vertices[0]}\t"
					f"{tex.face.vertices[1]}\t{tex.face.vertices[2]}{ENDL}"
				)
			buffer.write(f"{TAB}{TAB}}}{ENDL}")

			if pool == 1:
				buffer.write(f"{TAB}{TAB}*MESH_MAPPINGCHANNEL 2{ENDL}")
			buffer.write(f"{TAB}{TAB}*MESH_NUMTVERTEX {num_tvertex}{ENDL}")
			buffer.write(f"{TAB}{TAB}*MESH_TVERTLIST {{{ENDL}")
			for tex in object.texture_coords:
				for j, corner in enumerate(tex.face.vertices):
					uv = tex.uv_sets[pool][j] if len(tex.uv_sets) > pool else PTTextureVertex()
					v = -uv.v if isinstance(object, PTStageObject) else uv.v
					buffer.write(f"{TAB}{TAB}{TAB}*MESH_TVERT {corner}\t{mf([uv.u, v, 0])}{ENDL}")
			buffer.write(f"{TAB}{TAB}}}{ENDL}")

		buffer.write(f"{TAB}{TAB}*MESH_NUMTVFACES {object.num_faces}{ENDL}")
		buffer.write(f"{TAB}{TAB}*MESH_TFACELIST {{{ENDL}")
		for i, tex in enumerate(object.texture_coords):
			buffer.write(
				f"{TAB}{TAB}{TAB}*MESH_TFACE {i}\t{tex.face.vertices[0]}\t"
				f"{tex.face.vertices[1]}\t{tex.face.vertices[2]}{ENDL}"
			)
		buffer.write(f"{TAB}{TAB}}}{ENDL}")

	buffer.write(f"{TAB}}}{ENDL}")


def ase_animation(buffer: io.StringIO, object: PTActorObject | PTActorBone) -> None:
	animation = object.animation

	if not (animation.rotation or animation.position or animation.scale):
		return

	buffer.write(f"{TAB}*TM_ANIMATION {{{ENDL}")
	buffer.write(f"{TAB}{TAB}*NODE_NAME \"{object.name}\"{ENDL}")

	if animation.rotation:
		buffer.write(f"{TAB}{TAB}*CONTROL_ROT_TRACK {{{ENDL}")
		for rot in animation.rotation:
			# rotation keys are serialized as axis + angle, exactly like the
			# static *TM_ROTAXIS/*TM_ROTANGLE pair; the importer converts with
			# smQuaternionFromAxis (smRead3d.cpp:1360-1385)
			axis, angle = quaternion_to_axisangle(
				normalize_quaternion(PTQuaternion(rot.x, rot.y, rot.z, rot.w))
			)
			buffer.write(f"{TAB}{TAB}{TAB}*CONTROL_ROT_SAMPLE {rot.frame}\t{mf([axis.x, axis.y, axis.z, angle])}{ENDL}")
		buffer.write(f"{TAB}{TAB}}}{ENDL}")

	if animation.position:
		buffer.write(f"{TAB}{TAB}*CONTROL_POS_TRACK {{{ENDL}")
		for pos in animation.position:
			buffer.write(f"{TAB}{TAB}{TAB}*CONTROL_POS_SAMPLE {pos.frame}\t{mf([pos.x, pos.y, pos.z])}{ENDL}")
		buffer.write(f"{TAB}{TAB}}}{ENDL}")

	if animation.scale:
		buffer.write(f"{TAB}{TAB}*CONTROL_SCALE_TRACK {{{ENDL}")
		for scl in animation.scale:
			buffer.write(f"{TAB}{TAB}{TAB}*CONTROL_SCALE_SAMPLE {scl.frame}\t{mf([scl.x, scl.y, scl.z])}{ENDL}")
		buffer.write(f"{TAB}{TAB}}}{ENDL}")

	buffer.write(f"{TAB}}}{ENDL}")


def ase_physique(buffer: io.StringIO, object: PTActorObject) -> None:
	if not getattr(object, "physique", None) or object.num_vertices <= 0:
		return

	buffer.write(f"{TAB}*PHYSIQUE {{{ENDL}")
	buffer.write(f"{TAB}{TAB}*PHYSIQUE_NUMVERTEXASSIGNMENT  {object.num_vertices}{ENDL}")
	for i, bone in enumerate(object.physique):
		buffer.write(f"{TAB}{TAB}*PHYSIQUE_VERTEXASSIGNMENT_NONBLENDED_RIGIDTYPE\t{i}\t\"{bone}\"{ENDL}")
	buffer.write(f"{TAB}}}{ENDL}")


def ase_geomobject(buffer: io.StringIO, object: PTActorObject | PTActorBone, bone: bool = False) -> None:
	buffer.write(f"*GEOMOBJECT {{{ENDL}")
	buffer.write(f"{TAB}*NODE_NAME \"{object.name}\"{ENDL}")
	if object.parent:
		buffer.write(f"{TAB}*NODE_PARENT \"{object.parent}\"{ENDL}")

	ase_node_tm(buffer, object.name, object.transform)
	ase_mesh(buffer, object)

	buffer.write(f"{TAB}*PROP_MOTIONBLUR 0{ENDL}")
	buffer.write(f"{TAB}*PROP_CASTSHADOW 1{ENDL}")
	buffer.write(f"{TAB}*PROP_RECVSHADOW 1{ENDL}")

	if not bone:
		# the wrapper material; face MTLIDs index its submaterials
		buffer.write(f"{TAB}*MATERIAL_REF 0{ENDL}")
		buffer.write(f"{TAB}*WIREFRAME_COLOR 0.4000\t0.1000\t0.7000{ENDL}")

	ase_animation(buffer, object)
	ase_physique(buffer, object)

	buffer.write(f"}}{ENDL}")


def ase_lightobject(buffer: io.StringIO, light: PTStageLight) -> None:
	name = ""

	if light.dynamic:
		name = "dynamic:"
	if light.night:
		name = "night:"
	if light.lens:
		name = "lens:"
	if light.obj:
		name = "obj:"

	buffer.write(f"*LIGHTOBJECT {{{ENDL}")
	buffer.write(f"{TAB}*NODE_NAME \"{name}\"{ENDL}")
	buffer.write(f"{TAB}*LIGHT_TYPE Omni{ENDL}")
	# the stage light reader maps *TM_POS (x, z, y) into the engine struct
	# (smRead3d.cpp:2865-2871); the PT position is the swapped-back (x, z, y),
	# so the ASE line carries (x, z, y) of the PT vector
	buffer.write(f"{TAB}*TM_POS {mf([light.position.x, light.position.z, light.position.y])}{ENDL}")

	# the importer reads intensity first and folds it into the color channels
	# (smReadASE_LIGHTOBJECT, smRead3d.cpp:2878-2905); 1.0 keeps them verbatim
	buffer.write(f"{TAB}*LIGHT_COLOR {mf([light.color.r, light.color.g, light.color.b])}{ENDL}")
	buffer.write(f"{TAB}*LIGHT_INTENS {f(1)}{ENDL}")
	buffer.write(f"{TAB}*LIGHT_MAPRANGE {f(light.range / 64)}{ENDL}")
	buffer.write(f"}}{ENDL}")


def ase_stage_object(buffer: io.StringIO, object: PTStageObject) -> None:
	"""The stage importer reads the mesh without its *GEOMOBJECT wrapper
	(smSTAGE3D_ReadASE_GEOMOBJECT is handed the fp already inside); the mesh
	block alone carries everything it consumes."""
	ase_mesh(buffer, object)


def encode(model: PTActorModel | PTStageModel, path: str) -> None:
	"""Build the whole document in an in-memory buffer and write it to disk in
	one call (these are large text files; per-line writes thrash the disk)."""
	buffer = io.StringIO()

	ase_header(buffer)

	filename = model.filename or "model"

	if isinstance(model, PTStageModel):
		ase_scene(buffer, model.scene, filename)
		ase_materials(buffer, model.materials)

		for object in model.objects:
			ase_stage_object(buffer, object)

		for light in model.lights:
			ase_lightobject(buffer, light)
	else:
		# bones first, matching the original split: smASE_ReadBone keeps
		# only Bip* objects into the .smb, smASE_Read drops them from the
		# mesh (smRead3d.cpp:1957-1975)
		for bone in model.bones:
			ase_geomobject(buffer, bone, True)
		for object in model.objects:
			ase_geomobject(buffer, object)

	# actors reparse the frame data out of the keys, so the scene block is
	# written after the objects where the SMotionStEndInfo windows come from
	if isinstance(model, PTActorModel):
		first_frame = 0

		for object in model.bones + model.objects:
			if object.animation.rotation_windows:
				first_frame = object.animation.rotation_windows[0][0] // model.scene.ticks_per_frame
				break

		ase_scene(buffer, model.scene, model.filename or "model", first_frame)
		ase_materials(buffer, model.materials)

	with open(path, "w", encoding="ascii", newline="\n") as file:
		file.write(buffer.getvalue())
