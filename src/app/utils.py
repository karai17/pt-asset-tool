import os
from time import time_ns


def now() -> float:
	"""Current time in seconds with nanosecond precision."""
	return time_ns() / 1_000_000_000


def ftime(t0: float, t1: float) -> str:
	"""Delta between two timestamps formatted to 3 decimal positions."""
	return f"{t1-t0:.3f}"


def trailing_slash(dir: str | None) -> str | None:
	"""Guarantee that there is a trailing slash at the end of a path."""
	if dir:
		return os.path.join(dir, "")
