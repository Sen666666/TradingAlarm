"""Replay frozen trajectory code into a NEW directory. No account stage."""
from pathlib import Path
import argparse
import importlib.util
import shutil
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", type=Path, required=True,
                   help="saved pv-event-structure-20261020 directory")
    p.add_argument("--output-root", type=Path, required=True,
                   help="new, nonexistent directory; originals never overwritten")
    p.add_argument("--version", choices=["v0", "v1"], required=True)
    a = p.parse_args()
    source = a.source_dir.resolve()
    if len(list(source.glob("*-signals.csv"))) != 27:
        raise ValueError("Expected the 27 frozen saved input series")
    out = a.output_root.resolve()
    if out.exists():
        raise FileExistsError(out)
    archive = Path(__file__).resolve().parents[1]
    (out / "code").mkdir(parents=True)
    (out / "raw").mkdir()
    for name in ("context_model.py", "context_model_v1.py", "run_context.py"):
        shutil.copy2(archive / "code" / name, out / "code" / name)
    for name in ("protocol-v0.json", "protocol-v1.json"):
        shutil.copy2(archive / name, out / name)
    shutil.copy2(archive / "raw/case-index.json", out / "raw/case-index.json")
    sys.path.insert(0, str(out / "code"))
    path = out / "code/run_context.py"
    spec = importlib.util.spec_from_file_location("frozen_trajectory_runner", path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    # Supply the relocated input directory without changing the frozen code.
    runner.SOURCE = source
    sys.argv = [str(path), "--version", a.version]
    runner.main()


if __name__ == "__main__":
    main()
