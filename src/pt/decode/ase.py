"""ASE (3ds Max Ascii Export) reader.

Tokenizing matches the engine's GetWord/GetString pair (smRead3d.cpp:37):
words split on space/tab/colon, quoted sections become one token. Every value
read here mirrors what ReadASE_MATERIAL / ReadASE_GEOMOBJECT /
smReadASE_LIGHTOBJECT / smSTAGE3D_ReadASE_GEOMOBJECT consume; anything the
importers ignore (map class, smoothing groups, UVW blur, node colors, ...) is
ignored the same way.
"""

import math
import os

from pt.pdef import *
from pt.const import (
	STAGE_SCRIPT,
	FORM_SCRIPT,
	MTL_FORM_SCRIPT,
	MTL_FORM_BLEND
)
from pt.utils import atoi, atof


FONE = 256

# light type flags (smType.h:132-138)
SM_LIGHT_DYNAMIC = 0x80000
SM_LIGHT_NIGHT = 0x1
SM_LIGHT_LENS = 0x2
SM_LIGHT_OBJ = 0x8

ASE_MATERIAL_MAX = 4096


class AseMaterial:
	def __init__(self):
		self.SubPoint = 0
		self.ScriptState = 0
		self.BlendType = 0
		self.TextureCounter = 0
		self.BITMAP = []
		self.BitmapStateState = []
		self.BitmapFormState = []
		self.UVW_U_OFFSET = []
		self.UVW_V_OFFSET = []
		self.UVW_U_TILING = []
		self.UVW_V_TILING = []
		self.UVW_ANGLE = []
		self.MAP_OPACITY = ""
		self.Diffuse = PTVector3(0.5882, 0.5882, 0.5882)
		self.Transparency = 0.0
		self.SelfIllum = 0.0
		self.TwoSide = 0
		self.RegistNum = -1


class AseLight:
	def __init__(self):
		self.Type = 0
		self.x = 0
		self.y = 0
		self.z = 0
		self.r = 0
		self.g = 0
		self.b = 0
		self.Range = 0


class AseGeomObject:
	def __init__(self):
		self.NodeName = ""
		self.NodeParent = ""
		# row-major 4x4 of the *TM_ROW data (identity, engine default)
		self.Tm = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
		self.px = self.py = self.pz = 0.0
		self.qx = self.qy = self.qz = 0.0
		self.qw = 0.0
		self.has_qrot = False
		self.sx = self.sy = self.sz = 256.0
		self.TmRot = []
		self.TmPos = []
		self.TmScale = []
		self.vertices = []
		self.faces = []
		self.tvertex = []        # pool 0 (primary UV set)
		self.tface = []
		self.lightmap_tvertex = []  # pool 1 (second UV set)
		self.lightmap_tface = []
		self.extra_tvertex = []  # pools 2+ (third+ UV sets)
		self.extra_tface = []
		self.lightmap_active = False
		self.bLightMap = False
		self.FaceMatrial = []
		self.MatrialRef = 0
		self.Physique = []
		self.stage_mode = False
		self.tvertex_pool = 0


def tokenize(line: str) -> list[str]:
	"""GetWord semantics: skip space/tab/colons, a token runs to the next
	space/tab/colon; GetString semantics: inside quotes, to the closing quote."""
	tokens = []
	i, n = 0, len(line)

	while i < n:
		while i < n and line[i] in " \t\r\n:":
			i += 1
		if i >= n:
			break
		if line[i] == '"':
			i += 1
			start = i
			while i < n and line[i] not in '"\r\n':
				i += 1
			tokens.append(line[start:i])
			i += 1
		else:
			start = i
			while i < n and line[i] not in " \t\r\n:":
				i += 1
			tokens.append(line[start:i])

	return tokens


def word_at(tokens: list[str], index: int) -> str:
	return tokens[index] if index < len(tokens) else ""


def bitmap_basename(path: str) -> str:
	"""ReadASE_MATERIAL keeps the ASE-side path only for its directory
	(SetDirectoryFromFile) and concatenates DataDirectory + basename
	(smRead3d.cpp:425-445); the carried part is the basename."""
	return os.path.basename(path.replace("\\", "/"))


