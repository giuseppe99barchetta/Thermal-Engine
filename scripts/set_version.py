"""Write the release version into src/utils/app_version.py (used by every release job)."""
import re
import sys
from pathlib import Path

TEMPLATE = '''"""
Version information for Thermal Engine.
This file is automatically updated by the build process.
"""

__version__ = "{version}"
__version_info__ = ({major}, {minor}, {patch})

def get_version():
    """Get the current version string."""
    return __version__

def get_version_tuple():
    """Get the current version as a tuple."""
    return __version_info__
'''


def write_version(tag, target=Path("src/utils/app_version.py")):
    version = tag.lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"Invalid version: {tag}")
    major, minor, patch = version.split(".")
    Path(target).write_text(TEMPLATE.format(version=version, major=major, minor=minor, patch=patch), encoding="utf-8")


if __name__ == "__main__":
    write_version(sys.argv[1])
