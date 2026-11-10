"""Saved-state protection audit and instantaneous capacity arithmetic only."""
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal as D
import json,gzip,collections,math
import numpy as np,pandas as pd
import launch_v3 as L
J=L.J;O=J.O/'risk-occupancy-diagnostic'
def rows(p):
 with gzip.open(p,'rt') as f:
  for x in f:yield json.loads(x)
def dist(values):
 return dict(n=len(values),minimum=float(min(values)),p25=float(np.quantile(values,.25)),median=float(np.median(values)),p75=float(np.quantile(values,.75)),maximum=float(max(values))) if values else dict(n=0)

def main():
 assert L.read(O/'DONE.json')['completed'];a=json.load(gzip.open(J.O/'run-universe/pair/B.json.gz','rt'))
 sm={r['symbol']:r for r in L.read(L.U/'STOCK_MANIFEST.json')};facts={};cp={}
 def fact(sid):
  if sid not in facts:facts[sid]=pd.read_parquet(sm[sid]['refs']['facts'])
  return facts[sid]
 def cpline(sid):
  if sid not in cp:cp[sid]=pd.read_parquet(sm[sid]['refs']['CP1'])
  return cp[sid]
 buys={t['layer']:t for t in a['trades'] if t['side']=='buy'};exit_at={}
 for r in a['audit']:
  if r['kind']=='pilot_layer_exit':
   for lid in r['layers']:exit_at[lid]=min(exit_at.get(lid,r['at']),r['at'])
 audit=[]
 for path in sorted(O.glob('FIRST_EXCLUSIVE_URFI*.json')):
  if path.stem.endswith('_NAMED'):continue
  snap=L.read(path);major={l for s in snap['top10_stocks'] for l in s['lots']}
  for x in snap['lots']:
   if x['batch'] not in major:continue
   lid=int(x['batch']);t=buys[lid];sid=x['stock'];f=fact(sid);z=cpline(sid);line=D(t['floor']);known=snap['signal_evidence_known_at'][:10]
   for day,r in f.loc[t['at'][:10]:known].iterrows():
    date=str(day.date());valid=pd.notna(r.i_target) and bool(r.i_target)
    if x['role']=='core':
     if valid and pd.notna(r.i_floor):line=D(str(r.i_floor))
    else:
     if exit_at.get(lid,'9999')[:10]<=date:break
     if not valid:break
     if D(str(r.close))<=line:break
     if pd.notna(r.i_floor):line=max(line,D(str(r.i_floor)))
     if day in z.index and bool(z.loc[day,'receipt']):line=max(line,D(str(z.loc[day,'candidate'])))
   at=pd.Timestamp(snap['at'][:10]);factor=D(str(f.loc[:at].iloc[-1].factor));expected=float(line/factor);gap=x['effective_raw_floor']-expected
   audit.append(dict(snapshot=path.name,stock=sid,batch=lid,role=x['role'],adjusted_expected_line=str(line),current_factor=str(factor),expected_raw_line=expected,actual_raw_line=x['effective_raw_floor'],difference=gap,passed=abs(gap)<1e-8,
    semantics='core latest decision-known original I floor; mobile original max(entry,I floor,new CP1 candidate) while no latched exit; no invented closer line'))
 L.save(O/'TOP_RISK_PROTECTION_AUDIT.json',dict(passed=all(x['passed'] for x in audit),audited_layer_snapshots=len(audit),maximum_abs_line_difference=max(abs(x['difference']) for x in audit),rows=audit))

 # Original execution helpers, with only rule/protocol tables loaded. No market
 # runner/account is instantiated for the additional capacity arithmetic.
 Base=J.M.E.FastMarket.__mro__[1];market=Base.__new__(Base)
 market.rules=L.read(WROOT/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
 market.protocol=L.read(J.BP.C.OLD/'inputs-v2/economic-protocol.json')
 original_globals=Base.__init__.__globals__;records={r['series_id']:r for r in L.read(J.M.P/'manifest.json')['series']};raw={}
 def opening(sid,at):
  if sid not in raw:
   p=original_globals['checked_ref'](records[sid]['raw'],J.BP.C.OLD/'inputs-v2')
   q=original_globals['read_raw'](p,records[sid]);raw[sid]=q.loc[J.START:J.END,'open'].copy()
  return D(str(raw[sid].loc[pd.Timestamp(at.date())]))
 intents={(x['at'][:10],i['sid'],i['role']):i for x in a['decisions'] for i in x['intents']}
 meta=L.read(WROOT/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');items=[]
 assert J.LR.SLIP==D('.0005')
 for r in rows(O/'ROUTED_MOBILE.jsonl.gz'):
  if r['actual_reason']!='account_risk':continue
  assert r['without_account_check_route']
  sid=r['sid'];at=J.M.N.iso(r['at']);i=intents[(r['signal_at'][:10],sid,'mobile')];rule=Base.quantity(market,sid,at);schedule=Base.fees(market,sid,at)
  op=opening(sid,at);p=op*(D(1)+J.LR.SLIP);factor=D(str(fact(sid).loc[:pd.Timestamp(at.date())].iloc[-1].factor));floor=D(i['floor'])/factor;budget=D(i['budget']);cap=i['cap']
  target=J.LR.maximum_quantity(rule,min(cap,int(budget/p)),lambda q:D(q)*p<=budget)
  minq=rule.buy_minimum;cfmax=r['without_account_check_route'][0];assert minq<=cfmax<=target
  pre=r['resources_before'];nav=pre['marked_NAV'];lastnav=float(pre['last_decision_NAV'])
  def need(q):
   fee=float(J.LR.fees(q,p,schedule,'buy',D(meta[sid]['par_value'])))
   return max(0.,pre['total_risk']+q*max(0.,float(p-floor))-.03*(nav-pre['pending_fees']-fee))
  minimum=need(minq);target_legal=target<=cfmax
  items.append(dict(stock=sid,sector=r['sector'],signal_day=r['signal_at'][:10],execution=r['at'],minimum_quantity=minq,original_preview_target=target,
   max_quantity_all_other_checks=cfmax,min_extra_nominal_risk_cny=minimum,min_extra_pct_last_decision_NAV=100*minimum/lastnav,
   target_all_other_checks_allow=target_legal,target_extra_nominal_risk_cny=need(target) if target_legal else None,
   target_extra_pct_last_decision_NAV=100*need(target)/lastnav if target_legal else None,
   original_target_other_constraint_blocked=not target_legal,definition='additional risk capacity, not cash; pending fees and candidate fee retained; no request submitted'))
 groups={'all_strict_account_only':items}
 for key,s,start,end in [('energy_Q3','URFI881267','2025-07-01','2025-09-30'),('military_Q4','URFI881276','2025-10-01','2025-12-31'),('oil_Q1','URFI881107','2026-01-01','2026-03-31')]:groups[key]=[r for r in items if r['sector']==s and start<=r['signal_day']<=end]
 summaries={k:dict(strict_receipts=len(v),minimum_cny=dist([r['min_extra_nominal_risk_cny'] for r in v]),minimum_pct_decision_NAV=dist([r['min_extra_pct_last_decision_NAV'] for r in v]),
  original_target_legal_other_constraints=sum(r['target_all_other_checks_allow'] for r in v),target_cny=dist([r['target_extra_nominal_risk_cny'] for r in v if r['target_all_other_checks_allow']]),target_pct_decision_NAV=dist([r['target_extra_pct_last_decision_NAV'] for r in v if r['target_all_other_checks_allow']])) for k,v in groups.items()}
 L.save(O/'ADDITIONAL_CAPACITY_DISTRIBUTION.json',dict(summaries=summaries,not_a_threshold_recommendation=True,not_simultaneously_additive=True,fee_contract='original normal buy fee including minimum',rows=items))
 print('PROTECTION',len(audit),all(x['passed'] for x in audit),max(abs(x['difference']) for x in audit));print(json.dumps(summaries,indent=2))

WROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
if __name__=='__main__':main()
