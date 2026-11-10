"""Closed sale-proceeds slices; first original-structure Q only; no portfolio."""
from pathlib import Path
import sys,json,gzip,time,hashlib,importlib.util,bisect,collections
from decimal import Decimal as D
from datetime import time as dt
import pandas as pd
R=Path('/Users/bytedance/Documents/ChatGPT/money');O=R/'research_rounds/act-first-Q-reentry-local-20261029';PR=R/'research_rounds/act-forced-exit-local-20261029';HFILE=R/'research_rounds/s-entry-mechanism-audit-20261029/code/audit.py'
sp=importlib.util.spec_from_file_location('firstQ_existing_helpers',HFILE);H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
stage=sys.argv[1];assert stage in ['sample','full'];started=time.monotonic();dest=O/stage;dest.mkdir(exist_ok=False)
mother=pd.read_csv(O/'FROZEN_MOTHER_17.csv',dtype=str).fillna('');events=mother[mother.symbol.isin(read(O/'INPUT_IDENTITY.json')['sample'])] if stage=='sample' else mother;ids=set(events.symbol)
obj=read(R/'research_rounds/pvr-local-finite-capital-20261029/baseline/accounts-v2/I__S0_base.json');cache=pd.read_parquet(R/'research_rounds/s-entry-mechanism-audit-20261029/market-cache.parquet');grids={s:g.set_index('date').sort_index() for s,g in cache[cache.symbol.isin(ids)].groupby('symbol')};opps=pd.read_parquet(R/'research_rounds/s-entry-mechanism-audit-20261029/opportunities.parquet').set_index('event_id');_,m,_,dates=H.context(ids,False);loadsec=time.monotonic()-started
original17=pd.read_csv(PR/'FROZEN_17_EVENTS.csv',dtype=str);original_event_by_case={r.symbol+'|'+r.exit_request_at[:10]:r.event_id for r in original17.itertuples()}
assert len(original_event_by_case)==17 and all(e['case'] in original_event_by_case for e in events.to_dict('records'))
cashrows=[];cash={}
for e in events.to_dict('records'):
 matches=[x for x in obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='sell' and x['receipt']['security_id']==e['symbol'] and x['receipt']['at']==e['actual_sold_at']];assert len(matches)==1
 sale=matches[0]['receipt'];settles=[x for x in obj['audit_log'] if x['kind']=='settle' and x['settlement']['settlement_id']==sale['settlement_id']];assert len(settles)==1;settled=settles[0];assert not settled['settlement']['debit'];c=D(sale['gross_cny'])-D(sale['fees_cny']);assert c==D(settled['settlement']['cny_amount']) and c>0;assert H.C.native.iso(settled['at'])>=H.C.native.iso(sale['at']);cash[e['case']]=(c,settled['at']);cashrows.append(dict(case=e['case'],symbol=e['symbol'],sale_at=sale['at'],shares=sale['shares'],sale_gross=sale['gross_cny'],sale_fee=sale['fees_cny'],net_settlement=c,settled_at=settled['at'],settlement_id=sale['settlement_id'],exact=True))
pd.DataFrame(H.encoded(cashrows)).to_csv(dest/'actual-sale-cash-baseline.csv',index=False)

