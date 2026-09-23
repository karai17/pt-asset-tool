import os
import re

from pt.pdef import *
from pt.utils import atof
from pt.const import PARTICLE_BLEND_MODES, PARTICLE_TYPES

# HoNewParticleResMgr::LoadScript (HoNewParticleMgr.cpp:53-88) reads the whole
# script with a 6000-byte buffer; HoNewParticleEmitterTokenizer::Tokenize
# (HoNewParticle.cpp:1178-1295) splits it on whitespace and the punctuation
# ( ) , " { } / , strips //-comments, then HoNewParticleEmitter::Compile
# (:1801-1840) / AddScript (:1842-1878) walk the tokens: a particlesystem
# header, a position property, and eventsequence blocks.


def _tokenize(text: str) -> list[tuple[str, str]]:
	"""HoNewParticleEmitterTokenizer::Tokenize (HoNewParticle.cpp:1178-1295);
	quotes become their own token, ( ) , { } / are single-char tokens,
	//-comments run to end of line."""
	tokens: list[tuple[str, str]] = []
	textmode = quote = comment = False
	token = ""

	for index, char in enumerate(text):
		if comment:
			if char == "\n":
				comment = False
				token = ""
		elif quote:
			token += char
			if char == '"':
				tokens.append(("Quote", token))
				token = ""
				quote = False
		elif char == "/" and index + 1 < len(text) and text[index + 1] == "/":
			if textmode:
				tokens.append(("Text", token))
				token = ""
				textmode = False
			comment = True
		elif char.isspace():
			if textmode:
				tokens.append(("Text", token))
				token = ""
				textmode = False
		elif not textmode and char == '"':
			token = char
			quote = True
		elif char in "(),{}/":
			if textmode:
				tokens.append(("Text", token))
				token = ""
				textmode = False
			if char == '"':
				token = char
				quote = True
			else:
				tokens.append(("Punct", char))
		else:
			token += char
			textmode = True

	if not comment and token:
		tokens.append(("Quote" if token.startswith('"') else "Text", token))

	return tokens


def _process_number(tokens: list[tuple[str, str]], i: int) -> tuple[PTParticleKeyframes, int]:
	"""HoNewParticleEmitterTokenizer::ProcessNumber (HoNewParticle.cpp:712-772):
	either Random(min,max) into a min/max pair or a single number into both."""
	number = PTParticleKeyframes()

	kind, value = tokens[i]
	if kind == "Text" and value.upper() == "RANDOM":
		i += 2  # skip ( and land on min
		number.min = atof(tokens[i][1])
		i += 2  # skip , and land on max
		number.max = atof(tokens[i][1])
		i += 2  # skip Random's closing paren
	elif kind == "Text" and re.match(r"[-+]?\d", value):
		number.min = number.max = atof(value)
		i += 1

	# a non-number is left unconsumed, as the engine's failed ProcessNumber
	# return leaves the iterator in place (e.g. '=20' run-on tokens)
	return number, i


def _process_vector(tokens: list[tuple[str, str]], i: int) -> tuple[PTParticleKeyframes, int]:
	"""HoNewParticleEmitterTokenizer::ProcessVector (HoNewParticle.cpp:774-855):
	XYZ(x,y,z) where each component is a number or Random(...)."""
	if tokens[i][1].upper() != "XYZ" or tokens[i + 1] != ("Punct", "("):
		return PTParticleKeyframes(), i
	i += 2
	minv = [0.0, 0.0, 0.0]
	maxv = [0.0, 0.0, 0.0]

	for axis in range(3):
		number, i = _process_number(tokens, i)
		minv[axis] = number.min
		maxv[axis] = number.max
		i += 1  # skip , or )

	return PTParticleKeyframes(min=tuple(minv), max=tuple(maxv)), i


