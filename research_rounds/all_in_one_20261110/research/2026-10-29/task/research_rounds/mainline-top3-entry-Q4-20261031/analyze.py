"""Saved paths only: new-entry concentration vs inherited capital."""
import top3 as T
import json,gzip,time,collections
import pandas as pd,numpy as np
M=T.M;X=T.X;O=T.O;D=M.D;Z=D(0)
def main():
 start=time.monotonic();assert M.read(O/'ECONOMIC_DONE.json')['passed'];f=M.read(O/'FREEZE.json');assert all(M.sha(p)==h for p,h in f['sha256'].items());ob=T.obj(O/'results/T3.json.gz');ds=T.rows(O/'results/daily.jsonl.gz');prefix=[dict(r,account='T3') for r in T.rows(X.BASE/'results/daily.jsonl.gz')];seedcs=M.read(X.BASE/'analysis/NEW_CYCLES.json');seedpnl={(c['symbol'],c['entry_at']):D(c['net_pnl']) for c in seedcs if not c['closed']};seednav=D(M.read(T.PREV/'RECOVERY_GATE.json')['NAV']);meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');names={v['sector_id']:v['industry'] for v in meta.values()};au=M.BP.C.import_path('top3_independent_audit',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');prices=au.Prices.__new__(au.Prices);prices.records={r['series_id']:r for r in M.read(M.P/'manifest.json')['series']};prices.cache={};rules=M.read(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json');calendar=sorted(pd.Timestamp(x) for x in rules['calendars']['A']);cs,audit=au.audit_account('B0_T3',dict(audit_log=ob['audit']),prefix+ds,prices,meta,calendar)
 cc=[]
 for c in cs:
  if c['closed'] and c['exit_at'][:10]<='2025-09-30':continue
  c['account']='T3';c['Q4_net_contribution']=c['net_pnl']-seedpnl.get((c['symbol'],c['entry_at']),Z);cc.append(c)
 assert abs(sum((c['Q4_net_contribution'] for c in cc),Z)-(D(ds[-1]['nav'])-seednav))<D('.00000001')
 rawob=T.obj(T.PREV/'results/RAW.json.gz');rawds=[r for r in T.rows(T.PREV/'results/daily.jsonl.gz') if r['account']=='RAW'];rawcs=[c for c in M.read(T.PREV/'analysis/CYCLES_Q4.json') if c['account']=='RAW'];allcs={'RAW':rawcs,'T3':cc};allob={'RAW':rawob,'T3':ob};allds={'RAW':rawds,'T3':ds};target=M.read(O/'TARGETS.json');targetmap={r['day']:set(r['targets']) for r in target};sel={r['day']:r for r in T.rows(O/'results/selection.jsonl.gz')};funds=[];groups=[];values=[];dailycapital=[];money_parts={};new_summary=None
 for key in ['RAW','T3']:
  obj=allob[key];quarter=allds[key];cycles=allcs[key];byentry={(c['symbol'],c['entry_at']):c for c in cycles};firstbuy={(tr['security_id'],tr['at']):tr for tr in obj['trades'] if tr['side']=='buy'};origin={};history=collections.defaultdict(list)
  for c in cycles:
   k=(c['symbol'],c['entry_at']);o='inherited' if c['entry_at'][:10]<='2025-09-30' else 'transition' if firstbuy[k]['signal_at'][:10]<='2025-09-30' else 'new_Q4';origin[k]=o;history[c['symbol']].append(c)
  for o in ['inherited','new_Q4','transition']:
   part=[c for c in cycles if origin[(c['symbol'],c['entry_at'])]==o];closed=[c for c in part if c['closed']];opened=[c for c in part if not c['closed']]
   groups.append(dict(account=key,origin=o,cycles=len(part),Q4_net=sum((D(c['Q4_net_contribution']) for c in part),Z),negative_Q4_contributions=-sum((D(c['Q4_net_contribution']) for c in part if D(c['Q4_net_contribution'])<0),Z),closed_lifetime_tail30_Q4_net=sum((D(c['Q4_net_contribution']) for c in closed if float(c['net_return'])>=.3),Z),closed_other_Q4_net=sum((D(c['Q4_net_contribution']) for c in closed if float(c['net_return'])<.3),Z),open_Q4_marked_net=sum((D(c['Q4_net_contribution']) for c in opened),Z),closed=len(closed),open=len(opened)))
  # Every actual fill is categorized by its own signal-day contract.
  for tr in obj['trades']:
   if tr['side']!='buy' or tr['at'][:10]<='2025-09-30':continue
   day=tr['signal_at'][:10];carry=day<='2025-09-30';sid=tr['security_id'];sector=meta[sid]['sector_id']
   if key=='T3' and not carry:assert sector in targetmap[day] and sid in sel[day]['selected']
   funds.append(dict(account=key,decision=day,fill=tr['at'],sid=sid,name=meta[sid]['name'],sector=sector,industry=meta[sid]['industry'],transition=carry,cash_cost=D(tr['gross_cny'])+D(tr['fees_cny']),shares=tr['shares']))
  for r in quarter:
   day=r['at'][:10];origin_sector=collections.defaultdict(lambda:Z);counts=collections.Counter();total=Z
   for sid,q in r['positions'].items():
    active=[c for c in history[sid] if c['entry_at']<=r['at'] and (not c['closed'] or c['exit_at']>r['at'])];assert len(active)==1,(key,sid,day,'cycle identity');c=active[0];o=origin[sid,c['entry_at']];sec=meta[sid]['sector_id'];v=D(q)*prices.mark(sid,day);origin_sector[o,sec]+=v;counts[o]+=1;total+=v
   assert abs(total-D(r['inventory']))<D('.00000001')
   for (o,sec),v in origin_sector.items():values.append(dict(account=key,day=day,origin=o,sector=sec,industry=names[sec],market_value=v,NAV_fraction=v/D(r['nav']),in_current_target=sec in targetmap[day]))
   for o in ['inherited','new_Q4','transition']:
    vs=[(s,v) for (ori,s),v in origin_sector.items() if ori==o];subtotal=sum((v for _,v in vs),Z);outside=sum((v for s,v in vs if s not in targetmap[day]),Z);top3=sum(sorted((v for _,v in vs),reverse=True)[:3],Z)
    dailycapital.append(dict(account=key,day=day,origin=o,stocks=counts[o],industries=len(vs),market_value=subtotal,NAV_fraction=subtotal/D(r['nav']),outside_current_target_value=outside,top3_industry_share_of_origin=float(top3/subtotal) if subtotal else None))
  # Exact money components; same seed cancels all boundary capital.
  trades=[x for x in obj['trades'] if x['at'][:10]>'2025-09-30'];fee=D(quarter[-1]['fees_cny'])-D(prefix[-1]['fees_cny']);money_parts[key]=dict(principal_flow=sum((D(x['gross_cny'])*(1 if x['side']=='sell' else -1) for x in trades),Z),dividend=sum((D(x['receivable']['net_local']) for x in obj['audit'] if x['kind']=='dividend_accrual' and x['receivable']['ex_at'][:10]>'2025-09-30'),Z),terminal=D(quarter[-1]['inventory']),fee=fee)
  if key=='T3':
   nav=np.array([float(r['nav']) for r in quarter]);dd=1-nav/np.maximum.accumulate(np.r_[float(seednav),nav])[1:];risk=[r for r in obj['audit'] if r['kind']=='risk_checkpoint' and r['at'][:10]>'2025-09-30'];ff=M.read(O/'results/FUNNEL.json');ct=collections.Counter();qr=collections.Counter()
   for z in ff:ct.update(z['counts']);qr.update(z['Q_reasons'])
   new_summary=dict(account='T3',seed_NAV=seednav,end_NAV=D(quarter[-1]['nav']),Q4_net_return=float(nav[-1]/float(seednav)-1),Q4_NAV_contribution=D(quarter[-1]['nav'])-seednav,Q4_max_drawdown=float(dd.max()),mean_exposure=float(np.mean([float(r['inventory'])/float(r['nav']) for r in quarter])),Q4_fees=fee,Q4_slippage=sum((D(x['shares'])*abs(D(x['price'])-D(x['raw_open'])) for x in trades),Z),Q4_buy_fills=sum(x['side']=='buy' for x in trades),Q4_sell_fills=sum(x['side']=='sell' for x in trades),end_positions=len(quarter[-1]['positions']),peak_positions=max(len(r['positions']) for r in quarter),mean_available_NAV_fraction=float(np.mean([float(r['available'])/float(r['nav']) for r in quarter])),end_available=D(quarter[-1]['available']),ACT_pauses=sum(r['event']=='pause' for r in risk),ACT_resumes=sum(r['event']=='resume' for r in risk),ACT_paused_closes=sum(not r['on'] for r in risk),post_Q_counts=dict(ct),Q_reasons=dict(qr),final_counts=obj['counts'])
 # Per-week targets, retaining all changes without new hysteresis.
 weekly=[];last=None;all_sets=set();changes=0
 for r in target:
  signature=tuple(sorted(r['targets']));r['target_set_changed']=last is not None and signature!=last;changes+=r['target_set_changed'];last=signature;all_sets.add(signature);r['week']=str(pd.Period(r['day'],'W-FRI'));r['target_names']=[names[s] for s in r['targets']]
 for week in dict.fromkeys(r['week'] for r in target):
  rr=[r for r in target if r['week']==week];secs=set(s for r in rr for s in r['targets']);weekly.append(dict(week=week,trading_days=len(rr),target_industry_union=[names[s] for s in sorted(secs)],distinct_target_sets=len({tuple(sorted(r['targets'])) for r in rr}),set_changes=sum(r['target_set_changed'] for r in rr)))
 # Actual entry concentration is not inferred from daily target count.
 concentration=[]
 for key in ['RAW','T3']:
  fresh=[r for r in funds if r['account']==key and not r['transition']];alloc=collections.defaultdict(lambda:Z);perday=collections.defaultdict(set)
  for r in fresh:alloc[r['sector']]+=r['cash_cost'];perday[r['decision']].add(r['sector'])
  total=sum(alloc.values(),Z);ordered=sorted(alloc,key=lambda s:(-alloc[s],s));concentration.append(dict(account=key,actual_new_buy_industries=len(alloc),new_buy_fills=len(fresh),actual_new_buy_cash=total,top3_actual_industry_cash_share=float(sum((alloc[s] for s in ordered[:3]),Z)/total) if total else None,max_new_buy_industries_per_signal_day=max(map(len,perday.values()),default=0),industry_buy_cash=[dict(sector=s,industry=names[s],cash=alloc[s],share=float(alloc[s]/total)) for s in ordered],transition_buy_fills=sum(r['account']==key and r['transition'] for r in funds)))
 gap=dict(target_industry_days=sum(len(r['targets']) for r in target),target_industry_days_without_rawI=sum(len(r['target_without_rawI']) for r in target),all_targets_without_rawI_days=sum(all(not n for n in r['target_rawI'].values()) for r in target),unique_target_industries=len({s for r in target for s in r['targets']}),distinct_target_sets=len(all_sets),target_set_changes=changes,maximum_capacity_stock_days=sum(r['maximum_B'] for r in M.read(O/'CAPACITY.json')),actual_selected_stock_days=sum(r['actual_selected'] for r in M.read(O/'CAPACITY.json')),shortage_days=sum(r['shortage']>0 for r in M.read(O/'CAPACITY.json')))
 rawsummary=next(r for r in M.read(T.PREV/'analysis/SUMMARY.json') if r['account']=='RAW');delta=new_summary['end_NAV']-D(rawsummary['end_NAV']);money=dict(T3_minus_RAW=delta,principal_flow=money_parts['T3']['principal_flow']-money_parts['RAW']['principal_flow'],dividend=money_parts['T3']['dividend']-money_parts['RAW']['dividend'],terminal=money_parts['T3']['terminal']-money_parts['RAW']['terminal'],explicit_fee=-(money_parts['T3']['fee']-money_parts['RAW']['fee']));assert abs(sum((money[k] for k in ['principal_flow','dividend','terminal','explicit_fee']),Z)-delta)<D('.00000001')
 out=O/'analysis';out.mkdir(exist_ok=False)
 for name,data in [('SUMMARY',[rawsummary,new_summary]),('ORIGIN_CONTRIBUTIONS',groups),('T3_CYCLES',cc),('CAPITAL_ORIGIN_DAILY',dailycapital),('INDUSTRY_VALUES_BY_ORIGIN',values),('ACTUAL_BUY_USAGE',funds),('NEW_ENTRY_CONCENTRATION',concentration),('WEEKLY_TARGETS',weekly),('DAILY_TARGETS',target)]:
  M.save(out/(name+'.json'),data)
  if data:pd.DataFrame(M.N.encoded(data)).to_csv(out/(name+'.csv'),index=False)
 M.save(out/'TARGET_GAPS.json',gap);M.save(out/'MONEY_BRIDGE.json',money);M.save(out/'VERIFICATION.json',dict(passed=True,new_independent_audit=audit,old_RAW_audit_reused=True,all_origin_contributions_reconciled=True,stock_value_and_origin_identity_checked=True,new_fills_in_own_signal_day_targets=True,old_positions_outside_targets_not_violations=True,Q3_profits_not_recounted=True,seconds=time.monotonic()-start));print('AUDITED_TOP3',json.dumps(M.N.encoded(new_summary)),flush=True);print('CONCENTRATION',json.dumps(M.N.encoded(concentration)),flush=True);print('TARGET_GAPS',json.dumps(gap),flush=True);print('MONEY',json.dumps(M.N.encoded(money)),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  import traceback;M.save(O/'ANALYSIS_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
