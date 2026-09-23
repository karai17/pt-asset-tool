import math
import re
import numpy as np
import numpy.typing as npt
import os

from ctypes import *

from pt.pdef import *
from pt.const import (
	ANGLE_360,
	TAU
)


encodings = [
	"cp949",
	"euc-kr",
	"shift-jis",
	"ascii"
]


"""STRINGS"""


def encode_string(pstring: str) -> bytes:
	"""Convert text to bytes."""
	for enc in encodings:
		try:
			return pstring.encode(enc)
		except Exception:
			continue
	raise Exception("Unknown text encoding.")


def decode_string(cstring: Array[c_byte] | bytes) -> str:
	"""Convert bytes to text."""
	line = bytes(cstring).split(b"\x00")[0]
	for enc in encodings:
		try:
			return line.decode(enc)
		except Exception:
			continue
	raise Exception("Unknown text encoding.")


"""NUMERIC PARSING"""


def atoi(value: bytes | str) -> int:
	"""C atoi semantics (the engine atoi/atofs every config token): parse the
	leading decimal integer, truncate and ignore the rest, return 0 when the
	token starts with no digits (e.g. b'0;' -> 0, b'1.5' -> 1, b'abc' -> 0)."""
	if isinstance(value, bytes):
		value = value.decode("ascii", errors="ignore")
	match = re.match(r"[-+]?\d+", value)
	return int(match.group()) if match else 0


def atof(value: bytes | str) -> float:
	"""C atof semantics: parse the leading numeric prefix and ignore the rest
	(e.g. '0;' -> 0.0, b'5%' -> 5.0, b'abc' -> 0.0)."""
	if isinstance(value, bytes):
		value = value.decode("ascii", errors="ignore")
	match = re.match(r"[-+]?\d*\.?\d+", value)
	return float(match.group()) if match else 0.0


def get_filename(path: str, sep: str = "\\") -> tuple[str, str]:
	"""
	Get the root and extension of a filename.

	Note: backslashes are hard coded into Priston Tale's data so we default the
	seperator to back slashes.
	"""
	segments = path.split(sep)
	root, ext = os.path.splitext(segments[-1])
	return root, ext


_dircache: dict[str, list[str]] = {}


def _listdir_cached(dirpath: str) -> list[str]:
	names = _dircache.get(dirpath)
	if names is None:
		names = os.listdir(dirpath)
		_dircache[dirpath] = names
	return names


def resolve_casepath(path: str) -> str:
	"""
	Resolve a path case-insensitively, matching Win32 filesystem semantics: the
	engine resolves every file through FindFirstFile / fopen on FAT/NTFS
	(smFindFile, smRead3d.cpp:1713), which is case-insensitive and
	case-preserving. Returns the input path when no on-disk case variant exists
	so error messages keep the authored name.
	"""
	if os.path.exists(path):
		return path
	segments = path.split(os.path.sep)
	resolved = ""
	if not segments[0]:
		resolved = os.path.sep
		segments = segments[1:]
	for segment in segments:
		if segment in (".", ".."):
			resolved = os.path.join(resolved, segment)
			continue
		try:
			names = _listdir_cached(resolved or ".")
		except OSError:
			names = []
		match = next((name for name in names if name.casefold() == segment.casefold()), None)
		resolved = os.path.join(resolved, match if match else segment)
	return resolved


def split_config_tokens(line: bytes) -> list[bytes]:
	"""
	Split a config line into tokens the way the engine's GetWord/GetString pair
	does (fileread.cpp:81, smRead3d.cpp:4598): a token is a whitespace delimited
	word, unless it opens a double quote in which case the token runs to the
	closing quote and the quotes are stripped (quoted values keep inner spaces).
	Line terminators never become part of a token.
	"""
	tokens = []
	i, n = 0, len(line)
	while i < n:
		while i < n and line[i:i+1] in (b" ", b"\t", b"\r", b"\n"):
			i += 1
		if i >= n:
			break
		if line[i:i+1] == b'"':
			i += 1
			start = i
			while i < n and line[i:i+1] not in (b'"', b"\r", b"\n"):
				i += 1
			tokens.append(line[start:i])
			i += 1
		else:
			start = i
			while i < n and line[i:i+1] not in (b" ", b"\t", b"\r", b"\n"):
				i += 1
			tokens.append(line[start:i])
	return tokens


