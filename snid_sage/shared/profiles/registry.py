from __future__ import annotations

from typing import Dict, List
from .types import Profile

_REGISTRY: Dict[str, Profile] = {}


def register_profile(profile: Profile) -> None:
    pid = profile.id.lower().strip()
    if not pid:
        raise ValueError("Profile id must be non-empty")
    if pid in _REGISTRY and _REGISTRY[pid] != profile:
        raise ValueError(f"Profile '{pid}' already registered")
    _REGISTRY[pid] = profile


def get_profile(profile_id: str) -> Profile:
    pid = (profile_id or "optical").lower().strip()
    if pid not in _REGISTRY:
        raise KeyError(f"Unknown profile id: {profile_id}")
    return _REGISTRY[pid]


def list_profiles() -> List[Profile]:
    return list(_REGISTRY.values())


