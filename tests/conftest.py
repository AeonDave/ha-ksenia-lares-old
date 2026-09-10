"""Load HA-free parser modules without importing the integration package."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "ha_ksenia_lares"


def load_module(name: str):
    path = _COMPONENT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"lares_{name}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
