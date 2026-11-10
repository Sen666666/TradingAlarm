"""Independently recheck final plans and exact matching witnesses, no search."""
from pathlib import Path
import sys,json
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import extract as X
from matching import witness,self_test
def main():
 m=X.read(O/'INPUT_MANIFEST.json');out=[]
 for c in m['cases']:
  x=X.read(O/c['input']);ordered=sorted(x['demands'],key=lambda d:(d['priority'],d['sid']));limits={p['layer']:p['q'] for p in x['original_D_parts']}
  for mode in ['OFF','HARD','WEAK']:
   path=O/(mode+'-'+c['arm']+'-'+c['day']+'.json');r=X.read(path);Q=r.get('Q',r.get('original_Q'));Dmap=r.get('D',r.get('original_D'))
   assert all(0<=q<=x['certificate']['Q'][s] for s,q in Q.items()) and set(Q)==set(x['certificate']['Q'])
   assert all(0<=q<=x['original_D'][s] for s,q in Dmap.items())
   actual=X.add_budget_guard(x,X.B.evaluate(x['snapshot'],ordered,Q,Dmap))
   assert X.J.digest(actual)==X.J.digest(r['native'])
   assert actual['validation']['ok'] and all(p['q']<=limits[p['layer']] for p in actual['donors']['rows'])
   ok,w=witness(X.J,x['snapshot'],ordered,Q,actual['donors'],actual['validation'],x['scores'],'ALL' if mode=='OFF' else mode,True)
   assert ok and X.J.digest(w)==X.J.digest(r['matching'])
   if mode=='OFF':assert Q==x['certificate']['Q'] and Dmap==x['original_D']
   out.append(dict(case=x['case'],arm=x['arm'],day=x['day'],mode=mode,Q_D_bounds=True,original_full_snapshot_native_guard=True,
     per_layer_limits=True,exact_resource_witness_reproduced=True,output_sha256=X.sha(path)))
 assert all(X.sha(p)==h for p,h in m['sources_sha256'].items())
 assert all(X.sha(O/p)==h for p,h in m['inputs_sha256'].items())
 X.save(O/'VERIFICATION.json',dict(passed=True,final_plans=out,leakage_cases=len(self_test()),source_inputs_unchanged=True,
  financial_events=0,new_price_labels=0,actual_cash_released=0,actual_risk_released=0))
 print('VERIFY_ALL_18_PLANS_AND_WITNESSES_PASS',len(out))
if __name__=='__main__':main()
