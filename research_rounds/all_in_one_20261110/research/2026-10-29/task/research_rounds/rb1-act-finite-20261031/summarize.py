"""Aggregate already completed accounts; never calls the strategy runner."""
import adapter as m
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
from collections import defaultdict,Counter
import json,gzip,time,pandas as pd
O=m.O;w=m.w;RR=w.RR;Z=D(0);T=time.monotonic()
def read(p):return json.loads(Path(p).read_text())
def rows(p):return pd.read_csv(p,dtype=str).to_dict('records')
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def save(name,x):(O/name).write_text(json.dumps(w.K.H.encoded(x),ensure_ascii=False,indent=2,default=str))
def out(name,x):pd.DataFrame(w.K.H.encoded(x)).to_csv(O/name,index=False)
def recovery(ds):
 peak=D(1000000);peakday=datetime.fromisoformat(ds[0]['at']);under=trough=None;low=None;longest=completed=0
 for r in ds:
  t=datetime.fromisoformat(r['at']);n=D(r['nav'])
  if n>=peak:
   if under is not None:longest=max(longest,(t-under).days);completed=max(completed,(t-trough).days)
   peak=n;peakday=t;under=trough=None;low=None
  else:
   if under is None:under=peakday;trough=t;low=n
   if n<low:trough=t;low=n
 current=(datetime.fromisoformat(ds[-1]['at'])-under).days if under else 0
 return dict(longest_underwater_calendar_days=max(longest,current),longest_completed_trough_recovery_calendar_days=completed,current_underwater_calendar_days=current,unrecovered_at_end=under is not None)

