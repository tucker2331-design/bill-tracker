"""Per-state configuration registry (Standard #6). `get_state("VA")` -> StateConfig.

Adding a state = one module here + one registry line. The pipeline must not branch on a state code.
"""
from .base import Stage, StateConfig
from .va import VA

_REGISTRY = {VA.code: VA}


def get_state(code: str) -> StateConfig:
    try:
        return _REGISTRY[code.upper()]
    except KeyError:
        # Fail closed: an unknown state must stop the run, never fall back to Virginia's rules.
        raise KeyError(f"unknown state {code!r}; registered: {sorted(_REGISTRY)}") from None


def registered() -> list:
    return sorted(_REGISTRY)


__all__ = ["Stage", "StateConfig", "VA", "get_state", "registered"]
