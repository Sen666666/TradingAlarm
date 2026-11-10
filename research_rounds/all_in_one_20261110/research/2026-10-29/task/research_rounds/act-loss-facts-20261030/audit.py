from pathlib import Path
import json,gzip,csv,time,hashlib,importlib.util,bisect
from decimal import Decimal as D
from datetime import time as dt
import pandas as pd
import numpy as np

T=time.monotonic(); ROOT=Path('/Users/bytedance/Documents/ChatGPT/money'); R=ROOT/'research_rounds'; OUT=Path(__file__).resolve().parent
S=R/'s-entry-mechanism-audit-20261029'; B=R/'pvr-local-finite-capital-20261029/baseline'; F=R/'fat-tail-opportunity-ledger-20261029/full'; Z=D(0)
def save(n,x):
 (OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def export(n,rows):
 pd.DataFrame(rows).to_csv(OUT/n,index=False)
def loadrows(n):
 with gzip.open(B/'accounts-v2'/n,'rt') as f:return [x for l in f if (x:=json.loads(l))['account']=='I__S0_base']
def progress(**kw):print(json.dumps(kw,ensure_ascii=False,default=str),flush=True)
paths=[B/'accounts-v2/I__S0_base.json',B/'analysis/campaigns.csv',B/'accounts-v2/daily.jsonl.gz',B/'accounts-v2/decisions.jsonl.gz',S/'market-cache.parquet',S/'results/units.parquet',F/'daily-observed-funnel.parquet']
save('INPUT_IDENTITY.json',{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
a=json.loads(paths[0].read_text()); al=a['audit_log']; fill=[x for x in al if x['kind']=='fill']; daily=loadrows('daily.jsonl.gz'); decisions=loadrows('decisions.jsonl.gz')
ds={x['at'][:10]:x for x in daily}; de={x['at'][:10]:x for x in decisions}; cp={x['at'][:10]:x for x in al if x['kind']=='risk_checkpoint'}
cycles=[x for x in csv.DictReader((B/'analysis/campaigns.csv').open()) if x['scenario']=='base']; assert len(cycles)==69
cache=pd.read_parquet(S/'market-cache.parquet'); cache['day']=cache.date.dt.strftime('%Y-%m-%d'); cc={(x.symbol,x.day):x for x in cache.itertuples(index=False)}
cg={s:g.set_index('day').sort_index() for s,g in cache.groupby('symbol')}; ids=set(cg)
sp=importlib.util.spec_from_file_location('act_loss_frozen_helpers',S/'code/audit.py'); H=importlib.util.module_from_spec(sp); sp.loader.exec_module(H)
b,m,_,dates=H.context(ids,False); days=[str(x.date()) for x in dates]; di={d:i for i,d in enumerate(days)}
intents={x['order_id']:x for x in al if x['kind']=='entry_contract'}
divs=[x['receivable'] for x in al if x['kind']=='dividend_accrual']
def dividend(s,entry,end):return sum((D(x['net_local']) for x in divs if x['security_id']==s and entry[:10]<=x['ex_at'][:10]<=end[:10]),Z)
def valuation(s,day,q,basis,entry):
 tm=H.at(day,dt(15,10)); mark=m.latest_mark(s,tm); mv=D(q)*mark.raw_price; dv=dividend(s,entry,day); sell=mv*(1-D('.0005'))
 fee=sum(m.fees(s,tm).incremental('sell',sell,{}, {},1,shares=q,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value')).values(),Z)
 return dict(day=day,shares=q,raw_mark=mark.raw_price,mark_known_at=str(mark.known_at),accrued_dividend=dv,nav_mark_pnl=mv+dv-basis,net_liquidation_pnl=sell-fee+dv-basis,estimated_sell_fee=fee,estimated_sell_slippage=mv-sell)
all_daily=[]; memo={}
def analyze(c):
 s=c['symbol']; ent=c['entry_at']; ex=c['exit_at']; ed=ent[:10]; xd=ex[:10]; key=f'{s}|{ed}'; basis=D(c['buy_gross'])+D(c['buy_fees'])
 bf=[x for x in fill if x['receipt']['security_id']==s and x['receipt']['side']=='buy' and x['receipt']['at']==ent]; sf=[x for x in fill if x['receipt']['security_id']==s and x['receipt']['side']=='sell' and x['receipt']['at']==ex]
 assert len(bf)==len(sf)==1
 buy=bf[0]; sell=sf[0]; co=intents[buy['order_id']]; q0=buy['receipt']['shares']; factor=D(str(cc[s,ed].factor)); flo=D(co['floor_signal']); rawfloor=flo/factor; price=D(buy['price']); distance=(price-rawfloor)/price
 assert D(q0)*price==D(c['buy_gross']) and D(c['sell_gross'])==D(sell['price'])*sell['receipt']['shares']
 dv=dividend(s,ent,ex); pnl=D(c['sell_gross'])-D(c['sell_fees'])-basis+dv; assert pnl==D(c['net_pnl']) and dv==D(c['dividends'])
 req=[x for x in al if x['kind']=='exit_request' and x['sid']==s and ent<=x['at']<ex]; assert len(req)==1; rd=req[0]['at'][:10]
 rr=cc[s,rd]; reason='ACT_forced' if not cp[rd]['on'] else ('I_structure_off' if not bool(rr.i_target) else 'unknown')
 hist=[]; changes=[]; previous=flo
 for day in days:
  if not(ed<=day<xd):continue
  q=int(ds[day]['positions'].get(s,0)); assert q>0
  v=valuation(s,day,q,basis,ent); row=cc[s,day]; f=D(str(row.i_floor)) if pd.notna(row.i_floor) else None
  v.update(cycle_id=key,symbol=s,name=c['name'],net_liquidation_return=float(v['net_liquidation_pnl']/basis),nav_mark_return=float(v['nav_mark_pnl']/basis),I_active=bool(row.i_target),g_grade=float(row.g_grade) if pd.notna(row.g_grade) else None,g_acute_down=bool(row.g_acute_down),old_floor_causal=previous,new_floor_causal=f,causal_close=row.close,ACT_on=cp[day]['on'])
  if f is not None and f!=previous:changes.append(dict(day=day,old=previous,new=f,delta=f-previous))
  hist.append(v); previous=f if f is not None else previous
 assert hist and hist[-1]['day']==rd
 mfe=max(x['net_liquidation_return'] for x in hist); mae=min(x['net_liquidation_return'] for x in hist); netret=float(pnl/basis)
 cat=('loss_after_10pct' if mfe>=.10 else 'loss_without_10pct') if pnl<0 else (('profit_after_10pct' if mfe>=.10 else 'profit_without_10pct') if pnl>0 else 'zero')
 rq=hist[-1]; weak=next((x for x in hist if x['net_liquidation_return']<=-.10),None); cold=next((x for x in hist if x['g_acute_down'] or (x['g_grade'] is not None and x['g_grade']<=-2)),None)
 r=dict(cycle_id=key,symbol=s,name=c['name'],industry=c['industry'],entry_at=ent,exit_at=ex,entry_decision=co['decision_at'],initial_shares=q0,exit_shares=sell['receipt']['shares'],buy_gross=c['buy_gross'],buy_fees=c['buy_fees'],sell_gross=c['sell_gross'],sell_fees=c['sell_fees'],dividends=dv,net_pnl=pnl,net_return=netret,initial_floor_causal=flo,entry_factor=factor,initial_floor_raw=rawfloor,entry_execution_price=price,initial_floor_distance=float(distance),initial_NAV=co['nav'],initial_allocation=float(D(c['buy_gross'])/D(co['nav'])),initial_nominal_floor_risk=D(q0)*(price-rawfloor),initial_nominal_floor_account_risk=float(D(q0)*(price-rawfloor)/D(co['nav'])),logged_risk_budget=co['risk_budget'],risk_distance_sizing=False,exit_request=req[0]['at'],exit_reason=reason,request_I_active=bool(rr.i_target),request_old_floor=rq['old_floor_causal'],request_new_floor=rq['new_floor_causal'],request_causal_close=rr.close,request_mark_pnl=rq['nav_mark_pnl'],request_to_fill_delta=pnl-rq['nav_mark_pnl'],request_to_fill_loss=rq['nav_mark_pnl']-pnl,holding_sessions=len(hist),holding_calendar_days=(pd.Timestamp(xd)-pd.Timestamp(ed)).days,MFE_close=mfe,MAE_close=mae,MFE_NAV_close=max(x['nav_mark_return'] for x in hist),MAE_NAV_close=min(x['nav_mark_return'] for x in hist),severe_final=netret<=-.30,severe_close=mae<=-.30,trajectory_class=cat,first_minus10_day=weak['day'] if weak else None,first_minus10_I_active=weak['I_active'] if weak else None,first_minus10_floor=weak['old_floor_causal'] if weak else None,first_minus10_close=weak['causal_close'] if weak else None,first_minus10_return=weak['net_liquidation_return'] if weak else None,first_G1_cold_day=cold['day'] if cold else None,first_G1_cold_I_active=cold['I_active'] if cold else None,floor_change_count=len(changes),floor_changes=json.dumps(changes,default=str),closed=True)
 memo[key]=(r,hist);return r,hist
sample=[min(cycles,key=lambda c:(c['entry_at'],c['symbol'])),next(c for c in cycles if c['symbol']=='688143.SH' and float(c['net_return'])<=-.30)]
for c in sample:analyze(c)
save('SAMPLE_VERIFICATION.json',dict(passed=True,samples=[memo[f"{c['symbol']}|{c['entry_at'][:10]}"][0] for c in sample],elapsed=time.monotonic()-T,no_new_economic_paths=True))
progress(stage='two_samples_passed',elapsed=time.monotonic()-T,samples=[c['symbol'] for c in sample])
rows=[]
for c in cycles:
 k=f"{c['symbol']}|{c['entry_at'][:10]}";r,h=memo[k] if k in memo else analyze(c);rows.append(r);all_daily+=h
export('actual-cycles.csv',rows);export('actual-holding-close-paths.csv',all_daily);severe=[r for r in rows if r['severe_final']];export('severe-final-losses.csv',severe);export('severe-close-losses.csv',[r for r in rows if r['severe_close']])
assert sum((r['net_pnl'] for r in rows),Z)==D('2984160.2756603511085')
profit=[r for r in rows if r['net_pnl']>0];loss=[r for r in rows if r['net_pnl']<0];positive=sum((r['net_pnl'] for r in profit),Z);negative=-sum((r['net_pnl'] for r in loss),Z)
groups=[]
for cat in sorted(set(r['trajectory_class'] for r in rows)):
 g=[r for r in rows if r['trajectory_class']==cat];groups.append(dict(category=cat,count=len(g),fraction=len(g)/len(rows),profit=sum((r['net_pnl'] for r in g if r['net_pnl']>0),Z),loss=-sum((r['net_pnl'] for r in g if r['net_pnl']<0),Z),net=sum((r['net_pnl'] for r in g),Z),mean_holding_sessions=np.mean([r['holding_sessions'] for r in g]),mean_initial_floor_distance=np.mean([r['initial_floor_distance'] for r in g])))
export('trajectory-groups.csv',groups)
qtiles={k:{str(p):float(np.quantile([r[k] for r in rows],p)) for p in [0,.1,.25,.5,.75,.9,1]} for k in ['MFE_close','MAE_close','net_return','initial_floor_distance','holding_sessions']}
summary=dict(cycles=69,closed=69,open=0,positive_count=len(profit),negative_count=len(loss),positive=positive,negative=negative,net=positive-negative,mean_profit=positive/len(profit),mean_loss=negative/len(loss),profit_coverage=positive/negative,payoff=(positive/len(profit))/(negative/len(loss)),severe_final_count=len(severe),severe_final_loss=-sum((r['net_pnl'] for r in severe),Z),severe_close_count=sum(r['severe_close'] for r in rows),groups=groups,quantiles=qtiles,loss_never_close_positive=sum(r['net_pnl']<0 and r['MFE_close']<=0 for r in rows),loss_after_close_positive=sum(r['net_pnl']<0 and r['MFE_close']>0 for r in rows))
save('ACT_SUMMARY.json',summary);progress(stage='actual69_done',elapsed=time.monotonic()-T,summary=summary)

# Existing I equal-cash shadow ledger: no path replay. Keep all opportunities.
u=pd.read_parquet(S/'results/units.parquet');u=u[(u.variant=='I')&(u.cost==1)].copy();assert len(u)==5349 and not u.event_id.duplicated().any()
u['pnl']=u.net_pnl.map(D);u['invested']=u.buy_gross.map(D)>0;u['cash_scaled_return']=u.pnl.map(float)/1e6
up=u[u.pnl>0];un=u[u.pnl<0];iv=u[u.invested]
background=dict(events=len(u),stocks_with_events=u.symbol.nunique(),roster_stocks=407,unfilled=int((~u.invested).sum()),filled=len(iv),positive=len(up),negative=len(un),zero=int((u.pnl==0).sum()),share_open=int((u.shares>0).sum()),financial_closed=int(u.financial_closed.sum()),mean_positive_actual_entry_return=float(up.net_return.mean()),mean_negative_actual_entry_return=float(un.net_return.mean()),mean_positive_pnl=sum(up.pnl,Z)/len(up),mean_negative_pnl=sum(un.pnl,Z)/len(un),sum_shadow_pnl=sum(u.pnl,Z),event_equal_mean_cash_return=float(u.cash_scaled_return.mean()),stock_equal_mean_cash_return=float(u.groupby('symbol').cash_scaled_return.mean().sum()/407),event_equal_positive_fraction=float((u.pnl>0).mean()),filled_positive_fraction=len(up)/len(iv),stock_equal_all407_positive_fraction=float(u.assign(pos=u.pnl>0).groupby('symbol').pos.mean().sum()/407),not_shared_portfolio=True)
save('INDEPENDENT_I_BACKGROUND.json',background)

# Synchronous candidate facts in only the three severe windows. No replacement economics.
funnel=pd.read_parquet(F/'daily-observed-funnel.parquet');funnel['day']=pd.to_datetime(funnel.date).dt.strftime('%Y-%m-%d');fg={d:g for d,g in funnel.groupby('day')}
supp=pd.read_csv(F/'existing-admission-supplement.csv');suppmap={(x.date,x.symbol):x.reasons for x in supp.itertuples(index=False)}
meta={r['symbol']:r for r in H.roster()}; cr=[];counts=[];scenario=[]
for r in severe:
 key=r['cycle_id']; hist=memo[key][1]; anchors={};potential=0;negdays=0
 for v in hist:
  day=v['day'];gs=fg[day];cand=gs[(gs.Q==True)&(gs.held==False)];potential+=len(cand); neg=v['net_liquidation_return']<0;negdays+=int(neg)
  for x in cand.sort_values('symbol').itertuples(index=False):
   eid=x.event_id
   if pd.isna(eid):continue
   ck=(x.symbol,eid);p=cc[x.symbol,day]
   if x.ACT_on and ck not in anchors:anchors[ck]=(day,float(p.close))
   if not neg or ck not in anchors:continue
   ad,ap=anchors[ck];gain=float(p.close)/ap-1
   if gain<=0:continue
   ix=di[day];prev=days[ix-21] if ix>=21 else None
   h21=float(cc[r['symbol'],day].close)/float(cc[r['symbol'],prev].close)-1 if prev else None;c21=float(p.close)/float(cc[x.symbol,prev].close)-1 if prev else None
   entryday=r['entry_at'][:10]; hc=float(cc[r['symbol'],day].close)/float(cc[r['symbol'],entryday].close)-1;cn=float(p.close)/float(cc[x.symbol,entryday].close)-1
   dec=de[day]; reject='|'.join(sorted({why for sid,why in dec['rejected'] if sid==x.symbol})); ixopen=bisect.bisect_right(m.sessions['A'],H.at(day,dt(15,10)));nt=m.sessions['A'][ixopen] if ixopen<len(m.sessions['A']) else None
   w=m.window(x.symbol,nt,'buy',1) if nt else None
   # This is a market-only next-day postcheck, never an assertion of account cash availability.
   marketok=None;need=None;why=None
   if w is not None:
    qmin=w.quantity.buy_minimum;floor=D(str(p.i_floor))/D(str(cc[x.symbol,str(nt.date())].factor)) if (x.symbol,str(nt.date())) in cc and pd.notna(p.i_floor) else None
    marketok=bool(w.buy_allowed and w.capacity_shares>=qmin and floor is not None and w.raw_open>floor)
    need=D(qmin)*w.execution_price+sum(w.fees.incremental('buy',D(qmin)*w.execution_price,{}, {},1,shares=qmin,par_value=w.par_value).values(),Z)
    why='passed_market_proxy' if marketok else 'market_quantity_or_frozen_support_blocked'
   else:why='no_next_day_market_window'
   out=dict(held_cycle=key,held_symbol=r['symbol'],held_name=r['name'],date=day,held_entry_return=v['net_liquidation_return'],candidate=x.symbol,candidate_name=meta.get(x.symbol,{}).get('name'),candidate_event=eid,candidate_first_legal_unheld_Q=ad,candidate_since_first_Q_return=gain,held_return_21sessions=h21,candidate_return_21sessions=c21,relative_21sessions=c21-h21 if prev else None,held_same_start_close_return=hc,candidate_same_start_close_return=cn,relative_same_start=cn-hc,candidate_I_new=bool(x.raw_I_signal),candidate_Q=bool(x.Q),ACT_on=bool(x.ACT_on),already_accepted=bool(x.accepted),already_pending=bool(x.pending_buy),original_logged_rejection=reject or None,supplemental_static_observation=suppmap.get((day,x.symbol)),available_actual=ds[day]['available'],reserved_actual=ds[day]['order_reserved'],next_execution=str(nt) if nt else None,next_market_proxy=marketok,next_minimum_cash=need,next_market_reason=why,actual_replacement_fundable='unknown_not_simulated')
   cr.append(out)
 for x in cr:
  if x['held_cycle']==key and x['relative_21sessions'] is not None and x['relative_21sessions']>0:scenario.append(x)
 counts.append(dict(cycle=key,holding_close_days=len(hist),holding_loss_days=negdays,unheld_Q_candidate_days=potential,anchored_candidate_structures=len(anchors)))
export('synchronous-candidate-observations.csv',cr);export('synchronous-stronger-candidates.csv',scenario);export('candidate-denominators.csv',counts)
candidate_summary=dict(denominators=counts,observations_own_anchors=len(cr),cycles_own_anchors=len(set(x['held_cycle'] for x in cr)),cycle_days_own_anchors=len(set((x['held_cycle'],x['date']) for x in cr)),candidate_stocks_own_anchors=len(set(x['candidate'] for x in cr)),candidate_structures_own_anchors=len(set(x['candidate_event'] for x in cr)),common21_stronger_observations=len(scenario),common21_stronger_cycle_days=len(set((x['held_cycle'],x['date']) for x in scenario)),common21_stronger_cycles=len(set(x['held_cycle'] for x in scenario)),common21_stronger_stocks=len(set(x['candidate'] for x in scenario)),account_on_observations=sum(x['ACT_on'] for x in scenario),market_proxy_on_observations=sum(x['ACT_on'] and x['next_market_proxy'] is True for x in scenario),not_already_ordered_market_on=sum(x['ACT_on'] and x['next_market_proxy'] is True and not x['already_pending'] and not x['already_accepted'] for x in scenario),original_rejection_unknown=sum(x['original_logged_rejection'] is None for x in scenario),first_examples=sorted(scenario,key=lambda x:(x['date'],x['held_symbol'],x['candidate']))[:12])
save('CANDIDATE_SUMMARY.json',candidate_summary)
end=daily[-1];assert D(end['nav'])-D(1000000)==summary['net'];assert D(end['inventory'])==0
assert sum((D(c['buy_fees'])+D(c['sell_fees']) for c in cycles),Z)==D(end['fees_cny'])
save('VERIFICATION.json',dict(passed=True,cycles=69,actual_fills=len(fill),daily_rows=len(daily),net_residual=0,fees_residual=0,all_cycles_one_buy_one_sell=True,dividends=sum((D(c['dividends']) for c in cycles),Z),ending_unpaid_claim=end['dividend_receivable'],ending_inventory=end['inventory'],new_economic_paths=0,elapsed=time.monotonic()-T))
progress(stage='complete',elapsed=time.monotonic()-T,background=background,candidates=candidate_summary)
