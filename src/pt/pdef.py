from dataclasses import dataclass, field
from pt.const import VERSION


"""GENERICS"""


@dataclass
class PTVector3:
	x: float = 0
	y: float = 0
	z: float = 0


@dataclass
class PTVector3Int:
	x: int = 0
	y: int = 0
	z: int = 0


@dataclass
class PTQuaternion:
	x: float = 0
	y: float = 0
	z: float = 0
	w: float = 1


@dataclass
class PTMat4:
	_11: float = 1; _12: float = 0; _13: float = 0; _14: float = 0
	_21: float = 0; _22: float = 1; _23: float = 0; _24: float = 0
	_31: float = 0; _32: float = 0; _33: float = 1; _34: float = 0
	_41: float = 0; _42: float = 0; _43: float = 0; _44: float = 1


"""METADATA"""


@dataclass
class PTMotionMetadata:
	name: str | None = None
	start_frame: int = 0
	end_frame: int = 0
	repeat: bool = False
	event_frames: list[float] = field(default_factory=list)


@dataclass
class PTModelMetadata:
	model_names: list[str] = field(default_factory=list)
	animations: list[PTMotionMetadata] = field(default_factory=list)


"""TEXTURES"""


@dataclass
class PTTextureMap:
	diffuse_name: str | None = None
	diffuse_path: str | None = None
	selfillum_name: str | None = None
	selfillum_path: str | None = None
	opacity_name: str | None = None
	opacity_path: str | None = None


@dataclass
class PTTextureVertex:
	u: float = 0
	v: float = 0


"""OBJECTS"""


@dataclass
class PTColorVertex:
	r: float = 0
	g: float = 0
	b: float = 0
	a: float = 0


@dataclass
class PTObjectFace:
	vertices: list[int] = field(default_factory=list)
	material_id: int | None = None


@dataclass
class PTObjectTexture_Coord:
	face: PTObjectFace = field(default_factory=PTObjectFace)
	vertices: list[PTTextureVertex] = field(default_factory=list)


"""MODELS"""


@dataclass
class PTModelScene:
	ticks_per_frame: int = 160
	frame_speed: int = 30
	last_frame: int = 100


@dataclass
class PTModelMaterial:
	name: str | None = None
	num_textures: int = 0
	ambient: list[float] = field(default_factory=list)
	diffuse: list[float] = field(default_factory=list)
	specular: list[float] = field(default_factory=list)
	transparent: bool = False
	selfillum: bool = False
	two_sided: bool = False
	mesh_flags: int = 0
	collide: bool = False
	texture_map: PTTextureMap = field(default_factory=PTTextureMap)


"""TRANSFORMS"""


@dataclass
class PTObjectTransform(PTMat4):
	position: PTVector3 = field(default_factory=PTVector3)
	rotation: PTQuaternion = field(default_factory=PTQuaternion)
	scale: PTVector3 = field(default_factory=PTVector3)


"""ANIMATIONS"""


@dataclass
class PTAnimationPosition(PTVector3):
	frame: int = 0


@dataclass
class PTAnimationRotation(PTQuaternion):
	frame: int = 0


@dataclass
class PTAnimationScale(PTVector3):
	frame: int = 0


@dataclass
class PTAnimationSampler:
	input: int | None = None
	output: int | None = None


@dataclass
class PTAnimationTrack:
	position: PTAnimationSampler = field(default_factory=PTAnimationSampler)
	rotation: PTAnimationSampler = field(default_factory=PTAnimationSampler)
	scale: PTAnimationSampler = field(default_factory=PTAnimationSampler)


"""STAGES"""


@dataclass
class PTStageObject:
	name: str | None = None
	num_vertices: int = 0
	num_faces: int = 0
	num_texture_links: int = 0
	num_tfm_rotations: int = 0
	num_tfm_positions: int = 0
	num_tfm_scales: int = 0
	vertices: list[PTVector3] = field(default_factory=list)
	vertex_colors: list[PTColorVertex] = field(default_factory=list)
	faces: list[PTObjectFace] = field(default_factory=list)
	texture_coords: list[PTObjectTexture_Coord] = field(default_factory=list)
	transform: PTObjectTransform = field(default_factory=PTObjectTransform)


@dataclass
class PTStageModel:
	filename: str | None = None
	version: str = VERSION
	scene: PTModelScene = field(default_factory=PTModelScene)
	materials: list[PTModelMaterial] = field(default_factory=list)
	objects: list[PTStageObject] = field(default_factory=list)


"""ACTORS"""


@dataclass
class PTActorAnimation:
	rotation: list[PTAnimationRotation] = field(default_factory=list)
	position: list[PTAnimationPosition] = field(default_factory=list)
	scale: list[PTAnimationScale] = field(default_factory=list)


