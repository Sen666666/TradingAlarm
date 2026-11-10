"""Past-only necessary-condition ceiling, not a candidate policy test."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D, getcontext
from datetime import datetime
import json,hashlib,csv
import pandas as pd
getcontext().prec=60
O=Path(__file__).resolve().parent;T=O.parent/'timeline';E=O.parents[1];Z=D(0);SRC={}
def read(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def at(x):return datetime.fromisoformat(x)
def agg(z):
 return dict(fills=len(z),stocks=len({x['sid'] for x in z}),actual_buycash=sum((D(x['cost']) for x in z),Z),net=sum((D(x['net']) for x in z),Z),positive=sum((max(Z,D(x['net'])) for x in z),Z),negative=sum((min(Z,D(x['net'])) for x in z),Z),open_layers=sum(bool(x['qty']) for x in z))
def main():
 save('CEILING_SCOPE.json',dict(before_new_ceiling_values=True,question='Necessary-condition scope of same-stock>=2 consecutive completed net-trading-cash-negative campaigns; no progress/admin/giveback exclusions are applied, so this is broader than a valid candidate.',price_subset='At decision current close<=max known held-close high of all trailing negative completed campaigns; current-only necessary check, not a release latch. Unknown retained.',not_policy=True,no_quantity_solver=True,no_account=True))
 man=read(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'));sm={x['symbol']:x for x in man};frames={}
 def high(sid,c,byid):
  if sid not in frames:
   m=sm[sid];p=Path(m['refs']['facts']);h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==m['output_sha256'][str(p)];SRC[str(p)]=h;frames[sid]=pd.read_parquet(p,columns=['close','segment_id'])
  f=frames[sid];lo=min(byid[l]['actual_fill_at'][:10] for l in c['layer_ids']);w=f.loc[(f.index>=pd.Timestamp(lo))&(f.index<pd.Timestamp(c['closed_at'][:10]))]
  return None if w.empty or w.segment_id.nunique()!=1 else dict(high=float(w.close.max()),segment=str(float(w.iloc[-1].segment_id)))
 results={}
 for ref in ['2022_2024','strong']:
  rows=read(T/(ref+'_DECISION_TIMELINE.json'));byid={x['layer']:x for x in rows};cycles=read(T/(ref+'_COMPLETED_STOCK_CYCLES.json'));out=[]
  for x in rows:
   prior=sorted((c for c in cycles.get(x['sid'],[]) if at(c['closed_at'])<at(x['decision_at'])),key=lambda c:at(c['closed_at']));streak=[]
   for c in reversed(prior):
    if D(c['net_trade_cash'])>=0:break
    streak.append(c)
   hs=[high(x['sid'],c,byid) for c in streak] if len(streak)>=2 else []
   comparable=bool(hs) and all(h is not None and h['segment']==x['stock_price_position']['segment_id'] for h in hs)
   h=max(z['high'] for z in hs) if comparable else None
   out.append(dict(x,prior_consecutive_negative_campaigns=len(streak),prior_negative_cycle_layer_ids=[c['layer_ids'] for c in streak],prior_negative_cash=sum((D(c['net_trade_cash']) for c in streak),Z),failure_high_ceiling=h,no_higher_price_necessary=(float(x['stock_price_position']['close'])<=h if h is not None else None)))
  scopes={'ALL':out}
  if ref=='2022_2024':scopes.update(two_year=[x for x in out if x['actual_fill_at'][:10]<='2023-12-29'],post303=[x for x in out if x['actual_fill_at'][:10]>'2024-10-08'])
  summary={}
  for name,z in scopes.items():
   flags=[x for x in z if x['prior_consecutive_negative_campaigns']>=2];mobile=[x for x in flags if x['role']=='mobile'];nohigh=[x for x in mobile if x['no_higher_price_necessary'] is True]
   summary[name]=dict(all=agg(z),at_least_two_completed_negative_all_roles=agg(flags),at_least_two_completed_negative_mobile=agg(mobile),mobile_current_not_above_failed_high=agg(nohigh),mobile_unknown_high=agg([x for x in mobile if x['no_higher_price_necessary'] is None]),by_action={a:dict(all=agg([x for x in z if x['action']==a]),two_negative_mobile=agg([x for x in mobile if x['action']==a]),no_higher_price_mobile=agg([x for x in nohigh if x['action']==a])) for a in sorted({x['action'] for x in z})})
  old=read(E/'local_high'/(ref+'_FIXED_TAILS.json'));matches={x['layer'] for t in old for x in t['matched_actual_No60_rows']};summary['fixed_tail_correspondence']=dict(original_members=len(old),actual_matches=len(matches),two_negative_mobile=agg([x for x in out if x['layer'] in matches and x['role']=='mobile' and x['prior_consecutive_negative_campaigns']>=2]),no_higher_price_mobile=agg([x for x in out if x['layer'] in matches and x['role']=='mobile' and x['prior_consecutive_negative_campaigns']>=2 and x['no_higher_price_necessary'] is True]))
  results[ref]=summary
  save(ref+'_CEILING_ROWS.json',[{k:x[k] for k in ['layer','sid','name','role','action','decision_at','actual_fill_at','cost','net','qty','prior_consecutive_negative_campaigns','prior_negative_cycle_layer_ids','prior_negative_cash','failure_high_ceiling','no_higher_price_necessary']} for x in out])
 save('CEILING_RESULTS.json',results);save('CEILING_SOURCES.json',dict(sources=SRC,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),new_account_events=0,not_candidate_scope=True))
 print(json.dumps(results,ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':main()