def _process_color(tokens: list[tuple[str, str]], i: int) -> tuple[PTParticleKeyframes, int]:
	"""HoNewParticleEmitterTokenizer::ProcessColor (HoNewParticle.cpp:857-943):
	RGBA(r,g,b,a) with the same per-component number grammar."""
	if tokens[i][1].upper() != "RGBA" or tokens[i + 1] != ("Punct", "("):
		return PTParticleKeyframes(), i
	i += 2
	minv = [0.0, 0.0, 0.0, 0.0]
	maxv = [0.0, 0.0, 0.0, 0.0]

	for channel in range(4):
		number, i = _process_number(tokens, i)
		minv[channel] = number.min
		maxv[channel] = number.max
		i += 1  # skip , or )

	return PTParticleKeyframes(min=tuple(minv), max=tuple(maxv)), i


def _process_time(tokens: list[tuple[str, str]], i: int, event: PTParticleKeyframes, lifetime: float) -> int:
	"""HoNewParticleEmitterTokenizer::ProcessTime (HoNewParticle.cpp:1001-1052):
	[fade so] at <number>, initial, or final (final = lifetime max)."""
	event.fade = tokens[i][1].upper() == "FADE"

	if event.fade:
		i += 2  # skip fade and so

	kind, value = tokens[i]
	if value.upper() == "AT":
		# the engine ignores ProcessNumber's failure here; a malformed time
		# (e.g. 'fade so at color = ...') leaves ActualTime at 0 and falls
		# through to the property token
		i += 1
		if tokens[i][0] == "Text" and re.match(r"[-+]?\d", tokens[i][1]):
			event, i = _process_number(tokens, i)
	elif value.upper() == "INITIAL":
		event.min = event.max = 0
		i += 1
	elif value.upper() == "FINAL":
		event.min = event.max = lifetime
		i += 1

	return i


def _decode_event(name: str, tokens: list[tuple[str, str]], i: int, lifetime: float) -> tuple[PTParticleEvent | None, int]:
	"""One event line: a time specifier, the event property, = and a value
	(HoNewParticleEmitter::ProcessEventSequenceBlock HoNewParticle.cpp:1442-1566).
	Event types come from EventFactory (:1573-1604); their value grammar is the
	ProcessPropEqualsValue overload matching the event's field type. A malformed
	line is dropped without consuming past its '=', as the engine does when
	ProcessTokenStream or ProcessPropEqualsValue fails on the iterator."""
	event = PTParticleEvent(event=name.lower())
	frames = PTParticleKeyframes()
	i = _process_time(tokens, i, frames, lifetime)

	kind, value = tokens[i]
	if kind != "Text" or value.upper() == "=":
		print(f"Malformed event at token {i}: expected property")
		return None, i

	prop = value.upper()
	if i + 1 >= len(tokens) or not tokens[i + 1][1].startswith("="):
		print(f"Malformed event at token {i}: expected '=' after {value}")
		return None, i
	# a '=NNN' run-on token counts as the equals sign and the digits are
	# dropped, exactly as the engine's Equals tokenization loses them
	i += 2  # skip property and =

	if prop in ("SIZE", "SIZEEXT", "EVENTTIMER", "ALPHA", "REDCOLOR", "GREENCOLOR", "BLUECOLOR",
		"VELOCITYX", "VELOCITYY", "VELOCITYZ",
		"PARTANGLEX", "PARTANGLEY", "PARTANGLEZ",
		"LOCALANGLEX", "LOCALANGLEY", "LOCALANGLEZ"):
		frames, i = _process_number(tokens, i)
	elif prop in ("VELOCITY", "PARTANGLE", "LOCALANGLE"):
		if tokens[i][1].upper() in ("OUTLENGTH", "INLENGTH"):
			event.velocity_flag = tokens[i][1].upper() == "OUTLENGTH" and 1 or 2
			i += 1
		frames, i = _process_vector(tokens, i)
	elif prop == "COLOR":
		frames, i = _process_color(tokens, i)
	else:
		print(f"Malformed event at token {i}: unknown property {value}")
		return None, i

	event.frames.append(frames)

	return event, i


