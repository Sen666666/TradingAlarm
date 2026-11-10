"""One new independent audit; three saved paths measured, never simulated."""
import baseline as B
import json,gzip,time,collections
from pathlib import Path
import pandas as pd,numpy as np
M=B.M;O=B.O;OLD=B.OLD;D=M.D;Z=D(0)
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def main():
 t=time.monotonic();assert M.read(O/'ECONOMIC_DONE.json')['passed'];freeze=M.read(O/'FREEZE.json');assert all(M.sha(p)==h for p,h in freeze['sha256'].items())
 objects={k:obj((O if k=='NO_P' else OLD)/'results'/f'{k}.json.gz') for k in ['H1','ATT','NO_P']};daily={k:[r for r in B.rows((O if k=='NO_P' else OLD)/'results/daily.jsonl.gz') if r['account']==k] for k in objects};lists={k:[r for r in B.rows((O if k=='NO_P' else OLD)/'results/selection.jsonl.gz') if r['policy']==k] for k in objects};look={(k,r['day']):r for k,rs in lists.items() for r in rs}
 meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');au=M.BP.C.import_path('P_identity_original_audit',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');prices=au.Prices.__new__(au.Prices);prices.records={r['series_id']:r for r in M.read(M.P/'manifest.json')['series']};prices.cache={};rules=M.read(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json');cal=sorted(pd.Timestamp(x) for x in rules['calendars']['A']);contributions=[]
 cs,receipt=au.audit_account('B0_NO_P',dict(audit_log=objects['NO_P']['audit']),daily['NO_P'],prices,meta,cal,contributions)
 for c in cs:c['account']='NO_P'
 allcs=M.read(OLD/'analysis/CYCLES.json')+cs;allsummary=M.read(OLD/'analysis/SUMMARY.json');ds=daily['NO_P'];ob=objects['NO_P'];nav=np.array([float(r['nav']) for r in ds]);dd=1-nav/np.maximum.accumulate(np.r_[1e6,nav])[1:];closed=[c for c in cs if c['closed']];opened=[c for c in cs if not c['closed']];tail=[c for c in closed if c['net_return']>=.3];ordinary=[c for c in closed if c['net_return']<.3];funs=M.read(O/'results/FUNNEL.json');ct=collections.Counter();qr=collections.Counter()
 for x in funs:ct.update(x['counts']);qr.update(x['Q_reasons'])
 risk=[x for x in ob['audit'] if x['kind']=='risk_checkpoint'];counts=collections.Counter(x['kind'] for x in ob['audit']);peak=1e6;last=-1;longest=0
 for i,n in enumerate(nav):
  if n>=peak:peak=n;last=i
  else:longest=max(longest,i-last)
 ss=dict(account='NO_P',net_return=float(nav[-1]/1e6-1),final_nav=D(ds[-1]['nav']),max_drawdown=float(dd.max()),longest_underwater_observations=longest,underwater_at_end=bool(dd[-1]>0),fees=D(ds[-1]['fees_cny']),slippage=sum((D(x['shares'])*abs(D(x['price'])-D(x['raw_open'])) for x in ob['trades']),Z),mean_exposure=float(np.mean([float(x['inventory'])/n for x,n in zip(ds,nav)])),buy_fills=sum(x['side']=='buy' for x in ob['trades']),sell_fills=sum(x['side']=='sell' for x in ob['trades']),buy_orders=counts['reserve'],peak_positions=max(len(x['positions']) for x in ds),end_positions=len(ds[-1]['positions']),closed=len(closed),open=len(opened),cycles=len(cs),closed_tail30_net=sum((c['net_pnl'] for c in tail),Z),closed_ordinary_net=sum((c['net_pnl'] for c in ordinary),Z),open_marked_net=sum((c['net_pnl'] for c in opened),Z),all_negative_cycle_loss=-sum((c['net_pnl'] for c in cs if c['net_pnl']<0),Z),ACT_pauses=sum(x['event']=='pause' for x in risk),ACT_resumes=sum(x['event']=='resume' for x in risk),raw_I_stock_days=sum(r['raw_I_count'] for r in lists['NO_P']),common_P_stock_days=sum(r['P_score_known_count'] for r in lists['NO_P']),selected_stock_days=sum(r['B'] for r in lists['NO_P']),post_Q_counts=dict(ct),Q_reasons=dict(qr),final_counts=ob['counts'])
 allsummary.append(ss);print('AUDITED_NO_P',json.dumps(M.N.encoded(ss),ensure_ascii=False),flush=True)
 # Same daily P reference for all three saved accounts. No new indicators.
 matrix=pd.read_parquet(M.F);matrix=matrix[(matrix.day>=M.START)&(matrix.day<=M.END)];md={day:g.set_index('sector') for day,g in matrix.groupby('day',sort=False)};sector_days=[];portfolio_days=[];flows=[];usage=[];source=[]
 for key,rs in daily.items():
  prior=set();ob=objects[key];candidate_set={r['day']:set(r['selected']) for r in lists[key]};outside_fills=0;outside_cost=Z
  for r in rs:
   day=r['at'][:10];g=md[day];sector_value=collections.defaultdict(lambda:Z);sector_count=collections.Counter();outside=Z;outside_previous=Z;inv=Z
   for sid,q in r['positions'].items():
    sector=meta[sid]['sector_id'];value=D(q)*prices.mark(sid,day);inv+=value;sector_value[sector]+=value;sector_count[sector]+=1
    if not bool(g.loc[sector,'price_qualified']):outside+=value;outside_previous+=value if sid in prior else Z
   assert abs(inv-D(r['inventory']))<D('.00000001')
   for sector,value in sector_value.items():sector_days.append(dict(account=key,day=day,sector=sector,stocks=sector_count[sector],market_value=value,weight_NAV=value/D(r['nav']),weight_inventory=value/inv if inv else Z,P_qualified=bool(g.loc[sector,'price_qualified'])))
   portfolio_days.append(dict(account=key,day=day,P_qualified_industries=int(g.price_qualified.sum()),held_industries=len(sector_value),held_stocks=len(r['positions']),inventory=inv,NAV=D(r['nav']),outside_P_value=outside,outside_P_NAV_fraction=outside/D(r['nav']),outside_P_inventory_fraction=outside/inv if inv else Z,outside_P_previous_close_owned_symbols_value=outside_previous,available=D(r['available']),order_reserved=D(r['order_reserved'])))
   prior=set(r['positions'])
  for x in ob['trades']:
   if x['side']!='buy':continue
   day=x['signal_at'][:10];sid=x['security_id'];sector=meta[sid]['sector_id'];assert sid in candidate_set[day];outside=not bool(md[day].loc[sector,'price_qualified']);cost=D(x['gross_cny'])+D(x['fees_cny']);outside_fills+=outside;outside_cost+=cost if outside else Z
   flows.append(dict(account=key,decision=day,fill=x['at'],sid=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],P_at_decision=not outside,shares=x['shares'],price=x['price'],cash_cost=cost))
  pdays=[r for r in portfolio_days if r['account']==key];sel=lists[key];ints=[i for d in ob['decisions'] for i in d['intents']];fund=[x for x in ob['audit'] if x['kind']=='lot_risk_funded'];mean=lambda field:float(np.mean([float(r[field]) for r in pdays]));end=pdays[-1]
  usage.append(dict(account=key,mean_held_industries=mean('held_industries'),min_held_industries=min(r['held_industries'] for r in pdays),max_held_industries=max(r['held_industries'] for r in pdays),end_held_industries=end['held_industries'],mean_P_qualified_industries=mean('P_qualified_industries'),min_P_qualified_industries=min(r['P_qualified_industries'] for r in pdays),max_P_qualified_industries=max(r['P_qualified_industries'] for r in pdays),mean_outside_P_NAV_fraction=mean('outside_P_NAV_fraction'),mean_outside_P_inventory_fraction=mean('outside_P_inventory_fraction'),end_outside_P_NAV_fraction=float(end['outside_P_NAV_fraction']),end_outside_P_inventory_fraction=float(end['outside_P_inventory_fraction']),end_outside_P_value=end['outside_P_value'],selected_stock_days=sum(r['B'] for r in sel),pre_size_intents=len(ints),post_size_intents=sum(not i.get('size_reject') for i in ints),funded_orders=len(fund),funded_gross=sum((D(x['gross']) for x in fund),Z),funded_fees=sum((D(x['fees']) for x in fund),Z),actual_buy_cash_total=sum((D(x['gross_cny'])+D(x['fees_cny']) for x in ob['trades'] if x['side']=='buy'),Z),buy_fills_outside_P=outside_fills,buy_cash_outside_P=outside_cost,repeat_daily_requested_budgets_not_simultaneous_capital=sum((D(i['budget']) for i in ints if not i.get('size_reject')),Z)))
  source.append(dict(account=key,source=str((O if key=='NO_P' else OLD)/'results'/f'{key}.json.gz'),sha256=M.sha((O if key=='NO_P' else OLD)/'results'/f'{key}.json.gz'),reused=key!='NO_P'))
 # Mutually exclusive money bridge from complete cycle cash/entitlements.
 stock=collections.defaultdict(lambda:collections.defaultdict(lambda:dict(buys=Z,sales=Z,fees=Z,dividends=Z,terminal=Z,net=Z)))
 for c in allcs:
  v=stock[c['account']][c['symbol']];v['buys']+=D(c['buy_gross']);v['sales']+=D(c['sell_gross']);v['fees']+=D(c['buy_fees'])+D(c['sell_fees']);v['dividends']+=D(c['dividends']);v['terminal']+=D(c['market_value']);v['net']+=D(c['net_pnl'])
 bridges=[]
 for sid in sorted(set(stock['NO_P'])|set(stock['H1'])):
  a,b=stock['H1'][sid],stock['NO_P'][sid];q=dict(sid=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],H1_P_net=a['net'],NO_P_net=b['net'],NO_P_minus_H1_P=b['net']-a['net'],net_principal_flow=(b['sales']-b['buys'])-(a['sales']-a['buys']),dividends=b['dividends']-a['dividends'],terminal_inventory=b['terminal']-a['terminal'],explicit_fees=-(b['fees']-a['fees']));assert abs(q['NO_P_minus_H1_P']-sum((q[k] for k in ['net_principal_flow','dividends','terminal_inventory','explicit_fees']),Z))<D('.00000001');bridges.append(q)
 money={k:sum((q[k] for q in bridges),Z) for k in ['NO_P_minus_H1_P','net_principal_flow','dividends','terminal_inventory','explicit_fees']};assert abs(money['NO_P_minus_H1_P']-(ss['final_nav']-D(allsummary[0]['final_nav'])))<D('.00000001')
 # Earliest actual buys affected by P identity. Outcomes remain after-the-fact.
 cases=[]
 for key in ['H1','NO_P']:
  other='NO_P' if key=='H1' else 'H1'
  for x in objects[key]['trades']:
   if x['side']!='buy':continue
   day=x['signal_at'][:10];sid=x['security_id'];g=md[day].loc[meta[sid]['sector_id']]
   if sid in look[other,day]['selected']:continue
   cases.append(dict(bought_by=key,other=other,decision=day,fill=x['at'],sid=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],P=bool(g.price_qualified),R21=float(g.R21),relative90_R21=float(g.relative_R21),H1=float(g.H1_original),shares=x['shares'],price=x['price'],quarter_stock_net_buyer=stock[key][sid]['net'],quarter_stock_net_other=stock[other][sid]['net'],not_single_event_causal=True))
 def firstdiff(field):
  for a,b in zip(objects['H1']['decisions'],objects['NO_P']['decisions']):
   if [(i['sid'],i['cap'],i['budget']) for i in a['intents']]!=[(i['sid'],i['cap'],i['budget']) for i in b['intents']]:return a['at']
 for a,b in zip(daily['H1'],daily['NO_P']):
  if any(a[k]!=b[k] for k in ['nav','positions','available','fees_cny']):first_finance=a['at'];break
 else:first_finance=None
 out=O/'analysis';out.mkdir(exist_ok=False)
 for name,data in [('SUMMARY_3',allsummary),('NEW_CYCLES',cs),('PORTFOLIO_DAILY_3',portfolio_days),('INDUSTRY_DAILY_VALUES_3',sector_days),('CANDIDATE_FUNDING_3',usage),('ACTUAL_BUY_USAGE_3',flows),('STOCK_BRIDGE_NO_P_MINUS_P',bridges),('P_IDENTITY_EXCLUSION_CASES',cases),('SOURCE_RESULTS',source)]:
  M.save(out/(name+'.json'),data)
  if data:pd.DataFrame(M.N.encoded(data)).to_csv(out/(name+'.csv'),index=False)
 M.save(out/'MONEY_BRIDGE.json',money);M.save(out/'VERIFICATION.json',dict(passed=True,new_independent_audit=receipt,old_two_independent_audits_reused=True,same_frozen_daily_B=True,first_intent_divergence=firstdiff('intents'),first_financial_divergence=first_finance,three_saved_paths_no_old_simulation=True,all_holdings_valued_and_sector_weight_sum_checked=True,outside_shortlist_new_orders=0,seconds=time.monotonic()-t))
 print('BRIDGE',json.dumps(M.N.encoded(money)),flush=True);print('USAGE',json.dumps(M.N.encoded(usage)),flush=True);print('ANALYSIS_SECONDS',time.monotonic()-t,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  import traceback;M.save(O/'ANALYSIS_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
