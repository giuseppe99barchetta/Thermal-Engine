import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "set_version.py"


def _load():
    spec = importlib.util.spec_from_file_location("set_version", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_set_version_writes_an_importable_module(tmp_path):
    target = tmp_path / "app_version.py"
    _load().write_version("v1.2.3", target)
    namespace = {}
    exec(target.read_text(encoding="utf-8"), namespace)
    assert namespace["get_version"]() == "1.2.3" and namespace["get_version_tuple"]() == (1, 2, 3)


def test_set_version_rejects_garbage(tmp_path):
    with pytest.raises(ValueError):
        _load().write_version('1.2.3"; import os', tmp_path / "x.py")
