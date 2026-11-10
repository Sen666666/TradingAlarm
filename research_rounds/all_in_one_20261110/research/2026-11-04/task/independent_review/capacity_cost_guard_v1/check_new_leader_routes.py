"""Bounded exact saved route/plan/fill witness inspection, no preview/account."""
from pathlib import Path
import json,gzip,hashlib
R=Path('capacity_cost_guard_v1/runs/strong-v1');O=Path(__file__).resolve().parent
SIDS={'601869.SH','688146.SH'}
def book(p):
 with gzip.open(p,'rt')as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt')as f:return[json.loads(s)for s in f]
ds=rows(R/'pair/daily.jsonl.gz');out={};src={}
for arm in ['B','G10','G20','G40','NR20']:
 p=R/'pair'/f'{arm}.json.gz';b=book(p);src[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 actual=[t for t in b['trades']if t['security_id']in SIDS]
 plans=[dict(at=d['at'],intents=[i for i in d['intents']if i['sid']in SIDS])for d in b['decisions']if any(i['sid']in SIDS for i in d['intents'])]
 data={'actual_trades':actual,'max_daily_positions':{sid:max(r['positions'].get(sid,0)for r in ds if r['account']==arm)for sid in SIDS},'native_decision_plans':plans}
 if arm!='B':
  p=R/'pair'/f'{arm}-cost-guard.jsonl.gz';src[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();e=rows(p)
  data['actual_guard_routes']=[r for r in e if r['kind']=='route'and r['sid']in SIDS]
 out[arm]=data
p=O/'NEW_LEADER_NATIVE_WITNESSES.json';p.write_text(json.dumps({'source_sha256':src,'arms':out,'limits':'Original route pre-guard positive quantity is an admission counterfactual only; no claim of actual fill or profit transferred from the baseline.'},indent=2)+'\n')
for arm,v in out.items():
 print(arm,'maxpositions',v['max_daily_positions'])
 print('BUYS',[(t['security_id'],str(t['at'])[:10],str(t.get('signal_at'))[:10],t['shares'],t.get('kind'),t.get('reason'))for t in v['actual_trades']if t['side']=='buy'])
 if arm!='B':
  for r in v['actual_guard_routes']:
   if (r['sid']=='601869.SH'and str(r['at']).startswith('2025-12-19'))or r['sid']=='688146.SH':print('ROUTE',r['sid'],r['at'],r['decision_at'],r['role'],r['selected_quantity'],[(x['pool'],x['pre_guard_legal_quantity'],x['quantity'],x['minimum_reasons'])for x in r['routes']],r.get('budget_order_hint'))
