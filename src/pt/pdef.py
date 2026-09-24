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
	motion_frame: int = 0
	item_codes: list[int] = field(default_factory=list)
	job_code_bit: int = 0
	skill_codes: list[int] = field(default_factory=list)
	map_position: int = 0
	key_code: str | None = None
	rate: int = 0


@dataclass
class PTModelMetadata:
	model_names: list[str] = field(default_factory=list)
	# high/default/low quality groups (*정밀모양 / *보통모양 / *저질모양);
	# model_names holds the selected subset, this records all three
	model_lod_groups: dict[str, list[str]] = field(default_factory=dict)
	animations: list[PTMotionMetadata] = field(default_factory=list)
	talk_animations: list[PTMotionMetadata] = field(default_factory=list)
	link_file: str | None = None
	talk_link_file: str | None = None
	talk_motion_file: str | None = None
	sub_model_file: str | None = None
	npc_motion_rate_table: list[int] = field(default_factory=list)
	talk_motion_rate_table: list[list[int]] = field(default_factory=list)


"""TEXTURES"""


@dataclass
class PTTextureMap:
	diffuse_name: str | None = None
	diffuse_path: str | None = None
	selfillum_name: str | None = None
	selfillum_path: str | None = None
	opacity_name: str | None = None
	opacity_path: str | None = None
	lightmap_name: str | None = None
	lightmap_path: str | None = None
	thirdstage_name: str | None = None
	thirdstage_path: str | None = None
	second_has_alpha: bool = False
	anim_frames: list[str] = field(default_factory=list)
	anim_alphas: list[str] = field(default_factory=list)


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
	normal: PTVector3 | None = None


@dataclass
class PTObjectTexture_Coord:
	face: PTObjectFace = field(default_factory=PTObjectFace)
	uv_sets: list[list[PTTextureVertex]] = field(default_factory=list)


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
	num_anim_textures: int = 0
	ambient: list[float] = field(default_factory=list)
	diffuse: list[float] = field(default_factory=list)
	specular: list[float] = field(default_factory=list)
	transparency: float = 0.0
	selfillum: bool = False
	two_sided: bool = False
	mesh_flags: int = 0
	script_flags: int = 0
	blend_type: int = 0
	collide: bool = False
	wind_mesh_bottom: int = 0
	texture_map: PTTextureMap = field(default_factory=PTTextureMap)
	anim_speed: int = 0
	anim_mask: int = 0
	mat_frame: int = 0


"""TRANSFORMS"""


@dataclass
class PTObjectTransform(PTMat4):
	position: PTVector3 = field(default_factory=PTVector3)
	rotation: PTQuaternion = field(default_factory=PTQuaternion)
	scale: PTVector3 = field(default_factory=lambda: PTVector3(1, 1, 1))


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
	frames: list[int] = field(default_factory=list)
	times: list[float] = field(default_factory=list)
	values: list[float] = field(default_factory=list)
	output: int | None = None


@dataclass
class PTAnimationTrack:
	position: PTAnimationSampler = field(default_factory=PTAnimationSampler)
	rotation: PTAnimationSampler = field(default_factory=PTAnimationSampler)
	scale: PTAnimationSampler = field(default_factory=PTAnimationSampler)


"""STAGES"""


@dataclass
class PTStageLight:
	name: str | None = None
	type_flags: int = 0
	dynamic: bool = False
	night: bool = False
	lens: bool = False
	pulse: bool = False
	obj: bool = False
	position: PTVector3 = field(default_factory=PTVector3)
	range: float = 0
	color: PTColorVertex = field(default_factory=PTColorVertex)


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
	lights: list[PTStageLight] = field(default_factory=list)
	contrast: int = 0
	bright: int = 0
	vect_light: PTVector3 = field(default_factory=PTVector3)


"""ACTORS"""


@dataclass
class PTActorAnimation:
	rotation: list[PTAnimationRotation] = field(default_factory=list)
	position: list[PTAnimationPosition] = field(default_factory=list)
	scale: list[PTAnimationScale] = field(default_factory=list)
	# [start, end) index ranges of the readable motion-file windows inside the key
	# arrays (key_frame_windows) plus the absolute start FRAME of each window
	# after the first; the engine restarts its TmPrevRot rotation accumulation
	# at each window (smRead3d.cpp:1642-1671, GetRotFrame smObj3d.cpp:1130),
	# so the exporter must do the same
	rotation_windows: list[tuple[int, int]] = field(default_factory=list)
	rotation_window_frames: list[int] = field(default_factory=list)
	_filled: bool = False


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
	vertex_normals: list[PTVector3] = field(default_factory=list)
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
	vertex_normals: list[PTVector3] = field(default_factory=list)
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
	talk_animations: list[PTMotionMetadata] = field(default_factory=list)
	link_file: str | None = None
	talk_link_file: str | None = None
	talk_motion_file: str | None = None
	sub_model_file: str | None = None
	npc_motion_rate_table: list[int] = field(default_factory=list)
	talk_motion_rate_table: list[list[int]] = field(default_factory=list)
	# all three authored quality groups, regardless of which objects survived
	lod_groups: dict[str, list[str]] | None = None


