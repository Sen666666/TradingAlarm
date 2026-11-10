"""Read original B and completed instrumentation only; no account replay."""
from pathlib import Path
from bisect import bisect_left
from collections import Counter,defaultdict
import gzip,json,math
import pandas as pd,numpy as np
import launch_v3 as L
J=L.J;O=J.O/'risk-occupancy-diagnostic'
SPECS={'energy_Q3':('URFI881267','2025-07-01','2025-09-30'),
 'military_Q4':('URFI881276','2025-10-01','2025-12-31'),
 'oil_Q1':('URFI881107','2026-01-01','2026-03-31')}
def readrows(p):
 with gzip.open(p,'rt') as f:
  for x in f:yield json.loads(x)
def stats(snapshots):
 c=Counter();part=Counter();part_value=Counter();part_count=Counter();mark_profit=Counter();role=Counter();sectorstate=Counter();oldprobe=0.;oldprobevalue=0.;n=0;ratio=[];inventory=0.
 for r in snapshots:
  n+=1;total=r['resources']['total_risk'];c['total_risk_yuan_observations']+=total
  for k in ('principal_downside','profit_giveback','pending_buy_risk'):c[k]+=r[k]
  if total:ratio.append(r['profit_giveback']/total)
  for x in r['lots']:
   risk=x['risk'];role[x['role']]+=risk
   if x['has_pending_sell']:category='exit_requested_not_filled'
   elif x['known_stock_I'] is False:category='I_invalid_without_pending_exit'
   elif x['known_stock_I'] is None:category='I_unknown'
   elif x['full_layer_economic_PnL_including_realized_cash_and_dividend']>0:category='I_valid_profitable_layer'
   elif x['full_layer_economic_PnL_including_realized_cash_and_dividend']<0:category='I_valid_losing_layer'
   else:category='I_valid_flat_layer'
   part[category]+=risk;part_value[category]+=x['market_value'];part_count[category]+=1;inventory+=x['market_value']
   mark_profit['gross_remaining_mark_profitable' if x['gross_mark_profit']>0 else 'gross_remaining_mark_nonpositive']+=risk
   sectorstate['industry_active' if x['current_industry_active'] else 'industry_attempt_inactive']+=risk
   if x['old_attempt_probe_occupancy']:oldprobe+=risk;oldprobevalue+=x['market_value']
 total=c['total_risk_yuan_observations'];return dict(observations=n,risk_yuan_observation_sums=dict(c),
  risk_share={k:c[k]/total for k in ('principal_downside','profit_giveback','pending_buy_risk')} if total else {},
  mean_equal_observation_giveback_fraction=sum(ratio)/len(ratio) if ratio else None,
  stock_status_risk_share={k:v/total for k,v in part.items()} if total else {},role_risk_share={k:v/total for k,v in role.items()} if total else {},
  stock_status_lot_observations=dict(part_count),stock_status_inventory_value_share={k:v/inventory for k,v in part_value.items()} if inventory else {},
  gross_remaining_mark_profit_risk_share={k:v/total for k,v in mark_profit.items()} if total else {},
  industry_attempt_risk_share={k:v/total for k,v in sectorstate.items()} if total else {},old_attempt_probe_risk_share=oldprobe/total if total else None,
  old_attempt_probe_inventory_value_share=oldprobevalue/inventory if inventory else None,
  unit='risk yuan times observation; repeated snapshots are not independent market samples; status partitions concern stock I/exit, not just industry permission')

