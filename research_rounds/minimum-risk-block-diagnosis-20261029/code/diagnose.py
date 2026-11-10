"""Read-only order arithmetic; fee/quantity types only, no account instances/replay."""
from pathlib import Path
import sys,json,hashlib,collections,math
from decimal import Decimal as D
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1]
BASE=ROOT/'research_rounds/lot-risk-allocation-20261029'
SNAP=ROOT/'TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared'
sys.path.insert(0,str(ROOT/'research_rounds/rs-h1-execution-20261025/code'))
from market_rules import market_identity_on,version_on
from sector_account import QuantityRule,FeeSchedule,FeeComponent
NAMES={'300308.SZ':'中际旭创','688498.SH':'源杰科技','300502.SZ':'新易盛','688256.SH':'寒武纪'}
CASE_DAYS={'300308.SZ':['2024-02-06','2025-06-27','2025-06-30'],'688498.SH':['2024-02-08','2025-10-20','2025-10-21'],'300502.SZ':['2025-06-27'],'688256.SH':['2024-02-06','2025-04-09']}
ZERO=D(0);ONE=D(1);BPS=D('.0005')
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with Path(p).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def main():
 out=O/'data';out.mkdir(parents=True,exist_ok=False)
 obj=load(BASE/'results/L1.json');meta=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol').to_dict('index');rules=load(ROOT/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');proto=load(ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/economic-protocol.json');states={};cp={};fee_cache={};qty_cache={};rows=[];source_hashes={}
 existing=pd.read_csv(BASE/'analysis/allocation-events.csv');reasons={(r.symbol,r.signal_at):r.reason for r in existing[existing.account.eq('L1')].itertuples()}
 def state(sid):
  if sid not in states:
   p=SNAP/'facts'/f'{sid}.parquet';states[sid]=pd.read_parquet(p);source_hashes[str(p.relative_to(ROOT))]=sha(p)
  return states[sid]
 def terms(sid,day):
  key=(sid,day)
  if key not in qty_cache:qty_cache[key]=QuantityRule(**version_on(rules['quantity_versions'][sid],day,proto['approved_proxy_ids'])['rule'])
  identity=market_identity_on(rules,sid,pd.Timestamp(day).date(),proto['approved_proxy_ids']);key2=(identity['venue'],day)
  if key2 not in fee_cache:
   s=version_on(rules['fee_versions'][identity['venue']],day,proto['approved_proxy_ids'])['schedule'];fee_cache[key2]=FeeSchedule(s['schedule_id'],tuple(FeeComponent(**x) for x in s['components']))
  return qty_cache[key],fee_cache[key2]
 for r in obj['decisions']:
  day=r['at'][:10];nav=D(r['nav'])
  for i in r['intents']:
   if i['kind']!='core':continue
   sid=i['sid'];f=state(sid);j=f.index.get_loc(pd.Timestamp(day));bar=f.iloc[j];p=D(i['signal_price']);floor=D(i['frozen_floor_raw']);qrule,fee=terms(sid,day);q=qrule.buy_minimum;par=rules.get('security_metadata',{}).get(sid,{}).get('par_value');risk=D(i['risk_budget']);buy=p*(ONE+BPS)
   def charge(side,price):return sum(fee.incremental(side,D(q)*price,{}, {},1,shares=q,par_value=par).values(),ZERO)
   def loss(stop):return max(ZERO,D(q)*(buy-stop*(ONE-BPS))+charge('buy',buy)+charge('sell',stop*(ONE-BPS)))
   minimum=loss(floor);gross=D(q)*buy;buycash=gross+charge('buy',buy);lo,hi=ZERO,p
   if loss(p)>risk:needed=None;maxgap=None
   else:
    for _ in range(75):
     mid=(lo+hi)/2
     if loss(mid)<=risk:hi=mid
     else:lo=mid
    needed=hi;maxgap=ONE-needed/p
   k=j;v=float(bar.i_floor)
   while k>0 and bool(f.iloc[k-1].i_target) and f.iloc[k-1].segment_id==bar.segment_id and np.isfinite(f.iloc[k-1].i_floor) and math.isclose(float(f.iloc[k-1].i_floor),v,rel_tol=1e-11,abs_tol=1e-10):k-=1
   epoch=j
   while epoch>0 and bool(f.iloc[epoch-1].i_target) and f.iloc[epoch-1].segment_id==bar.segment_id:epoch-=1
   entry=dict(symbol=sid,name=meta[sid]['name'],date=day,nav=float(nav),price=float(p),protection=float(floor),gap=float(ONE-floor/p),minimum_shares=q,minimum_gross=float(gross),minimum_cash=float(buycash),minimum_weight=float(gross/nav),minimum_risk=float(minimum),minimum_risk_pct=float(minimum/nav),budget=float(risk),required_budget_multiple=float(minimum/risk),risk_ok=minimum<=risk,nominal_ok=gross<=nav*D('.1'),required_protection=float(needed) if needed is not None else None,maximum_gap_at_budget=float(maxgap) if maxgap is not None else None,minimum_nav_at_same_rules=float(max(minimum/D('.0025'),gross/D('.1'))),floor_since=str(f.index[k].date()),floor_unchanged_prior_observations=j-k,trend_since=str(f.index[epoch].date()),original_reason=reasons[sid,r['at']],cp_receipt=False,cp_protection=None,cp_gap=None,cp_minimum_risk_pct=None)
   if sid in NAMES:
    if sid not in cp:
     z=ROOT/'research_rounds/continuous-protection-lines-20261028/signals'/f'{sid}.parquet';cp[sid]=pd.read_parquet(z);source_hashes[str(z.relative_to(ROOT))]=sha(z)
    if pd.Timestamp(day) in cp[sid].index:
     c=cp[sid].loc[day]
     if bool(c.receipt):
      cp_floor=max(floor,D(str(c.candidate))/D(str(bar.factor)));entry.update(cp_receipt=True,cp_protection=float(cp_floor),cp_gap=float(ONE-cp_floor/p),cp_minimum_risk_pct=float(loss(cp_floor)/nav))
   rows.append(entry)
 df=pd.DataFrame(rows);df.to_csv(out/'all-core-orders.csv',index=False);named=df[df.symbol.isin(NAMES)];named.to_csv(out/'named-orders.csv',index=False);cases=named[named.apply(lambda r:r.date in CASE_DAYS[r.symbol],axis=1)];cases.to_csv(out/'cases.csv',index=False)
 result=[]
 for sid,g in [('ALL',df)]+[(sid,named[named.symbol.eq(sid)]) for sid in NAMES]:
  result.append(dict(symbol=sid,name='全407池核心意图' if sid=='ALL' else NAMES[sid],orders=len(g),risk_only=int((~g.risk_ok & g.nominal_ok).sum()),nominal_only=int((g.risk_ok & ~g.nominal_ok).sum()),both=int((~g.risk_ok & ~g.nominal_ok).sum()),pass_size=int((g.risk_ok & g.nominal_ok).sum()),gap_pct_quantiles={str(x):float(g.gap.quantile(x)*100) for x in [.1,.25,.5,.75,.9]},minimum_weight_pct_quantiles={str(x):float(g.minimum_weight.quantile(x)*100) for x in [.1,.25,.5,.75,.9]},required_risk_pct_quantiles={str(x):float(g.minimum_risk_pct.quantile(x)*100) for x in [.1,.25,.5,.75,.9]},reason_counts=g.original_reason.value_counts().to_dict(),floor_age_median=float(g.floor_unchanged_prior_observations.median())))
 expected=sum(i['kind']=='core' for r in obj['decisions'] for i in r['intents']);assert len(df)==expected==19623
 rejected=df[~df.risk_ok|~df.nominal_ok];assert len(rejected)==4307;assert set(rejected.original_reason)=={'size_minimum_unit_exceeds_risk_or_nominal_cap'}
 for sid,p in NAMES.items():assert int((named.symbol.eq(sid)&(~named.risk_ok|~named.nominal_ok)).sum())==int((named.symbol.eq(sid)&named.original_reason.eq('size_minimum_unit_exceeds_risk_or_nominal_cap')).sum())
 # Compare component magnitudes to contemporaneous eligible peers, not just whole-history medians.
 peers=[]
 for c in cases.itertuples():
  g=df[df.date.eq(c.date)];peers.append(dict(symbol=c.symbol,date=c.date,peer_orders=len(g),gap_percentile=float(g.gap.le(c.gap+1e-12).mean()*100),minimum_weight_percentile=float(g.minimum_weight.le(c.minimum_weight+1e-12).mean()*100),required_risk_percentile=float(g.minimum_risk_pct.le(c.minimum_risk_pct+1e-12).mean()*100),peer_gap_median=float(g.gap.median()),peer_minimum_weight_median=float(g.minimum_weight.median())))
 pd.DataFrame(peers).to_csv(out/'case-peer-context.csv',index=False);save(O/'SUMMARY.json',result)
 protected=load(BASE/'completion-sha256.json')['sha256'];assert all(sha(BASE/k)==v for k,v in protected.items())
 source_hashes[str((BASE/'results/L1.json').relative_to(ROOT))]=sha(BASE/'results/L1.json');source_hashes[str((BASE/'analysis/allocation-events.csv').relative_to(ROOT))]=sha(BASE/'analysis/allocation-events.csv')
 save(O/'VERIFICATION.json',dict(passed=True,new_backtests=0,new_signal_calculations=0,all_core_orders=expected,original_rejections_independently_reconciled=4307,unchanged_old_study_artifacts=len(protected),source_sha256=source_hashes,notes='All counterfactual numbers are static single-order affordability boundaries, not executed trades or account returns.'))
 print(cases[['name','date','price','protection','gap','minimum_shares','minimum_weight','minimum_risk','minimum_risk_pct','budget','required_protection','maximum_gap_at_budget','floor_since','floor_unchanged_prior_observations','cp_protection','cp_minimum_risk_pct']].to_string(index=False));print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
