"""Find the files that live next to the package: client profiles, reference
numbers and JSON Schemas.

Everything is resolved relative to the phase4_solutions folder, so it works
when you run from the repo (or after `pip install -e .`). Set
PHASE4_PROFILE_DIR to keep client profiles somewhere else.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Union

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "profiles"
REFERENCE_DIR = ROOT / "reference"
CONTRACTS_DIR = ROOT / "contracts"

SCHEMAS = {
    "input": "phase4_input.schema.json",
    "output": "phase4_output.schema.json",
    "manager-view": "manager_view.schema.json",
    "phase3-profile": "client_profile.schema.json",
}


def _read(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _profile_dirs() -> List[Path]:
    dirs = []
    if os.environ.get("PHASE4_PROFILE_DIR"):
        dirs.append(Path(os.environ["PHASE4_PROFILE_DIR"]))
    dirs.append(PROFILE_DIR)
    return dirs


def list_profiles() -> List[str]:
    names = set()
    for d in _profile_dirs():
        if d.is_dir():
            names.update(p.stem for p in d.glob("*.json"))
    return sorted(names)


def load_profile(ref: Union[str, Dict[str, Any], None]) -> Dict[str, Any]:
    """A profile dict, a path to a JSON file, or a profile name such as 'veloran'."""
    if ref is None:
        return {}
    if isinstance(ref, dict):
        return ref
    path = Path(ref)
    if path.suffix == ".json" and path.exists():
        return _read(path)
    for d in _profile_dirs():
        candidate = d / f"{ref}.json"
        if candidate.exists():
            return _read(candidate)
    raise FileNotFoundError(f"No client profile named {ref!r}. Known profiles: {', '.join(list_profiles()) or 'none'}")


def load_expected(ref: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Reference numbers: a dict, a path, or a name such as 'veloran'."""
    if isinstance(ref, dict):
        return ref
    path = Path(ref)
    if path.exists():
        return _read(path)
    candidate = REFERENCE_DIR / f"{ref}_expected.json"
    if candidate.exists():
        return _read(candidate)
    known = sorted(p.stem.replace("_expected", "") for p in REFERENCE_DIR.glob("*_expected.json"))
    raise FileNotFoundError(f"No reference named {ref!r}. Known references: {', '.join(known) or 'none'}")


def load_schema(name: str) -> Dict[str, Any]:
    if name not in SCHEMAS:
        raise KeyError(f"Unknown schema {name!r}; choose one of {', '.join(SCHEMAS)}")
    path = CONTRACTS_DIR / SCHEMAS[name]
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; run Phase 4 from the repo folder or install it with pip install -e .")
    return _read(path)
