"""Read existing month cache; physical day prefix, exact parents and new grants."""
from pathlib import Path
import copy,hashlib,json,sys
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent/'C-rights-Jan13-action-v3-20261102'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/g-s-C-month-continuation-20261102')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 assert not (O/'SOURCE_FREEZE.json').exists(),'already frozen'
 registry=P/'OUTPUT_REGISTRY.json';assert sha(registry)=='8bed1bd324fcee86ac989aa7287c741e63fd15a0bb61ee0adaeb42e878b090f6'
 audit=Path('/tmp/rights-ACTION-output-independent-h40r5bkx/FINAL_AUDIT.json');assert read(audit)['passed']
 source=M/'inputs/2022/MANIFEST.json';m=read(source);cut=O/'inputs/physical';cut.mkdir(parents=True,exist_ok=False);pm=copy.deepcopy(m);removed={}
 for group in ['files','extensions']:
  for k,rec in pm[group].items():
   original=source.parent/rec['path'];assert sha(original)==rec['sha256'];rec['path']=str(original)
 for key,rec in pm['month_extension'].items():
  original=source.parent/rec['path'];assert sha(original)==rec['sha256'];p=cut/rec['path'];p.parent.mkdir(parents=True,exist_ok=True)
  if p.suffix=='.parquet':
   f=pd.read_parquet(original);before=len(f);f=f[f.day<='2022-01-13'];f.to_parquet(p,index=False);removed[key]=before-len(f);rows=len(f)
  else:
   x=read(original)
   if key=='metadata':
    before=sum(map(len,x.values()));x={sid:[v for v in vs if v['observed_day']<='2022-01-13'] for sid,vs in x.items()};removed[key]=before-sum(map(len,x.values()))
   else:
    before=len(x);field={'receipts':'confirmed_day','actions':'effective_date','payments':'paid_at'}[key]
    x=[v for v in x if v.get(field) and v[field][:10]<='2022-01-13'];removed[key]=before-len(x)
   save(p,x);rows=len(x)
  rec.update(sha256=sha(p),rows=rows)
 pm['days']=[d for d in pm['days'] if d<='2022-01-13'];pm['physical_prefix']=dict(last_market_day='2022-01-13',original_daily_fill_proxy_preserved=True,published_calendars_retained=True)
 save(cut/'MANIFEST.json',pm)
 inputs={b:dict(path=str(p),sha256=sha(p)) for b,p in [('full',source),('physical',cut/'MANIFEST.json')]}
 save(O/'INPUT_FREEZE.json',dict(inputs=inputs,removed_future_rows=removed,current_input_only=True,legacy_certificate_input_views_retained_solely_for_genuine_old_verification=True,physical_granularity='daily through Jan13; OPEN uses unchanged same-day HLV postcheck execution proxy'))
 arms={x['arm']:x for x in read(registry)['outputs']};assert set(arms)=={'2022-C10','2022-C_BATCH20'}
 identity=dict(version='C_MONTH_RIGHTS_RESUME_1',parent_registry=str(registry),parent_registry_sha256=sha(registry),ACTION_output_audit=dict(path=str(audit),sha256=sha(audit)),parent_ACTION_identity_sha256=sha(P/'ACTION_IDENTITY.json'),inputs=inputs,input_freeze_sha256=sha(O/'INPUT_FREEZE.json'),arms=arms,no_account_reset=True,no_strategy_or_budget_changes=True)
 save(O/'IDENTITY.json',identity)
 grants={}
 for arm,rec in arms.items():
  for branch,inp in inputs.items():
   p=O/'grants'/(arm+'-'+branch+'.json')
   g=dict(parent_approved=True,scope='C_EXISTING_ACCOUNT_MONTH_CONTINUATION',runtime_identity_sha256=sha(O/'IDENTITY.json'),arm=arm,window='2022',mode=arm[5:],branch=branch,base_ACTION_checkpoint_sha256=rec['sha256'],input_manifest_sha256=inp['sha256'],days=['2022-01-13'],phases=['OPEN','CLOSE'],no_account_reset=True,technical_control=branch=='physical',approval_source='parent 01a1869e-bab0-73ad-a5ca-8b65eb61f01b: two2022 Jan13 remaining OPEN/CLOSE plus physical controls; no Jan14 or2025')
   save(p,g);grants[arm+'|'+branch]=dict(path=str(p),sha256=sha(p))
 save(O/'INITIAL_GRANTS.json',grants)
 files=list(O.glob('*.py'))+[O/'CONTRACT.txt',O/'INPUT_FREEZE.json',O/'IDENTITY.json',O/'INITIAL_GRANTS.json',audit,P/'SOURCE_FREEZE.json',P/'OUTPUT_REGISTRY.json',P/'ACTION_IDENTITY.json',Path(inputs['physical']['path'])]
 files += [Path(v['path']) for v in grants.values()]
 save(O/'SOURCE_FREEZE.json',dict(identity_sha256=sha(O/'IDENTITY.json'),sources={str(p):sha(p) for p in files}))
 print('PREPARED',sha(O/'IDENTITY.json'),flush=True)
if __name__=='__main__':main()
