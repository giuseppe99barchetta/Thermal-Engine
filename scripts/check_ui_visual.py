"""Capture the real QML views at desktop sizes and DPI scales, without services."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="build/visual-checks")
    parser.add_argument("--native", action="store_true", help="Use native windows instead of the offscreen Qt platform")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = Path(args.output).resolve()
    reports = []
    for width, height in ((1280, 720), (1920, 1080)):
        for scale in (1, 1.5, 2):
            target = destination / f"{width}x{height}-{int(scale * 100)}"
            target.mkdir(parents=True, exist_ok=True)
            env = {**os.environ, "QT_QUICK_BACKEND": "software", "QT_SCALE_FACTOR": str(scale)}
            if args.native:
                env.pop("QT_QPA_PLATFORM", None)
            else:
                env["QT_QPA_PLATFORM"] = "offscreen"
            size = f"{round(width / scale)}x{round(height / scale)}"
            process = subprocess.run([sys.executable, str(root / "main.py"), "--ui-smoke-test", str(target), "--ui-smoke-size", size],
                                     cwd=root, env=env, capture_output=True, text=True, timeout=60)
            (target / "runtime.log").write_text(process.stdout + process.stderr, encoding="utf-8")
            if process.returncode:
                raise RuntimeError(f"UI verification failed: {target}. See runtime.log")
            report = json.loads((target / "report.json").read_text(encoding="utf-8"))
            if not report["passed"] or report["qml_errors"] or len(report["screens"]) < 23:
                raise RuntimeError(f"Incomplete UI verification: {target}")
            reports.append({"directory": str(target), "scale": scale, "report": report})
            print(f"Verified {width}x{height} at {int(scale * 100)}%: {len(report['screens'])} screens", flush=True)
    (destination / "summary.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
