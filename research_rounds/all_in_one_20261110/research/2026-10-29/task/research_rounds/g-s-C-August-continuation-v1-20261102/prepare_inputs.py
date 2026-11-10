"""Source-only branch files and exact root August authorization; no finance."""
from pathlib import Path
import json,hashlib,shutil
import pandas as pd
P=Path(__file__).resolve().parent;W=P.parent;SRC=W/'g-s-C-AugSep-continuation-readiness-20261102';BASE=SRC/'inputs'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def branch(name,cut):
 out=P/name;out.mkdir(exist_ok=False);m=read(BASE/'MANIFEST.json');removed={}
 for group in ['files','extensions','month_extension','continuation_extension']:
  for key,rec in m[group].items():
   src=BASE/rec['path'];dst=out/rec['path'];dst.parent.mkdir(parents=True,exist_ok=True)
   if group!='continuation_extension':shutil.copy2(src,dst);removed[group+'/'+key]=0;continue
   if src.suffix=='.parquet':
    z=pd.read_parquet(src);before=len(z);z=z[z['day']<=cut];z.to_parquet(dst,index=False);removed[group+'/'+key]=before-len(z)
   else:
    z=read(src)
    if key=='metadata':
     before=sum(map(len,z.values()));z={s:[r for r in rs if r['observed_day']<=cut] for s,rs in z.items()};after=sum(map(len,z.values()))
    else:
     f={'actions':'effective_date','receipts':'confirmed_day','payments':'paid_at'}[key];before=len(z);z=[r for r in z if r.get(f) and r[f][:10]<=cut];after=len(z)
    save(dst,z);removed[group+'/'+key]=before-after
   rec['sha256']=sha(dst);rec['rows']=len(z)
 m['days']=[d for d in m['days'] if d<=cut];m['continuation_data_scope'].update(end=cut,canonical_source_manifest=str(BASE/'MANIFEST.json'),canonical_source_sha256=sha(BASE/'MANIFEST.json'),physical_cut_after=cut,model_recomputations=0)
 save(out/'MANIFEST.json',m);return dict(path=str((out/'MANIFEST.json').resolve()),sha256=sha(out/'MANIFEST.json'),removed=removed,cutoff=cut)
def main():
 states=read(SRC/'STATE_AND_EVENT_PREFLIGHT.json')['states']
 inputs={b:branch('full-August' if b=='full' else 'physical-through-Aug1',c) for b,c in [('full','2025-08-29'),('physical','2025-08-01')]}
 identity=dict(scope='same four own July31 accounts, no reset',inputs=inputs,accounts={k:{f:s[f] for f in ['checkpoint','checkpoint_sha256','NAV','stocks','layers','pending_intents','exit_orders']} for k,s in states.items()},old_input_manifest_sha256=sha(W/'g-s-C-month-continuation-20261102/inputs/2025_26/MANIFEST.json'),input_source_manifest_sha256=sha(BASE/'MANIFEST.json'),sources_recomputed=False)
 save(P/'INPUT_IDENTITY.json',identity)
 paths=[P/n for n in ['august_runtime.py','run_august.py','prepare_inputs.py','compare_gates.py']]
 auth=dict(parent_approved=True,financial_events_authorized=True,scope='FOUR_OWN_JUL31_ACCOUNTS_AUGUST_ONLY',root_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',start='2025-08-01',end='2025-08-29',technical_ceiling=250000,input_identity_sha256=sha(P/'INPUT_IDENTITY.json'),sources={str(p.resolve()):sha(p) for p in paths},cells=list(states),economic_changes=[],no_reset=True,no_July_rerun=True,no_September=True,root_instruction='After thin same-account input/source horizon import and Aug1 source restore/physical/restart gates, continue four own July31 accounts through Aug29. Keep old certificates/R0/Carry. Only unify exact-search technical ceiling, unchanged enumeration and predicates.')
 save(P/'AUTHORIZATION.json',auth);print('AUGUST_INPUT_AUTH_READY',sha(P/'INPUT_IDENTITY.json'),flush=True)
if __name__=='__main__':main()
