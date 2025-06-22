import math
import numpy as np
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


def encode_string(korean: str) -> bytes:
	""" Convert Korean text to bytes. """

	for enc in encodings:
		try:
			return korean.encode(enc)
		except Exception:
			continue
	raise Exception("Unknown text encoding.")


def decode_string(cstring: Array[c_byte] | bytes) -> str:
	""" Convert bytes to Korean text. """

	line = bytes(cstring).split(b"\x00")[0]
	for enc in encodings:
		try:
			return line.decode(enc)
		except Exception:
			continue
	raise Exception("Unknown text encoding.")


def normalize_rotation(q: PTRotation) -> PTRotation:
	""" Normalize a quaternion. """

	magnitude = math.sqrt(q.w**2 + q.x**2 + q.y**2 + q.z**2)
	if magnitude == 0:
			raise ValueError("Cannot normalize a zero-length quaternion.")

	return PTRotation(
		q.x / magnitude,
		q.y / magnitude,
		q.z / magnitude,
		q.w / magnitude
	)


def multiply_rotations(a: PTRotation | PTAnimationRotation, b: PTRotation | PTAnimationRotation | int | float) -> PTRotation:
	if not isinstance(b, PTRotation) and not isinstance(b, PTAnimationRotation):
		return normalize_rotation(PTRotation(
			a.x * b,
			a.y * b,
			a.z * b,
			a.w * b
		))

	return normalize_rotation(PTRotation(
		a.x * b.w + a.w * b.x + a.y * b.z - a.z * b.y,
		a.y * b.w + a.w * b.y + a.z * b.x - a.x * b.z,
		a.z * b.w + a.w * b.z + a.x * b.y - a.y * b.x,
		a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z
	))


def vector_lerp(v1: PTPosition | PTScale | PTAnimationPosition | PTAnimationScale, v2: PTPosition | PTScale | PTAnimationPosition | PTAnimationScale, t: float) -> PTPosition | PTScale:
	cls = type(v1)
	a = np.array([v1.x, v1.y, v1.z])
	b = np.array([v2.x, v2.y, v2.z])
	c = ((1 - t) * a + t * b).tolist()
	return cls(x=c[0], y=c[1], z=c[2])


def get_filename(path: str, sep: str = "\\") -> tuple[str, str]:
	"""
	Get the root and extension of a filename.

	Note: backslashes are hard coded into Priston Tale's data so we default the
	seperator to back slashes.
	"""

	segments = path.split(sep)
	root, ext = os.path.splitext(segments[-1])
	return root, ext


def get_radians(angle: int) -> float:
	"""
		Angles are defined as a 4096 unit circle.

		Reference: smSin.h::ANGLE_360
	"""

	return (angle % ANGLE_360) / ANGLE_360 * TAU


def get_rotation(x: int, y: int, z: int) -> PTRotation:
	"""
		Convert Priston Tale's 4096 unit angles to a quaternion.

		Reference: smgeosub.cpp::GetRadian2D
	"""

	rx = get_radians(x)
	ry = get_radians(y)
	rz = get_radians(z)

	cx = math.cos(rx / 2)
	sx = math.sin(rx / 2)
	cy = math.cos(ry / 2)
	sy = math.sin(ry / 2)
	cz = math.cos(rz / 2)
	sz = math.sin(rz / 2)

	return normalize_rotation(PTRotation(
		x = sx * cy * cz - cx * sy * sz,
		y = cx * sy * cz + sx * cy * sz,
		z = cx * cy * sz - sx * sy * cz,
		w = cx * cy * cz + sx * sy * sz
	))


def get_face_normal(a: PTObjectVertex, b: PTObjectVertex, c: PTObjectVertex) -> PTObjectVertex:
	a = np.array([a.x, a.y, a.z])
	b = np.array([b.x, b.y, b.z])
	c = np.array([c.x, c.y, c.z])

	ab = b - a
	ac = c - a

	n = np.cross(ab, ac)
	norm = np.linalg.norm(n)

	if norm == 0:
		return PTObjectVertex(0, 1, 0)

	n = (n / norm).tolist()

	return PTObjectVertex(n[0], n[1], n[2])


def to_np_matrix(m: PTObjectMatrix | PTObjectTransform):
	return np.array([
		[m._11, m._21, m._31, m._41],
		[m._12, m._22, m._32, m._42],
		[m._13, m._23, m._33, m._43],
		[m._14, m._24, m._34, m._44]
	], dtype=np.float32).T


def from_np_matrix(m) -> PTObjectMatrix:
	m = m.T.tolist()
	return PTObjectMatrix(
		_11=m[0][0], _21=m[1][0], _31=m[2][0], _41=m[3][0],
		_12=m[0][1], _22=m[1][1], _32=m[2][1], _42=m[3][1],
		_13=m[0][2], _23=m[1][2], _33=m[2][2], _43=m[3][2],
		_14=m[0][3], _24=m[1][3], _34=m[2][3], _44=m[3][3]
	)


def to_np_vector(v: PTObjectVertex):
	return np.array([ v.x, v.y, v.z, 1 ], dtype=np.float32)


def from_np_vector(v) -> PTObjectVertex:
	v = v.tolist()
	return PTObjectVertex(v[0], v[1], v[2])


def trs_to_np_matrix(t: PTPosition, r: PTRotation, s: PTScale):
	xx, yy, zz = r.x*r.x, r.y*r.y, r.z*r.z
	xy, xz, yz = r.x*r.y, r.x*r.z, r.y*r.z
	wx, wy, wz = r.w*r.x, r.w*r.y, r.w*r.z

	np_rm = np.array([
		[1-2*(yy+zz),   2*(xy-wz),   2*(xz+wy), 0],
		[  2*(xy+wz), 1-2*(xx+zz),   2*(yz-wx), 0],
		[  2*(xz-wy),   2*(yz+wx), 1-2*(xx+yy), 0],
		[          0,           0,           0, 1]
	]).T

	np_sm = np.array([
		[s.x,   0,   0, 0],
		[  0, s.y,   0, 0],
		[  0,   0, s.z, 0],
		[  0,   0,   0, 1]
	]).T

	np_rsm = np_rm @ np_sm
	np_rsm[:3, 3] = np.array([t.x, t.y, t.z])

	return np_rsm


def matrix_to_rotation(m: PTObjectMatrix) -> PTRotation:
	sq = 1 + m._11 + m._22 + m._33
	if sq <= 0:
		return PTRotation()

	w = math.sqrt(sq) / 2
	scale = w * 4

	q = normalize_rotation(PTRotation(
		x = (m._32 - m._23) / scale,
		y = (m._13 - m._31) / scale,
		z = (m._21 - m._12) / scale,
		w = w
	))

	# some matrices in the SMD data can have unusable data, converting to quaternions become NaN
	if q.w != q.w:
		return PTRotation()

	return q
