"""Read-only post-run binding of actual source-read sets to approved bytes."""
from pathlib import Path
import argparse,hashlib,json,sys
O=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent
sys.dont_write_bytecode=True;sys.path.insert(0,str(O))
from runtime import verify_original
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True);w=p.parse_args().window
auth=read(O/'ROOT_DMI_AUTHORIZATION.json');plan={str(Path(p).resolve()):h for p,h in auth['input_sha256'].items()}
assert all(plan[str(Path(p).resolve())]==h for p,h in auth['input_sha256'].items())
out={}
verified={}
for name in ['joint/SOURCE_HASHES.json','MARKET_SOURCES.json']:
 values=read(O/('dmi_'+w)/name);aliases=[]
 for p,h in values.items():
  q=str(Path(p).resolve());assert plan.get(q)==h,('UNPLANNED_ACTUAL_READ',name,p)
  if q not in verified:assert sha(q)==h;verified[q]=h
  assert verified[q]==h
  if p!=q:aliases.append(dict(logical=p,resolved=q,sha256=h))
 out[name]=dict(entries=len(values),unique_resolved_entries=len({str(Path(p).resolve()) for p in values}),aliases=aliases,all_read_inputs_approved_and_bytes_verified=True)
verify_original()
result=dict(status='PASS_POSTERIOR_ACTUAL_SOURCE_BINDINGS_AND_FROZEN_ORIGINAL_SEAL',window=w,actual_source_sets=out,unique_actual_sources=len(verified),original_all_frozen_outputs_verified=True,root_authorization_sha256=sha(O/'ROOT_DMI_AUTHORIZATION.json'),post_economic_audit_sha256=sha(A/('POSTERIOR_'+w+'.json')),auditor_economic_runs=0)
with (A/('SOURCE_BINDINGS_'+w+'.json')).open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result,indent=2))