matrix=[];rejects=[];cycles=[];groups=[];targets=[];tailcohorts=[];stockdiff=[];acts=[];riskchecks=[];priceconditions=[];bridges=[];quality=[]
for sec,reference,mode,prep in [
 ('TECH',RR/'pvr-local-finite-capital-20261029/baseline','I',Path(read(RR/'pvr-act-comparison-20261027/input.json')['snapshot']['path'])),
 ('DRUG',RR/'innovative-drug-local-recovery-20261028/S0','ACT',RR/'innovative-drug-sfw3-20261028/prepared')]:
 for stage in ['off','prefix-open','prefix-cut','on']:assert read(O/sec/stage/'TIMING.json')['status']=='complete'
 for g in ['off','prefix-cut']:assert read(O/sec/g/'IDENTITY.json')['passed']
 assert read(O/sec/'on/PREFIX_IDENTITY.json')['passed']
 for g in ['accounting','funding']:assert read(O/sec/f'on/analysis/{g}.json')['passed']
 factcache={};epochs={};A_caps=rows(reference/'analysis/campaigns.csv');A_normal=[c for c in A_caps if c['account']==f'{mode}__S0_base'];fixed_targets=[c for c in A_normal if c['closed']=='True' and D(c['net_return'])<=D('-.3')] if sec=='TECH' else []
 def fact(s):
  if s not in factcache:factcache[s]=pd.read_parquet(prep/'facts'/f'{s}.parquet')
  return factcache[s]
 def epoch(s,t):
  f=fact(s);day=pd.Timestamp(t[:10]);j=f.index.searchsorted(day,side='right')-1
  if j<0:return None
  if s not in epochs:
   known=f.e0_ready.astype(bool)&f.e0_target.notna();on=f.e0_target.astype('boolean').where(known).groupby(f.segment_id).ffill().fillna(False).astype(bool);start=on&~on.groupby(f.segment_id).shift(fill_value=False);labels=pd.Series(None,index=f.index,dtype=object)
   for dt in f.index[start]:labels.loc[dt]=f'{s}|source={int(f.loc[dt,"segment_id"])}|E0={dt.date()}'
   epochs[s]=labels.groupby(f.segment_id).ffill().where(on,None).to_dict()
  return epochs[s][f.index[j]]
 A_obj=read(reference/'accounts-v2'/f'{mode}__S0_base.json');A_intents={x['order_id']:x for x in A_obj['audit_log'] if x['kind']=='entry_contract'};A_first={(x['receipt']['security_id'],x['receipt']['at']):x['order_id'] for x in A_obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='buy'}
 def original_key(c):return epoch(c['symbol'],A_intents[A_first[c['symbol'],c['entry_at']]]['decision_at'])
 tailkeys={original_key(c) for c in A_normal if c['tail_closed']=='True'};assert None not in tailkeys
 roots={'A':reference,'RB1':O/sec/'on'};base_stocks={};base_net={};caps_by={}
 for policy,root in roots.items():
  allcaps=rows(root/'analysis/campaigns.csv');summaries=rows(root/'analysis/summary.csv');dsall=gz(root/'accounts-v2/daily.jsonl.gz');rules=read(root/'execution-rules-v2.json')
  for stress in ['base','cost2','delay1']:
   aid=f'{mode}__S0_{stress}';obj=read(root/'accounts-v2'/f'{aid}.json');logs=obj['audit_log'];ds=[r for r in dsall if r['account']==aid];cs=[dict(c) for c in allcaps if c['account']==aid];caps_by[policy,stress]=cs;contracts={r['order_id']:r for r in logs if r['kind']=='entry_contract'};firstbuy={(r['receipt']['security_id'],r['receipt']['at']):r for r in logs if r['kind']=='fill' and r['receipt']['side']=='buy'};grouped=defaultdict(list)
   for c in cs:
    order=firstbuy[c['symbol'],c['entry_at']]['order_id'];contract=contracts[order];key=epoch(c['symbol'],contract['decision_at']);c.update(sector=sec,model=policy,pressure=stress,structure_id=key,decision_at=contract['decision_at'],order_id=order,initial_R=contract['risk_budget'],actual_loss_over_initial_R=float(max(Z,-D(c['net_pnl']))/D(contract['risk_budget'])) if c['closed']=='True' else None);cycles.append(c);grouped[key or 'UNKNOWN:'+c['symbol']+c['entry_at']].append(c)
   gs=[]
   for key,cc in grouped.items():
    negative=-sum((min(Z,D(c['net_pnl'])) for c in cc),Z);g=dict(sector=sec,model=policy,pressure=stress,structure_id=key,symbol=cc[0]['symbol'],attempts=len(cc),closed=sum(c['closed']=='True' for c in cc),net=sum((D(c['net_pnl']) for c in cc),Z),all_negative_cycles=negative,fees=sum((D(c['buy_fees'])+D(c['sell_fees']) for c in cc),Z),first_entry=min(c['entry_at'] for c in cc),last_exit=max((c['exit_at'] if c['closed']=='True' else ds[-1]['at'] for c in cc)));gs.append(g);groups.append(g)
   risk=[r for r in logs if r['kind']=='risk_checkpoint'];acts.extend(dict(r,sector=sec,model=policy,pressure=stress,account=aid) for r in risk if r['event'] is not None)
   counts=Counter();unique=defaultdict(set)
   for r in logs:
    if r['kind'] in ['risk_reject','risk_open_reject','open_support_reject']:
     reason=r.get('reason','open_minimum_quantity' if r['kind']=='risk_open_reject' else 'open_at_or_below_or_missing_frozen_floor');counts[r['kind']+':'+reason]+=1;unique[r['kind']+':'+reason].add(r['sid']);rejects.append(dict(r,sector=sec,model=policy,pressure=stress,normalized_reason=reason))
   net=D(ds[-1]['nav'])-1000000;sumcycles=sum((D(c['net_pnl']) for c in cs),Z);assert abs(sumcycles-net)<D('.00000001');ss=defaultdict(lambda:Z)
   for c in cs:ss[c['symbol']]+=D(c['net_pnl'])
   if policy=='A':base_stocks[stress]=ss;base_net[stress]=net
   else:
    dif={s:ss.get(s,Z)-base_stocks[stress].get(s,Z) for s in set(ss)|set(base_stocks[stress])};assert abs(sum(dif.values(),Z)-(net-base_net[stress]))<D('.00000001');bridges.append(dict(sector=sec,pressure=stress,NAV_delta=net-base_net[stress],stock_delta_sum=sum(dif.values(),Z),residual=sum(dif.values(),Z)-(net-base_net[stress])));stockdiff.extend(dict(sector=sec,pressure=stress,symbol=s,difference=v) for s,v in sorted(dif.items(),key=lambda x:-abs(x[1])))
   summary=dict(next(x for x in summaries if x['account']==aid));row=dict(summary,sector=sec,model=policy,pressure=stress,source='existing_full_off_exact_A' if policy=='A' else 'new_full_verified_RB1',**recovery(ds));row.update(mean_available_NAV=sum(float(r['available'])/float(r['nav']) for r in ds)/len(ds),mean_order_reserved_NAV=sum(float(r['order_reserved'])/float(r['nav']) for r in ds)/len(ds),paused_observations=sum(not r['on'] for r in risk),pause_count=sum(r['event']=='pause' for r in risk),resume_count=sum(r['event']=='resume' for r in risk),risk_rejections_from_audit=sum(v for k,v in counts.items() if k.startswith('risk_')),risk_rejection_reasons=dict(counts),risk_rejection_unique_symbols={k:len(v) for k,v in unique.items()},actual_turnover=sum((D(f['gross_cny']) for f in obj['fills']),Z),execution_slippage=sum((abs(D(r['price'])-D(r['raw_open']))*r['receipt']['shares']*D(r['fx_rate']) for r in logs if r['kind']=='fill'),Z),closed_losses_over_initial_R=sum(c['actual_loss_over_initial_R']>1 for c in cs if c['closed']=='True'),maximum_actual_loss_over_initial_R=max((c['actual_loss_over_initial_R'] for c in cs if c['closed']=='True'),default=0),structures=len(gs),repeated_structures=sum(g['attempts']>1 for g in gs),max_attempts_same_structure=max((g['attempts'] for g in gs),default=0),worst_cumulative_structure_net=min((g['net'] for g in gs),default=Z))
   matrix.append(row)
   for d in ds:
    for s,at in d['mark_observed_at'].items():
     if at[:10]!=d['at'][:10]:priceconditions.append(dict(sector=sec,model=policy,pressure=stress,date=d['at'][:10],symbol=s,mark_observed_at=at))
   tailgroup=[g for g in gs if g['structure_id'] in tailkeys];tailcohorts.append(dict(sector=sec,model=policy,pressure=stress,cohort='A_normal_closed_30pct_tail_E0_structures',A_normal_tail_cycles=sum(c['tail_closed']=='True' for c in A_normal),frozen_structures=len(tailkeys),participated_structures=len(tailgroup),attempts=sum(g['attempts'] for g in tailgroup),net_contribution=sum((g['net'] for g in tailgroup),Z),all_negative_cycles=sum((g['all_negative_cycles'] for g in tailgroup),Z)))
   for c in fixed_targets:
    key=original_key(c);gg=[g for g in gs if g['structure_id']==key];same=[x for x in cs if x['symbol']==c['symbol'] and x['entry_at'][:10]==c['entry_at'][:10]];assert len(same)<=1
    targets.append(dict(sector=sec,model=policy,pressure=stress,symbol=c['symbol'],name=c['name'],original_A_entry=c['entry_at'],original_A_exit=c['exit_at'],original_A_normal_net=c['net_pnl'],original_A_normal_return=c['net_return'],structure_id=key,participated=bool(gg),actual_attempts=sum(g['attempts'] for g in gg),actual_net_same_structure=sum((g['net'] for g in gg),Z) if gg else None,actual_first_entry=min((g['first_entry'] for g in gg),default=None),actual_last_exit=max((g['last_exit'] for g in gg),default=None),same_original_entry_day=bool(same),same_entry_actual_net=same[0]['net_pnl'] if same else None,same_entry_actual_return=same[0]['net_return'] if same else None,same_entry_actual_exit=same[0]['exit_at'] if same else None,same_entry_cash_outlay=D(same[0]['buy_gross'])+D(same[0]['buy_fees']) if same else None,interpretation='same-entry-day_leg_separate_from_same_E0_structure_all_attempts_not_fixed_quantity_causal_pair'))
   if policy=='RB1':
    from market_rules import market_identity_on,version_on
    L=w.K.L;positions=defaultdict(int);gross=defaultdict(lambda:Z);buyfees=defaultdict(lambda:Z);oid_sid={};checks=[]
    for r in logs:
     if r['kind'] in ['split','split_fraction_floor_proxy']:
      for oid,s in oid_sid.items():
       if s==r['sid']:positions[oid]=int(D(positions[oid])*D(r['ratio']))
     if r['kind']!='fill' or r['receipt']['side']!='buy':continue
     f=r['receipt'];sid=f['security_id'];oid=r['order_id'];oid_sid[oid]=sid;positions[oid]+=f['shares'];gross[oid]+=D(f['gross_cny']);buyfees[oid]+=D(f['fees_cny']);c=contracts[oid];at=datetime.fromisoformat(f['at']);ff=fact(sid);j=ff.index.searchsorted(pd.Timestamp(at.date()),side='right')-1;floor=D(c['floor_signal'])/D(str(ff.iloc[j].factor));identity=market_identity_on(rules,sid,at.date(),['research_frozen_execution_proxy','historical_fee_proxy']) if False else None
     proto=read(RR/'rs-h1-execution-20261025/inputs-v2/economic-protocol.json');identity=market_identity_on(rules,sid,at.date(),proto['approved_proxy_ids']);spec=version_on(rules['fee_versions'][identity['venue']],at.date().isoformat(),proto['approved_proxy_ids'])['schedule'];schedule=L.FeeSchedule(spec['schedule_id'],tuple(L.FeeComponent(**x) for x in spec['components']));mult=2 if stress=='cost2' else 1;stop=floor*(1-D('.0005')*mult);sellfee=sum(schedule.incremental('sell',positions[oid]*stop,{}, {},mult,shares=positions[oid],par_value=rules['security_metadata'].get(sid,{}).get('par_value')).values(),Z);nominal=max(Z,gross[oid]+buyfees[oid]-positions[oid]*stop+sellfee);R=D(c['risk_budget']);assert nominal<=R+D('.000001'),(sec,aid,sid,nominal,R);checks.append(dict(sector=sec,account=aid,pressure=stress,order_id=oid,symbol=sid,at=f['at'],cumulative_shares=positions[oid],cumulative_gross=gross[oid],cumulative_buy_fees=buyfees[oid],floor=floor,estimated_exit_fee=sellfee,nominal_loss=nominal,R=R,ratio=float(nominal/R)))
    riskchecks+=checks;quality.append(dict(sector=sec,account=aid,actual_buy_fills=len(checks),cumulative_risk_verified=True,over_budget=0))

out('MATRIX_12.csv',matrix);out('RISK_REJECTIONS.csv',rejects);out('ALL_CYCLES.csv',cycles);out('STRUCTURE_TRIALS.csv',groups);out('THREE_SEVERE_COHORT.csv',targets);out('A_TAIL_STRUCTURE_COHORT.csv',tailcohorts);out('STOCK_DIFFERENCES.csv',stockdiff);out('INDEPENDENT_ENTRY_RISK.csv',riskchecks);out('PRICE_CONDITIONS.csv',priceconditions);save('ACT_EVENTS.json',acts);save('SUMMARY.json',dict(matrix=matrix,stock_bridges=bridges,independent_risk_checks=quality,unknown_price_conditions=priceconditions,seconds=time.monotonic()-T,new_paths_run=0));print('SUMMARY_COMPLETE',len(matrix),'seconds',time.monotonic()-T,flush=True)
