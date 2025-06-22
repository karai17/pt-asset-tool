from ctypes import *


class POINT3D(LittleEndianStructure):
	# 12 bytes
	_fields_ = [
		("x", c_int32), ("y", c_int32), ("z", c_int32)
]


class RECT(LittleEndianStructure):
	# 16 bytes
	_fields_ = [
		("left", c_int32),
		("top", c_int32),
		("right", c_int32),
		("bottom", c_int32)
	]


class smVERTEX(LittleEndianStructure):
	# 24 bytes
	_fields_ = [
		("x", c_int32), ("y", c_int32), ("z", c_int32),
		("nx", c_int32), ("ny", c_int32), ("nz", c_int32)
]


class smFACE(LittleEndianStructure):
	# 36 bytes
	_fields_ = [
		("v", c_uint16 * 4),
		("t", (c_float * 2) * 3),
		("lpTexLink_ptr", c_uint32)
	]


class smTEXLINK(LittleEndianStructure):
	# 32 bytes
	_fields_ = [
		("u", c_float * 3), ("v", c_float * 3),
		("hTexture_ptr", c_uint32),
		("NextTex_ptr", c_uint32)
	]


class smTM_ROT(LittleEndianStructure):
	# 20 bytes
	_fields_ = [
		("frame", c_int32),
		("x", c_float), ("y", c_float), ("z", c_float), ("w", c_float)
	]


class smTM_POS(LittleEndianStructure):
	# 16 bytes
	_fields_ = [
		("frame", c_int32),
		("x", c_float), ("y", c_float), ("z", c_float)
	]


class smTM_SCALE(LittleEndianStructure):
	# 16 bytes
	_fields_ = [
		("frame", c_int32),
		("x", c_int32), ("y", c_int32), ("z", c_int32)
	]


# smMATRIX et al are column-major despite DirectX being row-major. To
# compensate for this, the matrix math functions are written to perform
# backwards. When you do A * B, it secretly does B * A. Note that instead of
# _ij order, the operation in the reference is _ji.
# Reference: smmatrix.cpp::smMatrixMult.


class smMATRIX(LittleEndianStructure):
	# 64 bytes
	_fields_ = [
		("_11", c_int32), ("_12", c_int32), ("_13", c_int32), ("_14", c_int32),
		("_21", c_int32), ("_22", c_int32), ("_23", c_int32), ("_24", c_int32),
		("_31", c_int32), ("_32", c_int32), ("_33", c_int32), ("_34", c_int32),
		("_41", c_int32), ("_42", c_int32), ("_43", c_int32), ("_44", c_int32)
	]


class smFMATRIX(LittleEndianStructure):
	# 64 bytes
	_fields_ = [
		("_11", c_float), ("_12", c_float), ("_13", c_float), ("_14", c_float),
		("_21", c_float), ("_22", c_float), ("_23", c_float), ("_24", c_float),
		("_31", c_float), ("_32", c_float), ("_33", c_float), ("_34", c_float),
		("_41", c_float), ("_42", c_float), ("_43", c_float), ("_44", c_float)
	]


class smFRAME_POS(LittleEndianStructure):
	# 16 bytes
	_fields_ = [
		("StartFrame", c_int32),
		("EndFrame", c_int32),
		("PosNum", c_int32),
		("PosCnt", c_int32)
	]


class smDFILE_HEADER(LittleEndianStructure):
	# 556 bytes
	_fields_ = [
		("szHeader", c_byte * 24),
		("ObjCounter", c_int32),
		("MatCounter", c_int32),
		("MatFilePoint", c_int32),
		("First_ObjInfoPoint", c_int32),
		("TmFrameCounter", c_int32),
		("TmFrame", smFRAME_POS * 32)
	]


class smDFILE_OBJINFO(LittleEndianStructure):
	# 40 bytes
	_fields_ = [
		("szNodeName", c_byte * 32),
		("Length", c_int32),
		("ObjFilePoint", c_int32)
	]


class smMATERIAL_GROUP(LittleEndianStructure):
	# 88 bytes
	_fields_ = [
		("Head", c_uint32),
		("smMaterial_ptr", c_uint32),
		("MaterialCount", c_uint32),
		("ReformTexture", c_int32),
		("MaxMaterial", c_int32),
		("LastSearchMaterial", c_int32),
		("szLastSearchName", c_byte * 64)
	]


