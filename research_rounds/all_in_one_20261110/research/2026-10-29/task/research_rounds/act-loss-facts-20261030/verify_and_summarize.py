from pathlib import Path
import json,csv,gzip,importlib.util,time
from decimal import Decimal as D
from datetime import datetime
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');B=R/'pvr-local-finite-capital-20261029/baseline';Z=D(0)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
raw=json.loads((B/'accounts-v2/I__S0_base.json').read_text());fills=[x for x in raw['audit_log'] if x['kind']=='fill']
sp=importlib.util.spec_from_file_location('act_loss_verification_helpers',R/'s-entry-mechanism-audit-20261029/code/audit.py');H=importlib.util.module_from_spec(sp);sp.loader.exec_module(H)
_,m,_,_=H.context({x['receipt']['security_id'] for x in fills},False)
for x in fills:
 r=x['receipt'];tm=datetime.fromisoformat(r['at']);fee=m.fees(r['security_id'],tm).incremental(r['side'],D(r['gross_cny']),{}, {},1,shares=r['shares'],par_value=m.rules.get('security_metadata',{}).get(r['security_id'],{}).get('par_value'))
 assert fee=={k:D(v) for k,v in x['fee_components'].items()}
 assert sum(fee.values(),Z)==D(r['fees_cny'])
 w=m.window(r['security_id'],tm,r['side'],1);assert w is not None and w.raw_open==D(x['raw_open']) and w.execution_price==D(x['price'])
with gzip.open(B/'accounts-v2/daily.jsonl.gz','rt') as f:daily=[x for l in f if (x:=json.loads(l))['account']=='I__S0_base']
hold=list(csv.DictReader((O/'actual-holding-close-paths.csv').open()));values={};qsum={}
for x in hold:
 values[x['day']]=values.get(x['day'],Z)+D(x['shares'])*D(x['raw_mark']);qsum.setdefault(x['day'],{})[x['symbol']]=int(x['shares'])
for x in daily:
 day=x['at'][:10];assert values.get(day,Z)==D(x['inventory']);assert qsum.get(day,{})=={s:int(q) for s,q in x['positions'].items() if int(q)}
v=json.loads((O/'VERIFICATION.json').read_text());v.update(independent_actual_fee_components=138,independent_raw_open_slippage_matches=138,independent_daily_inventory_matches=len(daily),verification_extra_seconds=time.monotonic()-T);save('VERIFICATION.json',v)
c=pd.read_csv(O/'synchronous-candidate-observations.csv');s=c[(c.relative_same_start>0)&(~c.already_pending)&(~c.already_accepted)].copy();s.to_csv(O/'same-start-unordered-candidates.csv',index=False)
summ=dict(common_start_all_observations=int((c.relative_same_start>0).sum()),common_start_unordered_observations=len(s),common_start_unordered_cycles=int(s.held_cycle.nunique()),common_start_unordered_cycle_days=len(s[['held_cycle','date']].drop_duplicates()),common_start_unordered_stocks=int(s.candidate.nunique()),common_start_unordered_structures=int(s.candidate_event.nunique()),next_market_proxy_pass=int((s.next_market_proxy&s.ACT_on).sum()),common21_missing=int(c.relative_21sessions.isna().sum()),first_unordered_examples=json.loads(s.sort_values(['date','candidate']).groupby('held_cycle').head(1).to_json(orient='records')))
save('COMMON_START_SUMMARY.json',summ)
rs=list(csv.DictReader((R/'broad-stage-reentry-20261029/analysis/campaigns.csv').open()));rs=[x for x in rs if x['account']=='N1'];save('EXISTING_N1_COUNTS.json',dict(source='broad-stage-reentry-20261029/analysis/campaigns.csv; account N1; no replay',cycles=len(rs),positive=sum(D(x['net_pnl'])>0 for x in rs),negative=sum(D(x['net_pnl'])<0 for x in rs),open=sum(x['closed']!='True' for x in rs),positive_contribution=sum((D(x['net_pnl']) for x in rs if D(x['net_pnl'])>0),Z),negative_loss=-sum((D(x['net_pnl']) for x in rs if D(x['net_pnl'])<0),Z),net=sum((D(x['net_pnl']) for x in rs),Z)))
print(json.dumps(dict(verification=v,common_start=summ),ensure_ascii=False,default=str),flush=True)