"""QUATERNIONS / ANGLES"""


def angle_to_radian(angle: int) -> float:
	"""
		Angles are defined as a 4096 unit circle.

		Reference: `smSin.h::ANGLE_360`
	"""
	return (angle % ANGLE_360) / ANGLE_360 * TAU


def normalize_quaternion(q: PTQuaternion) -> PTQuaternion:
	"""Normalize a quaternion."""
	magnitude = math.sqrt(q.w**2 + q.x**2 + q.y**2 + q.z**2)
	if magnitude == 0:
		raise ValueError("Cannot normalize a zero-length quaternion.")
	return PTQuaternion(
		q.x / magnitude,
		q.y / magnitude,
		q.z / magnitude,
		q.w / magnitude
	)


def multiply_quaternions(a: PTQuaternion, b: PTQuaternion) -> PTQuaternion:
	"""Multiply two quaternions together."""
	return normalize_quaternion(PTQuaternion(
		a.x * b.w + a.w * b.x + a.y * b.z - a.z * b.y,
		a.y * b.w + a.w * b.y + a.z * b.x - a.x * b.z,
		a.z * b.w + a.w * b.z + a.x * b.y - a.y * b.x,
		a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z
	))


def matrix_to_quaternion(m: PTMat4) -> PTQuaternion:
	"""Convert a mat4 to a quaternion."""
	sq = 1 + m._11 + m._22 + m._33
	if sq <= 0:
		return PTQuaternion()

	w = math.sqrt(sq) / 2
	scale = w * 4

	q = normalize_quaternion(PTQuaternion(
		x = (m._32 - m._23) / scale,
		y = (m._13 - m._31) / scale,
		z = (m._21 - m._12) / scale,
		w = w
	))

	# some matrices in the SMD data can have unusable data
	# converting to a quaternion becomes NaN
	if q.w != q.w:
		return PTQuaternion()
	return q


def quaternion_from_matrix(m: npt.NDArray[np.floating]) -> PTQuaternion:
	"""Quaternion from a 3x3 (or the 3x3 block of a 4x4) rotation matrix using
	Shepperd's method: all four branches are selected by the largest diagonal
	element, which stays numerically stable where a single trace-based formula
	degenerates (trace near or below -1, e.g. matrices carrying baked scale
	shrink such as Raeda's clavicle Tm). Returns a unit quaternion; a
	non-orthonormal input yields an approximation of the rotation."""
	t = np.asarray(m, dtype=np.float64)
	trace = t[0, 0] + t[1, 1] + t[2, 2]

	if trace > 0:
		s = math.sqrt(trace + 1.0) * 2
		q = PTQuaternion(
			x = (t[2, 1] - t[1, 2]) / s,
			y = (t[0, 2] - t[2, 0]) / s,
			z = (t[1, 0] - t[0, 1]) / s,
			w = 0.25 * s
		)
	elif t[0, 0] > t[1, 1] and t[0, 0] > t[2, 2]:
		s = math.sqrt(1.0 + t[0, 0] - t[1, 1] - t[2, 2]) * 2
		q = PTQuaternion(
			x = 0.25 * s,
			y = (t[0, 1] + t[1, 0]) / s,
			z = (t[0, 2] + t[2, 0]) / s,
			w = (t[2, 1] - t[1, 2]) / s
		)
	elif t[1, 1] > t[2, 2]:
		s = math.sqrt(1.0 + t[1, 1] - t[0, 0] - t[2, 2]) * 2
		q = PTQuaternion(
			x = (t[0, 1] + t[1, 0]) / s,
			y = 0.25 * s,
			z = (t[1, 2] + t[2, 1]) / s,
			w = (t[0, 2] - t[2, 0]) / s
		)
	else:
		s = math.sqrt(1.0 + t[2, 2] - t[0, 0] - t[1, 1]) * 2
		q = PTQuaternion(
			x = (t[0, 2] + t[2, 0]) / s,
			y = (t[1, 2] + t[2, 1]) / s,
			z = 0.25 * s,
			w = (t[1, 0] - t[0, 1]) / s
		)

	return normalize_quaternion(q)