class smMATERIAL(LittleEndianStructure):
	# 320 bytes
	_fields_ = [
		("InUse", c_uint32),
		("TextureCounter", c_uint32),
		("smTexture_ptr", c_uint32 * 8),
		("TextureStageState", c_uint32 * 8),
		("TextureFormState", c_uint32 * 8),
		("ReformTexture", c_int32),
		("MapOpacity", c_int32),
		("TextureType", c_uint32),
		("BlendType", c_uint32),
		("Shade", c_uint32),
		("TwoSide", c_uint32),
		("SerialNum", c_uint32),
		("Diffuse", c_float * 3),
		("Transparency", c_float),
		("SelfIllum", c_float),
		("TextureSwap", c_int32),
		("MatFrame", c_int32),
		("TextureClip", c_int32),
		("UseState", c_int32),
		("MeshState", c_int32),
		("WindMeshBottom", c_int32),
		("smAnimTexture_ptr", c_uint32 * 32),
		("AnimTexCounter", c_uint32),
		("FrameMask", c_uint32),
		("Shift_FrameSpeed", c_uint32),
		("AnimationFrame", c_uint32)
	]


class smOBJ3D(LittleEndianStructure):
	# 2236 bytes
	_fields_ = [
		("Head", c_uint32),
		("Vertex_ptr", c_uint32),
		("Face_ptr", c_uint32),
		("TexLink_ptr", c_uint32),
		("Physique_ptr", c_uint32),
		("ZeroVertex", smVERTEX),
		("maxZ", c_int32), ("minZ", c_int32),
		("maxY", c_int32), ("minY", c_int32),
		("maxX", c_int32), ("minX", c_int32),
		("dBound", c_int32),
		("Bound", c_int32),
		("MaxVertex", c_int32),
		("MaxFace", c_int32),
		("nVertex", c_int32),
		("nFace", c_int32),
		("nTexLink", c_int32),
		("ColorEffect", c_int32),
		("ClipStates", c_uint32),
		("Posi", POINT3D),
		("CameraPosi", POINT3D),
		("Angle", POINT3D),
		("Trig", c_int32 * 8),
		("NodeName", c_byte * 32),
		("NodeParent", c_byte * 32),
		("pParent_ptr", c_uint32),
		("Tm", smMATRIX),
		("TmInvert", smMATRIX),
		("TmResult", smFMATRIX),  # unused in SMD
		("TmRotate", smMATRIX),
		("mWorld", smMATRIX), # unused in SMD
		("mLocal", smMATRIX),
		("lFrame", c_int32),
		("qx", c_float), ("qy", c_float), ("qz", c_float), ("qw", c_float),
		("sx", c_int32), ("sy", c_int32), ("sz", c_int32),
		("px", c_int32), ("py", c_int32), ("pz", c_int32),
		("TmRot_ptr", c_uint32),
		("TmPos_ptr", c_uint32),
		("TmScale_ptr", c_uint32),
		("TmPrevRot_ptr", c_uint32), # sandurr's "unknown"
		("TmRotCnt", c_int32),
		("TmPosCnt", c_int32),
		("TmScaleCnt", c_int32),
		("TmRotFrame", smFRAME_POS * 32),
		("TmPosFrame", smFRAME_POS * 32),
		("TmScaleFrame", smFRAME_POS * 32),
		("TmFrameCnt", c_int32)
	]


class _MODELGROUP(LittleEndianStructure):
	# 68 bytes
	_fields_ = [
		("ModelNameCnt", c_int32),
		("szModelName", (c_byte * 16) * 4),
	]


class smMOTIONINFO(LittleEndianStructure):
	# 117 bytes (120?)
	_fields_ = [
		("State", c_uint32),
		("MotionKeyWord_1", c_uint32),
		("StartFrame", c_uint32),
		("MotionKeyWord_2", c_uint32),
		("EndFrame", c_uint32),
		("EventFrame", c_uint32 * 4),
		("ItemCodeCount", c_int32),
		("ItemCodeList", c_ubyte * 52),
		("dwJobCodeBit", c_uint32),
		("SkillCodeList", c_ubyte * 8),
		("MapPosition", c_int32),
		("Repeat", c_uint32),
		("KeyCode", c_byte),
		("MotionFrame", c_int32)
	]