@dataclass
class PTActorObject:
	parent: str | None = None
	name: str | None = None
	num_vertices: int = 0
	num_faces: int = 0
	num_texture_links: int = 0
	num_tfm_positions: int = 0
	num_tfm_rotations: int = 0
	num_tfm_scales: int = 0
	vertices: list[PTVector3] = field(default_factory=list)
	faces: list[PTObjectFace] = field(default_factory=list)
	texture_coords: list[PTObjectTexture_Coord] = field(default_factory=list)
	transform: PTObjectTransform = field(default_factory=PTObjectTransform)
	transform_rotate: PTMat4 = field(default_factory=PTMat4)
	physique: list[str] = field(default_factory=list)
	animation: PTActorAnimation = field(default_factory=PTActorAnimation)


@dataclass
class PTActorBone:
	parent: str | None = None
	name: str | None = None
	num_vertices: int = 0
	num_faces: int = 0
	num_tfm_positions: int = 0
	num_tfm_rotations: int = 0
	num_tfm_scales: int = 0
	vertices: list[PTVector3] = field(default_factory=list)
	faces: list[PTObjectFace] = field(default_factory=list)
	texture_coords: list[PTObjectTexture_Coord] = field(default_factory=list)
	transform: PTObjectTransform = field(default_factory=PTObjectTransform)
	animation: PTActorAnimation = field(default_factory=PTActorAnimation)
	_id: int | None = None
	_parent = None
	_children: list[int] = field(default_factory=list)


@dataclass
class PTActorModel:
	filename: str | None = None
	version: str = VERSION
	scene: PTModelScene = field(default_factory=PTModelScene)
	materials: list[PTModelMaterial] = field(default_factory=list)
	objects: list[PTActorObject] = field(default_factory=list)
	bones: list[PTActorBone] = field(default_factory=list)
	animations: list[PTMotionMetadata] = field(default_factory=list)


"""SERVER STAGES"""


@dataclass
class PTServerStageMonster:
	name: str | None = None
	name_en: str | None = None
	spawn_rate: int = 0


@dataclass
class PTServerStageBoss:
	name: str | None = None
	name_en: str | None = None
	minion: str | None = None
	minion_en: str | None = None
	num_minions: int = 0
	hours: list[int] = field(default_factory=list)


@dataclass
class PTServerSpawnCharacter:
	active: bool = False
	name: str | None = None
	char: str | None = None
	npc: str | None = None
	position: PTVector3 = field(default_factory=PTVector3)
	rotation: PTQuaternion = field(default_factory=PTQuaternion)
	scale: PTVector3 = field(default_factory=PTVector3)


@dataclass
class PTServerSpawnMonster:
	spawn_interval_min: int = 0
	spawn_interval_max: int = 0
	max_monsters: int = 0
	max_monsters_per_point: int = 0
	monsters: list[PTServerStageMonster] = field(default_factory=list)
	bosses: list[PTServerStageBoss] = field(default_factory=list)


@dataclass
class PTServerSpawnPoint:
	active: bool = False
	position: PTVector3 = field(default_factory=PTVector3)


@dataclass
class PTServerStage(PTServerSpawnMonster):
	characters: list[PTServerSpawnCharacter] = field(default_factory=list)
	spawn_points: list[PTServerSpawnPoint] = field(default_factory=list)


@dataclass
class PTServerStages:
	version: str = VERSION
	stages: dict[str, PTServerStage] = field(default_factory=dict)


"""SERVER CHARACTERS"""


@dataclass
class PTServerCharacter:
	active: bool = False
	model: str | None = None
	level: int = 0
	name: str | None = None
	name_en: str | None = None
	dialogue: list[str] = field(default_factory=list)
	sell_weapons: list[str] = field(default_factory=list)
	sell_defences: list[str] = field(default_factory=list)
	sell_misc: list[str] = field(default_factory=list)
	skill_master: bool = False
	job_master: int = 0
	event: int = 0
	warehouse_master: bool = False
	item_mixing: bool = False
	item_smelting: bool = False
	item_crafting: bool = False
	item_mixing_200: bool = False
	item_aging: bool = False
	item_reset: bool = False
	clan_master: bool = False
	teleport_master: int = 0
	media_title: str | None = None
	media_path: str | None = None
	find_word: int = 0
	exit_number: int = 0
	quest_code: int = 0
	quest_param: int = 0
	zhoon_path: str | None = None

	CollectMoney: bool = False
	WowEvent: bool = False
	EventGift: bool = False
	GiftExpress: bool = False
	WingQuestNpc1: int = 0
	WingQuestNpc2: int = 0
	StarPointNpc: int = 0
	GiveMoneyNpc: bool = False
	BlessCastleNPC: int = 0
	PollingNpc: int = 0


"""SERVER MONSTERS"""