def _decode_sequence(tokens: list[tuple[str, str]], i: int) -> tuple[PTParticleSequence, int]:
	"""HoNewParticleEmitter::ProcessEventSequenceBlock (HoNewParticle.cpp:1421-1711)."""
	sequence = PTParticleSequence()
	sequence.name = tokens[i][1].strip('"')
	i += 2  # skip name and {

	started_events = False
	lifetime = 0.0

	while tokens[i] != ("Punct", "}"):
		kind, value = tokens[i]
		prop = value.upper() if kind == "Text" else value

		if prop in ("EMITRATE", "LIFETIME", "NUMPARTICLES", "LOOPS", "DELAY"):
			i += 2  # skip property and =
			number, i = _process_number(tokens, i)

			if prop == "EMITRATE":
				sequence.emit_rate = number
			elif prop == "LIFETIME":
				sequence.lifetime = number
				lifetime = number.max
			elif prop == "NUMPARTICLES":
				sequence.num_particles = number
			elif prop == "LOOPS":
				sequence.loops = number
			elif prop == "DELAY":
				sequence.delay = number.max

			if started_events:
				print("Sequence properties specified after events")
		elif prop in ("SPAWNDIR", "EMITRADIUS", "GRAVITY"):
			i += 2  # skip property and =
			vector, i = _process_vector(tokens, i)

			if prop == "SPAWNDIR":
				sequence.spawn_dir = vector
			elif prop == "EMITRADIUS":
				sequence.emit_radius = vector
			elif prop == "GRAVITY":
				sequence.gravity = vector
		elif prop == "PARTICLETYPE":
			i += 2  # skip property and =
			for mode, typeid in PARTICLE_TYPES:
				if tokens[i][1].upper() == mode:
					sequence.particle_type = mode
					break
			i += 1
		elif prop in ("SOURCEBLENDMODE", "DESTBLENDMODE"):
			i += 2  # skip property and =
			for mode, blend in PARTICLE_BLEND_MODES:
				if tokens[i][1].upper() == mode:
					sequence.blend_mode = mode
					break
			i += 1
		elif prop == "TEXTURE":
			i += 2  # skip property and =
			sequence.texture = tokens[i][1].strip('"')
			i += 1
		elif value.upper() in ("FADE", "AT", "INITIAL", "FINAL") or \
			(value.upper() == "SO" and tokens[i + 1][1].upper() in ("AT", "INITIAL", "FINAL")):
			started_events = True
			event, i = _decode_event(value, tokens, i, lifetime)
			if event is not None:
				sequence.events.append(event)
		else:
			print(f"Unexpected token in sequence block: {value}")
			i += 1

	i += 1  # skip }

	return sequence, i


def decode(path: str) -> PTParticleSystem:
	"""Decode a .part particle script."""
	particlesystem = PTParticleSystem()
	particlesystem.filename = os.path.basename(path)

	with open(path, "r", encoding="cp949", errors="replace") as f:
		tokens = _tokenize(f.read())

	i = 1  # skip particlesystem keyword
	particlesystem.name = tokens[i][1].strip('"')
	i += 1
	particlesystem.version = float(tokens[i][1])
	i += 1

	if tokens[i] == ("Punct", "{"):
		i += 1

	while i < len(tokens) and tokens[i] != ("Punct", "}"):
		kind, value = tokens[i]

		if kind == "Text" and value.upper() == "POSITION":
			i += 2  # skip property and =
			particlesystem.position, i = _process_vector(tokens, i)
		elif kind == "Text" and value.upper() == "EVENTSEQUENCE":
			i += 1
			sequence, i = _decode_sequence(tokens, i)
			particlesystem.sequences.append(sequence)
		else:
			print(f"Unexpected token in particle system block: {value}")
			i += 1

	return particlesystem
