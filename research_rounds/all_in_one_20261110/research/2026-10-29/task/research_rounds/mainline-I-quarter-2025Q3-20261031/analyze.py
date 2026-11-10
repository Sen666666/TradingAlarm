"""Existing results only: independent original ledger audit and exact bridge."""
import adapter as M
import gzip,json,collections,time
from pathlib import Path
import numpy as np,pandas as pd
O=M.O;D=M.D;Z=D(0)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def main():
 t=time.monotonic();assert M.read(O/'ECONOMIC_DONE.json')['passed'];freeze=M.read(O/'FREEZE.json');assert all(M.sha(p)==h for p,h in freeze['sha256'].items())
 data=rows(O/'results/daily.jsonl.gz');selected=rows(O/'results/selection.jsonl.gz');fun=M.read(O/'results/FUNNEL.json');objects={k:obj(O/'results'/f'{k}.json.gz') for k in ['H1','ATT']}
 meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');au=M.BP.C.import_path('mainline_independent_audit',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');prices=au.Prices.__new__(au.Prices);prices.records={r['series_id']:r for r in M.read(M.P/'manifest.json')['series']};prices.cache={}
 rules=M.read(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json');calendar=sorted(pd.Timestamp(x) for x in rules['calendars']['A']);summary=[];campaigns=[];audits=[];contrib=[];stock={};details=[];groups=[]
 for key in ['H1','ATT']:
  ob=objects[key];ds=[x for x in data if x['account']==key]
  cs,receipt=au.audit_account('B0_'+key,dict(audit_log=ob['audit']),ds,prices,meta,calendar,contrib);receipt['account']=key;audits.append(receipt)
  nav=np.array([float(x['nav']) for x in ds]);peak=np.maximum.accumulate(np.r_[1e6,nav])[1:];dd=1-nav/peak;longest=0;lastpeak=-1;pv=1e6
  for i,n in enumerate(nav):
   if n>=pv:pv=n;lastpeak=i
   else:longest=max(longest,i-lastpeak)
  ss=collections.defaultdict(lambda:dict(buys=Z,sales=Z,fees=Z,dividends=Z,terminal=Z,net=Z,cycles=0))
  for c in cs:
   c['account']=key;campaigns.append(c);v=ss[c['symbol']];v['buys']+=c['buy_gross'];v['sales']+=c['sell_gross'];v['fees']+=c['buy_fees']+c['sell_fees'];v['dividends']+=c['dividends'];v['terminal']+=c['market_value'];v['net']+=c['net_pnl'];v['cycles']+=1
  stock[key]=ss;assert abs(sum((v['net'] for v in ss.values()),Z)-(D(ds[-1]['nav'])-D(1_000_000)))<D('.00000001')
  closed=[c for c in cs if c['closed']];opened=[c for c in cs if not c['closed']];tail=[c for c in closed if c['net_return']>=.3];ordinary=[c for c in closed if c['net_return']<.3]
  for label,cc in [('closed_tail30',tail),('closed_ordinary',ordinary),('open_all',opened)]:groups.append(dict(account=key,group=label,cycles=len(cc),net=sum((c['net_pnl'] for c in cc),Z),negative_loss=-sum((c['net_pnl'] for c in cc if c['net_pnl']<0),Z)))
  sel=[x for x in selected if x['policy']==key];funs=[x for x in fun if x['policy']==key];ct=collections.Counter();qr=collections.Counter()
  for x in funs:ct.update(x['counts']);qr.update(x['Q_reasons'])
  auditcounts=collections.Counter(x['kind'] for x in ob['audit']);risk=[x for x in ob['audit'] if x['kind']=='risk_checkpoint'];unknownpos=[]
  for d in ds:
   for sid in d['positions']:
    if sid not in prices.cache:prices.mark(sid,d['at'][:10])
    dates,closes,_=prices.cache[sid];i=dates.get_indexer([pd.Timestamp(d['at'][:10])])[0]
    if i<0 or not np.isfinite(closes[i]):unknownpos.append((sid,d['at'][:10]))
  s=dict(account=key,net_return=float(nav[-1]/1e6-1),final_nav=D(ds[-1]['nav']),max_drawdown=float(dd.max()),underwater_at_end=bool(dd[-1]>0),longest_underwater_observations=longest,fees=D(ds[-1]['fees_cny']),slippage=sum((D(x['shares'])*abs(D(x['price'])-D(x['raw_open'])) for x in ob['trades']),Z),mean_exposure=float(np.mean([float(x['inventory'])/n for x,n in zip(ds,nav)])),peak_positions=max(len(x['positions']) for x in ds),end_positions=len(ds[-1]['positions']),end_cash_available=D(ds[-1]['available']),end_order_reserved=D(ds[-1]['order_reserved']),buy_fills=sum(x['side']=='buy' for x in ob['trades']),sell_fills=sum(x['side']=='sell' for x in ob['trades']),buy_orders=auditcounts['reserve'],cycles=len(cs),closed=len(closed),open=len(opened),all_negative_cycle_loss=-sum((c['net_pnl'] for c in cs if c['net_pnl']<0),Z),closed_tail30_net=sum((c['net_pnl'] for c in tail),Z),closed_ordinary_net=sum((c['net_pnl'] for c in ordinary),Z),open_marked_net=sum((c['net_pnl'] for c in opened),Z),open_tail30_marked_cycles=sum(c['net_return']>=.3 for c in opened),ACT_pauses=sum(x['event']=='pause' for x in risk),ACT_resumes=sum(x['event']=='resume' for x in risk),ACT_paused_closes=sum(not x['on'] for x in risk),raw_I_stock_days=sum(x['raw_I_count'] for x in sel),common_P_stock_days=sum(x['P_score_known_count'] for x in sel),rank_unknown_common_excluded=sum(x['P_rank_unknown_count'] for x in sel),selected_stock_days=sum(x['B'] for x in sel),attention_le1_selected_stock_days=sum(x['attention_at_or_below1_selected'] for x in sel),intent_count=sum(len(x['intents']) for x in ob['decisions']),post_Q_counts=dict(ct),Q_reasons=dict(qr),final_counts=ob['counts'],unknown_price_position_days=len(unknownpos),unknown_position_cases=unknownpos,max_stock_weight=receipt['max_stock_weight'],max_industry_weight=receipt['max_sector_weight'])
  summary.append(s);print('RESULT',key,'return',s['net_return'],'DD',s['max_drawdown'],'buys',s['buy_fills'],'fees',s['fees'],flush=True)
  for x in ob['audit']:
   if x['kind']=='risk_checkpoint' and x['event']:details.append(dict(account=key,**x))
 # Strict mutually exclusive money bridge: trade principal, entitlement,
 # terminal inventory and explicit fee differences; not causal sleeves.
 bridge=[]
 for sid in sorted(set(stock['H1'])|set(stock['ATT'])):
  a=stock['H1'][sid];b=stock['ATT'][sid]
  row=dict(symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],baseline_net=a['net'],attention_net=b['net'],difference=b['net']-a['net'],net_principal_flow_difference=(b['sales']-b['buys'])-(a['sales']-a['buys']),dividend_entitlement_difference=b['dividends']-a['dividends'],terminal_inventory_difference=b['terminal']-a['terminal'],explicit_cost_difference=-(b['fees']-a['fees']))
  assert abs(row['difference']-sum((row[c] for c in ['net_principal_flow_difference','dividend_entitlement_difference','terminal_inventory_difference','explicit_cost_difference']),Z))<D('.00000001');bridge.append(row)
 delta=summary[1]['final_nav']-summary[0]['final_nav'];assert abs(sum((x['difference'] for x in bridge),Z)-delta)<D('.00000001')
 money=dict(final_NAV_difference_ATT_minus_H1=delta,**{c:sum((x[c] for x in bridge),Z) for c in ['net_principal_flow_difference','dividend_entitlement_difference','terminal_inventory_difference','explicit_cost_difference']})
 # Concrete exclusions at the actual buy decision. No counterfactual profits.
 lookup={(x['policy'],x['day']):x for x in selected};cases=[]
 for key in ['H1','ATT']:
  other='ATT' if key=='H1' else 'H1'
  for x in objects[key]['trades']:
   if x['side']!='buy':continue
   day=x['signal_at'][:10];sid=x['security_id'];mine=lookup[(key,day)];alt=lookup[(other,day)]
   if sid in alt['selected']:continue
   cases.append(dict(bought_by=key,other=other,decision=day,fill=x['at'],symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],shares=x['shares'],price=x['price'],cash_cost=D(x['gross_cny'])+D(x['fees_cny']),common_candidate=sid in alt['candidates'],other_shortlisted=False,selected_budget=mine['B'],full_quarter_stock_contribution_buyer=stock[key][sid]['net'],other_stock_contribution=stock[other][sid]['net'],contribution_difference_not_single_event_causal=True))
 # Verify exact common budgets, no duplicate IDs and before divergence money.
 for day in sorted(set(x['day'] for x in selected)):
  a=lookup['H1',day];b=lookup['ATT',day];assert a['candidates']==b['candidates'] and a['B']==b['B'] and len(a['selected'])==len(b['selected'])==a['B'];assert len(set(a['selected']))==a['B'] and len(set(b['selected']))==b['B']
 first_order=None
 for a,b in zip(objects['H1']['decisions'],objects['ATT']['decisions']):
  ia=[(x['sid'],x['cap'],x['budget']) for x in a['intents']];ib=[(x['sid'],x['cap'],x['budget']) for x in b['intents']]
  if ia!=ib:first_order=a['at'];break
 first_nav=None
 d0={x['at']:x for x in data if x['account']=='H1'};d1={x['at']:x for x in data if x['account']=='ATT'}
 for day in sorted(d0):
  a,b=d0[day],d1[day]
  if any(a[k]!=b[k] for k in ['nav','positions','available','order_reserved','fees_cny']):first_nav=day;break
 # Cache quality is input quality, not a classification of absent events.
 grade_unknown=0;missing_rows=0;days=pd.DatetimeIndex([x['at'][:10] for x in data if x['account']=='H1'])
 for p in (M.IC/'facts').glob('*.parquet'):
  f=pd.read_parquet(p,columns=['g_grade']);q=f.reindex(days);missing_rows+=int((~days.isin(f.index)).sum());grade_unknown+=int(q.g_grade.isna().sum())
 out=O/'analysis';out.mkdir(exist_ok=False)
 for name,rs in [('SUMMARY',summary),('CYCLES',campaigns),('GROUPS',groups),('STOCK_BRIDGE',bridge),('EXCLUDED_ACTUAL_BUY_CASES',cases),('ACT_EVENTS',details)]:
  M.save(out/(name+'.json'),rs)
  if rs:pd.DataFrame(M.N.encoded(rs)).to_csv(out/(name+'.csv'),index=False)
 with gzip.open(out/'stock-daily-contributions.jsonl.gz','wt') as f:
  for x in contrib:f.write(json.dumps(M.N.encoded(x))+'\n')
 M.save(out/'MONEY_BRIDGE.json',money);M.save(out/'VERIFICATION.json',dict(passed=True,independent_account_audits=audits,equal_common_budget_all_days=True,only_two_normal_accounts=True,first_intent_divergence=first_order,first_financial_divergence=first_nav,all_stock_money_difference_reconciled=True,data_quality=dict(common_stock_day_denominator=len(days)*1709,no_exact_daily_I_row_stock_days=missing_rows,grade_unknown_including_absent_rows=grade_unknown,missing_not_filled_zero=True,raw_I_cache_no_Q_prefilter=True,snapshot_survivorship_bias=True,all_history_consumed_not_OOS=True,daily_HLV_execution_proxy=True,pay_dates_and_bonus_sellability_proxy_retained=True),seconds=time.monotonic()-t))
 print('MONEY_BRIDGE',json.dumps(M.N.encoded(money)),flush=True);print('ANALYSIS_COMPLETE',time.monotonic()-t,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  import traceback;M.save(O/'ANALYSIS_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