@dataclass
class PTServerMonster:
	wPlayClass: bool = False
	Size: bool = False
	szName: bool = False
	Level: bool = False
	wPlayClass2: bool = False
	ClassCode: bool = False
	GenerateGroup: bool = False
	IQ: bool = False
	Nature: bool = False
	Real_Sight: bool = False
	Life: bool = False
	Life2: bool = False
	Attack_Damage: bool = False
	SkillDamage: bool = False
	SkillRating: bool = False
	SkillDistance: bool = False
	SkillRange: bool = False
	SkillCurse: bool = False
	Absorption: bool = False
	Chance_Block: bool = False
	Defence: bool = False
	Attack_Speed: bool = False
	Attack_Rating: bool = False
	SpAttackPercetage: bool = False
	Shooting_Range: bool = False
	Resistance_sITEMINFO_BIONIC: bool = False
	Resistance_sITEMINFO_LIGHTING: bool = False
	Resistance_sITEMINFO_ICE: bool = False
	Resistance_sITEMINFO_FIRE: bool = False
	Resistance_sITEMINFO_POISON: bool = False
	Resistance_sITEMINFO_WATER: bool = False
	Resistance_sITEMINFO_WIND: bool = False
	Resistance_sITEMINFO_EARTH: bool = False
	Type: bool = False
	IsUndead: bool = False
	MoveRange: bool = False
	MoveType: bool = False
	SoundEffect: bool = False
	SoundEffect2: bool = False
	Exp: bool = False
	FallItemMax: bool = False
	FallItems: bool = False
	FallItems_Plus: bool = False
	AllSeeItem: bool = False
	_DropGold: bool = False
	_DropEmpty: bool = False
	State: bool = False
	szModelName: bool = False
	Name: bool = False
	ActiveHour: bool = False
	ArrowPosi: bool = False
	SizeLevel: bool = False
	PotionCount: bool = False
	PotionPercent: bool = False
	EventCode: bool = False
	EventInfo: bool = False
	dwEvnetItem: bool = False
	szModelName2: bool = False
	ExtraGold: bool = False
	DamageStunPers: bool = False
	DamageStunPers2: bool = False
	Move_Speed: bool = False
	lpDialogMessage: bool = False
	szNextFile: bool = False

	Small: bool = False
	Medium: bool = False
	Big: bool = False
	Bigger: bool = False
	No: bool = False
	good: bool = False
	evil: bool = False
	No: bool = False
	Day: bool = False
	Night: bool = False
	State_True: bool = False
	State_False: bool = False
	Normal: bool = False
	Daemon: bool = False
	Undead: bool = False
	Mutant: bool = False
	Mechanic: bool = False
	Iron: bool = False
	Normal: bool = False
	Undead: bool = False
	Undead2: bool = False


"""SERVER ITEMS"""


@dataclass
class PTServerItem:
	NameEnglish: bool = False
	ItemName: bool = False
	Code: bool = False
	Integrity: bool = False
	Weight: bool = False
	Price: bool = False
	sResistance_sITEMINFO_BIONIC: bool = False
	sResistance_sITEMINFO_FIRE: bool = False
	sResistance_sITEMINFO_ICE: bool = False
	sResistance_sITEMINFO_LIGHTING: bool = False
	sResistance_sITEMINFO_POISON: bool = False
	sDamage: bool = False
	sAttack_Rating: bool = False
	sDefence: bool = False
	fAbsorb: bool = False
	fBlock_Rating: bool = False
	Attack_Speed: bool = False
	Critical_Hit: bool = False
	Shooting_Range: bool = False
	Potion_Space: bool = False
	fLife_Regen: bool = False
	fLife_Regen2: bool = False
	fMana_Regen: bool = False
	fMana_Regen2: bool = False
	fStamina_Regen: bool = False
	fStamina_Regen2: bool = False
	Increase_Life: bool = False
	Increase_Life2: bool = False
	Increase_Mana: bool = False
	Increase_Mana2: bool = False
	Increase_Stamina: bool = False
	Increase_Stamina2: bool = False
	Level: bool = False
	Strength: bool = False
	Spirit: bool = False
	Talent: bool = False
	Agility_Dexterity: bool = False
	Health: bool = False
	DispEffect: bool = False
	sResistance_sITEMINFO_EARTH: bool = False
	sResistance_sITEMINFO_WATER: bool = False
	sResistance_sITEMINFO_WIND: bool = False
	TransfereSpeed: bool = False
	UniqueItem: bool = False
	dwJobBitCode_Random: bool = False
	JobCodeMask: bool = False
	fSpecial_Absorb: bool = False
	sSpecial_Defence: bool = False
	JobItem_Per_Life_Regen: bool = False
	JobItem_Per_Life_Regen2: bool = False
	fSpecial_Mana_Regen: bool = False
	fSpecial_Mana_Regen2: bool = False
	JobItem_Per_Stamina_Regen: bool = False
	JobItem_Per_Stamina_Regen2: bool = False
	fSpecial_fSpeed: bool = False
	JobItem_Add_Attack_Speed: bool = False
	JobItem_Add_fBlock_Rating: bool = False
	Lev_Attack_Rating: bool = False
	JobItem_Lev_Damage: bool = False
	JobItem_Add_Critical_Hit: bool = False
	fSpecial_Magic_Mastery: bool = False
	JobItem_Add_Shooting_Range: bool = False
	JobItem_Lev_Mana: bool = False
	JobItem_Lev_Mana2: bool = False
	JobItem_Lev_Life: bool = False
	JobItem_Lev_Life2: bool = False
	fMagic_Mastery: bool = False
	Stamina: bool = False
	Stamina2: bool = False
	Mana: bool = False
	Mana2: bool = False
	Life: bool = False
	Life2: bool = False
	EffectColor: bool = False
	sGenDay: bool = False
	szNextFile: bool = False
