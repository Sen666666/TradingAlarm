"""Read completed Q1 paths; reconcile own boundaries, no new economic path."""
import continuation as C
from pathlib import Path
import json,time,collections,traceback
import pandas as pd,numpy as np
M,T,X,O=C.M,C.T,C.X,C.O
D=M.D;Z=D(0);BOUND='2025-12-31';END='2026-03-31'
def amount(rs,key):return sum((D(r[key]) for r in rs),Z)
def mdd(initial,rs):
 v=np.r_[float(initial),[float(r['nav']) for r in rs]];return float((1-v/np.maximum.accumulate(v)).max())
def main():
 start=time.monotonic();assert M.read(O/'ECONOMIC_DONE.json')['passed'];assert all(M.sha(p)==h for p,h in M.read(O/'FREEZE.json')['sha256'].items());out=O/'analysis';out.mkdir(exist_ok=True)
 meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');names={v['sector_id']:v['industry'] for v in meta.values()};matrix=pd.read_parquet(M.F).set_index(['day','sector']);prefix=[dict(r,account='T3') for r in C.rows(X.BASE/'results/daily.jsonl.gz')];commonNAV=D(prefix[-1]['nav']);au=M.BP.C.import_path('Q1_independent_ledger_audit',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');prices=au.Prices.__new__(au.Prices);prices.records={r['series_id']:r for r in M.read(M.P/'manifest.json')['series']};prices.cache={};rules=M.read(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json');calendar=sorted(pd.Timestamp(d) for d in rules['calendars']['A']);summary=[];groups=[];cycles=[];funds=[];parts={};audits={};targets=[];diag=[];all_daily={};all_ob={};missing=[]
 for policy,root,oldname in [('RAW',C.ABS,'RAW'),('ATT',C.ATT,'T3')]:
  ob=C.obj(O/policy/'results/T3.json.gz');ds=C.rows(O/policy/'results/daily.jsonl.gz');q4=[dict(r,account='T3') for r in C.rows(root/'results/daily.jsonl.gz') if r['account']==oldname];initial=D(q4[-1]['nav']);all_daily[policy]=ds;all_ob[policy]=ob
  oldcs=M.read(C.ABS/'analysis/CYCLES_Q4.json') if policy=='RAW' else M.read(C.ATT/'analysis/T3_CYCLES.json');oldcs=[c for c in oldcs if (c.get('account',oldname)==oldname)];boundary={(c['symbol'],c['entry_at']):D(c['net_pnl']) for c in oldcs if not c['closed']};cs,audit=au.audit_account('B0_'+policy,dict(audit_log=ob['audit']),prefix+q4+ds,prices,meta,calendar);audits[policy]=audit
  buys={(r['security_id'],r['at']):r for r in ob['trades'] if r['side']=='buy'};selection={r['day']:r for r in C.rows(O/policy/'results/selection.jsonl.gz')};part=[]
  for c in cs:
   if c['closed'] and c['exit_at'][:10]<=BOUND:continue
   k=c['symbol'],c['entry_at'];c['policy']=policy;c['Q1_net_contribution']=D(c['net_pnl'])-boundary.get(k,Z);tr=buys[k];c['signal_day']=tr['signal_at'][:10];c['origin']='inherited_12_31' if c['entry_at'][:10]<=BOUND else 'carry_intent' if c['signal_day']<=BOUND else 'new_Q1';part.append(c);cycles.append(c)
  assert abs(amount(part,'Q1_net_contribution')-(D(ds[-1]['nav'])-initial))<D('.00000001'),(policy,'quarter contribution')
  for origin in ['inherited_12_31','carry_intent','new_Q1']:
   pp=[c for c in part if c['origin']==origin];closed=[c for c in pp if c['closed']];opened=[c for c in pp if not c['closed']];groups.append(dict(policy=policy,origin=origin,cycles=len(pp),Q1_net=amount(pp,'Q1_net_contribution'),negative_Q1_contributions=-sum((D(c['Q1_net_contribution']) for c in pp if D(c['Q1_net_contribution'])<0),Z),closed=len(closed),open=len(opened),closed_lifetime_tail30_Q1_net=amount([c for c in closed if float(c['net_return'])>=.3],'Q1_net_contribution'),closed_other_Q1_net=amount([c for c in closed if float(c['net_return'])<.3],'Q1_net_contribution'),open_Q1_marked_net=amount(opened,'Q1_net_contribution')))
  for tr in ob['trades']:
   if tr['side']!='buy' or tr['at'][:10]<=BOUND:continue
   day=tr['signal_at'][:10];sid=tr['security_id'];sec=meta[sid]['sector_id'];r=matrix.loc[(day,sec)];carry=day<=BOUND
   if policy=='ATT' and not carry:assert sec in selection[day]['targets'] and sid in selection[day]['selected']
   funds.append(dict(policy=policy,sid=sid,name=meta[sid]['name'],sector=sec,industry=meta[sid]['industry'],decision=day,fill=tr['at'],carry_intent=carry,shares=tr['shares'],cash_cost=D(tr['gross_cny'])+D(tr['fees_cny']),R21=float(r.R21),effective_members=int(r.attention_members),snapshot_members=int(r.member_count)))
  trades=[r for r in ob['trades'] if r['at'][:10]>BOUND];fees=D(ds[-1]['fees_cny'])-D(q4[-1]['fees_cny']);risk=[r for r in ob['audit'] if r['kind']=='risk_checkpoint' and r['at'][:10]>BOUND];parts[policy]=dict(principal_flow=sum((D(r['gross_cny'])*(1 if r['side']=='sell' else -1) for r in trades),Z),dividend_accrued=sum((D(r['receivable']['net_local']) for r in ob['audit'] if r['kind']=='dividend_accrual' and r['receivable']['ex_at'][:10]>BOUND),Z),inventory_change=D(ds[-1]['inventory'])-D(q4[-1]['inventory']),explicit_fee=-fees)
  assert abs(sum(parts[policy].values(),Z)-(D(ds[-1]['nav'])-initial))<D('.00000001'),(policy,'cashflow bridge')
  fr=[r for r in funds if r['policy']==policy and not r['carry_intent']];industry_cash=collections.defaultdict(lambda:Z);date_industry=collections.defaultdict(set)
  for r in fr:industry_cash[r['sector']]+=r['cash_cost'];date_industry[r['decision']].add(r['sector'])
  repeated=[];seen={c['symbol'] for c in cs if c['entry_at'][:10]<=BOUND};newcs=sorted([c for c in part if c['origin']=='new_Q1'],key=lambda c:(c['entry_at'],c['symbol']));within=collections.Counter();repeat_prior=0;repeat_within=0
  for c in newcs:
   sid=c['symbol'];cost=D(c['buy_gross'])+D(c['buy_fees']);prior=sid in seen;rep=within[sid]>0;repeat_prior+=prior;repeat_within+=rep;repeated.append(dict(policy=policy,sid=sid,entry=c['entry_at'],seen_before_Q1=prior,Q1_repeat=rep,buy_cash=cost,Q1_net=c['Q1_net_contribution']));within[sid]+=1
  M.save(out/(policy+'_REPEAT_CYCLES.json'),repeated)
  open_cs=[c for c in part if not c['closed']]
  summary.append(dict(policy=policy,Q1_initial_NAV=initial,Q1_end_NAV=D(ds[-1]['nav']),Q1_net_return=float(D(ds[-1]['nav'])/initial-1),Q1_NAV_change=D(ds[-1]['nav'])-initial,Q1_max_drawdown=mdd(initial,ds),common_9_30_NAV=commonNAV,cumulative_9_30_return=float(D(ds[-1]['nav'])/commonNAV-1),cumulative_9_30_max_drawdown=mdd(commonNAV,q4+ds),Q1_fees=fees,Q1_slippage=sum((D(r['shares'])*abs(D(r['price'])-D(r['raw_open'])) for r in trades),Z),buy_fills=sum(r['side']=='buy' for r in trades),sell_fills=sum(r['side']=='sell' for r in trades),initial_positions=len(q4[-1]['positions']),end_positions=len(ds[-1]['positions']),peak_positions=max(len(r['positions']) for r in ds),mean_exposure=float(np.mean([float(r['inventory'])/float(r['nav']) for r in ds])),mean_available_NAV_fraction=float(np.mean([float(r['available'])/float(r['nav']) for r in ds])),end_inventory=D(ds[-1]['inventory']),end_available=D(ds[-1]['available']),end_unclosed_cycles=len(open_cs),unclosed_lifetime_net=amount(open_cs,'net_pnl'),unclosed_Q1_marked_net=amount(open_cs,'Q1_net_contribution'),ACT_pauses=sum(r['event']=='pause' for r in risk),ACT_resumes=sum(r['event']=='resume' for r in risk),ACT_paused_closes=sum(not r['on'] for r in risk),actual_new_industries=len(industry_cash),new_buy_cash=sum(industry_cash.values(),Z),new_buy_fills=len(fr),max_new_industries_per_signal_day=max(map(len,date_industry.values()),default=0),repeat_Q1_cycles=repeat_within,previously_bought_cycles=repeat_prior,repeat_Q1_buy_cash=sum((r['buy_cash'] for r in repeated if r['Q1_repeat']),Z),previously_bought_cash=sum((r['buy_cash'] for r in repeated if r['seen_before_Q1']),Z),quarter_closes=len(ds)))
  for row in ds:
   day=row['at'][:10]
   for sid in row['positions']:
    dates,closes,_=prices.cache[sid];idx=dates.searchsorted(pd.Timestamp(day));exact=idx<len(dates) and dates[idx]==pd.Timestamp(day)
    if not exact or pd.isna(closes[idx]):missing.append(dict(policy=policy,day=day,sid=sid,prior_legal_mark_proxy=True))
  if policy=='ATT':
   for r in selection.values():
    targets.append(dict(day=r['day'],targets=r['targets'],raw_I_count=r['raw_I_count'],capacity=r['maximum_B'],selected=len(r['selected']),target_pool_count=r['target_pool_count']))
    for sec in r['targets']:
     q=matrix.loc[(r['day'],sec)];diag.append(dict(day=r['day'],sector=sec,industry=names[sec],R21=float(q.R21),effective_members=int(q.attention_members),snapshot_members=int(q.member_count),attention=float(q.attention_ratio)))
 # Set-spell lengths measure exact 3-industry set stability, not hindsight trends.
 spells=[];last=None
 for r in targets:
  sig=tuple(sorted(r['targets']))
  if sig!=last:spells.append(dict(start=r['day'],end=r['day'],targets=sig,observations=1));last=sig
  else:spells[-1]['end']=r['day'];spells[-1]['observations']+=1
 spells[0]['left_censored']=True;spells[-1]['right_censored']=True
 sector_spells=[];active={}
 for i,r in enumerate(targets):
  now=set(r['targets'])
  for sec in list(active):
   if sec not in now:sector_spells.append(active.pop(sec))
  for sec in sorted(now):
   if sec not in active:active[sec]=dict(sector=sec,industry=names[sec],start=r['day'],end=r['day'],observations=0,left_censored=i==0,right_censored=False)
   active[sec]['end']=r['day'];active[sec]['observations']+=1
 for r in active.values():r['right_censored']=True;sector_spells.append(r)
 stability=dict(target_days=len(targets),target_industry_days=len(diag),set_changes=max(len(spells)-1,0),distinct_target_sets=len({tuple(sorted(r['targets'])) for r in targets}),target_industry_union=len({r['sector'] for r in diag}),set_spell_observations=[r['observations'] for r in spells],set_spell_median=float(np.median([r['observations'] for r in spells])),set_spell_max=max(r['observations'] for r in spells),sector_spell_median=float(np.median([r['observations'] for r in sector_spells])),sector_spell_max=max(r['observations'] for r in sector_spells),effective_lt5_target_days=sum(r['effective_members']<5 for r in diag),snapshot_lt5_target_days=sum(r['snapshot_members']<5 for r in diag),R21_nonpositive_target_days=sum(r['R21']<=0 for r in diag),capacity=sum(r['capacity'] for r in targets),selected=sum(r['selected'] for r in targets),target_no_rawI_days=sum(r['target_pool_count']==0 for r in targets))
 flowsplits=[]
 for policy in ['RAW','ATT']:
  cc=[c for c in cycles if c['policy']==policy and c['origin']=='new_Q1']
  for group in ['R21_nonpositive','effective_members_lt5','all']:
   pp=[c for c in cc if group=='all' or (matrix.loc[(c['signal_day'],meta[c['symbol']]['sector_id'])].R21<=0 if group=='R21_nonpositive' else matrix.loc[(c['signal_day'],meta[c['symbol']]['sector_id'])].attention_members<5)];flowsplits.append(dict(policy=policy,group=group,cycles=len(pp),buy_cash=sum((D(c['buy_gross'])+D(c['buy_fees']) for c in pp),Z),closed=sum(c['closed'] for c in pp),closed_net=amount([c for c in pp if c['closed']],'Q1_net_contribution'),open=sum(not c['closed'] for c in pp),open_marked_net=amount([c for c in pp if not c['closed']],'Q1_net_contribution')))
 s0,s1=summary;bridge={k:parts['ATT'][k]-parts['RAW'][k] for k in parts['RAW']};bridge.update(initial_NAV_difference=s1['Q1_initial_NAV']-s0['Q1_initial_NAV'],Q1_profit_difference=s1['Q1_NAV_change']-s0['Q1_NAV_change'],terminal_NAV_difference=s1['Q1_end_NAV']-s0['Q1_end_NAV']);assert abs(sum((bridge[k] for k in parts['RAW']),Z)-bridge['Q1_profit_difference'])<D('.00000001');assert abs(bridge['initial_NAV_difference']+bridge['Q1_profit_difference']-bridge['terminal_NAV_difference'])<D('.00000001')
 for name,data in [('SUMMARY',summary),('ORIGIN_CONTRIBUTIONS',groups),('CYCLES',cycles),('ACTUAL_BUY_USAGE',funds),('TARGETS',targets),('TARGET_DIAGNOSTICS',diag),('TARGET_SPELLS',spells),('SECTOR_SPELLS',sector_spells),('FUNDING_DIAGNOSTICS',flowsplits),('MISSING_CLOSE_MARKS',missing)]:
  M.save(out/(name+'.json'),data)
  if data:pd.DataFrame(M.N.encoded(data)).to_csv(out/(name+'.csv'),index=False)
 M.save(out/'STABILITY.json',stability);M.save(out/'MONEY_BRIDGE.json',bridge);M.save(out/'VERIFICATION.json',dict(passed=True,own_12_31_boundaries=True,independent_original_audit=audits,all_cycle_and_cashflow_bridges_exact=True,missing_close_mark_proxy_positiondays=len(missing),seconds=time.monotonic()-start));print('Q1_AUDITED_SUMMARY',json.dumps(M.N.encoded(summary)),flush=True);print('ORIGINS',json.dumps(M.N.encoded(groups)),flush=True);print('MONEY_BRIDGE',json.dumps(M.N.encoded(bridge)),flush=True);print('STABILITY',json.dumps(stability),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ANALYSIS_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
