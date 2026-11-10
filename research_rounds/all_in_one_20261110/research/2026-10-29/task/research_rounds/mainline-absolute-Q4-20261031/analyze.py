"""Q4 suffix accounting, inherited-cycle boundary and observed gate effects."""
import importlib.util,sys
from pathlib import Path
_spec=importlib.util.spec_from_file_location('Q4_analysis_implementation',Path(__file__).with_name('experiment.py'));X=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=X;_spec.loader.exec_module(X)
import json,gzip,time,collections
from pathlib import Path
import pandas as pd,numpy as np
M=X.M;O=X.O;D=M.D;Z=D(0)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def main():
 t=time.monotonic();assert M.read(O/'ECONOMIC_DONE.json')['passed'];f=M.read(O/'FREEZE.json');assert all(M.sha(p)==h for p,h in f['sha256'].items());assert all(M.sha(O/'industry-facts'/p)==h for p,h in f['industry_sha'].items())
 original=rows(X.BASE/'results/daily.jsonl.gz');q4=rows(O/'results/daily.jsonl.gz');selection=rows(O/'results/selection.jsonl.gz');funnel=M.read(O/'results/FUNNEL.json');meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');seedcs=M.read(X.BASE/'analysis/NEW_CYCLES.json');seedmap={(c['symbol'],c['entry_at']):D(c['net_pnl']) for c in seedcs if not c['closed']};seed_nav=D(M.read(O/'RECOVERY_GATE.json')['NAV'])
 au=M.BP.C.import_path('Q4_suffix_original_audit',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');prices=au.Prices.__new__(au.Prices);prices.records={r['series_id']:r for r in M.read(M.P/'manifest.json')['series']};prices.cache={};rules=M.read(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json');cal=sorted(pd.Timestamp(x) for x in rules['calendars']['A']);matrix=pd.read_parquet(M.F);md={d:g.set_index('sector') for d,g in matrix.groupby('day',sort=False)}
 summaries=[];campaigns=[];audit=[];dailycon=[];contrib_by_stock={};buyrows=[];stocks={};positiondays=[];gatecases=[];objects={};newclosed=[];cash_parts={}
 for key in ['RAW','POS']:
  ob=obj(O/'results'/f'{key}.json.gz');objects[key]=ob;ds=[d for d in q4 if d['account']==key];prefix=[dict(d,account=key) for d in original]
  cs,receipt=au.audit_account('B0_'+key,dict(audit_log=ob['audit']),prefix+ds,prices,meta,cal,dailycon);receipt['account']=key;audit.append(receipt)
  stock=collections.defaultdict(lambda:Z);cc=[]
  for c in cs:
   if c['closed'] and c['exit_at'][:10]<='2025-09-30':continue
   c['account']=key;c['Q4_net_contribution']=c['net_pnl']-seedmap.get((c['symbol'],c['entry_at']),Z);stock[c['symbol']]+=c['Q4_net_contribution'];campaigns.append(c);cc.append(c)
  assert abs(sum(stock.values(),Z)-(D(ds[-1]['nav'])-seed_nav))<D('.00000001');stocks[key]=stock
  for sid,net in stock.items():newclosed.append(dict(account=key,sid=sid,name=meta[sid]['name'],Q4_contribution=net))
  # Value of inherited/current positions in absolute-nonpositive sectors.
  inherited_until={c['symbol']:c['exit_at'] for c in cs if (c['symbol'],c['entry_at']) in seedmap};unknown_marks=[]
  for d in ds:
   day=d['at'][:10];g=md[day];negative=Z;inherited_negative=Z;inv=Z;negative_stocks=0;sectors=set()
   for sid,n in d['positions'].items():
    value=D(n)*prices.mark(sid,day);inv+=value;sec=meta[sid]['sector_id'];sectors.add(sec)
    if g.loc[sec,'R21']<=0:
     negative+=value;negative_stocks+=1
     if sid in inherited_until and (inherited_until[sid] is None or d['at']<inherited_until[sid]):inherited_negative+=value
    dates,closes,_=prices.cache[sid];ix=dates.get_indexer([pd.Timestamp(day)])[0]
    if ix<0 or not np.isfinite(closes[ix]):unknown_marks.append([sid,day])
   assert abs(inv-D(d['inventory']))<D('.00000001')
   positiondays.append(dict(account=key,day=day,NAV=D(d['nav']),inventory=inv,negative_sector_value=negative,negative_sector_NAV_fraction=negative/D(d['nav']),negative_sector_inventory_fraction=negative/inv if inv else Z,inherited_same_cycle_negative_value=inherited_negative,negative_sector_stocks=negative_stocks,held_industries=len(sectors),held_stocks=len(d['positions'])))
  for x in ob['trades']:
   if x['side']!='buy' or x['at'][:10]<='2025-09-30':continue
   decision=x['signal_at'][:10];sid=x['security_id'];r=md[decision].loc[meta[sid]['sector_id']];carry=decision<='2025-09-30';negative=r.R21<=0
   if key=='POS' and not carry:assert not negative
   buyrows.append(dict(account=key,decision=decision,fill=x['at'],sid=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],carry_in_Q3_intent=carry,industry_R21=float(r.R21),nonpositive_at_decision=bool(negative),shares=x['shares'],cash_cost=D(x['gross_cny'])+D(x['fees_cny'])))
  nav=np.array([float(x['nav']) for x in ds]);peak=np.maximum.accumulate(np.r_[float(seed_nav),nav])[1:];dd=1-nav/peak;held=[r for r in positiondays if r['account']==key];sel=[r for r in selection if r['policy']==key];ct=collections.Counter();reasons=collections.Counter()
  for r in funnel:
   if r['policy']==key:ct.update(r['counts']);reasons.update(r['Q_reasons'])
  # Only Q4 events/fees/costs; Q3 already known boundary is not new profit.
  trades=[x for x in ob['trades'] if x['at'][:10]>'2025-09-30'];risk=[x for x in ob['audit'] if x['kind']=='risk_checkpoint' and x['at'][:10]>'2025-09-30'];closed=[c for c in cc if c['closed']];opened=[c for c in cc if not c['closed']];tail=[c for c in closed if c['net_return']>=.3];ordinary=[c for c in closed if c['net_return']<.3];br=[r for r in buyrows if r['account']==key];fresh=[r for r in br if not r['carry_in_Q3_intent']];initial_fees=D(original[-1]['fees_cny'])
  summary=dict(account=key,seed_NAV=seed_nav,end_NAV=D(ds[-1]['nav']),Q4_net_return=float(nav[-1]/float(seed_nav)-1),Q4_NAV_contribution=D(ds[-1]['nav'])-seed_nav,Q4_max_drawdown=float(dd.max()),end_drawdown=float(dd[-1]),mean_exposure=float(np.mean([float(r['inventory'])/float(r['NAV']) for r in held])),mean_negative_sector_NAV_fraction=float(np.mean([float(r['negative_sector_NAV_fraction']) for r in held])),mean_negative_sector_inventory_fraction=float(np.mean([float(r['negative_sector_inventory_fraction']) for r in held])),end_negative_sector_value=held[-1]['negative_sector_value'],end_negative_sector_NAV_fraction=float(held[-1]['negative_sector_NAV_fraction']),end_inherited_same_cycle_negative_value=held[-1]['inherited_same_cycle_negative_value'],mean_inherited_same_cycle_negative_NAV_fraction=float(np.mean([float(r['inherited_same_cycle_negative_value'])/float(r['NAV']) for r in held])),end_positions=len(ds[-1]['positions']),peak_positions=max(len(d['positions']) for d in ds),Q4_fees=D(ds[-1]['fees_cny'])-initial_fees,Q4_slippage=sum((D(x['shares'])*abs(D(x['price'])-D(x['raw_open'])) for x in trades),Z),Q4_buy_fills=sum(x['side']=='buy' for x in trades),Q4_sell_fills=sum(x['side']=='sell' for x in trades),carry_in_Q3_buy_fills=sum(r['carry_in_Q3_intent'] for r in br),fresh_Q4_nonpositive_buy_fills=sum(r['nonpositive_at_decision'] for r in fresh),fresh_Q4_nonpositive_buy_cash=sum((r['cash_cost'] for r in fresh if r['nonpositive_at_decision']),Z),carry_in_nonpositive_buy_cash=sum((r['cash_cost'] for r in br if r['carry_in_Q3_intent'] and r['nonpositive_at_decision']),Z),Q4_negative_cycle_contributions=-sum((c['Q4_net_contribution'] for c in cc if c['Q4_net_contribution']<0),Z),closed_lifetime_tail30_Q4_contribution=sum((c['Q4_net_contribution'] for c in tail),Z),closed_other_Q4_contribution=sum((c['Q4_net_contribution'] for c in ordinary),Z),open_Q4_marked_contribution=sum((c['Q4_net_contribution'] for c in opened),Z),closed_tail_cycles=len(tail),closed_other_cycles=len(ordinary),open_cycles=len(opened),ACT_pauses=sum(x['event']=='pause' for x in risk),ACT_resumes=sum(x['event']=='resume' for x in risk),ACT_paused_closes=sum(not x['on'] for x in risk),raw_I_stock_days=sum(r['raw_I_count'] for r in sel),rank_unknown_excluded=sum(r['P_rank_unknown_count'] for r in sel),maximum_capacity_stock_days=sum(r['maximum_B'] for r in sel),selected_stock_days=sum(r['B'] for r in sel),post_Q_counts=dict(ct),Q_reasons=dict(reasons),final_counts=ob['counts'],unknown_price_position_days=len(unknown_marks),unknown_mark_cases=unknown_marks)
  cash_parts[key]=dict(principal_flow=sum((D(x['gross_cny'])*(1 if x['side']=='sell' else -1) for x in trades),Z),new_dividend_entitlements=sum((D(x['receivable']['net_local']) for x in ob['audit'] if x['kind']=='dividend_accrual' and x['receivable']['ex_at'][:10]>'2025-09-30'),Z),terminal_inventory=D(ds[-1]['inventory']),fees=summary['Q4_fees'])
  assert abs(summary['closed_lifetime_tail30_Q4_contribution']+summary['closed_other_Q4_contribution']+summary['open_Q4_marked_contribution']-summary['Q4_NAV_contribution'])<D('.00000001');summaries.append(summary);print('AUDITED_Q4',json.dumps(M.N.encoded(summary),ensure_ascii=False),flush=True)
  # RAW actual new negative-sector trades as observational gate examples.
  if key=='RAW':
   firstbuy={}
   for tr in trades:
    if tr['side']=='buy':firstbuy.setdefault((tr['security_id'],tr['at']),tr)
   for c in cc:
    if c['entry_at'][:10]<='2025-09-30':continue
    tr=firstbuy[(c['symbol'],c['entry_at'])];decision=tr['signal_at'][:10]
    if decision<='2025-09-30':continue
    r=md[decision].loc[meta[c['symbol']]['sector_id']]
    if r.R21<=0:gatecases.append(dict(sid=c['symbol'],name=meta[c['symbol']]['name'],industry=meta[c['symbol']]['industry'],decision=decision,entry=c['entry_at'],exit=c['exit_at'],closed=c['closed'],R21=float(r.R21),actual_RAW_cost=c['buy_gross']+c['buy_fees'],actual_RAW_Q4_contribution=c['Q4_net_contribution']))
 # Common initial state makes terminal inter-arm difference equal suffix diff.
 bridge=[dict(sid=sid,name=meta[sid]['name'],RAW_Q4=stocks['RAW'][sid],POS_Q4=stocks['POS'][sid],POS_minus_RAW=stocks['POS'][sid]-stocks['RAW'][sid]) for sid in sorted(set(stocks['RAW'])|set(stocks['POS']))]
 delta=summaries[1]['end_NAV']-summaries[0]['end_NAV'];assert abs(sum((r['POS_minus_RAW'] for r in bridge),Z)-delta)<D('.00000001')
 money=dict(POS_minus_RAW=delta,principal_flow=cash_parts['POS']['principal_flow']-cash_parts['RAW']['principal_flow'],dividend_entitlements=cash_parts['POS']['new_dividend_entitlements']-cash_parts['RAW']['new_dividend_entitlements'],terminal_inventory=cash_parts['POS']['terminal_inventory']-cash_parts['RAW']['terminal_inventory'],explicit_fees=-(cash_parts['POS']['fees']-cash_parts['RAW']['fees']));assert abs(sum((money[k] for k in ['principal_flow','dividend_entitlements','terminal_inventory','explicit_fees']),Z)-delta)<D('.00000001')
 for c in gatecases:
  later=[r for r in buyrows if r['account']=='POS' and r['sid']==c['sid'] and r['fill']>=c['entry']];c['POS_later_same_stock_buy']=later[0]['fill'] if later else None;c['POS_full_Q4_stock_contribution']=stocks['POS'][c['sid']]
 observed=dict(actual_RAW_negative_sector_cycles=len(gatecases),positive_cycles=sum(c['actual_RAW_Q4_contribution']>0 for c in gatecases),negative_cycles=sum(c['actual_RAW_Q4_contribution']<0 for c in gatecases),positive_RAW_contribution=sum((c['actual_RAW_Q4_contribution'] for c in gatecases if c['actual_RAW_Q4_contribution']>0),Z),negative_RAW_contribution=sum((c['actual_RAW_Q4_contribution'] for c in gatecases if c['actual_RAW_Q4_contribution']<0),Z),RAW_net=sum((c['actual_RAW_Q4_contribution'] for c in gatecases),Z),POS_later_same_stock_cycles=sum(c['POS_later_same_stock_buy'] is not None for c in gatecases),not_single_mechanism_causal_avoided_loss_or_missed_profit=True)
 # Full existing90 state dependency availability for every matrix cell.
 coverage=[]
 for p in (O/'industry-facts').glob('*.parquet'):
  st=pd.read_parquet(p,columns=['e0_ready','e0_target']);g=matrix[matrix.sector.eq(p.stem)];q=st.reindex(pd.to_datetime(g.day));g=g.copy();g['Q_dependency_known']=q.e0_ready.to_numpy()==True;g['Q_target_known']=q.e0_target.notna().to_numpy();coverage.append(g[['quarter','Q_dependency_known','Q_target_known']])
 cov=pd.concat(coverage).groupby('quarter').agg(cells=('Q_dependency_known','size'),ready=('Q_dependency_known','sum'),target_known=('Q_target_known','sum')).reset_index().to_dict('records')
 out=O/'analysis';out.mkdir(exist_ok=False)
 for n,data in [('SUMMARY',summaries),('CYCLES_Q4',campaigns),('DAILY_NEGATIVE_EXPOSURE',positiondays),('BUY_USAGE',buyrows),('STOCK_BRIDGE',bridge),('RAW_BLOCKED_NEGATIVE_CYCLES',gatecases),('INDUSTRY_Q_COVERAGE',cov)]:
  M.save(out/(n+'.json'),data)
  if data:pd.DataFrame(M.N.encoded(data)).to_csv(out/(n+'.csv'),index=False)
 M.save(out/'OBSERVED_GATE_TRADEOFF.json',observed);M.save(out/'MONEY_BRIDGE.json',money);M.save(out/'VERIFICATION.json',dict(passed=True,audits=audit,seed_boundary_NAV=seed_nav,Q3_known_profit_subtracted_from_suffix=True,stock_difference_bridge=delta,mutually_exclusive_money_components_reconciled=True,full90_industry_dependencies=cov,unknowns_not_false=True,only_Q4_two_normal_economic_paths=True,seconds=time.monotonic()-t))
 print('GATE_TRADEOFF',json.dumps(M.N.encoded(observed)),flush=True);print('BRIDGE_POS_RAW',str(delta),'ANALYSIS_SECONDS',time.monotonic()-t,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  import traceback;M.save(O/'ANALYSIS_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