def angles_to_quaternion(x: int, y: int, z: int) -> PTQuaternion:
	"""
		Convert Priston Tale's 4096 unit angles to a quaternion.

		Reference: `smgeosub.cpp::GetRadian2D`
	"""
	rx = angle_to_radian(x)
	ry = angle_to_radian(y)
	rz = angle_to_radian(z)

	cx = math.cos(rx / 2)
	sx = math.sin(rx / 2)
	cy = math.cos(ry / 2)
	sy = math.sin(ry / 2)
	cz = math.cos(rz / 2)
	sz = math.sin(rz / 2)

	return normalize_quaternion(PTQuaternion(
		x = sx * cy * cz - cx * sy * sz,
		y = cx * sy * cz + sx * cy * sz,
		z = cx * cy * sz - sx * sy * cz,
		w = cx * cy * cz + sx * sy * sz
	))


"""VECTORS"""


def lerp_vector(v1: PTVector3, v2: PTVector3, t: float) -> PTVector3:
	"""
	Linear interpolation of a vector between a start and end posiition based on a
	time value between 0 and 1.
	"""
	cls = type(v1)
	a = np.array([v1.x, v1.y, v1.z])
	b = np.array([v2.x, v2.y, v2.z])
	c = ((1 - t) * a + t * b).tolist()
	return cls(x=c[0], y=c[1], z=c[2])


def to_np_vector(v: PTVector3) -> npt.NDArray[np.float32]:
	"""Convert a vec3 to a numpy vec3."""
	return np.array([ v.x, v.y, v.z, 1 ], dtype=np.float32)


def from_np_vector(v: npt.NDArray[np.float32]) -> PTVector3:
	"""Convert a numpy vec3 to a vec3."""
	v = v.tolist()
	return PTVector3(v[0], v[1], v[2])


"""MATRICES"""


def to_np_matrix(m: PTMat4) -> npt.NDArray[np.float32]:
	"""Convert a mat4 to a numpy mat4."""
	return np.array([
		[m._11, m._21, m._31, m._41],
		[m._12, m._22, m._32, m._42],
		[m._13, m._23, m._33, m._43],
		[m._14, m._24, m._34, m._44]
	], dtype=np.float32).T


def from_np_matrix(m: npt.NDArray[np.float32]) -> PTMat4:
	"""Convert a numpy mat4 to a mat4."""
	m = m.T.tolist()
	return PTMat4(
		_11=m[0][0], _21=m[1][0], _31=m[2][0], _41=m[3][0],
		_12=m[0][1], _22=m[1][1], _32=m[2][1], _42=m[3][1],
		_13=m[0][2], _23=m[1][2], _33=m[2][2], _43=m[3][2],
		_14=m[0][3], _24=m[1][3], _34=m[2][3], _44=m[3][3]
	)


