"""Acceptance tests for evidence preservation and stage recovery, not strategy tests."""
import csv
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import research_flow as F

FIXTURE = '''import csv,json,sys,time
from pathlib import Path
phase,out,behavior=sys.argv[1:]
p=Path(out)
with (p/'calls.txt').open('a') as f:f.write(phase+'\\n')
if behavior=='sleep':time.sleep(10)
if behavior=='fail':raise RuntimeError('native fixture failure')
with (p/(phase+'.json')).open('x') as f:json.dump({'passed':behavior!='bad'},f)
if phase=='report':
 with (p/'native.csv').open('x') as f:f.write('account,ret,dd\\nA,0.10000000000000001,0.02\\n')
'''


class FlowAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.entry = self.root / "entry.py"
        self.entry.write_text(FIXTURE)
        (self.root / "data.csv").write_text("date,close\n2024-01-01,1\n")
        self.dest = self.root / "attempt"
        self.spec = dict(version=1, project_root=str(self.root), python=sys.executable,
                         identity=dict(code=["entry.py"], data=["data.csv"]), max_seconds=10,
                         steps=[dict(name=n, argv=["{python}", "{project_root}/entry.py", n,
                                    "{run_dir}", "ok"], outputs=["{run_dir}/"+n+".json"],
                                    checks=[dict(path="{run_dir}/"+n+".json", key=["passed"], equals=True)])
                                for n in F.PHASES],
                         summary=dict(path="{run_dir}/native.csv", columns=dict(account="account", net_return="ret")))
        self.spec["steps"][-1]["outputs"].append("{run_dir}/native.csv")

    def tearDown(self):
        self.temp.cleanup()

    def freeze(self, saved=False):
        p = self.root / "plan.json"
        p.write_text(json.dumps(self.spec))
        F.freeze(p, self.dest, saved)

    def calls(self):
        return (self.dest / "calls.txt").read_text().splitlines()

    def saved_spec(self):
        (self.root / "passed.json").write_text('{"passed":true}')
        (self.root / "native.csv").write_text("a,r\nold,0.1\n")
        self.spec = dict(version=1, project_root=str(self.root), python=sys.executable,
                         identity=dict(code=["entry.py"], data=["data.csv"]),
                         checks=[dict(path="passed.json", key=["passed"], equals=True)],
                         summary=dict(path="native.csv", columns=dict(account="a", net_return="r")))

    def test_resume_skips_verified_stages_and_cannot_complete_before_audit(self):
        self.freeze()
        r = F.run(self.dest, "economic")
        self.assertEqual(r["completed_phases"], F.PHASES[:2])
        self.assertFalse(r["complete"])
        F.run(self.dest, "report")
        F.run(self.dest, "report")
        self.assertEqual(self.calls(), F.PHASES)
        self.assertTrue(F.completion(self.dest, "prospective"))
        with (self.dest / "summary.csv").open() as f:
            self.assertEqual(next(csv.DictReader(f))["net_return"], "0.10000000000000001")

    def test_false_audit_stops_report_and_preserves_failure(self):
        self.spec["steps"][2]["argv"][-1] = "bad"
        self.freeze()
        with self.assertRaisesRegex(ValueError, "Receipt failed"):
            F.run(self.dest, "report")
        self.assertFalse((self.dest / "complete.json").exists())
        with self.assertRaisesRegex(ValueError, "Failed phase"):
            F.run(self.dest, "report")
        self.assertEqual(self.calls(), F.PHASES[:3])

    def test_code_drift_blocks_before_execution(self):
        self.freeze()
        self.entry.write_text("raise RuntimeError('changed')")
        with self.assertRaisesRegex(ValueError, "Frozen identity changed"):
            F.run(self.dest, "report")
        self.assertFalse((self.dest / "calls.txt").exists())

    def test_data_drift_blocks_completed_stage_reuse(self):
        self.freeze()
        F.run(self.dest, "preflight")
        (self.root / "data.csv").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Frozen identity changed"):
            F.run(self.dest, "report")
        self.assertEqual(self.calls(), ["preflight"])

    def test_spec_drift_blocks(self):
        self.freeze()
        (self.dest / "spec.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Frozen spec changed"):
            F.run(self.dest, "report")

    def test_uncertain_phase_is_not_automatically_rerun(self):
        self.freeze()
        F.save(self.dest / "preflight.started.json", dict(at=F.now()))
        with self.assertRaisesRegex(ValueError, "Uncertain phase"):
            F.run(self.dest, "report")
        self.assertFalse((self.dest / "calls.txt").exists())

    def test_old_output_and_existing_attempt_are_refused(self):
        self.spec["steps"][0]["outputs"] = ["data.csv"]
        with self.assertRaisesRegex(ValueError, "listed in the phase outputs"):
            self.freeze()
        self.assertEqual((self.root / "data.csv").read_text().splitlines()[1], "2024-01-01,1")

    def test_existing_output_inside_attempt_not_overwritten(self):
        self.freeze()
        (self.dest / "preflight.json").write_text("old")
        with self.assertRaisesRegex(ValueError, "Refusing existing output"):
            F.run(self.dest, "report")
        self.assertEqual((self.dest / "preflight.json").read_text(), "old")

    def test_tampered_completed_output_blocks_resume(self):
        self.freeze()
        F.run(self.dest, "preflight")
        (self.dest / "preflight.json").write_text('{"passed":true,"tampered":true}')
        with self.assertRaisesRegex(ValueError, "Frozen identity changed"):
            F.run(self.dest, "report")

    def test_concurrent_run_guard(self):
        self.freeze()
        with (self.dest / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                F.run(self.dest, "report")

    def test_timeout_preserves_failed_phase(self):
        self.spec["max_seconds"] = 0.2
        self.spec["steps"][0]["argv"][-1] = "sleep"
        self.freeze()
        with self.assertRaises(Exception):
            F.run(self.dest, "report")
        self.assertEqual(F.read(self.dest / "preflight.result.json")["status"], "failed")
        self.assertFalse((self.dest / "preflight.json").exists())

    def test_saved_import_is_explicitly_posthoc_and_readonly(self):
        self.saved_spec()
        self.freeze(saved=True)
        r = F.read(self.dest / "complete.json")
        self.assertEqual(r["status"], "saved_evidence_verified")
        self.assertEqual(r["new_economic_paths"], 0)
        self.assertIn("not rerun", r["accounting_scope"])
        with self.assertRaisesRegex(ValueError, "read-only"):
            F.run(self.dest, "report")
        (self.root / "passed.json").write_text('{"passed":false}')
        with self.assertRaisesRegex(ValueError, "Frozen identity changed"):
            F.load_run(self.dest)

    def test_native_manifest_tamper_is_rejected(self):
        self.saved_spec()
        (self.root / "manifest.json").write_text(json.dumps({"files_sha256":{"data.csv":"0"*64}}))
        self.spec["artifact_manifests"] = [dict(path="manifest.json", field="files_sha256", base=str(self.root))]
        with self.assertRaisesRegex(ValueError, "Native artifact hash mismatch"):
            self.freeze(saved=True)
        self.assertFalse((self.dest / "complete.json").exists())

    def test_enabled_true_is_not_an_accounting_receipt(self):
        self.spec["steps"][2]["checks"][0]["key"] = ["enabled"]
        with self.assertRaisesRegex(ValueError, "positive native pass receipt"):
            self.freeze()

    def test_summary_tamper_invalidates_completion(self):
        self.freeze()
        F.run(self.dest, "report")
        (self.dest / "summary.csv").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Frozen identity changed"):
            F.completion(self.dest, "prospective")

    def test_old_summary_cannot_be_attached_to_new_run(self):
        self.spec["summary"]["path"] = "data.csv"
        with self.assertRaisesRegex(ValueError, "inside the new run directory"):
            self.freeze()

    def test_missing_phase_receipt_invalidates_completion(self):
        self.freeze()
        F.run(self.dest, "report")
        (self.dest / "audit.result.json").unlink()
        with self.assertRaises(FileNotFoundError):
            F.completion(self.dest, "prospective")

    def test_existing_attempt_is_never_refrozen(self):
        self.freeze()
        original = (self.dest / "freeze.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.freeze()
        self.assertEqual((self.dest / "freeze.json").read_bytes(), original)

    def test_optimized_native_checks_are_refused(self):
        with patch.dict(os.environ, {"PYTHONOPTIMIZE":"1"}):
            with self.assertRaisesRegex(ValueError, "Optimized Python is forbidden"):
                self.freeze()

    def test_relative_entry_is_resolved_against_project(self):
        for step in self.spec["steps"]:
            step["argv"][1] = "entry.py"
        self.freeze()
        F.run(self.dest, "report")
        self.assertEqual(self.calls(), F.PHASES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
