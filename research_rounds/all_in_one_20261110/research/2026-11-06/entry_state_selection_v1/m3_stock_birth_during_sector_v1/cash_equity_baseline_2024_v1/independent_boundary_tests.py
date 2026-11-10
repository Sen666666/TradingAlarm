"""Independent AST boundary tests and persisted-output comparisons; no strategy runs."""
from pathlib import Path
from decimal import Decimal as D
from unittest.mock import patch
import ast,copy,json,hashlib
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;E=O.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
nodes={n.name:n for n in ast.parse((O/'engine.py').read_text()).body if isinstance(n,ast.FunctionDef)}
base={'series_id':'S.SZ','currency':'CNY','events':[{'effective_date':'2024-10-01','split_ratio':'1','cash_per_old_share':'0.1'}],'coverage_evidence':[{'path':'/rights','sha256':'h'}]}
results={}
for name,change in [('valid',{}),('wrong_sid',{'series_id':'OTHER'}),('wrong_currency',{'currency':'USD'}),('bad_date',{'events':[{'effective_date':'notdate'}]}),('duplicate_date',{'events':base['events']*2}),('empty_rights',{}),('missing',{})]:
 a=copy.deepcopy(base);a.update(change);files={'/audit/inputs-v1/actions/S.SZ.json':a,'/rights':{'records':[] if name=='empty_rights' else [{}]}}
 if name=='missing':files={}
 g={'AS':Path('/audit'),'Path':Path,'D':D,'pd':pd,'actions_sources':{},'hashes':{},'read':lambda p:copy.deepcopy(files[str(p)]),'sha':lambda p:'h','BRIDGE':True,'EVENT_AT':{},'ALLOWED_EVENT_IDS':None}
 for f in ['local_actions','enabled','unadmitted_action_at']:
  exec(compile(ast.Module(body=[nodes[f]],type_ignores=[]),'independent_audit','exec'),g)
 with patch.object(Path,'exists',lambda p:str(p) in files):
  a=g['local_actions']('S.SZ');bad=name not in ['valid','empty_rights'];assert a['_source_integrity_ok'] is (not bad)
  assert g['unadmitted_action_at']('S.SZ',pd.Timestamp('2024-10-02')) is bad
  assert g['unadmitted_action_at']('S.SZ',pd.Timestamp('2024-10-01'))
  if name=='empty_rights':assert a['_source_coverage_status']=='COVERAGE_UNKNOWN'
  g['BRIDGE']=False;assert not g['unadmitted_action_at']('S.SZ',pd.Timestamp('2024-10-01'))
  results[name]={'passed':True,'coverage':a['_source_coverage_status'],'issues':a['_source_issues']}
# Disabled registry event must not bypass finite-scope guard.
d=pd.Timestamp('2024-10-01');g.update(BRIDGE=True,EVENT_AT={('S.SZ',d):{'economic_event_id':'E'}},ALLOWED_EVENT_IDS=set(),local_actions=lambda sid:dict(events=base['events'],_source_integrity_ok=True))
assert g['unadmitted_action_at']('S.SZ',d);g['ALLOWED_EVENT_IDS']={'E'};assert not g['unadmitted_action_at']('S.SZ',d)
results['disabled_known_event_scope']={'passed':True}
# Independently compare all original columns, not merely parent QA booleans.
tables={}
for name,keys in [('ROUNDS',['round_id']),('ACTIONS',['round_id','day','side']),('DECISIONS',['event_id']),('RANKING_AUDIT',['event_id']),('END_STATES',['round_id'])]:
 old=pd.read_csv(E/'relative_priority_v1/baseline'/f'{name}.csv',low_memory=False);old=old[old.window.eq('2024_924')].sort_values(keys).reset_index(drop=True)
 new=pd.read_csv(O/'bridge_off'/f'{name}.csv',low_memory=False).sort_values(keys).reset_index(drop=True)
 assert len(old)==len(new)
 for col in old:
  assert col in new or old[col].isna().all()
  if col not in new:continue
  a,b=new[col],old[col]
  if pd.api.types.is_numeric_dtype(b) and not pd.api.types.is_bool_dtype(b):
   assert np.allclose(pd.to_numeric(a,errors='coerce'),pd.to_numeric(b,errors='coerce'),rtol=1e-12,atol=1e-7,equal_nan=True),(name,col)
  else:
   norm=lambda x: '' if pd.isna(x) else str(x)[:10] if len(str(x))>10 and str(x)[4:5]=='-' and str(x)[7:8]=='-' and str(x)[10:11] in (' ','T') else str(x)
   assert a.map(norm).equals(b.map(norm)),(name,col)
 tables[name]={'rows':len(old),'original_columns':len(old.columns),'pass':True}
for folder in ['units','cases','bridge_off']:
 q=json.loads((O/folder/'QA.json').read_text());assert q['engine_sha256']==sha(O/'engine.py') and q['driver_sha256']==sha(O/'run.py')
# Independently reconcile case register inventory from its pre-record trading ledger.
cases=[]
for q in json.loads((O/'cases/QA.json').read_text())['cases']:
 p=O/'cases'/q['sid'];a=pd.read_csv(p/'ACTIONS.csv');claims=json.loads((p/'CLAIMS.json').read_text())
 if claims:
  c=claims[0];rec=pd.Timestamp(c['record_date']);n=sum(int(x.q)*(1 if x.side.startswith('buy') else -1) for x in a.itertuples() if pd.Timestamp(x.day)<=rec)
  assert n==c['record_q'] and D(c['amount'])==D(n)*D(c['d_cash'])*D('.8') and c['owner_round_id']==q['round_id']
  ledger=pd.read_csv(p/'CLAIM_LEDGER.csv');assert list(ledger.event)==['ACCRUE_NET80','PAY_CLOSE_TRANSFER'];assert len(claims)==1
 else:assert q['record_q']==0 and q['claim_count']==0
 cases.append({'sid':q['sid'],'register_q':q['record_q'],'pass':True})
out={'engine_sha256':sha(O/'engine.py'),'driver_sha256':sha(O/'run.py'),'boundary_tests':results,'bridge_off_independent_comparison':tables,'case_inventory_reconciliation':cases,'economic_runs':0}
(O/'INDEPENDENT_BOUNDARY_QA.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