def main():
 assert L.read(O/'DONE.json')['completed'];a=json.load(gzip.open(J.O/'run-universe/pair/B.json.gz','rt'))
 eligible=list(readrows(O/'ELIGIBLE_CP1.jsonl.gz'));route={x['receipt']:x for x in readrows(O/'ROUTED_MOBILE.jsonl.gz')};snap=list(readrows(O/'RISK_SNAPSHOTS.jsonl.gz'))
 closes=[x for x in snap if x['label']=='daily_close'];assert len(closes)==182
 sums={'whole_182_closes':stats(closes)}
 for label,(sector,start,end) in SPECS.items():
  sums[label+'_account_closes']=stats([x for x in closes if start<=x['at'][:10]<=end])
  sums[label+'_account_risk_refusals']=stats([x for x in snap if x['label']=='target_mobile_before_route' and x['candidate']['sector']==sector and x['route']['actual_route'] is None and 'account_risk' in (x['route']['actual_reason'] or '')])
 L.save(O/'RISK_SOURCE_SUMMARY.json',sums)
 seq=list(readrows(O/'ALL_ACTUAL_ROUTE_SEQUENCE.jsonl.gz'));first={}
 for r in seq:first.setdefault(r['at'],r['risk_before'])
 timing={}
 for label,scope in [('all',None)]+[(k,v) for k,v in SPECS.items()]:
  rs=[r for r in route.values() if r['actual_route'] is None and 'account_risk' in (r['actual_reason'] or '') and (scope is None or r['sector']==scope[0] and scope[1]<=r['signal_at'][:10]<=scope[2])]
  adds=[max(0.,r['resources_before']['total_risk']-first[r['at']]) for r in rs]
  timing[label]=dict(refusal_receipts=len(rs),positive_same_open_preceding_reservation_risk=sum(x>1e-7 for x in adds),
   incumbent_risk_already_at_or_above_gross3percent_before_any_new_reservation=sum(first[r['at']]>=.03*r['resources_before']['marked_NAV']-1e-9 for r in rs),
   added_same_open_risk_median=float(np.median(adds)) if adds else None,max_added_same_open_risk=max(adds,default=None),
   interpretation='actual earlier reservations only; observations overlap and are not an alternative allocation path')
 L.save(O/'SAME_OPEN_COMPETITION.json',timing)

 meta=L.read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
 manifests={r['symbol']:r for r in L.read(L.U/'STOCK_MANIFEST.json')};named={}
 source={}
 for r in readrows(J.O/'run-universe/pair/opportunities.jsonl.gz'):
  if r['account']=='B' and r['sid'] in ('300308.SZ','300502.SZ'):source[(r['sid'],r['day'])]=r
 for sid in ('300308.SZ','300502.SZ'):
  f=pd.read_parquet(manifests[sid]['refs']['facts']).loc[J.START:J.END];cp=pd.read_parquet(manifests[sid]['refs']['CP1']).loc[J.START:J.END]
  originalI=set(str(d.date()) for d in f.index[f.i_buy.fillna(False).astype(bool)&f.i_target.fillna(False).astype(bool)])
  ee=[x for x in eligible if x['sid']==sid];rr=[r for r in route.values() if r['sid']==sid];allroutes=[r for r in seq if r['sid']==sid]
  qpassI=[d for d in originalI if source[(sid,d)]['core_Q'] is True]
  firstI=min(originalI) if originalI else None;firstCP=str(cp.index[cp.receipt.astype(bool)].min().date()) if cp.receipt.any() else None
  funding=[];times=[pd.Timestamp(x['at']) for x in a['decisions']]
  for r in readrows(J.O/'run-universe/pair/funding.jsonl.gz'):
   if r['account']=='B' and r['sid']==sid:funding.append(r)
  named[sid]=dict(name=meta[sid]['name'],in_fixed_universe=sid in L.read(L.U/'FREEZE.json')['stocks'],price_observations=len(f),
   original_I_fresh_days=len(originalI),I_Q_pass_days=len(qpassI),fresh_CP1=int(cp.receipt.sum()),CP1_Q_pass=len(ee),
   CP1_industry_active=sum(x['industry_active'] for x in ee),CP1_mobile_intent=sum(x['mobile_intent_created'] for x in ee),
   CP1_real_route=len(rr),CP1_minimum_legal_under_all_real_checks=sum(bool(x['actual_route']) for x in rr),
   CP1_extra_minimum_legal_only_without_account_check=sum(x['actual_route'] is None and bool(x['without_account_check_route']) for x in rr),
   actual_core_route=sum(r['role']=='core' for r in allroutes),actual_buy_fills=sum(t['side']=='buy' and t['security_id']==sid for t in a['trades']),
   first_original_I=None if firstI is None else source[(sid,firstI)],first_original_CP1=None if firstCP is None else source[(sid,firstCP)],
   route_refusals=dict(Counter((r['why'] or 'reserved') for r in allroutes)),funding_results=dict(Counter(r['result'] for r in funding)),first_funding_attempts=funding[:4])
 L.save(O/'NAMED_STOCK_FULL_FUNNEL.json',named)
 # Fixed original stage and old peak dates: direct saved states, no relabeling.
 fixed=L.read(O/'FIXED_STAGE_DATES.json');chosen=[]
 for sector,dates in fixed.items():
  for label,d in dates.items():
   hit=next((r for r in closes if r['at'][:10]==d),None)
   if hit:chosen.append(dict(case_sector=sector,selection=label,**hit))
 dump=O/'FIXED_STAGE_AND_PEAK_SNAPSHOTS.jsonl.gz'
 with gzip.open(dump,'wt') as out:
  for r in chosen:out.write(json.dumps(r,ensure_ascii=False)+'\n')
 L.save(O/'SUMMARY_READY.json',dict(complete_main_readonly_aggregation=True,global_unique_eligible=len(eligible),global_unique_routed=len(route),
  risk_closing_snapshots=len(closes),fixed_stage_and_peak_snapshots=len(chosen),no_new_replay=True))
 print(json.dumps(dict(risk_sums=sums,named=named),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
