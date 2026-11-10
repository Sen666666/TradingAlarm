"""Explain already saved D10/B outcomes. No strategy/account/basis engine."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import csv,gzip,hashlib,importlib.util,json
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0);EPS=D('.000001');SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def book(p):
 SRC[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def gzrows(p):
 SRC[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt') as f:return[json.loads(x)for x in f]
def save(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n')
def csvout(p,rr):
 if rr:
  with p.open('w')as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def near(a,b,tag):assert abs(D(a)-D(b))<EPS,(tag,a,b)
def num(v,d=2):return f'{D(str(v)):.{d}f}'
BASE=T/'market_gross_admission_outcome_analysis_v1';CONTROL=T/'market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json';controls=read(CONTROL);annual=[];whole=[];data={};cohort_summary={}
for win in ['long','strong']:
 out=BASE/f'full_{win}_v1';summary=read(out/'SUMMARY.json');periods=read(out/'ALL_PERIODS_VS_ARCHIVED_B.json')
 for item in periods:
  if item['grain']!='year':continue
  for arm in ['D_GROSS10','ARCHIVED_B']:
   p=item[arm];annual.append(dict(window=win,period=item['period'] if win=='long' else item['period']+('H2' if item['period']=='2025' else 'H1'),arm=arm,actual_first_CLOSE=p['start'],actual_last_CLOSE=p['end'],CLOSE_days=p['days'],initial_own_period_NAV=p['initial_own_NAV'],end_NAV=p['end_NAV'],net_CNY=p['wealth_change'],return_pct=p['return_pct'],period_local_CLOSE_MDD_pct=p['DD']['percent'],period_MDD_peak_day=p['DD']['preceding_peak_day'],period_MDD_trough_day=p['DD']['day'],mean_lag_market_exposure_pct=p['mean_lag_exposure_pct'],mean_close_market_exposure_pct=p['mean_close_exposure_pct'],mean_close_native_nominal_mark_floor_risk_pct=p['mean_close_nominal_risk_pct'],actual_fees_CNY=p['actual_fees'],actual_buy_fills=p['buy_fills'],actual_sell_fills=p['sell_fills'],actual_buy_cash=p['actual_buy_cash'],actual_sell_net=p['actual_sell_net'],recognized_dividend=p['recognized_dividend']))
 for arm in ['D_GROSS10','ARCHIVED_B']:
  s=summary[arm];m=s['account_metrics'];p=s['whole_calendar'];whole.append(dict(window=win,arm=arm,first_CLOSE=p['start'],last_CLOSE=p['end'],CLOSE_days=p['days'],initial_cash=1000000,end_NAV=p['end_NAV'],net_CNY=p['wealth_change'],return_pct=p['return_pct'],full_window_global_CLOSE_MDD_pct=m['global_DD']['percent'],MDD_peak_day=m['global_DD']['preceding_peak_day'],MDD_trough_day=m['global_DD']['day'],mean_lag_market_exposure_pct=p['mean_lag_exposure_pct'],mean_close_market_exposure_pct=p['mean_close_exposure_pct'],mean_close_native_nominal_mark_floor_risk_pct=p['mean_close_nominal_risk_pct'],actual_fees_CNY=p['actual_fees'],actual_buy_fills=m['buy_fills'],actual_sell_fills=m['sell_fills'],terminal_marked_inventory=m['terminal_inventory'],terminal_dividend_AR=m['terminal_dividend_receivable']))
  if arm=='D_GROSS10':root=T/'market_gross_admission_native_v1'/f'full-{win}-v1/pair';bp=root/'D_GROSS10.json.gz';lp=out/'analysis'/win/'D_GROSS10/LAYERS.json'
  else:
   for p0,h in controls[win]['source_sha256'].items():assert sha(p0)==h
   bp=next(Path(p)for p in controls[win]['source_sha256']if p.endswith('/pair/B.json.gz'));root=bp.parent;lp=T/f'capacity_cost_guard_analysis_v1/full_{win}_v1/analysis/{win}/B/LAYERS.json'
  b=book(bp);ls=read(lp);native={x['id']:x for x in b['layers']};by=defaultdict(list)
  for l in ls:by[l['sid']].append(l)
  stocks={}
  for sid,ll in by.items():
   raw=[native[l['layer']]for l in ll];closed=[x for x in raw if not x['qty']];open_=[x for x in raw if x['qty']];div=sum((D(x['dividend'])for x in raw),Z);value=sum((D(x['value'])for x in ll),Z);cash_closed=sum((D(x['cash'])for x in closed),Z);cash_open=sum((D(x['cash'])for x in open_),Z);net=sum((D(x['net'])for x in ll),Z);near(cash_closed+cash_open+value+div,net,(win,arm,sid,'native-components'))
   stocks[sid]=dict(sid=sid,name=ll[0]['name'],actual_buy_layers=len(ll),actual_buy_cash=sum((D(x['cost'])for x in ll),Z),whole_window_stock_net=net,closed_layer_trade_cash_net_ex_dividend=cash_closed,open_layer_trade_cash_net_ex_dividend_NOT_unrealized_PnL=cash_open,terminal_marked_inventory_VALUE_NOT_PnL=value,recognized_dividend_equity_paid_plus_AR=div,stock_terminal_dividend_AR='0_ZERO_ALL_RECOGNIZED_DIVIDENDS'if div==0 else'UNKNOWN_NO_SAVED_PER_STOCK_TERMINAL_AR',closed_layers=len(closed),open_layers=len(open_),first_actual_buy=min(x['opened']for x in ll),last_actual_buy=max(x['opened']for x in ll))
  near(sum((x['whole_window_stock_net']for x in stocks.values()),Z),D(b['ending_NAV'])-D(1000000),(win,arm,'stocknet'))
  data[win,arm]=dict(book=b,layers=ls,stocks=stocks,root=root)
  csvout(O/f'ALL_ACTUAL_STOCK_COMPONENTS_{win}_{arm}.csv',list(stocks.values()))
 B=data[win,'ARCHIVED_B']['stocks'];DD=data[win,'D_GROSS10']['stocks'];winners=[]
 for sid,b in B.items():
  if b['whole_window_stock_net']<=0:continue
  d=DD.get(sid);status='COMPLETELY_UNBOUGHT_BY_D'if d is None else'BUY_CASH_REDUCED'if d['actual_buy_cash']<b['actual_buy_cash']else'BUY_CASH_EQUAL'if d['actual_buy_cash']==b['actual_buy_cash']else'BUY_CASH_INCREASED'
  winners.append(dict(sid=sid,name=b['name'],B_fixed_winner_definition='original_B_full_window_stock_net_gt0_POSTHOC',funding_status=status,B_actual_buy_cash=b['actual_buy_cash'],D_actual_buy_cash=d['actual_buy_cash']if d else Z,B_actual_buy_layers=b['actual_buy_layers'],D_actual_buy_layers=d['actual_buy_layers']if d else 0,B_original_net=b['whole_window_stock_net'],D_original_net=d['whole_window_stock_net']if d else Z,path_net_difference_NOT_alpha=(d['whole_window_stock_net']if d else Z)-b['whole_window_stock_net'],B_terminal_marked_VALUE=b['terminal_marked_inventory_VALUE_NOT_PnL'],D_terminal_marked_VALUE=d['terminal_marked_inventory_VALUE_NOT_PnL']if d else Z,B_closed_layer_trade_cash_net=b['closed_layer_trade_cash_net_ex_dividend'],D_closed_layer_trade_cash_net=d['closed_layer_trade_cash_net_ex_dividend']if d else Z,B_open_layer_trade_cash_net_NOT_unrealized=b['open_layer_trade_cash_net_ex_dividend_NOT_unrealized_PnL'],D_open_layer_trade_cash_net_NOT_unrealized=d['open_layer_trade_cash_net_ex_dividend_NOT_unrealized_PnL']if d else Z,B_recognized_dividend_equity=b['recognized_dividend_equity_paid_plus_AR'],D_recognized_dividend_equity=d['recognized_dividend_equity_paid_plus_AR']if d else Z,B_stock_terminal_AR=b['stock_terminal_dividend_AR'],D_stock_terminal_AR=d['stock_terminal_dividend_AR']if d else'0_NEVER_HELD'))
 winners.sort(key=lambda r:-r['B_original_net']);csvout(O/f'FIXED_B_WINNERS_ALL_{win}.csv',winners);csvout(O/f'FIXED_B_WINNERS_D_UNBOUGHT_{win}.csv',[r for r in winners if r['funding_status']=='COMPLETELY_UNBOUGHT_BY_D']);csvout(O/f'FIXED_B_WINNERS_D_REDUCED_{win}.csv',[r for r in winners if r['funding_status']=='BUY_CASH_REDUCED'])
 new=[dict(**d,posterior_group='D_actual_funded_B_never_funded',path_net_NOT_alpha=d['whole_window_stock_net'])for sid,d in DD.items()if sid not in B];new.sort(key=lambda r:-r['whole_window_stock_net']);csvout(O/f'ALL_D_NEWLY_FUNDED_{win}.csv',new);csvout(O/f'ALL_D_NEW_POSITIVE_BENEFICIARIES_{win}.csv',[r for r in new if r['whole_window_stock_net']>0])
 delta=[dict(sid=sid,name=(DD.get(sid)or B[sid])['name'],B_net=B.get(sid,{}).get('whole_window_stock_net',Z),D_net=DD.get(sid,{}).get('whole_window_stock_net',Z),net_difference_NOT_alpha=DD.get(sid,{}).get('whole_window_stock_net',Z)-B.get(sid,{}).get('whole_window_stock_net',Z))for sid in set(B)|set(DD)];delta.sort(key=lambda r:-r['net_difference_NOT_alpha']);csvout(O/f'ALL_STOCK_PATH_DIFFERENCES_{win}.csv',delta);csvout(O/f'ALL_POSITIVE_PATH_DIFFERENCES_{win}.csv',[r for r in delta if r['net_difference_NOT_alpha']>0])
 cohort_summary[win]=dict(all_original_B_positive_stocks=len(winners),D_unbought_B_positive=sum(r['funding_status']=='COMPLETELY_UNBOUGHT_BY_D'for r in winners),D_buycash_reduced_B_positive=sum(r['funding_status']=='BUY_CASH_REDUCED'for r in winners),D_buycash_increased_B_positive=sum(r['funding_status']=='BUY_CASH_INCREASED'for r in winners),D_new_actual_funded_stocks=len(new),D_new_positive_stocks=sum(r['whole_window_stock_net']>0 for r in new),D_new_stock_net=sum((r['whole_window_stock_net']for r in new),Z),source='archivedNo60 current1709 pool, not old407 PVR pool',semantics='All are posthoc complete paths, never signals or avoidable/lost-profit causal alpha. Buycash is actual fee-inclusive turnover, not current/max capital weight.')
csvout(O/'YEAR_AND_HALF_YEAR_METRICS.csv',annual);save(O/'YEAR_AND_HALF_YEAR_METRICS.json',annual);csvout(O/'WHOLE_WINDOW_METRICS.csv',whole);save(O/'WHOLE_WINDOW_METRICS.json',whole);save(O/'FULL_LIST_COHORT_SUMMARY.json',cohort_summary)

# Strict H1 semiconductor: existing126 members and existing interval money.
members=read(T/'capacity_cost_guard_analysis_v1/STRICT_SEMICONDUCTOR_MEMBERS.json')['members'];ids={r['sid']for r in members};assert len(ids)==126
phase=read(BASE/'full_strong_v1/FIXED_PHASE_WEALTH.json')['strict_semiconductor_2026H1'];semi=[];semi_summary={};lo='2026-01-01';hi='2026-06-30'
for arm,key in [('D_GROSS10','D_actual_stock_wealth'),('ARCHIVED_B','ARCHIVED_B_phase')]:
 p=phase[key];a=data['strong',arm];b=a['book'];ls=a['layers'];by={r['sid']:D(r['wealth'])for r in p['stock_wealth']};assert len(by)==126;prior=gzrows(a['root']/'daily.jsonl.gz');before=next(r for r in prior if r['at'][:10]=='2025-12-31');assert not(set(before['positions'])&ids),'nonzero carry requires existing interval component bridge; do not invent basis'
 for member in members:
  sid=member['sid'];tx=[t for t in b['trades']if t['security_id']==sid and lo<=t['at'][:10]<=hi];ll=[l for l in ls if l['sid']==sid and lo<=l['opened'][:10]<=hi];raw={r['id']:r for r in b['layers']};cc=sum((D(raw[l['layer']]['cash'])for l in ll if not l['qty']),Z);oc=sum((D(raw[l['layer']]['cash'])for l in ll if l['qty']),Z);val=sum((D(l['value'])for l in ll),Z);div=sum((D(raw[l['layer']]['dividend'])for l in ll),Z);near(cc+oc+val+div,by[sid],(arm,sid,'semiH1native-interval'));full=a['stocks'].get(sid)
  semi.append(dict(arm=arm,sid=sid,name=member.get('name',full['name']if full else sid),H1_period_wealth=by[sid],H1_actual_buy_cash=sum((D(t['gross_cny'])+D(t['fees_cny'])for t in tx if t['side']=='buy'),Z),H1_actual_sell_net=sum((D(t['gross_cny'])-D(t['fees_cny'])for t in tx if t['side']=='sell'),Z),H1_actual_fees=sum((D(t['fees_cny'])for t in tx),Z),H1_buy_fills=sum(t['side']=='buy'for t in tx),H1_sell_fills=sum(t['side']=='sell'for t in tx),H1_closed_layer_trade_cash_net_ex_dividend=cc,H1_open_layer_trade_cash_net_NOT_unrealized=oc,end_marked_inventory_VALUE_NOT_PnL=val,H1_recognized_dividend_equity=div,stock_terminal_AR=full['stock_terminal_dividend_AR']if full else'0_NEVER_HELD',first_H1_actual_buy=next((t['at']for t in tx if t['side']=='buy'),None)))
 rr=[r for r in semi if r['arm']==arm];near(sum((r['H1_period_wealth']for r in rr),Z),D(p['interval_wealth']),('semi126',arm));startnav=next(r for r in annual if r['window']=='strong'and r['period']=='2026H1'and r['arm']==arm)['initial_own_period_NAV'];semi_summary[arm]=dict(**{k:v for k,v in p.items()if k!='stock_wealth'},fixed_members=126,actually_bought_members=sum(r['H1_buy_fills']>0 for r in rr),never_bought_members=sum(r['H1_buy_fills']==0 for r in rr),period_wealth_over_own_H1_initial_NAV_contribution_pp=D(p['interval_wealth'])/D(startnav)*100,sector_return='UNKNOWN_NO_SINGLE_SELF_FINANCING_SECTOR_ACCOUNT; turnover buycash is not a return denominator')
csvout(O/'SEMICONDUCTOR126_H1_ALL_MEMBERS.csv',semi);save(O/'SEMICONDUCTOR126_H1_SUMMARY.json',semi_summary)

# D daily sector capital path reuses original saved-reader rawmark only.
HP=T/'capacity_cost_guard_analysis_v1/analyze_completed_v1.py';sp=importlib.util.spec_from_file_location('same_original_saved_rawmark_helper',HP);H=importlib.util.module_from_spec(sp);sp.loader.exec_module(H);SRC[str(HP.resolve())]=sha(HP);SRC[str(H.P)]=sha(H.P)
a=data['strong','D_GROSS10'];b=a['book'];native_days=gzrows(a['root']/'daily.jsonl.gz');txday=defaultdict(list);divday=defaultdict(lambda:Z)
for tr in b['trades']:
 if tr['security_id']in ids:txday[tr['at'][:10]].append(tr)
for e in b['audit']:
 if e['kind']=='dividend_accrual'and e['receivable']['security_id']in ids:divday[e['receivable']['ex_at'][:10]]+=D(e['receivable']['net_local'])
prev=Z;path=[];weights=[];flows=[]
for d in native_days:
 date=d['at'][:10]
 if not lo<=date<=hi:continue
 pos={s:q for s,q in d['positions'].items()if s in ids and q};inventory=sum((D(q)*H.A.price(s,date)for s,q in pos.items()),Z);tx=txday[date];bc=sum((D(t['gross_cny'])+D(t['fees_cny'])for t in tx if t['side']=='buy'),Z);sn=sum((D(t['gross_cny'])-D(t['fees_cny'])for t in tx if t['side']=='sell'),Z);weight=inventory/D(d['nav'])*100;wealth=inventory-prev+sn-bc+divday[date];path.append(dict(day=date,own_NAV=d['nav'],strict_semi_inventory=inventory,strict_semi_weight_pct_NAV=weight,held_member_count=len(pos),actual_buy_cash=bc,actual_sell_net=sn,actual_fees=sum((D(t['fees_cny'])for t in tx),Z),recognized_dividend=divday[date],interval_wealth_increment=wealth,buy_fills=sum(t['side']=='buy'for t in tx),sell_fills=sum(t['side']=='sell'for t in tx),own_ACT_after_CLOSE=d['on']));prev=inventory;weights.append(weight);flows.append(wealth)
near(sum(flows,Z),D(semi_summary['D_GROSS10']['interval_wealth']),'Dsemi dailywealth');near(sum(weights,Z)/len(weights),D(semi_summary['D_GROSS10']['mean_close_weight_pct']),'Dsemi meanweight');near(max(weights),D(semi_summary['D_GROSS10']['peak_close_weight_pct']),'Dsemi peakweight');csvout(O/'SEMICONDUCTOR_D_H1_DAILY_CAPITAL_PATH.csv',path)

# Primary source binding includes exact original ACT implementation chain.
codepaths=[T/'market_gross_admission_native_v1/gross_adapter.py',T/'market_gross_admission_native_v1/market_info.py',T/'market_gross_admission_native_v1/market_info_v2.py',Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/code/experiment.py'),Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/desk/refresh.py')]
for p in codepaths:SRC[str(p.resolve())]=sha(p)
receipts=[T/'market_gross_admission_full_ledger_review_v1/DERIVED_KEY_REVIEW.json',T/'market_gross_admission_full_ledger_review_v1/STRONG_FINANCE_PVR_ATOMIC_REVIEW.json',T/'market_gross_admission_full_ledger_review_v1/long/FINANCE_AND_ATOMIC_AUDIT.json',T/'market_gross_admission_full_ledger_review_v1/long/CONTINUITY_DD_AND_INFO_ATTRIBUTION.json']
for p in receipts:read(p)
save(O/'SOURCE_BINDING.json',dict(source_sha256=SRC,code_sha256=sha(Path(__file__)),rules_sha256=sha(O/'RULES_AND_CLOCKS.txt'),new_accounts=0,new_B_books_or_views=0,new_price_loader_or_financial_basis=0,existing_price_function=str(H.P)+':price',new_output_independent_review='PENDING; prior receipts directly support original finance/924/periods; new annualMDD/components/full-list/sector-daily aggregation not automatically separately audited',AR_scope='Global native terminal AR known. Per-stock recognized dividends is paid+AR; terminal split UNKNOWN if total dividends nonzero. Zero lifetime recognized dividends proves zero AR in fresh account. Closed layer tradecash and terminal marked value are direct native components, not invented tax basis/unrealized profit.'))
print('COMPILED',len(annual),'annual/halfrows',len(whole),'fullrows',len(semi),'semimemberrows',len(path),'Dsemi days',cohort_summary,flush=True)
