from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,hashlib
import pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/market-proof-lifecycle-readonly-20261101');W=O.parent;Z=D(0)
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def num(x):return D(str(x))
SM={x['symbol']:x for x in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())};cache={}
def mark(sid,d):
 if sid not in cache:cache[sid]=pd.read_parquet(SM[sid]['refs']['facts'],columns=['raw_close'])
 f=cache[sid];i=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert i>=0;return num(f.iloc[i].raw_close)
out=[]
for s in json.loads((O/'FIXED_CASES_BEFORE_COMPONENT_EXPORT.json').read_text()):
 if s['name'] not in ['BDIAG2022','BDIAG2023']:continue
 p=Path(s['path']);b=gz(p/'B.json.gz');dd={x['at'][:10]:x for x in rows(p/'daily.jsonl.gz')};pd_=s['peak']['at'][:10];ed=s['flat']['at'][:10];peak=dd[pd_];end=dd[ed]
 assert num(end['nav'])==num(b['ending_NAV'])
 assert not [x for x in b['trades'] if x['at'][:10]>ed]
 assert not [x for x in b['audit'] if x['kind']=='dividend_accrual' and x['receivable']['ex_at'][:10]>ed]
 final={x['id']:x for x in b['layers']};journal={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill'};old=[];new=[]
 for x in peak['layers']:
  f=final[x['id']];assert f['qty']==0 and f['closed'][:10]<=ed
  before=num(x['cash'])+num(x['dividend'])+D(x['qty'])*mark(x['sid'],pd_);after=num(f['cash'])+num(f['dividend']);old.append(dict(layer=x['id'],sid=x['sid'],role=x['role'],pool_at_peak=x['pool'],net_at_peak=before,net_at_actual_flat=after,wealth_change=after-before))
 for x in b['layers']:
  if pd_<x['opened'][:10]<=ed:
   assert x['qty']==0 and x['closed'][:10]<=ed;j=journal[x['id']];new.append(dict(layer=x['id'],sid=x['sid'],role=j['role'],pool_at_fill=j['pool'],net=num(x['cash'])+num(x['dividend'])))
 oldnet=sum((x['wealth_change'] for x in old),Z);newnet=sum((x['net'] for x in new),Z);delta=num(end['nav'])-num(peak['nav']);residual=oldnet+newnet-delta;assert abs(residual)<D('.00000001')
 oldroles=defaultdict(lambda:Z);newroles=defaultdict(lambda:Z)
 for x in old:oldroles[x['role']+'|'+x['pool_at_peak']]+=x['wealth_change']
 for x in new:newroles[x['role']+'|'+x['pool_at_fill']]+=x['net']
 r=dict(case=s['name'],peak_day=pd_,actual_flat_day=ed,peak_NAV=peak['nav'],actual_flat_NAV=end['nav'],peak_to_flat_wealth_change=delta,old_peak_live_layers=len(old),old_peak_layers_wealth_change=oldnet,new_actual_fill_layers_after_peak=len(new),new_after_peak_layers_net=newnet,old_net_share_of_total_decline=oldnet/delta,new_net_share_of_total_decline=newnet/delta,
 old_positive_wealth_changes=sum((x['wealth_change'] for x in old if x['wealth_change']>0),Z),old_negative_wealth_changes=sum((x['wealth_change'] for x in old if x['wealth_change']<0),Z),new_positive_net=sum((x['net'] for x in new if x['net']>0),Z),new_negative_net=sum((x['net'] for x in new if x['net']<0),Z),old_by_role_pool=dict(oldroles),new_by_role_pool=dict(newroles),residual=residual,
 scope='accounting cohort bridge, not causal policy PnL; current peak snapshot net carried correctly, no lifetime old profit double-counted; dividends recognized include receivables; all end positions actually flat',old_layers=old,new_layers=new)
 out.append(r)
(O/'PEAK_TO_ACTUAL_FLAT_WEALTH_BRIDGE.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
for r in out:print(json.dumps({k:v for k,v in r.items() if k not in ['old_layers','new_layers']},ensure_ascii=False,default=str))
