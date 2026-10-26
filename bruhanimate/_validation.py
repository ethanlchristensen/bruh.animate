"""Shared validation for simulation time."""

from math import isfinite


def _seconds(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    if not isfinite(value) or value < 0:
        raise ValueError(f"{name} must be non-negative and finite")
