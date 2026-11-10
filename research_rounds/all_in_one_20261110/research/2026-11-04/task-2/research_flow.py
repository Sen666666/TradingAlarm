#!/usr/bin/env python3
"""Small, offline stage wrapper for TradingAlarm research; no strategy engine."""
import argparse
import csv
import fcntl
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

PHASES = ["preflight", "economic", "audit", "report"]


def ensure_assertions():
    if not __debug__ or os.environ.get("PYTHONOPTIMIZE", "") not in {"", "0"}:
        raise ValueError("Optimized Python is forbidden: native accounting uses assert")


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    # Receipts are append-only. A partial receipt blocks reuse rather than passing.
    with Path(path).open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def sha(path):
    path = Path(path)
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"File changed while hashing: {path}")
    return h.hexdigest()


def expand(value, spec, dest):
    for token, replacement in {"{project_root}": spec["project_root"],
                               "{run_dir}": str(dest),
                               "{python}": spec.get("python", sys.executable)}.items():
        value = value.replace(token, replacement)
    return value


def path(value, spec, dest):
    p = Path(expand(value, spec, dest))
    return p.resolve() if p.is_absolute() else (Path(spec["project_root"]) / p).resolve()


def inside(p, dest):
    if not p.is_relative_to(dest) or p == dest:
        raise ValueError(f"New output must be inside the new run directory: {p}")


def check(conditions, spec, dest):
    for condition in conditions:
        p = path(condition["path"], spec, dest)
        value = read(p)
        for key in condition["key"]:
            value = value[key]
        expected = condition["equals"]
        # In particular, 1 must not silently pass a boolean receipt.
        if type(value) is not type(expected) or value != expected:
            raise ValueError(f"Receipt failed: {p} {condition['key']} = {value!r}")


def identities(spec, dest):
    records = []
    for kind, files in spec.get("identity", {}).items():
        if kind not in {"code", "data", "protocol"}:
            raise ValueError(f"Unknown identity category: {kind}")
        for name in files:
            p = path(name, spec, dest)
            records.append(dict(kind=kind, path=str(p), sha256=sha(p), bytes=p.stat().st_size))
    records.append(dict(kind="wrapper", path=str(Path(__file__).resolve()), sha256=sha(__file__)))
    return records


def verify_identity(records):
    for item in records:
        if sha(item["path"]) != item["sha256"]:
            raise ValueError(f"Frozen identity changed: {item['path']}")


