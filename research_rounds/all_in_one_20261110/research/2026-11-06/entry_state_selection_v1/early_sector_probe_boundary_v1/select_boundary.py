"""Predeclared residual-capacity selector. Private same-day arithmetic only."""
import sys,json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import pandas as pd
O=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def out(n,x):
 p=O/n;assert not p.exists(),p;p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 assert not (O/'SELECTION_SEAL.json').exists()
 src=read(O/'INPUT_HASHES.json')
 for p,h in src.items():assert sha(p)==h,('input changed',p)
 for pp in [Path(__file__),O/'ORIGINAL_OPEN_RESOURCES.json',O/'ORIGINAL_OPEN_RESERVATION_SNAPSHOTS.json',O/'risk_reconstruction.py',O/'RISK_RECONSTRUCTION_QA.json',O/'DOMAIN.parquet',O/'NEXT_OPEN_INPUTS.parquet']:src[str(pp)]=sha(pp)
 r=read(O/'ORIGINAL_OPEN_RESOURCES.json');rs=r['rows'];by={v['day']:v for v in rs}
 c=pd.read_parquet(O/'DOMAIN.parquet').merge(pd.read_parquet(O/'NEXT_OPEN_INPUTS.parquet'),on=['row','sid','day'],validate='one_to_one')
 # Frozen global original priority, never forward outcomes.
 c=c.sort_values(['day','priority_rank','sid']);c['sector_day_priority']=c.groupby(['day','sector']).cumcount()+1
 used=set();uncertain=set();aud=[];selected=[];daily=[];first_signal=c.groupby('episode').day.min().to_dict()
 for day,g in c.groupby('day',sort=True):
  od=g.open_day.dropna().unique();assert len(od)<=1
  snap=by.get(str(od[0])) if len(od) else None
  extra_cash=D(0);extra_fee=D(0);extra_cap=0.;extra_risk=0.;sector_add=defaultdict(lambda:[0.,0.]);stock_add=defaultdict(float)
  known=snap is not None and snap['status']=='EXACT_VERIFIED'
  if known:
   bal=snap['balance_components'];available=D(bal['available']);N0=D(bal['nav']);navclose=D(snap['decision_NAV_exact']);pf=D(snap['reservation_fees_exact'])
  new_count=0;status=Counter()
  for r in g.to_dict('records'):
   ep=r['episode'];a=dict(row=r['row'],day=day,open_day=r['open_day'],sid=r['sid'],name=r['name'],sector=r['sector'],industry_name=r['industry_name'],episode=ep,ep_start=r['ep_start'],left_truncated=r['left_truncated'],priority_rank=r['priority_rank'],sector_day_priority=r['sector_day_priority'],first_episode_CORE_day=first_signal[ep],status=None,reasons=[])
   if ep in used:a.update(status='EPISODE_ALREADY_ASSIGNED',reasons=['episode_one_probe_already_assigned'])
   elif ep in uncertain:a.update(status='EARLIER_UNKNOWN_EPISODE',reasons=['cannot_certify_first_after_prior_unknown'])
   elif r['input_status']!='KNOWN':
    a.update(status='INPUT_UNKNOWN',reasons=[r['input_status']])
    if r['input_status']=='RULE_OR_FACTOR_UNKNOWN':uncertain.add(ep)
   elif r['preview_reject']:a.update(status='FROZEN_CONTRACT_REJECT',reasons=r['preview_reject'].split(','))
   elif not known:
    a.update(status='ORIGINAL_RISK_UNKNOWN',reasons=['original_open_resource_not_exact']);uncertain.add(ep)
   else:
    q=int(r['quantity']);C=D(r['gross']);F=D(r['buy_fee']);R=float(r['nominal_risk']);p=D(r['price'])
    N=N0-pf-extra_fee-F;cash=available-extra_cash-D('.1')*navclose
    sector=r['sector'];sc,sr,_=snap['sectors'].get(sector,[0.,0.,0.]);pc,pr,_=snap['probe'];held=snap['stocks'].get(r['sid'],{'quantity':0,'open_mark_exact':r['raw_open']});hc=float(held['quantity'])*float(held['open_mark_exact'])
    failures=[]
    if float(C+F)>float(cash)+1e-9:failures.append('cash_or_original_reserve')
    # available is exact unreserved spendable cash; original cash-reserve is the same bridge.
    if float(C+F)>float(available-extra_cash)+1e-9:failures.append('cash')
    if pc+extra_cap+float(C)>.10*float(N)+1e-9:failures.append('probe_capital')
    if pr+extra_risk+R>.005*float(N)+1e-9:failures.append('probe_risk')
    if sc+sector_add[sector][0]+float(C)>.02*float(N)+1e-9:failures.append('sector_capital')
    if sr+sector_add[sector][1]+R>.01*float(N)+1e-9:failures.append('sector_risk')
    if hc+stock_add[r['sid']]+float(C)>.10*float(navclose)+1e-9:failures.append('stock_capital')
    a.update(quantity=q,price=str(p),gross=str(C),buy_fee=str(F),nominal_risk=R,protection_risk=r['protection_risk'],original_risk_budget=r['original_risk_budget'],adjusted_open=r['adjusted_open'],original_available_after_reserves=str(available),original_decision_NAV=str(navclose),original_open_NAV=str(N0),original_pending_fees=str(pf),effective_NAV=str(N),cash_above_floor_before=str(cash),prior_micro_cash=str(extra_cash),prior_micro_capital=extra_cap,prior_micro_risk=extra_risk,original_probe_capital=pc,original_probe_risk=pr,probe_capital_remaining=.10*float(N)-pc-extra_cap,probe_risk_remaining=.005*float(N)-pr-extra_risk,original_sector_capital=sc,original_sector_risk=sr,sector_capital_remaining=.02*float(N)-sc-sector_add[sector][0],sector_risk_remaining=.01*float(N)-sr-sector_add[sector][1],prior_original_stock_value=hc)
    if failures:a.update(status='CAPACITY_REJECT',reasons=failures)
    else:
     a.update(status='CONDITIONAL_MINIMUM_SLOT',reasons=[])
     used.add(ep);new_count+=1
     extra_cash+=C+F;extra_fee+=F;extra_cap+=float(C);extra_risk+=R
     sector_add[sector][0]+=float(C);sector_add[sector][1]+=R;stock_add[r['sid']]+=float(C)
     a['same_day_micro_sequence']=new_count;a['cash_above_floor_after']=str(available-extra_cash-D('.1')*navclose)
     selected.append(a.copy())
   status[a['status']]+=1;aud.append(a)
  daily.append(dict(day=day,open_day=str(od[0]) if len(od) else None,original_snapshot_known=known,opportunities=len(g),sectors=g.sector.nunique(),selected=new_count,micro_cash=str(extra_cash),micro_fees=str(extra_fee),micro_capital=extra_cap,micro_nominal_risk=extra_risk,status_counts=dict(status)))
 aa=pd.DataFrame(aud);ss=pd.DataFrame(selected)
 assert len(ss)==ss.episode.nunique() and not ss.duplicated(['day','sector']).any()
 aa['reasons']=aa.reasons.map(lambda x:','.join(x));aa.to_csv(O/'ALL_BOUNDARY_DECISIONS.csv',index=False)
 ss.to_csv(O/'SEALED_EPISODE_FIRST_PROBES.csv',index=False);pd.DataFrame(daily).to_csv(O/'DAILY_CAPACITY.csv',index=False)
 qa=dict(candidate_rows=len(c),episodes=c.episode.nunique(),selected=len(ss),selected_days=ss.day.nunique(),selected_stocks=ss.sid.nunique(),selected_sectors=ss.sector.nunique(),status_counts=aa.status.value_counts().to_dict(),reason_counts=dict(Counter(z for a in aud for z in a['reasons'])),unknown_resource_dates=sum(not d['original_snapshot_known'] for d in daily),left_truncated_selected=int(ss.left_truncated.sum()),no_Account_or_Runner=True,same_day_cash_and_risk_consumed=True,cross_day_new_exposure_not_propagated=True,not_an_account_or_executable_portfolio=True,no_future_labels_read=True)
 out('SELECTION_QA.json',qa)
 out('SELECTION_INPUT_HASHES.json',src)
 sealed={str(O/n):sha(O/n) for n in ['PROTOCOL.json','DOMAIN.parquet','NEXT_OPEN_INPUTS.parquet','ALL_BOUNDARY_DECISIONS.csv','SEALED_EPISODE_FIRST_PROBES.csv','DAILY_CAPACITY.csv','SELECTION_QA.json','select_boundary.py']}
 out('SELECTION_SEAL.json',dict(created_utc=pd.Timestamp.now(tz='UTC').isoformat(),hashes=sealed,no_future_labels_read=True,no_parameter_grid=True))
 print(qa,flush=True)
if __name__=='__main__':main()
