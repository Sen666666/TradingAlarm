"""Empty-directory success/error smoke; no account or strategy is loaded."""
from pathlib import Path
import gzip,hashlib,importlib.util,json,pickle,tempfile
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'_shared/research_output_io.py'
spec=importlib.util.spec_from_file_location('R1_shared_atomic_output_io',SOURCE)
IO=importlib.util.module_from_spec(spec);spec.loader.exec_module(IO)
def main():
 root=Path(tempfile.mkdtemp(prefix='research-output-io-smoke-',dir='/tmp'));assert list(root.iterdir())==[]
 targets=dict(prefix_full=root/'prefix/full/pair',prefix_physical=root/'prefix/physical/pair',checkpoint=root/'checkpoints/state.pkl',final=root/'final/pair',failure=root/'failures/ERROR.json')
 preflight=IO.prepare_targets(targets,directory_keys={'prefix_full','prefix_physical','final'});checks=[]
 checks.append('all five output families prepared from empty directory')
 IO.write_json(targets['prefix_physical']/'GATE.json',{'passed':True});assert json.loads((targets['prefix_physical']/'GATE.json').read_text())['passed'];checks.append('nested prefix JSON success')
 IO.write_pickle(targets['checkpoint'],{'cash':'1000000','qty':200});assert pickle.loads(targets['checkpoint'].read_bytes())['qty']==200;checks.append('checkpoint pickle success')
 gz=targets['final']/'daily.jsonl.gz';IO.write_gzip_jsonl(gz,[{'d':1},{'d':2}])
 with gzip.open(gz,'rt') as f:assert [json.loads(x)['d'] for x in f]==[1,2]
 checks.append('final gzip stream success')
 old=hashlib.sha256(targets['checkpoint'].read_bytes()).hexdigest()
 try:IO.write_pickle(targets['checkpoint'],{'bad':lambda:None})
 except (pickle.PicklingError,AttributeError):pass
 else:raise AssertionError('expected pickle serialization failure')
 assert hashlib.sha256(targets['checkpoint'].read_bytes()).hexdigest()==old;checks.append('failed checkpoint preserves prior target')
 old=hashlib.sha256(gz.read_bytes()).hexdigest()
 try:IO.write_gzip_jsonl(gz,[{'ok':1},{'bad':object()}])
 except TypeError:pass
 else:raise AssertionError('expected stream serialization failure')
 assert hashlib.sha256(gz.read_bytes()).hexdigest()==old;checks.append('mid-stream failure preserves prior final')
 aborted=root/'prefix/aborted/sub/new.bin'
 try:
  with IO.atomic_binary(aborted) as f:f.write(b'incomplete');raise RuntimeError('injected write failure')
 except RuntimeError as e:IO.write_json(targets['failure'],{'expected':True,'action':'injected prefix write','reason':str(e)})
 assert not aborted.exists() and json.loads(targets['failure'].read_text())['expected'];checks.append('new-target failure leaves no partial file and failure report is saved')
 assert not list(root.rglob('*.tmp'));checks.append('no temporary output leftovers')
 save_module=SimpleNamespace(save=lambda p,v:Path(p).write_text(json.dumps(v)))
 class FakeRunner:
  def checkpoint(self,out,event):
   out=Path(out);out.mkdir(exist_ok=True);(out/'checkpoint.pkl').write_bytes(b'complete-state');save_module.save(out/'checkpoint.json',{'at':event})
  def dump_joint(self,path):
   path=Path(path);path.mkdir(exist_ok=True);(path/'B.json.gz').write_bytes(b'complete-journal')
   if self.fail:raise RuntimeError('injected export failure')
   save_module.save(path.parent/'R1_AUDIT.json',{'complete':True})
 fake=FakeRunner();fake.fail=False;original=fake.__class__;old_save=save_module.save;wrapped=root/'runner-boundary'
 with IO.atomic_runner_outputs(fake,save_module,wrapped):
  fake.checkpoint(wrapped,'T');fake.dump_joint(wrapped/'prefix-physical-source/pair')
 assert fake.__class__ is original and save_module.save is old_save
 assert (wrapped/'checkpoint.pkl').read_bytes()==b'complete-state'
 assert json.loads((wrapped/'prefix-physical-source/R1_AUDIT.json').read_text())['complete'];checks.append('runner checkpoint/prefix/side-audit staging and identity restoration')
 final=wrapped/'pair/B.json.gz';IO.write_bytes(final,b'old-complete');fake.fail=True
 try:
  with IO.atomic_runner_outputs(fake,save_module,wrapped):fake.dump_joint(wrapped/'pair')
 except RuntimeError:pass
 else:raise AssertionError('expected runner export failure')
 assert final.read_bytes()==b'old-complete' and json.loads((wrapped/'failure/ERROR.json').read_text())['error_type']=='RuntimeError'
 assert fake.__class__ is original and save_module.save is old_save;checks.append('runner export failure preserves prior final and saves failure evidence')
 payload=dict(passed=True,checks=len(checks),details=checks,temp_evidence_root=str(root),preflight=preflight,source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),scope='I/O only; no economic replay or trading-code change')
 IO.write_json(ROOT/'OUTPUT_IO_SMOKE.json',payload);print(json.dumps(payload,indent=2))
if __name__=='__main__':main()