"""EFFECTS"""


@dataclass
class PTParticleKeyframes:
	min: float | int | tuple = 0
	max: float | int | tuple = 0
	fade: bool = False
	time: float = 0


@dataclass
class PTParticleEvent:
	event: str | None = None
	velocity_flag: int = 0
	frames: list[PTParticleKeyframes] = field(default_factory=list)


@dataclass
class PTParticleSequence:
	name: str | None = None
	texture: str | None = None
	particle_type: str = "TYPE_ONE"
	blend_mode: str = "BLEND_ALPHA"
	emit_rate: PTParticleKeyframes = field(default_factory=PTParticleKeyframes)
	num_particles: PTParticleKeyframes = field(default_factory=PTParticleKeyframes)
	loops: PTParticleKeyframes = field(default_factory=PTParticleKeyframes)
	lifetime: PTParticleKeyframes = field(default_factory=PTParticleKeyframes)
	delay: float = 0
	spawn_dir: PTParticleKeyframes = field(default_factory=PTParticleKeyframes)
	emit_radius: PTParticleKeyframes = field(default_factory=PTParticleKeyframes)
	gravity: PTParticleKeyframes = field(default_factory=PTParticleKeyframes)
	events: list[PTParticleEvent] = field(default_factory=list)


@dataclass
class PTParticleSystem:
	filename: str | None = None
	name: str | None = None
	version: float = 1
	position: PTParticleKeyframes = field(default_factory=PTParticleKeyframes)
	sequences: list[PTParticleSequence] = field(default_factory=list)


@dataclass
class PTEffectController:
	type: str | None = None
	position: PTVector3 | tuple | None = None
	mesh_name: str | None = None
	bone_name: str | None = None
	max_frame: float = 0
	loop: int = 0
	start_delay_time: float = 0
	end_time: float | tuple | None = None
	color: tuple | None = None
	size: tuple | None = None
	texture_name: str | None = None
	ani_texture_count: int = 0
	ani_texture_delay: float = 0
	blend_type: str | None = None
	spawn_bounding_box: tuple | None = None
	spawn_bounding_sphere: tuple | None = None
	spawn_bounding_doughnut: tuple | None = None
	particle_num: float = 0
	emit_rate: float = 0
	axial_pos: tuple | None = None
	velocity: tuple | None = None
	particle_type: str | None = None
	velocity_type: str | None = None
	events: list[PTParticleEvent] = field(default_factory=list)


@dataclass
class PTEffectScript:
	filename: str | None = None
	parent_position: PTVector3 | None = None
	controllers: list[PTEffectController] = field(default_factory=list)


@dataclass
class PTAnimFrame:
	image_num: int = 0
	delay: int = 0
	alpha: int = 0
	size_width: int | None = None
	size_height: int | None = None
	angle: float | None = None
	color: tuple | None = None


@dataclass
class PTAnimSequenceData:
	filename: str | None = None
	data_file: str | None = None
	blend_type: int = 0
	start_blend_value: int = 0
	frames: list[PTAnimFrame] = field(default_factory=list)


@dataclass
class PTAnimImageData:
	filename: str | None = None
	texture_name: str | None = None
	texture_count: int = 0


@dataclass
class PTAnimData:
	filename: str | None = None
	image_data: list[PTAnimImageData] = field(default_factory=list)
	sequences: list[PTAnimSequenceData] = field(default_factory=list)


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
	scale: PTVector3 = field(default_factory=lambda: PTVector3(1, 1, 1))


@dataclass
class PTServerSpawnMonster:
	spawn_interval: int = 0
	spawn_interval_time: int = 0
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
	size: str | None = None
	size_level: int = -1
	sound: str | None = None
	rank: int = 0
	model_scale: float = 1
	arrow_position: list[int] = field(default_factory=list)

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
class PTServerFallItem:
	kind: str = "item"
	percent: int = 0
	codes: list[str] = field(default_factory=list)
	gold_min: int = 0
	gold_max: int = 0