class smMOTIONINFO_EX(LittleEndianStructure):
	# 169 bytes (172?)
	_fields_ = [
		("State", c_uint32),
		("MotionKeyWord_1", c_uint32),
		("StartFrame", c_uint32),
		("MotionKeyWord_2", c_uint32),
		("EndFrame", c_uint32),
		("EventFrame", c_uint32 * 4),
		("ItemCodeCount", c_int32),
		("ItemCodeList", c_uint16 * 52),
		("dwJobCodeBit", c_uint32),
		("SkillCodeList", c_ubyte * 8),
		("MapPosition", c_int32),
		("Repeat", c_uint32),
		("KeyCode", c_byte),
		("MotionFrame", c_int32)
	]


class smMODELINFO(LittleEndianStructure):
	# 67084 bytes
	_fields_ = [
		("szModelFile", c_byte * 64),
		("szMotionFile", c_byte * 64),
		("szSubModelFile", c_byte * 64),
		("HighModel", _MODELGROUP),
		("DefaultModel", _MODELGROUP),
		("LowModel", _MODELGROUP),
		("MotionInfo", smMOTIONINFO * 512),
		("MotionCount", c_uint32),
		("FileTypeKeyWord", c_uint32),
		("LinkFileKeyWord", c_uint32),
		("szLinkFile", c_byte * 64),
		("szTalkLinkFile", c_byte * 64),
		("szTalkMotionFile", c_byte * 64),
		("TalkMotionInfo", smMOTIONINFO * 30),
		("TalkMotionCount", c_uint32),
		("NpcMotionRate", c_int32 * 30),
		("NpcMotionRateCnt", c_int32 * 100),
		("TalkMotionRate", c_int32 * 30),
		("TalkMotionRateCnt", (c_int32 * 100) * 2)
	]


class smMODELINFO_EX(LittleEndianStructure):
	# 95268 bytes (67084 + 28184)
	_fields_ = [
		("szModelFile", c_byte * 64),
		("szMotionFile", c_byte * 64),
		("szSubModelFile", c_byte * 64),
		("HighModel", _MODELGROUP),
		("DefaultModel", _MODELGROUP),
		("LowModel", _MODELGROUP),
		("MotionInfo", smMOTIONINFO_EX * 512),
		("MotionCount", c_uint32),
		("FileTypeKeyWord", c_uint32),
		("LinkFileKeyWord", c_uint32),
		("szLinkFile", c_byte * 64),
		("szTalkLinkFile", c_byte * 64),
		("szTalkMotionFile", c_byte * 64),
		("TalkMotionInfo", smMOTIONINFO_EX * 30),
		("TalkMotionCount", c_uint32),
		("NpcMotionRate", c_int32 * 30),
		("NpcMotionRateCnt", c_int32 * 100),
		("TalkMotionRate", c_int32 * 30),
		("TalkMotionRateCnt", (c_int32 * 100) * 2)
	]


class smSTAGE_VERTEX(LittleEndianStructure):
	# 28 bytes
	_fields_ = [
		("sum", c_uint32),
		("lpRendVertex_ptr", c_uint32),
		("x", c_int32), ("y", c_int32), ("z", c_int32),
		("sDef_Color", c_int16 * 4), # BGRA
	]


class smSTAGE_FACE(LittleEndianStructure):
	# 28 bytes
	_fields_ = [
		("sum", c_uint32),
		("CalcSum", c_int32),
		("Vertex", c_uint16 * 4), # a, b, c, Material
		("lpTexLink_ptr", c_uint32),
		("VectNormal", c_int16 * 4)
	]


class smLIGHT3D(LittleEndianStructure):
	# 26 bytes
	_fields_ = [
		("type", c_int32),
		("x", c_int32), ("y", c_int32), ("z", c_int32),
		("Range", c_int32),
		("r", c_int16), ("g", c_int16), ("b", c_int16),
	]