class AseReader:
	"""Line cursor over the whole file; block() consumes one `{ ... }` group.
	The engine tracks braces anywhere in the line (strstr); shipped files and
	this project's encoder never share braces across lines."""

	def __init__(self, lines: list[str]):
		self.lines = lines
		self.i = 0

	def next_line(self) -> str | None:
		if self.i >= len(self.lines):
			return None
		line = self.lines[self.i]
		self.i += 1
		return line

	def block(self) -> list[list[str]]:
		"""Tokenized lines of one block; assumes the opening line was already
		consumed. Ends after the line that closes the block."""
		out = []
		level = 1

		for line in iter(self.next_line, None):
			out.append(tokenize(line))
			level += line.count("{") - line.count("}")

			if level <= 0:
				break

		return out


def parse_material_list(reader: AseReader) -> list[AseMaterial]:
	"""ReadASE_MATERIAL (smRead3d.cpp:258-556): submaterials flatten into the
	global aseMaterial[] array via SubPoint arithmetic; every *MATERIAL_NAME
	parses its scripts; every *BITMAP lands on the current diffuse index."""
	ase_materials = [ AseMaterial() for _ in range(ASE_MATERIAL_MAX) ]
	cur = 0
	material_num = 0
	last_material = 0
	subpoint = 0
	bitmap_num = -1
	bitmap_diffuse = -1
	bitmap_stage = 0
	bitmap_form = 0
	str_level = 0

	for tokens in reader.block():
		word = word_at(tokens, 0)

		# the engine's keyword checks run against the pre-line brace level (the
		# `{` of "*MATERIAL 0 {" increments only after the line was parsed), so
		# the level bookkeeping happens after the keyword chain
		line_level_up = 1 if "{" in " ".join(tokens) else 0
		line_level_down = -1 if "}" in " ".join(tokens) else 0

		if line_level_down:
			str_level -= 1
			if str_level < 0:
				break

		if word == "*MATERIAL_COUNT":
			subpoint = atoi(word_at(tokens, 1))
		elif word == "*MATERIAL":
			material_num = atoi(word_at(tokens, 1))
			cur = material_num
			last_material = max(last_material, material_num)
			bitmap_num = -1
		elif str_level == 1 and word == "*NUMSUBMTLS":
			sm_count = atoi(word_at(tokens, 1))
			ase_materials[material_num].SubPoint = subpoint
			subpoint += sm_count
		elif str_level == 1 and word == "*SUBMATERIAL":
			cur = ase_materials[material_num].SubPoint + atoi(word_at(tokens, 1))
			last_material = max(last_material, cur)
			bitmap_num = -1

		elif word == "*MATERIAL_NAME":
			value = word_at(tokens, 1)
			for script, code in MTL_FORM_SCRIPT:
				if script in value:
					ase_materials[cur].ScriptState |= code
			for script, code in MTL_FORM_BLEND:
				if script in value:
					ase_materials[cur].BlendType = code
					break

		elif word == "*MAP_DIFFUSE":
			bitmap_diffuse = 1
		elif word == "*MAP_OPACITY":
			bitmap_diffuse = 0
		elif word == "*MAP_AMBIENT":
			bitmap_diffuse = -1
		elif word == "*MAP_NAME":
			value = word_at(tokens, 1)
			bitmap_stage = 0
			bitmap_form = 0

			for script, code in STAGE_SCRIPT:
				if script in value:
					bitmap_stage = code
					break
			for index, (script, _) in enumerate(FORM_SCRIPT):
				if script in value:
					bitmap_form = index
					break

		elif word == "*BITMAP":
			value = word_at(tokens, 1)

			if bitmap_diffuse == 1:
				bitmap_num += 1
				mat = ase_materials[cur]
				while len(mat.BITMAP) <= bitmap_num:
					mat.BITMAP.append("")
					mat.BitmapStateState.append(0)
					mat.BitmapFormState.append(0)
					mat.UVW_U_OFFSET.append(0.0)
					mat.UVW_V_OFFSET.append(0.0)
					mat.UVW_U_TILING.append(1.0)
					mat.UVW_V_TILING.append(1.0)
					mat.UVW_ANGLE.append(0.0)
				mat.BITMAP[bitmap_num] = value
				mat.TextureCounter += 1
				mat.BitmapStateState[bitmap_num] = bitmap_stage
				mat.BitmapFormState[bitmap_num] = bitmap_form
			elif bitmap_diffuse == 0:
				ase_materials[cur].MAP_OPACITY = value

		elif word == "*MATERIAL_TWOSIDED":
			ase_materials[cur].TwoSide = 1
		elif word == "*MATERIAL_DIFFUSE":
			mat = ase_materials[cur]
			mat.Diffuse = PTVector3(
				atof(word_at(tokens, 1)),
				atof(word_at(tokens, 2)),
				atof(word_at(tokens, 3))
			)
		elif word == "*MATERIAL_TRANSPARENCY":
			ase_materials[cur].Transparency = atof(word_at(tokens, 1))
		elif word == "*MATERIAL_SELFILLUM":
			ase_materials[cur].SelfIllum = atof(word_at(tokens, 1))

		str_level += line_level_up

	# aseMaterialCnt = curMatrialNum + 1 (smRead3d.cpp:558); the flat list is
	# trimmed so downstream registration only sees the declared range
	return ase_materials[:last_material + 1]


