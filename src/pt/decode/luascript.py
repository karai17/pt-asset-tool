import ast
import operator
import os

from pt.pdef import *
from pt.const import EFFECT_BLEND_TYPES

# NewEffect scripts run through a registered-subset Lua interpreter
# (PiScript::RegisterCommand PiScript.cpp:36-71, HoEffectMain::LoadScript
# HoEffectMain.cpp:29-41). Each Begin("type") switches the work type
# (HoEffectMain::LuaBegin :67-110) that scopes the following commands to a
# controller; End() commits the controller to the group. InitMeshName and
# InitTextureName prefix "Effect\\NewEffect\\" (PiScriptLuaCommand.cpp:72-111).


def _blend_type(name: str) -> str:
	for blend, _ in EFFECT_BLEND_TYPES:
		if blend.lower() == name.lower():
			return blend
	return name


def _strip_quotes(value: str) -> str:
	return value.strip('"')


_LUA_BINOPS = {
	ast.Add: operator.add,
	ast.Sub: operator.sub,
	ast.Mult: operator.mul,
	ast.Div: operator.truediv,
}


def _number(value: str) -> float:
	"""Evaluates a Lua numeric literal or a constant arithmetic expression
	(e.g. '70-10' in SkillArchMageMeteo2.lua)."""
	try:
		return float(value)
	except ValueError:
		pass

	def _eval(node):
		if isinstance(node, ast.Expression):
			return _eval(node.body)
		if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
			return node.value
		if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
			operand = _eval(node.operand)
			return operand if isinstance(node.op, ast.UAdd) else -operand
		if isinstance(node, ast.BinOp) and type(node.op) in _LUA_BINOPS:
			return _LUA_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
		raise ValueError(f"unsupported expression: {value}")

	return float(_eval(ast.parse(value.replace("--", "+"), mode="eval")))


def _floats(args: list[str]) -> list[float]:
	return [_number(arg) for arg in args]


def _command(command: str, args: list[str], script: PTEffectScript, controller: PTEffectController) -> None:
	match command:
		case "Begin":
			controller.type = _strip_quotes(args[0])
		case "End":
			script.controllers.append(controller)
		case "InitPos":
			controller.position = PTVector3(*_floats(args))
		case "InitMeshName":
			# PiScriptLuaCommand.cpp:72-96 prefixes Effect\NewEffect\ and
			# accepts an optional second bone-name argument
			controller.mesh_name = _strip_quotes(args[0])
			if len(args) > 1:
				controller.bone_name = _strip_quotes(args[1])
		case "InitMaxFrame":
			controller.max_frame = _number(args[0])
		case "InitLoop":
			controller.loop = int(_number(args[0]))
		case "InitStartDelayTime":
			controller.start_delay_time = _number(args[0])
		case "InitEndTime":
			controller.end_time = _number(args[0]) if len(args) == 1 else tuple(_floats(args))
		case "InitColor":
			controller.color = tuple(_floats(args))
		case "InitSize":
			controller.size = tuple(_floats(args))
		case "InitTextureName":
			controller.texture_name = _strip_quotes(args[0])
		case "InitAniTextureName":
			# PiScriptLuaCommand.cpp:113-124: name, count, delay; the name is
			# also fed to InitTextureName
			controller.texture_name = _strip_quotes(args[0])
			controller.ani_texture_count = int(_number(args[1]))
			controller.ani_texture_delay = _number(args[2])
		case "InitBlendType":
			controller.blend_type = _blend_type(_strip_quotes(args[0]))
		case "InitSpawnBoundingBox":
			controller.spawn_bounding_box = tuple(_floats(args))
		case "InitSpawnBoundingSphere":
			controller.spawn_bounding_sphere = tuple(_floats(args))
		case "InitSpawnBoundingDoughnut":
			controller.spawn_bounding_doughnut = tuple(_floats(args))
		case "InitParticleNum":
			controller.particle_num = _number(args[0])
		case "InitEmitRate":
			controller.emit_rate = _number(args[0])
		case "InitAxialPos":
			controller.axial_pos = tuple(_floats(args))
		case "InitVelocity":
			controller.velocity = tuple(_floats(args))
		case "InitParticleType":
			controller.particle_type = _strip_quotes(args[0])
		case "InitVelocityType":
			controller.velocity_type = _strip_quotes(args[0])
		case "EventColor" | "EventFadeColor" | "EventSize" | "EventFadeSize":
			event = PTParticleEvent(event=command)
			frames = PTParticleKeyframes(time=_number(args[0]))
			frames.min = tuple(_floats(args[1:]))
			frames.max = frames.min
			event.frames.append(frames)
			controller.events.append(event)
		case _:
			print(f"Unknown command: {command}")


def decode(path: str) -> PTEffectScript:
	"""Decode a NewEffect .lua effect script."""
	script = PTEffectScript()
	script.filename = os.path.basename(path)
	controller = PTEffectController()

	with open(path, "r", encoding="cp949", errors="replace") as f:
		text = f.read()

	for line in text.splitlines():
		code = line.split("--")[0].strip()
		if not code or not code.endswith(");"):
			continue

		name = code.split("(", 1)[0].strip()
		args = [arg.strip() for arg in code[code.index("(") + 1:code.rindex(")")].split(",")] \
			if "(" in code else []
		_command(name, args, script, controller)

	return script
