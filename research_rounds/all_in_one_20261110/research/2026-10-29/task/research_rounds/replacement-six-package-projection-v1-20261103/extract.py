"""Extract original trusted arithmetic inputs. Never call an account event."""
from pathlib import Path
import sys,json,pickle,gzip,hashlib,copy
O=Path(__file__).resolve().parent;R=O.parent
sys.path.insert(0,str(R/'g-s-C-August-continuation-v1-20261102'))
import august_runtime as A
C=A.R.M.C;B=C.B;J=C.J
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def budget_book(x):
 v=x['trusted'];raw=v['budget_before'];cls=A.R.M.BatchBook if x['old_budget_mode']=='C_BATCH20' else A.R.M.OffBook
 return cls.loads(raw,trusted_sha256=hashlib.sha256(raw.encode()).hexdigest(),account_id=v['snapshot']['account_id'],source_binding=J.digest(v['snapshot']),actual_commitments=json.loads(raw)['body']['lines'])
def add_budget_guard(x,result):
 if x['old_budget_mode']=='C_BATCH20':
  a=budget_book(x).preview({str(p['layer']):p['q'] for p in result['donors']['rows']});result['batch20']=a
  result['validation']['checks'].append(dict(stage='full_batch_D',constraint='opportunity_gross_batch20',value=str(J.D(a['carry'])+J.D(a['already_new'])+J.D(a['additional'])),limit=a['limit'],residual=a['residual']))
  if not a['ok']:result['validation']['ok']=False;result['validation']['violations'].append('opportunity_gross_batch20')
 return result
def main():
 cases=read(R/'replacement-quality-design-v1-20261102/SAMPLE_BINDING.json')['cases'];source={};out=[]
 scores=read(R/'replacement-quality-six-batches-v2-20261102/ALL_ROWS.json')
 sp=R/'replacement-quality-six-batches-v2-20261102/ALL_ROWS.json';source[str(sp)]=sha(sp)
 for c in cases:
  arm,day=c['arm'],c['signal_close'][:10]
  if arm=='2022-C10':root=R/'g-s-C-month-continuation-20261102/runs/2022-C10'
  elif day[:7]=='2025-07':root=R/'g-s-C-month-continuation-20261102/runs/2025_26-C10'
  else:root=R/'g-s-C-August-continuation-v1-20261102/runs'/arm
  pp=root/(day+'-CLOSE.pkl');gz=pp.with_suffix('.pkl.gz');pr=root/(day+'-CLOSE.provenance.json');pro=read(pr)
  physical=pp if pp.exists() else gz;payload=physical.read_bytes() if pp.exists() else gzip.decompress(gz.read_bytes())
  assert hashlib.sha256(payload).hexdigest()==pro['checkpoint_sha256'],'checkpoint bytes not original'
  source[str(physical)]=sha(physical);source[str(pr)]=sha(pr)
  obj=pickle.loads(payload)
  for p,h in pro['binding']['source'].items():assert sha(p)==h,'source changed: '+p
  row=next(z for z in obj.results if z['certificate']['certificate_id']==c['certificate'])
  cert=row['certificate'];v=obj.trusted[cert['trusted_id']]
  assert J.digest(dict(s=v['snapshot'],ds=v['demands'],e=v['evidence'],bb=v['budget_before']))==cert['trusted_id']
  assert J.digest(v['snapshot'])==cert['snapshot_hash']
  assert J.digest(row['projection'])==cert['projection_hash']
  assert not v['snapshot']['assets'] and not v['snapshot']['other_saved_goal_need'],'unsupported external coverage asset'
  ss,dd,rank=C.transform(copy.deepcopy(v['snapshot']),copy.deepcopy(v['demands']),v['evidence'])
  q={s:q for s,q in cert['Q'].items() if q};dp=cert['D'];rr=[r for r in scores if r['case']==c['certificate']]
  sr={r['sid']:{k:r['signal'][k] for k in ['PVR','stock_H1','I_target','G1_grade','CP1_market_receipt','name']} for r in rr}
  assert set(sr)==set(q)|set(dp)
  save(O/('INPUT-'+arm+'-'+day+'.json'),dict(arm=arm,day=day,case=c['certificate'],contract_sha256=sha(O/'CONTRACT.txt'),
    trusted=v,certificate=cert,original_result=row['projection'],snapshot=ss,demands=dd,rank_binding=rank,scores=sr,
    original_positive_Q=q,original_D=dp,original_D_parts=row['projection']['donors']['rows'],
    old_budget_mode=obj.mode,checkpoint_sha256=pro['checkpoint_sha256'],no_account_event=True))
  out.append(dict(arm=arm,day=day,case=c['certificate'],Q_stocks=len(q),D_stocks=len(dp),D_layers=len(row['projection']['donors']['rows']),
    input='INPUT-'+arm+'-'+day+'.json',checkpoint=str(physical),observed_guard_source_unchanged=True))
  print('EXTRACTED',arm,day,'Q/D/layers',len(q),len(dp),len(row['projection']['donors']['rows']),flush=True)
 save(O/'INPUT_MANIFEST.json',dict(contract_sha256=sha(O/'CONTRACT.txt'),cases=out,sources_sha256=source,
   inputs_sha256={r['input']:sha(O/r['input']) for r in out},financial_events=0,account_event_calls=0))
if __name__=='__main__':main()