def parse_lightobject(reader: AseReader) -> AseLight:
	"""smReadASE_LIGHTOBJECT (smRead3d.cpp:2792-2905): type comes from the
	node-name prefixes, position reads (x, z, y), range = value*16384."""
	light = AseLight()

	for tokens in reader.block():
		word = word_at(tokens, 0)

		if word == "*NODE_NAME":
			value = word_at(tokens, 1)
			if "dynamic:" in value:
				light.Type |= SM_LIGHT_DYNAMIC
			if "night:" in value:
				light.Type |= SM_LIGHT_DYNAMIC | SM_LIGHT_NIGHT
			if "lens:" in value:
				light.Type |= SM_LIGHT_DYNAMIC | SM_LIGHT_LENS
			if "obj:" in value:
				light.Type |= SM_LIGHT_DYNAMIC | SM_LIGHT_OBJ
		elif word == "*LIGHT_COLOR":
			light.r = round(atof(word_at(tokens, 1)) * 255)
			light.g = round(atof(word_at(tokens, 2)) * 255)
			light.b = round(atof(word_at(tokens, 3)) * 255)
		elif word == "*LIGHT_INTENS":
			intens = int(atof(word_at(tokens, 1)) * FONE)
			if intens:
				if 0 <= intens < 64: intens = 64
				if -64 < intens < 0: intens = -64
				light.r = (light.r * intens) >> 8
				light.g = (light.g * intens) >> 8
				light.b = (light.b * intens) >> 8
		elif word == "*TM_POS":
			# the reader maps (x, z, y) into the engine struct
			# (smRead3d.cpp:2865-2871); the PT light position is already
			# swapped back by decode_stage_lights, so keep the ASE order
			# verbatim here and let decode_ase_stage map (x, z, y)
			light.x = int(atof(word_at(tokens, 1)) * FONE)
			light.y = int(atof(word_at(tokens, 2)) * FONE)
			light.z = int(atof(word_at(tokens, 3)) * FONE)
		elif word == "*LIGHT_MAPRANGE":
			light.Range = int(atof(word_at(tokens, 1)) * FONE / 4 * FONE)

	return light


