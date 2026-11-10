"""Recovery chronology only. No C fills, portfolio replay, or indicator recomputation."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D
from collections import Counter,defaultdict
import sys,json,csv,gzip,time,hashlib,bisect,statistics,importlib.util
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;P=O.parent/'old-side-exit-all69-20261030';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');S=R/'s-entry-mechanism-audit-20261029';BASE=R/'pvr-local-finite-capital-20261029/baseline/accounts-v2';PH=R/'ph1-cross-sector-20261028';CP=R/'continuous-protection-lines-20261028';Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def export(n,x):pd.DataFrame(H.encoded(x)).to_csv(O/n,index=False)
def stamp(x):return datetime.fromisoformat(x)
sp=importlib.util.spec_from_file_location('recovery_timing_existing_helpers',S/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
ARITH=R/'pv-strength-b5-20261025/code/arithmetic.py';pa=importlib.util.spec_from_file_location('recovery_frozen_scalar_arithmetic',ARITH);AR=importlib.util.module_from_spec(pa);pa.loader.exec_module(AR)
mother=list(csv.DictReader((P/'FROZEN_69_CYCLES.csv').open()));es=[x for x in mother if x['triggered']=='True'];assert len(mother)==69 and len(es)==57
obj=read(BASE/'I__S0_base.json');oa=obj['audit_log'];cp={x['at'][:10]:x for x in oa if x['kind']=='risk_checkpoint'}
with gzip.open(P/'full/audit.json.gz','rt') as f:old_arms=json.load(f)
sales={};settled={}
for st in old_arms:
 if st['arm']!='B':continue
 ff=[x for x in st['fills'] if x['side']=='sell'];assert len(ff)==1;sales[st['cycle_id'],st['cost']]=ff[0]
 ss=[x for x in st['audit'] if x['kind']=='settle' and not x['settlement']['debit']];assert len(ss)==1;settled[st['cycle_id'],st['cost']]=stamp(ss[0]['at'])
ids={e['old'] for e in es};_,m,_,_=H.context(ids,False);cache=pd.read_parquet(S/'market-cache.parquet');cc={(x.symbol,str(x.date.date())):x for x in cache.itertuples(index=False)};days=sorted(set(x[1] for x in cc));di={d:i for i,d in enumerate(days)}
funnel=pd.read_parquet(R/'fat-tail-opportunity-ledger-20261029/full/daily-observed-funnel.parquet',columns=['date','symbol','event_id']);eid={(x.symbol,str(pd.Timestamp(x.date).date())):x.event_id for x in funnel.itertuples(index=False)}
sources=[O/'PROTOCOL.txt',Path(__file__),ARITH,P/'FROZEN_69_CYCLES.csv',P/'full/audit.json.gz',P/'full/unit-ledgers.csv',P/'cycle-differences.csv',BASE/'I__S0_base.json',S/'market-cache.parquet'];identity={str(p):sha(p) for p in sources};event_cache={};cp_cache={}
for s in sorted(ids):
 ep=PH/'events/TECH'/f'{s}.parquet';p=CP/'signals'/f'{s}.parquet';identity[str(ep)]=sha(ep);identity[str(p)]=sha(p);event_cache[s]=pd.read_parquet(ep);cp_cache[s]=pd.read_parquet(p)
save('INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),before_recovery_sequence_and_economic_join=True,sha256=identity))
def new_fact(e,day,kind):
 s=e['old'];r=cc[s,day];t=H.at(day,dt(15,10));same=pd.notna(eid.get((s,day))) and eid.get((s,day))==e['_structure'];active=bool(pd.notna(r.i_target) and r.i_target);on=bool(cp[day]['on']);oldexit=t>=e['_request'];g=int(r.g_grade) if pd.notna(r.g_grade) else None
 reasons=[]
 if not same:reasons.append('not_original_E0_structure')
 if not active:reasons.append('I_not_active')
 if not bool(r.i_buy):reasons.append('no_new_I_today')
 if not bool(r.Q):reasons.append('full_Q_not_true_components_not_saved')
 if not on:reasons.append('ACT_not_allowed')
 if oldexit:reasons.append('original_exit_request_has_priority')
 return dict(cycle_id=e['cycle_id'],symbol=s,kind=kind,date=day,confirmation_at=t,same_original_structure=same,I_active=active,new_I=bool(r.i_buy),Q=bool(r.Q),ACT_on=on,old_exit_priority=oldexit,original_protection_valid=bool(active and pd.notna(r.i_floor) and float(r.close)>float(r.i_floor)),I_floor_causal=D(str(r.i_floor)) if pd.notna(r.i_floor) else None,G1_grade=g,full_legal_IQ=not reasons,legality_reasons='|'.join(reasons),signal_delay_market_observations=di[day]-di[e['_sold'][:10]])
def execution_check(e,fact,cost):
 s=e['old'];t=stamp(str(fact['confirmation_at']));ix=bisect.bisect_right(m.sessions['A'],t);op=m.sessions['A'][ix] if ix<len(m.sessions['A']) else None;out=dict(next_open=op,precheck_cost=cost,closed_sale_cash=D(sales[e['cycle_id'],cost]['net']),cash_known_at=settled[e['cycle_id'],cost]);why=[]
 if op is None:why.append('next_calendar_unknown')
 elif op>=stamp(e['original_exit']) or t>=e['_request']:why.append('original_exit_boundary_before_buy')
 if settled[e['cycle_id'],cost]>t:why.append('sale_cash_not_yet_available')
 q=m.quote(s,t);w=m.window(s,op,'buy',cost) if op else None
 if q is None:why.append('decision_quote_unknown')
 elif fact['I_floor_causal'] is None:why.append('frozen_support_unknown')
 if w is None:why.append('next_buy_market_window_unavailable')
 elif not w.buy_allowed:why.append('next_buy_not_allowed')
 if w is not None:
  minimum=w.quantity.buy_minimum;gross=D(minimum)*w.execution_price;fee=sum(w.fees.incremental('buy',gross,{}, {},cost,shares=minimum,par_value=w.par_value).values(),Z);out.update(minimum_shares=minimum,capacity=w.capacity_shares,minimum_execution_cash=gross+fee,raw_open=w.raw_open)
  if w.capacity_shares<minimum:why.append('minimum_quantity_exceeds_capacity')
  if gross+fee>out['closed_sale_cash']:why.append('sealed_sale_cash_below_execution_minimum')
  if q is not None:
   dg=D(q.quantity.buy_minimum)*q.raw_price;df=sum(q.fees.incremental('buy',dg,{}, {},cost,shares=q.quantity.buy_minimum,par_value=q.par_value).values(),Z);out['minimum_decision_cash']=dg+df
   if dg+df>out['closed_sale_cash']:why.append('sealed_sale_cash_below_decision_minimum')
  nr=cc.get((s,str(op.date())))
  if nr is None or pd.isna(nr.factor):why.append('execution_factor_unknown')
  elif fact['I_floor_causal'] is not None and w.raw_open<=fact['I_floor_causal']/D(str(nr.factor)):why.append('next_open_not_above_frozen_support')
 out.update(executable_proxy=not why,execution_reasons='|'.join(why));return out

seq=[];facts=[];curve_cache={};checks=Counter()
for e0 in es:
 e=dict(e0);s=e['old'];sale=sales[e['cycle_id'],1];sold=stamp(sale['at']);e['_sold']=sale['at'];e['_structure']=eid.get((s,e['date']));assert pd.notna(e['_structure'])
 req=[x for x in oa if x['kind']=='exit_request' and x['sid']==s and e['original_entry']<=x['at']<e['original_exit']];assert len(req)==1;e['_request']=stamp(req[0]['at']);first={};policy=None;prices=[];missing_event=[];missing_cp=[];unknown=False
 for day in days[di[str(sold.date())]:di[str(e['_request'].date())]+1]:
  t=H.at(day,dt(15,10));assert t>sold;r=cc[s,day];dd=pd.Timestamp(day);ev=event_cache[s].loc[dd] if dd in event_cache[s].index else None;cpr=cp_cache[s].loc[dd] if dd in cp_cache[s].index else None
  if ev is None:missing_event.append(day)
  if cpr is None:missing_cp.append(day)
  typ=[]
  if ev is not None and pd.notna(ev.event) and int(ev.event)==1:typ.append('event_plus1')
  if bool(r.i_buy) and bool(r.Q):typ.append('new_IQ')
  if cpr is not None and bool(cpr.receipt):typ.append('CP1_receipt')
  for k in typ:
   if k not in first:
    z=new_fact(e,day,k);z.update(execution_check(e,z,1));first[k]=z
  legal=bool(pd.notna(eid.get((s,day))) and eid.get((s,day))==e['_structure'] and pd.notna(r.i_target) and r.i_target and r.i_buy and r.Q and cp[day]['on'] and t<e['_request'])
  if legal and policy is None:
   policy=new_fact(e,day,'policy_first_legal_new_IQ');policy.update(execution_check(e,policy,1));second=execution_check(e,policy,2);policy['cost2_executable_proxy']=second['executable_proxy'];policy['cost2_execution_reasons']=second['execution_reasons'];policy['cost2_minimum_cash']=second.get('minimum_execution_cash');policy['cost2_sale_cash']=second['closed_sale_cash']
  raw=m.raw[s]
  if dd in raw.index and bool(raw.loc[dd,'valid_price']) and bool(raw.loc[dd,'observed_bar']):prices.append((day,D(str(r.close))))
 for k in ['event_plus1','new_IQ','CP1_receipt']:
  if k in first:facts.append(first[k])
  else:facts.append(dict(cycle_id=e['cycle_id'],symbol=s,kind=k,date=None,confirmation_at=None,status='not_observed_in_original_window',missing_event_rows=len(missing_event) if k=='event_plus1' else len(missing_cp) if k=='CP1_receipt' else 0))
 if policy:facts.append(policy)
 factor=D(str(cc[s,str(sold.date())].factor));anchor=D(sale['raw_open'])*factor;lower=next((d for d,p in prices if AR.compare(p,anchor)<0),None);upper=next((d for d,p in prices if AR.compare(p,anchor)>0),None)
 if not prices:unknown=True
 if unknown:cl='U_critical_unknown'
 elif policy:
  if not policy['executable_proxy']:cl='L3_legal_IQ_execution_or_cash_block'
  elif lower is not None and lower<=policy['date']:cl='L1_lower_close_before_or_at_legal_recovery'
  else:cl='L2_legal_recovery_without_lower_close'
 elif 'event_plus1' in first or 'CP1_receipt' in first or upper is not None:cl='N1_recovery_evidence_without_legal_IQ'
 elif lower is not None:cl='N2_further_decline_no_recovery_evidence'
 else:cl='N3_no_direction_or_legal_recovery'
 seq.append(dict(cycle_id=e['cycle_id'],symbol=s,name=e['name'],warning=e['date'],sold_at=sold,original_exit_request=e['_request'],original_exit=e['original_exit'],original_structure=e['_structure'],mother_unknown_days=e['unknown_event_days'],missing_post_event_rows=json.dumps(missing_event),missing_post_CP_rows=json.dumps(missing_cp),price_anchor_causal=anchor,first_lower_close=lower,first_upper_close=upper,class_code=cl,first_event_plus1=first.get('event_plus1',{}).get('date'),first_raw_IQ=first.get('new_IQ',{}).get('date'),first_CP1=first.get('CP1_receipt',{}).get('date'),policy_IQ=policy['date'] if policy else None,policy_executable=policy['executable_proxy'] if policy else None,policy_cost2_executable=policy['cost2_executable_proxy'] if policy else None,policy_execution_reasons=policy['execution_reasons'] if policy else None,delay_market_observations=policy['signal_delay_market_observations'] if policy else None,post_min_price_return=min(p for d,p in prices)/anchor-1 if prices else None,post_max_price_return=max(p for d,p in prices)/anchor-1 if prices else None,terminal_price_return=prices[-1][1]/anchor-1 if prices else None,real_account_funding_or_memory_lock='not_identified_original_account_still_held_stock',cross_structure_or_after_original_exit='not_used_not_extended'))
 checks['cycles_scanned']+=1
export('recovery-timing-before-economic-labels.csv',seq);export('first-confirmation-facts.csv',facts)
freeze={str(O/n):sha(O/n) for n in ['PROTOCOL.txt','recovery-timing-before-economic-labels.csv','first-confirmation-facts.csv']};save('TIMING_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_joining_AB_labels_and_loss_timing=True,sha256=freeze,C_economic_paths=0))
print(json.dumps(dict(stage='timing_frozen',cycles=len(seq),policy_signal=sum(bool(x['policy_IQ']) for x in seq),proxy_ok=sum(x['policy_executable'] is True for x in seq),seconds=time.monotonic()-T)),flush=True)

# Reuse old A/B and original market equity ONLY after chronology has been frozen.
ab=[x for x in csv.DictReader((P/'cycle-differences.csv').open()) if x['cost']=='1'];ab={x['cycle_id']:x for x in ab};units=list(csv.DictReader((P/'full/unit-ledgers.csv').open()));ui={(x['cycle_id'],x['arm']):x for x in units if x['cost']=='1'};held=list(csv.DictReader((O.parent/'act-loss-facts-20261030/actual-holding-close-paths.csv').open()));hp={(x['cycle_id'],x['day']):x for x in held};combined=[]
for x in seq:
 old=ab[x['cycle_id']];delta=D(old['B_minus_A']);r=x|dict(old_B_minus_A=delta,old_exit_group='benefit37' if delta>0 else 'harm20',original_tail30=old['original_tail30']=='True',old_total_A_minus_B=-delta,loss_before_IQ=None,loss_after_IQ=None)
 if x['policy_IQ']:
  a,b=ui[x['cycle_id'],'A'],ui[x['cycle_id'],'B'];basis=D(a['initial_actual_cost']);ae=basis+D(hp[x['cycle_id'],x['policy_IQ']]['nav_mark_pnl']);be=D(b['final_equity']);pre=ae-be;post=D(a['final_equity'])-ae;assert pre+post==-delta;r.update(loss_before_IQ=pre,loss_after_IQ=post,A_equity_at_IQ=ae,B_equity_at_IQ=be)
 combined.append(r)
export('recovery-with-old-loss-timing.csv',combined)
def coverage(g):
 matched=[x for x in g if x['policy_IQ']];d=[x['delay_market_observations'] for x in matched]
 return dict(cycles=len(g),first_event_plus1=sum(bool(x['first_event_plus1']) for x in g),first_raw_IQ=sum(bool(x['first_raw_IQ']) for x in g),first_CP1=sum(bool(x['first_CP1']) for x in g),legal_policy_IQ=len(matched),proxy_executable=sum(x['policy_executable'] is True for x in g),cost2_proxy_executable=sum(x['policy_cost2_executable'] is True for x in g),classes=dict(Counter(x['class_code'] for x in g)),median_signal_delay=statistics.median(d) if d else None,max_signal_delay=max(d) if d else None,old_AB_difference=sum((x['old_B_minus_A'] for x in g),Z),matched_old_A_minus_B=sum((x['old_total_A_minus_B'] for x in matched),Z),matched_loss_before_IQ=sum((x['loss_before_IQ'] for x in matched),Z),matched_loss_after_IQ=sum((x['loss_after_IQ'] for x in matched),Z),no_policy_old_A_minus_B=sum((x['old_total_A_minus_B'] for x in g if not x['policy_IQ']),Z))
targets={'605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'};sm=dict(all57=coverage(combined),old_harm20=coverage([x for x in combined if x['old_exit_group']=='harm20']),old_benefit37=coverage([x for x in combined if x['old_exit_group']=='benefit37']),original_tail14=coverage([x for x in combined if x['original_tail30']]),targets3=coverage([x for x in combined if x['cycle_id'] in targets]),target_rows=[x for x in combined if x['cycle_id'] in targets],first_harm_case=next((x for x in combined if x['old_exit_group']=='harm20'),None),first_benefit_case=next((x for x in combined if x['old_exit_group']=='benefit37'),None))
save('SUMMARY.json',sm)
assert all(sha(p)==h for p,h in identity.items());assert all(sha(p)==h for p,h in freeze.items())
save('VERIFICATION.json',dict(passed=True,mother=69,warning_cycles=57,no_warning_unchanged=12,classes_exhaustive=sum(sm['all57']['classes'].values())==57,first_signal_chronology_frozen_before_loss_join=True,AB_paths_recomputed=0,C_economic_paths=0,indicator_recomputations=0,source_hashes_unchanged=True,loss_timing_exact_for_matched=sm['all57']['legal_policy_IQ'],seconds=time.monotonic()-T))
print(json.dumps(H.encoded(dict(stage='complete',seconds=time.monotonic()-T,summary=sm)),ensure_ascii=False),flush=True)