class smSTAGE3D(LittleEndianStructure):
	# 262260 bytes
	_fields_ = [
		("Head", c_uint32),
		("StageArea_ptr", (c_uint32 * 256) * 256),
		("AreaList_ptr", c_uint32),
		("AreaListCnt", c_int32),
		("MemMode", c_int32),
		("SumCount", c_uint32),
		("CalcSumCount", c_int32),
		("Vertex_ptr", c_uint32),
		("Face_ptr", c_uint32),
		("TexLink_ptr", c_uint32),
		("smLight_ptr", c_uint32),
		("smMaterialGroup_ptr", c_uint32),
		("StageObject_ptr", c_uint32),
		("smMaterial_ptr", c_uint32),
		("nVertex", c_int32),
		("nFace", c_int32),
		("nTexLink", c_int32),
		("nLight", c_int32),
		("nVertColor", c_int32),
		("Contrast", c_int32),
		("Bright", c_int32),
		("VectLight", POINT3D), # probably sun direction
		("lpwAreaBuff_ptr", c_uint32),
		("wAreaSize", c_int32),
		("StageMapRect", RECT),
	]


""" SERVER """


class STG_START_POINT(LittleEndianStructure):
	# 12 bytes
	_fields_ = [
		("state", c_int32),
		("x", c_int32), ("z", c_int32)
	]


class smCHAR_INFO(LittleEndianStructure):
	# 472 bytes
	_fields_ = [
		("szName", c_ubyte * 32),
		("szModelName", c_ubyte * 64),
		("szModelName2", c_ubyte * 60),
		("ModelNameCode2", c_uint32),
		("dwObjectSerial", c_uint32),
		("ClassClan", c_int32),
		("State", c_int32),
		("SizeLevel", c_int32),
		("dwCharSoundCode", c_uint32),
		("JOB_CODE", c_uint32),
		("Level", c_int32),
		("Strength", c_int32),
		("Spirit", c_int32),
		("Talent", c_int32),
		("Dexterity", c_int32),
		("Health", c_int32),
		("Accuracy", c_int32),
		("Attack_Rating", c_int32),
		("Attack_Damage", c_int32 * 2),
		("Attack_Speed", c_int32),
		("Shooting_Range", c_int32),
		("Critical_Hit", c_int32),
		("Defence", c_int32),
		("Chance_Block", c_int32),
		("Absorption", c_int32),
		("Move_Speed", c_int32),
		("Sight", c_int32),
		("Weight", c_int16 * 2),
		("Resistance", c_int16 * 8),
		("Attack_Resistance", c_int16 * 8),
		("Life", c_int16 * 2),
		("Mana", c_int16 * 2),
		("Stamina", c_int16 * 2),
		("Life_Regen", c_float),
		("Mana_Regen", c_float),
		("Stamina_Regen", c_float),
		("Exp", c_int32),
		("Next_Exp", c_int32),
		("Money", c_int32),
		("lpMonInfo_ptr", c_uint32),
		("Brood", c_uint32),
		("StatePoint", c_int32),
		("bUpdateInfo", c_ubyte * 4),
		("ArrowPosi", c_int16 * 2),
		("Potion_Space", c_int32),
		("LifeFunction", c_int32),
		("ManaFunction", c_int32),
		("StaminaFunction", c_int32),
		("DamageFunction", c_int16 * 2),
		("RefomCode", c_uint32),
		("ChangeJob", c_uint32),
		("JobBitMask", c_uint32),
		("wPlayerKilling", c_uint16 * 2),
		("wPlayClass", c_uint16 * 2),
		("Exp_High", c_int32),
		("dwEventTime_T", c_uint32),
		("sEventParam", c_int16 * 2),
		("sPresentItem", c_int16 * 2),
		("GravityScroolCheck", c_int16 * 2),
		("dwTemp", c_uint32 * 11),
		("dwLoginServerIP", c_uint32),
		("dwLoginServerSafeKey", c_uint32),
		("wVersion", c_uint16 * 2)
	]


class smTRNAS_PLAYERINFO(LittleEndianStructure): # [sic]
	# 504 bytes
	_fields_ = [
		("size", c_int32), # 504
		("code", c_int32), # 1212612720
		("smCharInfo", smCHAR_INFO),
		("dwObjectSerial", c_uint32),
		("x", c_int32), ("y", c_int32), ("z", c_int32),
		("ax", c_int32), ("ay", c_int32), ("az", c_int32),
		("state", c_int32)
	]
