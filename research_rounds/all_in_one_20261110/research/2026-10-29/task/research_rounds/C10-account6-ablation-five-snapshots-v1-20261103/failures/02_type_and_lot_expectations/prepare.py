"""Bind five complete original provider snapshots; no account events."""
from pathlib import Path
import sys,json,gzip,pickle,hashlib
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import ar6_policy as E
X=E.X;R=O.parent
def read(p):return json.loads(Path(p).read_text())
def main():
 sources={};cases=[]
 refs=[('2025-07-08',R/'g-s-C-three-batch-causal-preview-20261102/INPUT-C10-2025-07-08.json'),
  ('2025-07-22',R/'replacement-six-package-projection-v1-20261103/INPUT-C10-2025-07-22.json'),
  ('2025-08-13',R/'replacement-six-package-projection-v1-20261103/INPUT-C10-2025-08-13.json'),
  ('2025-08-15',R/'replacement-aug15-package-projection-v1-20261103/INPUT.json')]
 for day,p in refs:
  x=read(p);sources[str(p.resolve())]=X.sha(p);v=x['trusted'];cert=x.get('certificate',x.get('saved_certificate'));res=x.get('original_result',x.get('saved_result'))
  cases.append(dict(day=day,trusted=v,certificate=cert,original_result=res))
 cp=R/'g-s-C-August-continuation-v1-20261102/runs/C10/2025-08-05-CLOSE.pkl.gz';pr=cp.with_name('2025-08-05-CLOSE.provenance.json');side=read(pr);raw=gzip.decompress(cp.read_bytes())
 assert hashlib.sha256(raw).hexdigest()==side['checkpoint_sha256']
 for p,h in side['binding']['source'].items():assert X.sha(p)==h
 sources[str(cp.resolve())]=X.sha(cp);sources[str(pr.resolve())]=X.sha(pr)
 obj=pickle.loads(raw);row=next(z for z in obj.results if z['certificate']['known_at'][:10]=='2025-08-05');cert=row['certificate'];cases.append(dict(day='2025-08-05',trusted=obj.trusted[cert['trusted_id']],certificate=cert,original_result=row['projection']))
 for x in sorted(cases,key=lambda x:x['day']):
  v=x['trusted'];c=x['certificate'];assert E.J.digest(dict(s=v['snapshot'],ds=v['demands'],e=v['evidence'],bb=v['budget_before']))==c['trusted_id'];assert E.J.digest(x['original_result'])==c['projection_hash']
  assert not v['snapshot']['assets'] and not v['snapshot']['other_saved_goal_need']
  p=O/('INPUT-'+x['day']+'.json');X.save(p,x);print('BOUND',x['day'],len(v['demands']),sum(q>0 for q in c['Q'].values()),flush=True)
 for p in [Path(E.B.__file__),Path(E.J.__file__),Path(E.C.__file__),R/'g-s-C-native-synthetic-v3-20261102/native_c.py',O/'ar6_policy.py',O/'prepare.py']:
  sources[str(p.resolve())]=X.sha(p)
 X.save(O/'AUTHORIZATION_AND_FREEZE.json',dict(parent_authorized=True,scope='FIVE_COMPLETE_ORIGINAL_C10_SNAPSHOTS_STATIC_AR6_ONLY',dates=sorted(x['day'] for x in cases),
  financial_events=0,account_runner_allowed=False,ablation_enabled_false='original account risk6 enforced',ablation_enabled_true='only account risk6 admission removed, risk still fully measured',
  unchanged=['sector risk5','account capital90','cash10','stock10','original eligibility/role/priority/target','probe/core constraints','fees','protection','ACT','actual exit locks/reservations'],
  full_candidate_inputs={p.name:X.sha(p) for p in sorted(O.glob('INPUT-*.json'))},sources_sha256=sources,technical_native_check_ceiling=250000,
  not_continuous_paths=True,no_Pareto_no_R0_no_C20=True))
if __name__=='__main__':main()