def environment(spec):
    python = Path(spec.get("python", sys.executable)).resolve()
    result = dict(wrapper_python=sys.version, python=str(python), python_sha256=sha(python),
                  python_version=subprocess.check_output([str(python), "--version"], text=True).strip())
    # Metadata only; no pip invocation or import side effects.
    result["wrapper_distributions"] = {}
    for name in ["numpy", "pandas", "pyarrow", "matplotlib"]:
        try:
            result["wrapper_distributions"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["wrapper_distributions"][name] = None
    result["dependency_scope"] = "wrapper interpreter; use the project Python to capture project versions"
    try:
        result["git_head"] = subprocess.check_output(
            ["git", "-C", spec["project_root"], "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL, timeout=5).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        result["git_head"] = None
    return result


def verify_environment(frozen):
    if Path(sys.executable).resolve() != Path(frozen["python"]) or sys.version != frozen["wrapper_python"]:
        raise ValueError("Use the same Python interpreter as the freeze")
    if sha(frozen["python"]) != frozen["python_sha256"]:
        raise ValueError("Python executable changed")
    for name, expected in frozen["wrapper_distributions"].items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        if actual != expected:
            raise ValueError(f"Dependency version changed: {name}")


def completion(dest, mode):
    dest = Path(dest).resolve()
    p = dest / "complete.json"
    if not p.exists():
        return False
    r = read(p)
    expected = "complete" if mode == "prospective" else "saved_evidence_verified"
    if r["status"] != expected:
        raise ValueError("Invalid completion receipt")
    verify_identity(r["summary_artifacts"])
    verify_identity(r.get("native_artifact_hashes", []))
    if mode == "prospective":
        expected_paths = {str(dest / (name + ".result.json")) for name in PHASES}
        if {r["path"] for r in r["phase_receipts"]} != expected_paths:
            raise ValueError("Completion must bind all four phase receipts")
        verify_identity(r["phase_receipts"])
    return True


def summary_artifacts(dest):
    return [dict(path=str(dest / name), sha256=sha(dest / name))
            for name in ["summary.csv", "summary-source.json"]]


def normalize(spec, dest):
    source = path(spec["summary"]["path"], spec, dest)
    columns = spec["summary"]["columns"]
    source_bytes = source.read_bytes()
    with io.StringIO(source_bytes.decode("utf-8-sig"), newline="") as f:
        reader = csv.DictReader(f)
        missing = set(columns.values()) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Summary columns missing: {sorted(missing)}")
        rows = [{k: r[v] for k, v in columns.items()} for r in reader]
    if not rows:
        raise ValueError("Empty summary is not a complete result")
    with (dest / "summary.csv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)
    save(dest / "summary-source.json", dict(path=str(source), sha256=hashlib.sha256(source_bytes).hexdigest(), rows=len(rows),
         columns=columns, units=spec["summary"].get("units", {}),
         scope="field mapping only; no recomputed returns, no cross-round ranking"))
    return len(rows)


def validate(spec, dest, saved=False):
    if spec.get("version") != 1 or not Path(spec["project_root"]).is_absolute():
        raise ValueError("version=1 and absolute project_root required")
    if not spec.get("identity", {}).get("code") or not spec.get("identity", {}).get("data"):
        raise ValueError("Explicit code and data identities required")
    if Path(spec.get("python", sys.executable)).resolve() != Path(sys.executable).resolve():
        raise ValueError("Invoke the wrapper with the same project Python declared in the spec")
    if saved:
        if not spec.get("checks"):
            raise ValueError("Saved evidence needs explicit native receipt checks")
        return
    if [s["name"] for s in spec["steps"]] != PHASES:
        raise ValueError(f"Exactly four ordered phases required: {PHASES}")
    if type(spec.get("max_seconds")) not in (int, float) or not math.isfinite(spec["max_seconds"]) or spec["max_seconds"] <= 0:
        raise ValueError("Positive cumulative command budget max_seconds required")
    seen = set()
    code_paths = {path(v, spec, dest) for v in spec["identity"]["code"]}
    for step in spec["steps"]:
        if not step.get("argv") or not step.get("outputs") or not step.get("checks"):
            raise ValueError("Each phase needs argv, explicit output files, and native receipt checks")
        argv = step["argv"]
        if len(argv) < 2 or argv[0] != "{python}" or path(argv[1], spec, dest) not in code_paths:
            raise ValueError("Commands must invoke a declared frozen Python entry script")
        if not any("{run_dir}" in v for v in argv[2:]):
            raise ValueError("Commands must explicitly receive the new run directory")
        outputs = {path(v, spec, dest) for v in step["outputs"]}
        if seen & outputs:
            raise ValueError("Each phase must own different output files")
        seen |= outputs
        for c in step["checks"]:
            if path(c["path"], spec, dest) not in outputs:
                raise ValueError("Each checked receipt must be listed in the phase outputs")
        for value in step["outputs"]:
            p = path(value, spec, dest)
            inside(p, dest)
            if p.exists():
                raise ValueError(f"Refusing existing output: {p}")
    audit = spec["steps"][2]
    if not any(c.get("equals") is True and c.get("key", [])[-1:] == ["passed"] for c in audit["checks"]):
        raise ValueError("Audit phase needs a positive native pass receipt")
    summary = path(spec["summary"]["path"], spec, dest)
    inside(summary, dest)
    if summary not in seen:
        raise ValueError("Summary source must be a declared new phase output")


def freeze(spec_path, dest, saved=False):
    ensure_assertions()
    dest = Path(dest).resolve()
    t0 = time.monotonic()
    spec = read(spec_path)
    validate(spec, dest, saved)
    dest.mkdir(parents=True, exist_ok=False)
    save(dest / "spec.json", spec)
    records = identities(spec, dest)
    if saved:
        names = [c["path"] for c in spec["checks"]] + [spec["summary"]["path"]]
        names += [m["path"] for m in spec.get("artifact_manifests", [])]
        known = {r["path"] for r in records}
        for name in names:
            p = path(name, spec, dest)
            if str(p) not in known:
                records.append(dict(kind="saved_evidence", path=str(p), sha256=sha(p)))
                known.add(str(p))
    copies = dest / "code-snapshot"
    copies.mkdir()
    for i, record in enumerate(records):
        if record["kind"] in {"code", "protocol", "wrapper"}:
            data = Path(record["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise ValueError("Identity changed before snapshot")
            (copies / f"{i:03d}-{Path(record['path']).name}").write_bytes(data)
    receipt = dict(created_utc=now(), mode="saved_evidence_import" if saved else "prospective",
                   spec_sha256=sha(dest / "spec.json"), identity=records, environment=environment(spec),
                   identity_scope="explicit files only; a manifest hash alone does not verify its referenced data",
                   freeze_seconds=time.monotonic() - t0)
    save(dest / "freeze.json", receipt)
    if saved:
        check(spec["checks"], spec, dest)
        verified = []
        for manifest in spec.get("artifact_manifests", []):
            mp = path(manifest["path"], spec, dest)
            mapping = read(mp)[manifest["field"]]
            base = path(manifest["base"], spec, dest)
            for name, expected in mapping.items():
                p = (base / name).resolve()
                if sha(p) != expected:
                    raise ValueError(f"Native artifact hash mismatch: {p}")
                verified.append(dict(path=str(p), sha256=expected))
        verify_identity(records)
        n = normalize(spec, dest)
        verify_identity(records)
        save(dest / "complete.json", dict(status="saved_evidence_verified", summary_rows=n,
             imported_utc=now(), checks=spec["checks"], native_artifact_hashes=verified,
             summary_artifacts=summary_artifacts(dest),
             accounting_scope="saved native receipts checked; accounting engine not rerun",
             new_economic_paths=0, seconds=time.monotonic() - t0))
    return receipt


def load_run(dest):
    ensure_assertions()
    dest = Path(dest).resolve()
    frozen = read(dest / "freeze.json")
    if sha(dest / "spec.json") != frozen["spec_sha256"]:
        raise ValueError("Frozen spec changed")
    spec = read(dest / "spec.json")
    verify_identity(frozen["identity"])
    verify_environment(frozen["environment"])
    return spec, frozen


def result_state(dest, spec):
    dest = Path(dest).resolve()
    finished = []
    for step in spec["steps"]:
        result = dest / (step["name"] + ".result.json")
        started = dest / (step["name"] + ".started.json")
        if result.exists():
            r = read(result)
            if r["status"] != "complete":
                raise ValueError(f"Failed phase preserved: {step['name']}; use a new attempt directory")
            verify_identity(r["artifacts"])
            check(step["checks"], spec, dest)
            finished.append(r)
        elif started.exists():
            raise ValueError(f"Uncertain phase: {step['name']}; inspect native outputs, do not auto-rerun")
        else:
            break
    return finished


def run(dest, through):
    dest = Path(dest).resolve()
    spec, frozen = load_run(dest)
    if frozen["mode"] != "prospective":
        raise ValueError("Imported historical evidence is read-only and cannot run")
    # Kernel lock releases on process death; no stale-lock deletion is needed.
    with (dest / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finished = result_state(dest, spec)
        used = sum(r["command_seconds"] for r in finished)
        for step in spec["steps"][len(finished):PHASES.index(through) + 1]:
            verify_identity(frozen["identity"])
            outputs = [path(s, spec, dest) for s in step["outputs"]]
            for p in outputs:
                inside(p, dest)
                if p.exists():
                    raise ValueError(f"Refusing existing output: {p}")
            remaining = spec["max_seconds"] - used
            if remaining <= 0:
                raise ValueError("Cumulative command budget exhausted")
            argv = [expand(v, spec, dest) for v in step["argv"]]
            argv[1] = str(path(step["argv"][1], spec, dest))
            save(dest / (step["name"] + ".started.json"), dict(at=now(), argv=argv, remaining_seconds=remaining))
            t0 = time.monotonic()
            proc = None
            try:
                child_env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR=str(dest / ".mplcache"))
                child_env.pop("PYTHONOPTIMIZE", None)
                with (dest / (step["name"] + ".log")).open("x") as log:
                    proc = subprocess.Popen(argv, cwd=dest, stdout=log, stderr=subprocess.STDOUT,
                                            env=child_env, start_new_session=True)
                    code = proc.wait(timeout=remaining)
                elapsed = time.monotonic() - t0
                if code != 0:
                    raise ValueError(f"Native command exited {code}")
                check(step["checks"], spec, dest)
                verify_identity(frozen["identity"])
                artifacts = [dict(path=str(p), sha256=sha(p)) for p in outputs]
                r = dict(status="complete", phase=step["name"], finished_utc=now(),
                         command_seconds=elapsed, artifacts=artifacts)
                save(dest / (step["name"] + ".result.json"), r)
                used += elapsed
            except BaseException as exc:
                if proc is not None and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                save(dest / (step["name"] + ".result.json"), dict(status="failed", phase=step["name"],
                     command_seconds=time.monotonic() - t0, error=repr(exc), finished_utc=now()))
                raise
        finished = result_state(dest, spec)
        if len(finished) == len(PHASES) and not (dest / "complete.json").exists():
            n = normalize(spec, dest)
            result_state(dest, spec)
            save(dest / "complete.json", dict(status="complete", summary_rows=n, completed_utc=now(),
                 summary_artifacts=summary_artifacts(dest),
                 phase_receipts=[dict(path=str(dest / (name + ".result.json")),
                                      sha256=sha(dest / (name + ".result.json"))) for name in PHASES],
                 command_seconds=sum(r["command_seconds"] for r in finished),
                 accounting_scope="native audit command and explicit pass receipts required"))
        return dict(completed_phases=[r["phase"] for r in finished], command_seconds=used,
                    complete=completion(dest, frozen["mode"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["freeze", "import-saved"]:
        p = sub.add_parser(name)
        p.add_argument("--spec", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
    for name in ["run", "status"]:
        p = sub.add_parser(name)
        p.add_argument("--run-dir", type=Path, required=True)
        if name == "run":
            p.add_argument("--through", choices=PHASES, default="report")
    args = parser.parse_args()
    try:
        if args.command in {"freeze", "import-saved"}:
            result = freeze(args.spec, args.output.resolve(), args.command == "import-saved")
            result = {k: result[k] for k in ["mode", "created_utc", "freeze_seconds"]}
        elif args.command == "run":
            result = run(args.run_dir.resolve(), args.through)
        else:
            dest = args.run_dir.resolve()
            spec, frozen = load_run(dest)
            result = dict(mode=frozen["mode"], complete=completion(dest, frozen["mode"]))
            if frozen["mode"] == "prospective":
                result["completed_phases"] = [r["phase"] for r in result_state(dest, spec)]
            else:
                check(spec["checks"], spec, dest)
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