@dataclass
class PTServerMonster:
	name: str | None = None
	name_en: str | None = None
	active: bool = False
	model: str | None = None
	model_alt: str | None = None
	event_model: bool = False
	model_scale: float = 1
	level: int = 0
	is_boss: bool = False
	rank: int = 0
	size: str | None = None
	size_level: int = -1
	sound: str | None = None
	move_speed: float = 0
	move_type: int | None = None
	move_range: float = 0
	attack_damage: list[int] = field(default_factory=list)
	attack_speed: float = 0
	shooting_range: int = 0
	attack_rating: int = 0
	defence: int = 0
	absorption: int = 0
	chance_block: int = 0
	life: int = 0
	resistances: dict[str, int] = field(default_factory=dict)
	sight: int = 0
	arrow_position: list[int] = field(default_factory=list)
	skill_damage: list[int] = field(default_factory=list)
	skill_distance: int = 0
	skill_range: int = 0
	skill_rating: int = 0
	skill_curse: int = 0
	active_hour: int = 0
	generate_group: list[int] = field(default_factory=list)
	iq: int = 0
	class_code: int = 0
	damage_stun_percent: int | None = None
	nature: str | None = None
	event_code: int = 0
	event_info: int = 0
	event_item: str | None = None
	special_attack_percent: int = 0
	brood: str | None = None
	undead: bool = False
	exp: int = 0
	potion_count: int | None = None
	potion_percent: int | None = None
	all_see_item: bool = False
	fall_item_max: int | None = None
	fall_items: list[PTServerFallItem] = field(default_factory=list)
	fall_items_plus: list[PTServerFallItem] = field(default_factory=list)
	sell_weapons: list[str] = field(default_factory=list)
	sell_defences: list[str] = field(default_factory=list)
	sell_misc: list[str] = field(default_factory=list)
	dialogue: list[str] = field(default_factory=list)
	next_file: str | None = None


"""SERVER ITEMS"""


@dataclass
class PTServerItemRange:
	min: float = 0
	max: float = 0


@dataclass
class PTServerItem:
	name: str | None = None
	name_en: str | None = None
	code: str | None = None
	durability: list[int] = field(default_factory=list)
	weight: int = 0
	price: int = 0
	resistances: dict[str, list[int]] = field(default_factory=dict)
	damage: list[int] = field(default_factory=list)
	shooting_range: int = 0
	attack_speed: int = 0
	attack_rating: list[int] = field(default_factory=list)
	critical_hit: int = 0
	absorb: list[float] = field(default_factory=list)
	defence: list[int] = field(default_factory=list)
	block_rating: list[float] = field(default_factory=list)
	speed: list[float] = field(default_factory=list)
	potion_space: int = 0
	magic_mastery: float | None = None
	mana_regen: list[float] = field(default_factory=list)
	life_regen: list[float] = field(default_factory=list)
	stamina_regen: list[float] = field(default_factory=list)
	increase_mana: list[int] = field(default_factory=list)
	increase_life: list[int] = field(default_factory=list)
	increase_stamina: list[int] = field(default_factory=list)
	level: int = 0
	strength: int = 0
	spirit: int = 0
	talent: int = 0
	dexterity: int = 0
	health: int = 0
	stamina: list[int] = field(default_factory=list)
	mana: list[int] = field(default_factory=list)
	life: list[int] = field(default_factory=list)
	unique: bool = False
	effect_color: list[int] = field(default_factory=list)
	disp_effect: int = 0
	job_code_mask: str | None = None
	job_code_random: list[str] = field(default_factory=list)
	special_absorb: list[float] = field(default_factory=list)
	special_defence: list[int] = field(default_factory=list)
	special_speed: list[float] = field(default_factory=list)
	special_magic_mastery: list[float] = field(default_factory=list)
	special_mana_regen: list[float] = field(default_factory=list)
	per_life_regen: float | None = None
	per_stamina_regen: float | None = None
	job_add_block_rating: float | None = None
	job_add_attack_speed: int | None = None
	job_add_critical_hit: int | None = None
	job_add_shooting_range: int | None = None
	job_lev_mana: int | None = None
	job_lev_life: int | None = None
	lev_attack_rating: list[int] = field(default_factory=list)
	job_lev_damage: list[int] = field(default_factory=list)
	gen_day: int | None = None
	next_file: str | None = None