def trs_to_np_matrix(t: PTVector3, r: PTQuaternion, s: PTVector3) -> npt.NDArray[np.float32]:
	"""Build a numpy mat4 from a translation, rotation, and scale."""
	xx, yy, zz = r.x*r.x, r.y*r.y, r.z*r.z
	xy, xz, yz = r.x*r.y, r.x*r.z, r.y*r.z
	wx, wy, wz = r.w*r.x, r.w*r.y, r.w*r.z

	np_rm = np.array([
		[1-2*(yy+zz),   2*(xy-wz),   2*(xz+wy), 0],
		[  2*(xy+wz), 1-2*(xx+zz),   2*(yz-wx), 0],
		[  2*(xz-wy),   2*(yz+wx), 1-2*(xx+yy), 0],
		[          0,           0,           0, 1]
	], dtype=np.float32).T

	np_sm = np.array([
		[s.x,   0,   0, 0],
		[  0, s.y,   0, 0],
		[  0,   0, s.z, 0],
		[  0,   0,   0, 1]
	], dtype=np.float32).T

	np_rsm = np_rm @ np_sm
	np_rsm[:3, 3] = np.array([t.x, t.y, t.z])
	return np_rsm


def sm_tm_to_np(tm) -> npt.NDArray[np.float64]:
	"""Convert a raw ctypes smMATRIX to a float64 4x4 in the engine's row-major
	layout (translation in the last row). Fields are 8.8 fixed point against the
	fONE base (smType.h:21-24); the engine converts with smFMatrixFromMatrix
	(smmatrix.cpp:863, /fONE). The runtime reads Tm verbatim from the SMD file
	(smPAT3D::LoadFile, smObj3d.cpp:2937) and uses it as-is in the static branch
	of TmAnimation, so no rescaling is applied here."""
	return np.array([
		[tm._11 / 256.0, tm._12 / 256.0, tm._13 / 256.0, 0.0],
		[tm._21 / 256.0, tm._22 / 256.0, tm._23 / 256.0, 0.0],
		[tm._31 / 256.0, tm._32 / 256.0, tm._33 / 256.0, 0.0],
		[tm._41 / 256.0, tm._42 / 256.0, tm._43 / 256.0, 1.0]
	], dtype=np.float64)


def sm_tm_parent_local(child: npt.NDArray[np.float64], parent: npt.NDArray[np.float64]) -> npt.NDArray[np.float64] | None:
	"""Parent-local transform of a bone from the engine's accumulated world
	matrices: qmat = Tm * pParent->TmInvert (the static branch of
	smOBJ3D::TmAnimation, smObj3d.cpp). Returns None when the parent matrix is
	singular - the engine's smMatrixInvert also produces garbage there
	(degenerate helper bones), and the result is never sampled."""
	try:
		return child @ np.linalg.inv(parent)
	except np.linalg.LinAlgError:
		return None


def decompose_rotation(m: npt.NDArray[np.float64]) -> tuple[PTQuaternion, npt.NDArray[np.float64], bool]:
	"""Decompose the 3x3 rotation block of a row-major 4x4 into quaternion +
	per-axis scale. Authored bone matrices may carry baked uniform scale (det
	magnitude != 1) or a mirror (det < 0); the engine renders them as matrices
	so nothing stops an exporter from emitting them. Scale is removed before
	quaternion extraction (a shrink below ~0.5 pushes the matrix trace negative
	and misroutes a naive trace-based extraction into the 180-degree branch),
	and the mirror is recorded as a negative scale component - the glTF
	convention for flipped chains. Returns (quaternion, scale vector, flipped)."""
	scale = np.linalg.norm(m[:3, :3], axis=1)
	scale[scale < 1e-9] = 1.0

	r = m[:3, :3] / scale[:, np.newaxis]
	det = np.linalg.det(r)
	flipped = det < 0
	if flipped:
		r[:, 2] *= -1

	return quaternion_from_matrix(r), scale, flipped


"""PRIMITIVES"""


def normalize_face(a: PTVector3, b: PTVector3, c: PTVector3) -> PTVector3:
	"""Normalize a face."""
	a = np.array([a.x, a.y, a.z])
	b = np.array([b.x, b.y, b.z])
	c = np.array([c.x, c.y, c.z])

	ab = b - a
	ac = c - a

	n = np.cross(ab, ac)
	norm = np.linalg.norm(n)

	if norm == 0:
		return PTVector3(0, 1, 0)

	n = (n / norm).tolist()
	return PTVector3(n[0], n[1], n[2])
