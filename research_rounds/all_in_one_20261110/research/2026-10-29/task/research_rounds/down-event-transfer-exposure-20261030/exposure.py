"""Read existing facts/journals only. No execution, financial paths or indicator engines."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D
from types import SimpleNamespace as NS
from collections import defaultdict,Counter
import json,gzip,hashlib,importlib.util,time,csv,bisect
import pandas as pd
import numpy as np

T=time.monotonic();ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');R=ROOT/'research_rounds';O=Path(__file__).resolve().parent;S=R/'s-entry-mechanism-audit-20261029';B=R/'pvr-local-finite-capital-20261029/baseline/accounts-v2';PH=R/'ph1-cross-sector-20261028';Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def export(n,rr):pd.DataFrame(rr).to_csv(O/n,index=False)
def emit(**x):print(json.dumps(x,ensure_ascii=False,default=str),flush=True)
def rows(p):
 with gzip.open(p,'rt') as f:return [x for l in f if (x:=json.loads(l))['account']=='I__S0_base']
snap=Path(json.loads((R/'pvr-act-comparison-20261027/input.json').read_text())['snapshot']['path']);evproof=json.loads((PH/'event-validation.json').read_text());assert evproof['passed']
sources=[O/'CONTRACT-v1.txt',Path(__file__),B/'I__S0_base.json',B/'daily.jsonl.gz',B/'decisions.jsonl.gz',S/'market-cache.parquet',snap/'h1.npz',PH/'event-validation.json']
identity={str(p):sha(p) for p in sources};save('INPUT_IDENTITY.json',dict(frozen_at=datetime.now(timezone.utc).isoformat(),before_exposure=True,before_new_forward_returns=True,sha256=identity))
obj=json.loads((B/'I__S0_base.json').read_text());al=obj['audit_log'];ds=rows(B/'daily.jsonl.gz');dec=rows(B/'decisions.jsonl.gz');dc={x['at'][:10]:x for x in dec};assert len(ds)==len(dec)==681
cache=pd.read_parquet(S/'market-cache.parquet');cache['day']=cache.date.dt.strftime('%Y-%m-%d');cc={(x.symbol,x.day):x for x in cache.itertuples(index=False)};days=sorted(cache.day.unique());di={d:i for i,d in enumerate(days)}
sp=importlib.util.spec_from_file_location('transfer_exposure_helpers',S/'code/audit.py');H=importlib.util.module_from_spec(sp);sp.loader.exec_module(H);A=H.A
ids=set(cache.symbol);b,m,_,_=H.context(ids,False);meta={x['symbol']:x for x in H.roster()};lines={x.security_id:x for x in b.lines};sec={s:meta[s]['sector_id'] for s in ids}
ev={};ev_identity={};frozen=json.loads((PH/'freeze.json').read_text())['sha256'];event_rows=0
for s in sorted(ids):
 p=PH/'events/TECH'/f'{s}.parquet';h=sha(p);assert h==frozen[str(p)],s;ev_identity[str(p)]=h;f=pd.read_parquet(p);event_rows+=len(f)
 for d,r in f.iterrows():
  day=str(pd.Timestamp(d).date())
  if (s,day) not in cc:continue
  cr=cc[s,day];assert float(r.close)==float(cr.close) and int(r.segment_id)==int(cr.segment_id),(s,day,'event source identity')
  ev[s,day]=dict(event=int(r.event) if pd.notna(r.event) else None,pivot=float(r.pivot) if pd.notna(r.pivot) else None,pivot_date=str(r.pivot_date) if pd.notna(r.pivot_date) else None)
  if pd.notna(r.pivot_date) and int(r.event)!=0:assert str(r.pivot_date)[:10]<=day
save('EVENT_INPUT_IDENTITY.json',ev_identity)
h=np.load(snap/'h1.npz');hd=pd.DatetimeIndex(h['dates']);hs={str(s):i for i,s in enumerate(h['symbols'])};hv=h['score'];assert len(hd)==len(hv)
funnel=pd.read_parquet(R/'fat-tail-opportunity-ledger-20261029/full/daily-observed-funnel.parquet',columns=['date','symbol','event_id']);funnel['day']=pd.to_datetime(funnel.date).dt.strftime('%Y-%m-%d');eid={(x.symbol,x.day):x.event_id for x in funnel.itertuples(index=False)}
ag=defaultdict(list)
for x in al:
 tm=x['receipt']['at'] if x['kind']=='fill' else x.get('at')
 if tm:ag[tm[:10]].append(x)
buys={};splits=[];pending={};pfee={};psid={};exposure=[];pair_options=[];selected=[];candidates=[];used=set();reserve_checks=0;eligible_checks=0;timing_checks=0
def score(s,ix):
 if s not in hs:return None
 v=float(hv[ix,hs[s]]);return v if np.isfinite(v) else None
def R21(s,day):
 ix=di[day]
 if ix<21:return None,'left_history_missing'
 a=cc[s,days[ix-21]];z=cc[s,day]
 if int(a.segment_id)!=int(z.segment_id):return None,'source_segment_boundary'
 if not(np.isfinite(a.close) and a.close>0 and np.isfinite(z.close) and z.close>0):return None,'price_unknown'
 return float(z.close)/float(a.close)-1,None
def project(old,new,day,state,tm,clock,occupied,P):
 q=int(state['positions'][old]);orow=cc[old,day];nrow=cc[new,day];out=dict(date=day,old=old,new=new,cycle_id=f"{old}|{buys[old]['at'][:10]}",old_quantity=q,new_R21=R21(new,day)[0]);reasons=[]
 after=[x for x in occupied if x['security_id']!=old];counts=Counter(x['sector_id'] for x in after)
 if len(after)>=6:reasons.append('total_slots_full_after_removal')
 if counts[sec[new]]>=2:reasons.append('sector_issuer_slots_full_after_removal')
 if sec[new] not in counts and len(counts)>=3:reasons.append('sector_slots_full_after_removal')
 if lines[new].issuer_id in {x['issuer_id'] for x in after}:reasons.append('issuer_occupied_after_removal')
 old_mature=m.lag('A',datetime.fromisoformat(buys[old]['at']),m.protocol['sellable_lag_sessions']['A'])
 if old_mature>clock.earliest_execution_at:reasons.append('old_not_T1_sellable')
 if any(x['sid']==old and x['at']<=str(tm) and datetime.fromisoformat(x['new_shares_sellable_at'])>clock.earliest_execution_at for x in splits):reasons.append('bonus_shares_not_sellable')
 oq=m.quote(old,tm);nq=m.quote(new,tm)
 if oq is None or nq is None:reasons.append('quote_unknown');out.update(feasible=False,unknown=True,reasons='|'.join(reasons),first_block=reasons[0]);return out
 oldmv=D(q)*m.latest_mark(old,tm).raw_price;sale=oldmv*(1-D('.0005'));sf=sum(oq.fees.incremental('sell',sale,{}, {},1,shares=q,par_value=oq.par_value).values(),Z);Snet=max(Z,sale-sf)
 budget=max(Z,min(D('.15')*D(state['nav']),D('.90')*D(state['nav'])-(D(state['inventory'])-oldmv)-P,Snet,D(state['available'])+Snet))
 price=nq.raw_price*(1+D('.0005'));qty=nq.quantity.buy_floor(int(budget/price));bf=Z
 if qty:
  bf=sum(nq.fees.incremental('buy',D(qty)*price,{}, {},1,shares=qty,par_value=nq.par_value).values(),Z)
  while qty and D(qty)*price+bf>Snet:
   qty=nq.quantity.buy_floor(qty-nq.quantity.fill_step)
   bf=sum(nq.fees.incremental('buy',D(qty)*price,{}, {},1,shares=qty,par_value=nq.par_value).values(),Z) if qty else Z
 if qty<nq.quantity.buy_minimum:reasons.append('sealed_sale_slice_or_budget_below_minimum')
 if not(np.isfinite(nrow.i_floor)):reasons.append('new_support_unknown')
 if budget<=0:reasons.append('original_90pct_or_budget_exhausted')
 out.update(feasible=not reasons,unknown=any('unknown' in r for r in reasons),reasons='|'.join(reasons),first_block=reasons[0] if reasons else None,old_market_value=oldmv,projected_net_sale=Snet,pending_original_gross=P,available_original=state['available'],reserved_original=state['order_reserved'],original_NAV=state['nav'],new_gross_cap=budget,new_projected_shares=qty,new_projected_spend=D(qty)*price+bf,next_open_market_check='not_read_current_phase')
 if not reasons:assert qty>0 and D(qty)*price+bf<=Snet
 return out

for nn,state in enumerate(ds):
 day=state['at'][:10];tm=datetime.fromisoformat(state['at']);decision=dc[day];on=next(x['on'] for x in ag[day] if x['kind']=='risk_checkpoint')
 for x in ag[day]:
  k=x['kind']
  if k=='reserve':pending[x['order_id']]=D(x['gross_budget_cny']);pfee[x['order_id']]=D(x['fee_reserved_cny']);psid[x['order_id']]=x['sid']
  elif k=='fill' and x['receipt']['side']=='buy':pending[x['order_id']]=D(x['gross_budget_remaining']);pfee[x['order_id']]-=D(x['receipt']['fees_cny']);buys[x['receipt']['security_id']]=x['receipt']
  elif k=='release_buy':pending.pop(x['order_id'],None);pfee.pop(x['order_id'],None);psid.pop(x['order_id'],None)
  elif k in ['split','split_fraction_floor_proxy']:splits.append(x)
 P=sum(pending.values(),Z);assert P+sum(pfee.values(),Z)==D(state['order_reserved']),(day,'pending reserve mismatch');reserve_checks+=1
 clock=A.Clock(tm,m.sessions['A'][bisect.bisect_right(m.sessions['A'],tm)],tm.date());ix=hd.searchsorted(pd.Timestamp(day),side='right')-1;assert ix>=0 and hd[ix]<=pd.Timestamp(day)
 ss={};res={};sects={};readynew=[];positive=[];unknownr=0
 for s in sorted(ids):
  r=cc[s,day];assert (s in decision['eligible'])==(bool(r.Q) and on),(day,s,'Q');eligible_checks+=1
  if not(bool(r.i_buy) and bool(r.Q) and on):continue
  if s in state['positions'] or s in state['pending_buys'] or s in state['pending_sells'] or s in decision['accepted']:continue
  readynew.append(s);rr,why=R21(s,day)
  candidates.append(dict(date=day,symbol=s,new_I=True,Q=True,R21=rr,R21_unknown=why,structure_id=eid.get((s,day)),H1=score(s,ix),sector_H1=score(sec[s],ix)))
  if rr is None:unknownr+=1;continue
  if rr<=0:continue
  positive.append(s);ss[s]=NS(rank=A.Fact(score(s,ix),tm,tm));res[s]=NS(sector_id=sec[s]);sects[sec[s]]=NS(rank=A.Fact(score(sec[s],ix),tm,tm))
 priority=A._priority(positive,ss,sects,res,clock,'S0',[],'down_event_transfer') if positive else []
 todays=[]
 for s,q in sorted(state['positions'].items()):
  if not int(q):continue
  r=cc[s,day];e=ev.get((s,day));cycle=f"{s}|{buys[s]['at'][:10]}";known=bool(e is not None and e['event'] is not None)
  stknown=all(pd.notna(x) for x in [r.e0_target,r.e0_ready,r.i_target]);active=bool(stknown and r.e0_target and r.e0_ready and r.i_target);down=bool(known and e['event']==-1);reasons=[]
  if not known:reasons.append('event_row_missing_or_unknown')
  elif not down:reasons.append('not_new_down_confirmation')
  if not stknown:reasons.append('structure_unknown')
  elif not active:reasons.append('original_structure_inactive')
  if not on:reasons.append('ACT_paused')
  if s in state['pending_sells']:reasons.append('original_sell_already_pending')
  if s in state['pending_buys']:reasons.append('old_buy_pending')
  er=dict(date=day,cycle_id=cycle,symbol=s,name=meta[s]['name'],entry_at=buys[s]['at'],shares=int(q),event=e['event'] if known else None,pivot=e['pivot'] if e else None,pivot_date=e['pivot_date'] if e else None,e0_I_active=active,ACT_on=on,old_sell_pending=s in state['pending_sells'],old_buy_pending=s in state['pending_buys'],source_segment=int(r.segment_id),original_structure_id=eid.get((s,day)),old_signal=not reasons,old_unknown=not known or not stknown,old_first_block=reasons[0] if reasons else None,old_reasons='|'.join(reasons),new_I_Q_count=len(readynew),new_positive_R21_count=len(positive),new_R21_unknown=unknownr,new_rank_unknown=len(positive)-len(priority),cycle_already_selected=cycle in used,feasible_candidates=0,first_feasible_candidate=None)
  if down and e and e['pivot_date']:assert e['pivot_date'][:10]<=day;timing_checks+=1
  if not reasons:
   opts=[project(s,n,day,state,tm,clock,decision['occupancy'],P) for n in priority];pair_options+=opts;feas=[x for x in opts if x['feasible']];er['feasible_candidates']=len(feas)
   if feas:er['first_feasible_candidate']=feas[0]['new']
   if feas and cycle not in used:todays.append((er,feas[0]))
  exposure.append(er)
 if todays:
  er,z=min(todays,key=lambda x:(x[0]['entry_at'],x[0]['symbol']));used.add(er['cycle_id']);selected.append(z|dict(old_name=er['name'],old_entry_at=er['entry_at'],old_pivot=er['pivot'],old_pivot_date=er['pivot_date'],old_source_segment=er['source_segment'],old_structure_id=er['original_structure_id'],new_structure_id=eid.get((z['new'],day)),new_name=meta[z['new']]['name']))
 if nn in [20,200,400,680]:emit(stage='exposure_scan',days=nn+1,holding_cycle_days=len(exposure),selected=len(selected),seconds=time.monotonic()-T)

assert len(selected)==len(set(x['cycle_id'] for x in selected))==len(set(x['date'] for x in selected))
export('all-holding-exposure-before-labels.csv',exposure);export('pair-options-before-labels.csv',pair_options);export('selected-events-before-labels.csv',selected);export('new-candidate-background.csv',candidates)
freeze={str(O/n):sha(O/n) for n in ['CONTRACT-v1.txt','all-holding-exposure-before-labels.csv','pair-options-before-labels.csv','selected-events-before-labels.csv']};save('SELECTION_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_reading_existing_final_cycle_labels=True,sha256=freeze,new_forward_return_paths=0))
emit(stage='selection_frozen',seconds=time.monotonic()-T,selected=len(selected))

# Only now join existing original-cycle labels; no post-trigger price path or candidate return read.
cs=[x for x in csv.DictReader((R/'pvr-local-finite-capital-20261029/baseline/analysis/campaigns.csv').open()) if x['scenario']=='base'];labels={f"{x['symbol']}|{x['entry_at'][:10]}":dict(original_final_return=float(x['net_return']),original_final_pnl=x['net_pnl'],original_tail30=float(x['net_return'])>=.30,original_profitable=D(x['net_pnl'])>0) for x in cs}
assert len(labels)==69 and set(x['cycle_id'] for x in exposure)==set(labels)
with_labels=[x|labels[x['cycle_id']] for x in exposure];sel_labels=[x|labels[x['cycle_id']] for x in selected]
export('holding-exposure-with-original-labels.csv',with_labels);export('selected-with-original-labels.csv',sel_labels)
old=[x for x in with_labels if x['old_signal']];downactive=[x for x in with_labels if x['event']==-1 and x['e0_I_active']]
def coverage(rr):return dict(rows=len(rr),cycles=len(set(x['cycle_id'] for x in rr)),calendar_days=len(set(x['date'] for x in rr)),stocks=len(set(x.get('symbol',x.get('old')) for x in rr)))
summary=dict(all_decision_days=len(ds),all_holding=coverage(with_labels),event_unknown=sum(x['event'] is None for x in exposure),structure_unknown=sum('structure_unknown' in x['old_reasons'] for x in exposure),event_down_structure_active=coverage(downactive),old_gate=coverage(old),old_gate_positive_new=coverage([x for x in old if x['new_positive_R21_count']>0]),old_gate_feasible=coverage([x for x in old if x['feasible_candidates']>0]),selected=coverage(sel_labels),all_pair_options=len(pair_options),feasible_pair_options=sum(x['feasible'] for x in pair_options),pair_first_block=dict(Counter(x['first_block'] for x in pair_options if not x['feasible'])),old_first_block=dict(Counter(x['old_first_block'] for x in exposure if not x['old_signal'])),candidate_R21_unknown=sum(x['R21'] is None for x in candidates),candidate_positive_R21=sum(x['R21'] is not None and x['R21']>0 for x in candidates),old_gate_original_tail30=coverage([x for x in old if x['original_tail30']]),selected_original_tail30=coverage([x for x in sel_labels if x['original_tail30']]),selected_original_profitable=coverage([x for x in sel_labels if x['original_profitable']]),selected_original_loss=coverage([x for x in sel_labels if not x['original_profitable']]),first_selected=sel_labels[:2],first_tail_counterexample=next((x for x in sel_labels if x['original_tail30']),None),first_nontrigger=next((x for x in with_labels if x['old_first_block']=='not_new_down_confirmation'),None),first_original_exit_priority=next((x for x in with_labels if x['event']==-1 and not x['old_signal'] and (x['old_sell_pending'] or not x['ACT_on'])),None))
save('EXPOSURE_SUMMARY.json',summary)
assert all(sha(p)==h for p,h in identity.items());assert all(sha(p)==h for p,h in freeze.items())
save('VERIFICATION.json',dict(passed=True,original_reserve_rows_exact=reserve_checks,original_Q_rows_exact=eligible_checks,event_close_and_segment_exact=True,event_validation_preexisting_passed=True,event_files=407,full_event_rows_read=event_rows,past_pivot_timing_checks=timing_checks,selection_uses_no_final_outcome=True,single_event_per_cycle_and_day=True,input_hashes_unchanged=True,new_economic_paths=0,indicator_recomputations=0,seconds=time.monotonic()-T))
emit(stage='done',seconds=time.monotonic()-T,summary=summary)
