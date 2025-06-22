import os
from time import time_ns


def now():
	return time_ns() / 1000000000


def ftime(t0: float, t1: float):
	return format(t1 - t0, "0.3f")


def trailing_slash(dir: str | None):
	if dir:
		return os.path.join(dir, "")