def run(e,cost):
 s=e['symbol'];c0,settled=cash[e['case']];g=grids[s];flow=e['initial_flow'];qday=e['first_Q_date'] or None;event_id=original_event_by_case[e['case']];ef=opps.loc[event_id];end=pd.Timestamp(ef.end_signal) if pd.notna(ef.end_signal) else None
 basic=dict(case=e['case'],symbol=s,batch=e['batch'],cost=cost,original_event=event_id,first_Q=qday,initial_flow=flow,initial_cash=c0,original_settled_at=settled,cash_wait_terminal=c0,paired_known=True)
 if flow!='first_Q_while_paused':
  return dict(**basic,status=flow,exposed=False,buy_fills=0,final_equity=c0,net_increment=D(0),buy_gross=D(0),buy_fees=D(0),sell_fees=D(0),fees=D(0),slippage=D(0),final_shares=0,inventory=D(0),claim=D(0),min_return_after_entry=None,max_local_drawdown=None),[],[]
 qdate=pd.Timestamp(qday);qr=g.loc[qdate];qcl=H.at(qdate,dt(15,10));quote=m.quote(s,qcl)
 unknown=None
 if not bool(qr.Q) or not bool(qr.e0_target) or not bool(qr.e0_ready):unknown='frozen_Q_or_structure_not_confirmed'
 elif end is not None and qdate>=end:unknown='first_Q_outside_original_epoch'
 elif pd.isna(qr.i_floor) or quote is None:unknown='first_Q_support_or_quote_unknown'
 if unknown:return dict(**basic,status=unknown,paired_known=False,exposed=False,net_increment=None),[],[]
 if H.C.native.iso(settled)>qcl:
  return dict(**basic,status='first_Q_cash_not_yet_settled',exposed=False,buy_fills=0,final_equity=c0,net_increment=D(0),buy_gross=D(0),buy_fees=D(0),sell_fees=D(0),fees=D(0),slippage=D(0),final_shares=0,inventory=D(0),claim=D(0),min_return_after_entry=None,max_local_drawdown=None),[],[]
 a=H.L.SectorAccount(initial_cash=c0,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);qcheck=0;trade=D(0);div=D(0);cursor=0;fee_state={};attempted=False;attempt=None;floor=D(str(qr.i_floor));firstfill=None;lastsell=None;buygross=buyfee=sellfee=slip=D(0);buys=sells=0;navrows=[];unknowns=[];entry_equity=None;exit_request=None;actions=collections.defaultdict(list)
 for x in m.actions.get(s,[]):
  if settled[:10]<=x['effective_date']<='2026-10-27':actions[x['effective_date']].append(x)
 for day in g.index[g.index>=pd.Timestamp(settled[:10])]:
  d=str(day.date());op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10));rr=g.loc[day]
  for x in actions.get(d,[]):H.action(a,m,s,x)
  H.pay(a,m,op)
  if s in a.exits:
   w=m.window(s,op,'sell',cost)
   if w:
    f=a.fill_exit(s,w)
    if f:lastsell=f.at
  if s in a.buys:
   w=m.window(s,op,'buy',cost)
   if w is None:unknowns.append(d+':buy_window_unavailable')
   elif pd.isna(rr.factor):unknowns.append(d+':open_factor_unknown');a.cancel_buy(s)
   elif w.raw_open<=floor/D(str(rr.factor)):
    a.audit_log.append(dict(kind='first_Q_open_support_reject',at=op,sid=s));a.cancel_buy(s)
   else:
    f=a.fill_buy(s,w)
    if f and firstfill is None:firstfill=f.at
  H.pay(a,m,op);H.pay(a,m,cl);a.expire_day_buys(cl)
  if a.quantity(s) and s not in a.exits:
   known=pd.notna(rr.e0_target) and pd.notna(rr.e0_ready) and bool(rr.e0_ready)
   if not known:unknowns.append(d+':E0_unknown')
   if (known and not bool(rr.e0_target)) or (end is not None and day>=end):
    qq=m.quote(s,cl)
    if qq is None:unknowns.append(d+':exit_quote_unknown')
    else:a.request_exit(qq,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));exit_request=d
  if day==qdate:
   assert not attempted;attempted=True;ok,why=a.reserve_budget(quote=quote,clock=H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()),gross_budget_cny=c0,candidate_id=e['case']+'|FIRST_Q');attempt=dict(accepted=ok,reason=why,decision_at=cl,frozen_floor=floor)
  for x in a.audit_log[cursor:]:
   k=x['kind']
   if k=='fill':
    f=x['receipt'];assert f.at>qcl and D(f.shares)*x['price']==f.gross_cny and sum(x['fee_components'].values(),D(0))==f.fees_cny
    pp,pa=fee_state.get(x['order_id'],({},{}));fs=m.fees(s,f.at);expected=fs.incremental(f.side,f.gross_cny,pp,pa,cost,shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));assert expected==x['fee_components'];fee_state[x['order_id']]=({k:pp.get(k,D(0))+v for k,v in expected.items()},{k:pa.get(k,D(0))+v for k,v in fs.rate_accrual(f.side,f.gross_cny,cost,shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value')).items()});slip+=abs(x['price']-x['raw_open'])*f.shares
    if f.side=='buy':qcheck+=f.shares;trade-=f.gross_cny+f.fees_cny;buygross+=f.gross_cny;buyfee+=f.fees_cny;buys+=1
    else:qcheck-=f.shares;trade+=f.gross_cny-f.fees_cny;sellfee+=f.fees_cny;sells+=1
   elif k in ['split','split_fraction_floor_proxy']:qcheck=int(D(qcheck)*x['ratio'])
   elif k=='dividend_accrual':div+=x['receivable'].net_local
  cursor=len(a.audit_log);assert qcheck==a.quantity(s) and a.available>=0;mark=m.latest_mark(s,cl) if qcheck else None;mv=qcheck*mark.raw_price if mark else D(0);bal=a.balance(cl,{s:mark} if mark else {});assert bal['nav']==c0+trade+div+mv
  if firstfill is not None and entry_equity is None:entry_equity=bal['nav']
  navrows.append(dict(case=e['case'],symbol=s,batch=e['batch'],cost=cost,date=d,nav=str(bal['nav']),shares=qcheck,cash=str(bal['available']),inventory=str(mv),claim=str(bal['dividend_receivable'])))
 assert attempted and sum(x['kind']=='reserve' for x in a.audit_log)<=1
 if unknowns:
  return dict(**basic,status='field_or_execution_window_unknown',paired_known=False,exposed=buys>0,net_increment=None,unknowns='|'.join(unknowns)),navrows,a.audit_log
 used=buygross+buyfee;assert used<=c0
 if buys:
  after=[D(x['nav']) for x in navrows if x['date']>=str(firstfill.date())];peak=c0;dd=D(0)
  for value in after:peak=max(peak,value);dd=max(dd,1-value/peak)
  minret=min(after)/c0-1;status='first_Q_filled'
 else:minret=dd=None;status='first_Q_order_unfilled:'+str(attempt['reason'])
 final=navrows[-1];nav=D(final['nav']);est=sum(m.fees(s,H.at(H.END,dt(15,10))).incremental('sell',D(final['inventory']),{}, {},cost,shares=qcheck,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value')).values(),D(0)) if qcheck else D(0)
 return dict(**basic,status=status,exposed=buys>0,buy_fills=buys,sell_fills=sells,first_fill=firstfill,exit_request=exit_request,last_sell=lastsell,final_equity=nav,net_increment=nav-c0,net_return=(nav-c0)/c0,buy_gross=buygross,buy_fees=buyfee,sell_fees=sellfee,fees=buyfee+sellfee,slippage=slip,used_cash=used,unused_initial_cash=c0-used,final_shares=qcheck,inventory=D(final['inventory']),claim=D(final['claim']),min_return_after_entry=minret,max_local_drawdown=dd,estimated_terminal_sell_fee=est,estimated_terminal_slippage=D(final['inventory'])*D('.0005')*cost if qcheck else D(0),attempt=attempt),navrows,a.audit_log

results=[];curves=[];aud=[]
for e in events.to_dict('records'):
 for cost in [1,2]:
  x,c,a=run(e,cost);results.append(x);curves+=c;aud.append(dict(case=e['case'],cost=cost,audit=a));print(json.dumps(dict(stage=stage,case=e['case'],cost=cost,status=x['status'],delta=str(x['net_increment']) if x['net_increment'] is not None else None,seconds=time.monotonic()-started)),flush=True)
 if time.monotonic()-started>300:raise TimeoutError('300s small local diagnostic budget')
pd.DataFrame(H.encoded(results)).to_csv(dest/'pairs.csv',index=False);pd.DataFrame(H.encoded(curves)).to_parquet(dest/'daily-reentry-equity.parquet',index=False)
with gzip.open(dest/'audit.json.gz','wt') as stream:json.dump(H.encoded(aud),stream,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/pairs.csv',dtype=str).fillna('').set_index(['case','cost']);fu=pd.read_csv(dest/'pairs.csv',dtype=str).fillna('').set_index(['case','cost']);pd.testing.assert_frame_equal(sm,fu.loc[sm.index],check_exact=True)
 for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():assert sha(p)==expected,p
save(dest/'VERIFICATION.json',dict(passed=True,mother_cases=len(events),cost_pairs=len(results),actual_sale_cash_baselines_exact=len(cashrows),known_pairs=sum(x['paired_known'] for x in results),unknown_pairs=sum(not x['paired_known'] for x in results),source_first_Q_only=True,max_reservations_per_slice=1,no_external_cash=True,independent_cash_shares_fees_rights_NAV=True,sample_full_equal=stage=='full',load_seconds=loadsec,total_seconds=time.monotonic()-started,new_account_portfolio_paths=0))
