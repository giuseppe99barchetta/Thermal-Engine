"""Check QML syntax and types; Python context properties are verified by runtime tests."""
import subprocess
import sys
from pathlib import Path
import PySide6

root = Path(__file__).resolve().parents[1]
qml = root / "src/ui/qml"
tool = Path(PySide6.__file__).parent / ("qmllint.exe" if sys.platform == "win32" else "qmllint")
command = [str(tool), "--ignore-settings", "--unqualified", "disable", "-I", str(qml), "-W", "0"]
result = subprocess.run(command + [str(path) for path in sorted(qml.rglob("*.qml"))])
raise SystemExit(result.returncode)