def parse_geomobject(reader: AseReader, node_name: str | None = None, stage_mode: bool = False) -> AseGeomObject:
	"""ReadASE_GEOMOBJECT (smRead3d.cpp:914-1696). node_name mirrors the
	szNodeName filter: a mismatched name aborts the object (nFace/nVertex 0)."""
	obj = AseGeomObject()
	obj.stage_mode = stage_mode

	for tokens in reader.block():
		word = word_at(tokens, 0)

		if word == "*NODE_NAME":
			obj.NodeName = word_at(tokens, 1)[:31]
			if node_name and obj.NodeName.lower() != node_name.lower():
				obj.NodeName = node_name
				return obj
		elif word == "*NODE_PARENT":
			obj.NodeParent = word_at(tokens, 1)[:31]
		elif word == "*TM_ROW0":
			obj.Tm[0] = atof(word_at(tokens, 1))
			obj.Tm[1] = atof(word_at(tokens, 2))
			obj.Tm[2] = atof(word_at(tokens, 3))
		elif word == "*TM_ROW1":
			obj.Tm[4] = atof(word_at(tokens, 1))
			obj.Tm[5] = atof(word_at(tokens, 2))
			obj.Tm[6] = atof(word_at(tokens, 3))
		elif word == "*TM_ROW2":
			obj.Tm[8] = atof(word_at(tokens, 1))
			obj.Tm[9] = atof(word_at(tokens, 2))
			obj.Tm[10] = atof(word_at(tokens, 3))
		elif word == "*TM_ROW3":
			obj.Tm[12] = atof(word_at(tokens, 1))
			obj.Tm[13] = atof(word_at(tokens, 2))
			obj.Tm[14] = atof(word_at(tokens, 3))
		elif word == "*TM_POS":
			obj.px = atof(word_at(tokens, 1))
			obj.py = atof(word_at(tokens, 2))
			obj.pz = atof(word_at(tokens, 3))
		elif word == "*TM_ROTAXIS":
			obj.qx = atof(word_at(tokens, 1))
			obj.qy = atof(word_at(tokens, 2))
			obj.qz = atof(word_at(tokens, 3))
		elif word == "*TM_ROTANGLE":
			obj.qw = atof(word_at(tokens, 1))
			obj.has_qrot = True
		elif word == "*TM_SCALE":
			obj.sx = atof(word_at(tokens, 1))
			obj.sy = atof(word_at(tokens, 2))
			obj.sz = atof(word_at(tokens, 3))
		elif word in ("*CONTROL_ROT_SAMPLE", "*CONTROL_TCB_ROT_KEY"):
			obj.TmRot.append((
				atoi(word_at(tokens, 1)),
				atof(word_at(tokens, 2)),
				atof(word_at(tokens, 3)),
				atof(word_at(tokens, 4)),
				atof(word_at(tokens, 5))
			))
		elif word in ("*CONTROL_POS_SAMPLE", "*CONTROL_TCB_POS_KEY", "*CONTROL_BEZIER_POS_KEY"):
			obj.TmPos.append((
				atoi(word_at(tokens, 1)),
				atof(word_at(tokens, 2)),
				atof(word_at(tokens, 3)),
				atof(word_at(tokens, 4))
			))
		elif word in ("*CONTROL_SCALE_SAMPLE", "*CONTROL_TCB_SCALE_KEY", "*CONTROL_BEZIER_SCALE_KEY"):
			obj.TmScale.append((
				atoi(word_at(tokens, 1)),
				atof(word_at(tokens, 2)),
				atof(word_at(tokens, 3)),
				atof(word_at(tokens, 4))
			))
		elif word == "*MESH_VERTEX":
			obj.vertices.append((
				atof(word_at(tokens, 2)),
				atof(word_at(tokens, 3)),
				atof(word_at(tokens, 4))
			))
		elif word == "*MESH_FACE":
			# GetWord drops the ':' delimiter, so the face line tokenizes as
			# ['*MESH_FACE', '0', 'A', '12', 'B', '11', 'C', '0', 'AB', '1',
			# ..., '*MESH_MTLID', '1'] - values sit one token after the labels
			a = atoi(word_at(tokens, 3))
			b = atoi(word_at(tokens, 5))
			c = atoi(word_at(tokens, 7))
			obj.faces.append((a, b, c))

			for k in range(7, 7 + 16):
				if word_at(tokens, k) == "*MESH_MTLID":
					obj.FaceMatrial.append(atoi(word_at(tokens, k + 1)))
					break
			else:
				obj.FaceMatrial.append(0)
		elif word == "*MESH_TVERT":
			# the stage reader negates v on entry (smRead3d.cpp:2535-2540);
			# the actor reader stores it verbatim (smRead3d.cpp:1543-1546)
			v = -atof(word_at(tokens, 3)) if obj.stage_mode else atof(word_at(tokens, 3))
			value = (atof(word_at(tokens, 2)), v)
			if obj.lightmap_active:
				if obj.tvertex_pool > 2:
					obj.extra_tvertex.append(value)
				else:
					obj.lightmap_tvertex.append(value)
			else:
				obj.tvertex.append(value)
		elif word == "*MESH_MAPPINGCHANNEL":
			obj.bLightMap = True
		elif word == "*MESH_NUMTVERTEX":
			# each *MESH_NUMTVERTEX (re)allocates the active pool
			# (smRead3d.cpp:1160-1174); when *MESH_MAPPINGCHANNEL appeared
			# earlier, the second pool is the lightmap one
			obj.tvertex_pool += 1
			obj.lightmap_active = obj.bLightMap and obj.tvertex_pool > 1
		elif word == "*MESH_NUMTVFACES":
			# each TFACE list feeds the currently active pool (the C importer
			# fills lpTexFace, repointed at every *MESH_NUMTVERTEX)
			obj.lightmap_active = obj.bLightMap and obj.tvertex_pool > 1
		elif word == "*MESH_TFACE":
			value = (
				atoi(word_at(tokens, 2)),
				atoi(word_at(tokens, 3)),
				atoi(word_at(tokens, 4))
			)
			if obj.lightmap_active:
				if obj.tvertex_pool > 2:
					obj.extra_tface.append(value)
				else:
					obj.lightmap_tface.append(value)
			else:
				obj.tface.append(value)
		elif word == "*MATERIAL_REF":
			obj.MatrialRef = atoi(word_at(tokens, 1))
		elif word == "*PHYSIQUE_VERTEXASSIGNMENT_NONBLENDED_RIGIDTYPE":
			pnum = atoi(word_at(tokens, 1))
			while len(obj.Physique) <= pnum:
				obj.Physique.append("")
			obj.Physique[pnum] = word_at(tokens, 2)
		elif word == "*PHYSIQUE_VERTEXASSIGNMENT_BLENDED_RIGIDTYPE":
			pnum = atoi(word_at(tokens, 1))
			while len(obj.Physique) <= pnum:
				obj.Physique.append("")
		elif word == "*PHYSIQUE_VERTEXASSIGNMENT_NODE":
			# only the x==0 (first) assignment is kept (smRead3d.cpp:1562-1576)
			if atoi(word_at(tokens, 1)) == 0:
				pnum = atoi(word_at(tokens, 2))
				while len(obj.Physique) <= pnum:
					obj.Physique.append("")
				obj.Physique[pnum] = word_at(tokens, 3)

	return obj


