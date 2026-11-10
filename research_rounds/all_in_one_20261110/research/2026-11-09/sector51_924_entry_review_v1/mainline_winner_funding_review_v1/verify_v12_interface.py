"""Independent frozen V12 review. Synthetic/scalar checks only, no Data or history.
Official test output writes are redirected to this review directory only.
"""
from pathlib import Path
from unittest.mock import patch
import importlib.util,hashlib,json,sys,contextlib,io
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent.parent
P=ROOT/"mainline_candidate_v12_winner_funding_competition"
OUT=Path(__file__).resolve().parent
EXPECTED={"engine.py":"2e37d2a20e33760ffdb1b1b9ba84f8edce7492a3162880ba800759d8773cdd72",
"synthetic_tests.py":"808f541527f67fdbe1090269a2dd61d6959e41fff044d0a9a9e341a3a9764b53",
"SYNTHETIC_QA.json":"a847e01cc965d541c7bdda62e23a0a01404c95c8018aa9f8c38099b858f9679b",
"SOURCE_HASHES.json":"7e78f1851781f89c168123585d0d807d9f00527f7f1885a7e158fb95d3b50554"}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert all(sha(P/n)==v for n,v in EXPECTED.items())
source=json.loads((P/"SOURCE_HASHES.json").read_text())["files"]
assert all(sha(p)==v for p,v in source.items())
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
original_write=Path.write_text
def redirect(self,*a,**kw):
 if self.parent.resolve()==P.resolve() and self.name in {"SYNTHETIC_QA.json","SYNTHETIC_SCALE.json","INPUT_TYPE_QA.json"}:
  return original_write(OUT/("V12_INDEPENDENT_"+self.name),*a,**kw)
 raise AssertionError("Unexpected test write:"+str(self))
with patch.object(Path,"write_text",redirect),contextlib.redirect_stdout(io.StringIO()):
 t=load("v12_final_independent_tests",P/"synthetic_tests.py");t.run()
 it=load("v12_final_independent_types",P/"input_type_tests.py");types=it.run()
with contextlib.redirect_stdout(io.StringIO()):
 ns={"__name__":"review_extras"};exec(compile((OUT/"v12_extra_checks.py").read_text(),str(OUT/"v12_extra_checks.py"),"exec"),ns)
extra=ns["RESULT"]
qa=json.loads((OUT/"V12_INDEPENDENT_SYNTHETIC_QA.json").read_text())
assert qa["assertions"]==101 and qa["result"]=="PASS" and extra["count"]==8
assert all(sha(P/n)==v for n,v in EXPECTED.items())
assert all(sha(p)==v for p,v in source.items())
report=dict(result="PASS_FOR_ONE_FROZEN_OFFLINE_EXPERIMENT",engine_sha256=EXPECTED["engine.py"],
tests_sha256=EXPECTED["synthetic_tests.py"],source_manifest_sha256=EXPECTED["SOURCE_HASHES.json"],
native_and_contract_assertions=qa["assertions"],independent_extra_assertions=extra["count"],
scalar_samples=len(types["samples"]),source_files_verified=len(source),source_unchanged_after_review=True,
original_methods_unchanged=t.e.self_check()["unchanged_methods"],
extra_checks=extra["checks"],history_run=False,real_Data_constructed=False,
remaining_blockers=[],not_certified=["economic efficacy","point-in-time source certification","real-world fills","actual 93-day runtime scale"],
scope="Frozen original M7 plus minimal-A funding competition; standalone selector and real native-interface synthetic checks only.",
test_output_redirect="Only official test QA/scale/type JSON writes rerouted into review folder; test predicates and candidate files unchanged.")
(OUT/"V12_INDEPENDENT_INTERFACE_QA.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2))