def parse_scene(reader: AseReader) -> tuple[int, int, int]:
	first_frame = 0
	last_frame = 0
	ticks = 160

	for tokens in reader.block():
		word = word_at(tokens, 0)
		if word == "*SCENE_FIRSTFRAME":
			first_frame = atoi(word_at(tokens, 1))
		elif word == "*SCENE_LASTFRAME":
			last_frame = atoi(word_at(tokens, 1))
		elif word == "*SCENE_TICKSPERFRAME":
			ticks = atoi(word_at(tokens, 1))

	return first_frame, last_frame, ticks


def parse_ase(path: str) -> dict:
	"""Top-level pass mirroring smASE_Read / smASE_ReadBone /
	smSTAGE3D_ReadASE: scene, material list, then every GEOMOBJECT /
	LIGHTOBJECT block in file order."""
	with open(path, encoding="cp949", errors="replace") as f:
		lines = f.read().splitlines()

	reader = AseReader(lines)
	ase = {
		"first_frame": 0,
		"last_frame": 0,
		"ticks": 160,
		"materials": [],
		"objects": [],
		"lights": []
	}

	while True:
		line = reader.next_line()
		if line is None:
			break

		stripped = line.strip()
		if not stripped.startswith("*"):
			continue

		word = stripped.split(None, 1)[0].rstrip("{").strip()

		if word == "*SCENE":
			ase["first_frame"], ase["last_frame"], ase["ticks"] = parse_scene(reader)
		elif word == "*MATERIAL_LIST":
			ase["materials"] = parse_material_list(reader)
		elif word == "*GEOMOBJECT":
			ase["objects"].append(parse_geomobject(reader))
		elif word == "*MESH":
			# stage files carry bare *MESH blocks (smSTAGE3D_ReadASE_GEOMOBJECT
			# is handed the fp already positioned inside the mesh); reuse the
			# same parser - its *NODE_NAME filter simply never matches
			ase["objects"].append(parse_geomobject(reader, stage_mode=True))
		elif word == "*LIGHTOBJECT":
			ase["lights"].append(parse_lightobject(reader))

	return ase


def quat_from_axisangle(axis: tuple[float, float, float], angle: float) -> PTQuaternion:
	"""smQuaternionFromAxis (smmatrix.cpp:233): w is the angle in radians, the
	axis components scale sin(angle/2)."""
	x, y, z = axis
	sn = math.sin(angle / 2)
	return PTQuaternion(
		x = x * sn,
		y = y * sn,
		z = z * sn,
		w = math.cos(angle / 2)
	)
