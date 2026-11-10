"""Seventeen existing-position forks; no portfolio, new buys, or cash reinvestment."""
from pathlib import Path
import sys,json,gzip,time,hashlib,importlib.util,bisect,collections
from decimal import Decimal as D
from datetime import time as dt
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/act-forced-exit-local-20261029';PR=ROOT/'research_rounds/fat-tail-opportunity-ledger-20261029';SRC=ROOT/'research_rounds/pvr-local-finite-capital-20261029/baseline';HFILE=ROOT/'research_rounds/s-entry-mechanism-audit-20261029/code/audit.py'
sp=importlib.util.spec_from_file_location('read_frozen_market_helpers',HFILE);H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(x):return pd.Timestamp(x).to_pydatetime()
stage=sys.argv[1];assert stage in ['sample','full'];t=time.monotonic();dest=O/stage;dest.mkdir(exist_ok=False)
ev=pd.read_csv(O/'FROZEN_17_EVENTS.csv',dtype=str);sample=read(O/'INPUT_IDENTITY.json')['sample_symbols'];events=ev[ev.symbol.isin(sample)] if stage=='sample' else ev;ids=set(events.symbol)
obj=read(SRC/'accounts-v2/I__S0_base.json');daily={r['at'][:10]:r for r in rows(SRC/'accounts-v2/daily.jsonl.gz') if r['account']=='I__S0_base'};dec={r['at'][:10]:r for r in rows(SRC/'accounts-v2/decisions.jsonl.gz') if r['account']=='I__S0_base'};risk={r['at'][:10]:r for r in obj['audit_log'] if r['kind']=='risk_checkpoint'}
cache=pd.read_parquet(ROOT/'research_rounds/s-entry-mechanism-audit-20261029/market-cache.parquet');grids={s:g.set_index('date').sort_index() for s,g in cache[cache.symbol.isin(ids)].groupby('symbol')};ef=pd.read_parquet(PR/'full/daily-observed-funnel.parquet');event_days={(r.date,r.symbol):r.event_id for r in ef[ef.symbol.isin(ids)].itertuples()};ol=pd.read_csv(PR/'full/order-event-links.csv',dtype=str);sup=pd.read_csv(PR/'full/existing-admission-supplement.csv',dtype=str);supmap={(r.date,r.symbol):r.reasons for r in sup.itertuples()}
_,m,_,mdates=H.context(ids,False);calendar=[str(x.date()) for x in mdates];loadsec=time.monotonic()-t
pending={};pending_byday={}
for x in obj['audit_log']:
 k=x['kind'];day=x.get('at','')[:10]
 if k=='reserve':pending[x['order_id']]=D(x['gross_budget_cny'])
 elif k=='fill' and x['receipt']['side']=='buy':pending[x['order_id']]=D(x['gross_budget_remaining']);day=x['receipt']['at'][:10]
 elif k=='release_buy':pending.pop(x['order_id'],None)
 if day and (k in ['risk_checkpoint','reserve','release_buy'] or k=='fill' and x['receipt']['side']=='buy'):pending_byday[day]=dict(pending)

def run_arm(e,arm):
 s=e['symbol'];g=grids[s];pause=e['exit_request_at'][:10];cl=stamp(e['exit_request_at']);q0=int(daily[pause]['positions'][s]);quote=m.quote(s,cl);assert quote is not None and q0>0
 initial=m.latest_mark(s,cl).raw_price*D(q0);nxt=m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)]
 # Constructor basis is existing inventory value; actual spendable cash is0.
 a=H.L.SectorAccount(initial_cash=initial,cost_multiplier=1,fractional_split_policy=m.protocol['fractional_split_policy']);a.available=D(0);a.positions[s]=H.L.Position(s,quote.issuer_id,quote.sector_id,quote.currency,[H.L.InventoryLot(q0,nxt)])
 seed=dict(at=cl,shares=q0,raw_mark=initial/D(q0),existing_stock_equity=initial,available_cash=D(0),original_entry=e['entry_at']);qcheck=q0;flow=D(0);div=D(0);cursor=0;navrows=[];request=None;unknown=[];fee_state={};firstfills=[]
 acts=collections.defaultdict(list)
 for x in m.actions.get(s,[]):
  if pause<x['effective_date']<='2026-10-27':acts[x['effective_date']].append(x)
 days=sorted(set(x for x in calendar if x>=pause)|set(acts))
 for day in days:
  op=H.at(day,dt(9,30));close=H.at(day,dt(15,10))
  if day!=pause:
   for action in acts.get(day,[]):H.action(a,m,s,action)
   H.pay(a,m,op)
   if s in a.exits:
    w=m.window(s,op,'sell',1)
    if w:a.fill_exit(s,w)
   H.pay(a,m,op);H.pay(a,m,close)
  if day in calendar and a.quantity(s) and s not in a.exits:
   rr=g.loc[pd.Timestamp(day)];known=pd.notna(rr.e0_target) and pd.notna(rr.e0_ready) and bool(rr.e0_ready)
   lost=bool(known and not bool(rr.e0_target))
   if not known:unknown.append(day)
   if (arm=='ACT' and day==pause) or (arm=='E0' and lost):
    qq=m.quote(s,close)
    if qq is None:unknown.append(day+':exit_quote_missing')
    else:
     nc=m.sessions['A'][bisect.bisect_right(m.sessions['A'],close)];a.request_exit(qq,H.A.Clock(close,nc,close.date()));request=day
  for x in a.audit_log[cursor:]:
   k=x['kind']
   if k=='fill':
    f=x['receipt'];assert f.side=='sell' and f.at>cl;assert sum(x['fee_components'].values(),D(0))==f.fees_cny;assert D(f.shares)*D(x['price'])==f.gross_cny
    pp,pa=fee_state.get(x['order_id'],({},{}));fs=m.fees(s,f.at);expected=fs.incremental('sell',f.gross_cny,pp,pa,1,shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));assert expected==x['fee_components'];fee_state[x['order_id']]=({k:pp.get(k,D(0))+v for k,v in expected.items()},{k:pa.get(k,D(0))+v for k,v in fs.rate_accrual('sell',f.gross_cny,1,shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value')).items()})
    qcheck-=f.shares;flow+=f.gross_cny-f.fees_cny;firstfills.append(dict(at=f.at,shares=f.shares,gross=f.gross_cny,fees=f.fees_cny,price=x['price'],components=x['fee_components']))
   elif k in ['split','split_fraction_floor_proxy']:qcheck=int(D(qcheck)*D(x['ratio']))
   elif k=='dividend_accrual':div+=x['receivable'].net_local
  cursor=len(a.audit_log);assert qcheck==a.quantity(s) and a.available>=0
  mark=m.latest_mark(s,close) if qcheck else None;mv=D(qcheck)*mark.raw_price if qcheck else D(0);bal=a.balance(close,{s:mark} if mark else {});assert bal['nav']==flow+div+mv,(s,arm,day,'independent equity mismatch')
  if day in calendar:navrows.append(dict(case=e['case_id'],symbol=s,batch=pause,arm=arm,date=day,shares=qcheck,nav=str(bal['nav']),cash=str(bal['available']),inventory=str(mv),dividend_receivable=str(bal['dividend_receivable'])))
 assert not a.buys and all(x['receipt'].side=='sell' for x in a.audit_log if x['kind']=='fill')
 final=navrows[-1];vals=[D(x['nav']) for x in navrows];peak=initial;dd=D(0)
 for value in vals:peak=max(peak,value);dd=max(dd,1-value/peak)
 return dict(case=e['case_id'],symbol=s,batch=pause,arm=arm,initial_q=q0,initial_stock_equity=initial,final_equity=D(final['nav']),final_inventory=D(final['inventory']),final_shares=int(final['shares']),available=D(final['cash']),dividend_receivable=D(final['dividend_receivable']),sale_receivable=bal['sale_receivable'],sell_gross=sum((x['gross'] for x in firstfills),D(0)),sell_fees=sum((x['fees'] for x in firstfills),D(0)),dividend_accrued=div,first_exit_request=request,first_sell=firstfills[0]['at'] if firstfills else None,last_sell=firstfills[-1]['at'] if firstfills else None,sells=firstfills,unknown_days=unknown,min_equity=min(vals),min_return_from_pause=min(vals)/initial-1,max_local_drawdown=dd,seed=seed),navrows,a.audit_log

results=[];curves=[];audits=[];qrows=[];chron=[]
for _,z in events.iterrows():
 e=z.to_dict();e['case_id']=e['symbol']+'|'+e['exit_request_at'][:10];s=e['symbol'];pause=e['exit_request_at'][:10];g=grids[s];a,ar,al=run_arm(e,'ACT');b,br,bl=run_arm(e,'E0');source=[x for x in obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='sell' and x['receipt']['security_id']==s and x['receipt']['at']==e['sold_at']];assert len(source)==1;src=source[0];assert len(a['sells'])==1
 af=a['sells'][0];assert af['shares']==src['receipt']['shares'] and af['gross']==D(src['receipt']['gross_cny']) and af['fees']==D(src['receipt']['fees_cny']) and af['at']==stamp(src['receipt']['at']) and af['price']==D(src['price']) and af['components']=={k:D(v) for k,v in src['fee_components'].items()}
 delta=b['final_equity']-a['final_equity'];coincident=e['e0_active_at_request']=='False'
 if coincident:assert delta==0 and H.encoded(a['sells'])==H.encoded(b['sells'])
 resume=next((d for d,r in risk.items() if d>pause and r['event']=='resume'),None);same=[];after=g[g.index>=pd.Timestamp(e['sold_at'][:10])]
 for day,rr in after.iterrows():
  d=str(day.date());eid=event_days.get((d,s));in_original=eid==e['event_id']
  if not bool(rr.Q):continue
  dc=dec[d];dr=daily[d];reasons=sorted({reason for sid,reason in dc['rejected'] if sid==s});supreasons=supmap.get((d,s));held=int(dr['positions'].get(s,0))>0
  state='already_held' if held else 'ACT_not_resumed_or_paused' if not risk[d]['on'] else 'actual_accepted' if s in dc['accepted'] else 'explicit_rejection:'+('|'.join(reasons)) if reasons else 'verified_capacity_record:'+supreasons if supreasons else 'admission_unrecorded_unknown'
  cl=H.at(day,dt(15,10));op=m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)];w=m.window(s,op,'buy',1) if op.date()<=H.END.date() else None;market='beyond_cutoff' if op.date()>H.END.date() else 'no_executable_proxy_window' if w is None else 'market_rule_or_min_lot_capacity' if not w.buy_allowed or w.quantity.buy_floor(w.capacity_shares)==0 else 'market_proxy_feasible_without_ACT_cash_admission'
  if w is not None and market.startswith('market_proxy'):
   fr=g.loc[pd.Timestamp(op.date())];floor=rr.i_floor
   if pd.isna(floor) or pd.isna(fr.factor):market='support_guard_unknown'
   elif w.raw_open<=D(str(floor))/D(str(fr.factor)):market='original_next_open_support_guard_reject'
  pp=pending_byday.get(d);pk=set(pp or {});pg=sum(pp.values(),D(0)) if pp is not None and pk==set(dr['pending_buys']) else None
  qquote=m.quote(s,cl);minimum=qquote.quantity.buy_minimum if qquote else None;demand=qquote.raw_price*minimum if qquote else None
  qr=dict(case=e['case_id'],symbol=s,date=d,in_original_structure=in_original,ACT_on=risk[d]['on'],state=state,raw_I=bool(rr.i_buy),next_day_order_event=op,market_proxy=market,available_after_original_flow=dr['available'],order_reserved=dr['order_reserved'],pending_gross=pg,remaining90_after_original_flow=max(D(0),D('.9')*D(dr['nav'])-D(dr['inventory'])-pg) if pg is not None else None,minimum_shares=minimum,minimum_gross_at_known_close=demand,note='Residual budget after actual flow is memo, not inferred rejection cause; next-day market proxy is not account admission.')
  qrows.append(qr)
  if in_original:same.append(qr)
 fi=after[after.i_buy.astype(bool)];fq=after[after.Q];sic=[x for x in same if x['raw_I']];actual=ol[ol.symbol.eq(s)&ol.decision_at.ge(e['sold_at'])].sort_values('decision_at');actualsame=actual[actual.event_id.eq(e['event_id'])];safe=not a['unknown_days'] and not b['unknown_days']
 if coincident:category='coincident_original_E0_exit_no_incremental_ACT_sale'
 elif not safe:category='inconclusive_missing_input'
 elif delta>0:category='hold_terminal_advantage_with_adverse_path_tradeoff'
 elif delta<0 and not same:category='local_protection_effective_no_same_structure_Q'
 elif delta<0 and any(not x['ACT_on'] for x in same):category='protection_effective_recovery_wait_candidate_economic_harm_unidentified'
 elif delta<0:category='protection_effective_later_admission_or_execution_check'
 else:category='equal_terminal_equity'
 result=dict(case=e['case_id'],symbol=s,batch=pause,entry_at=e['entry_at'],actual_sold_at=e['sold_at'],initial_q=a['initial_q'],stock_equity_at_pause=a['initial_stock_equity'],coincident_E0_exit=coincident,ACT_final_equity=a['final_equity'],E0_final_equity=b['final_equity'],delta_hold_minus_ACT=delta,ACT_avoided_loss=max(D(0),-delta),ACT_foregone_terminal_equity=max(D(0),delta),ACT_sell_fees=a['sell_fees'],E0_sell_fees=b['sell_fees'],E0_exit_decision=b['first_exit_request'],E0_first_sell=b['first_sell'],E0_last_sell=b['last_sell'],E0_terminal_shares=b['final_shares'],E0_terminal_inventory=b['final_inventory'],E0_terminal_claim=b['dividend_receivable'],E0_min_return_from_pause=b['min_return_from_pause'],E0_max_local_drawdown=b['max_local_drawdown'],min_hold_minus_cash_path=min(D(x['nav'])-D(y['nav']) for x,y in zip(br,ar)),actual_whole_cycle_pnl=D(e['cycle_net_pnl']),conditional_hold_whole_cycle_pnl=D(e['cycle_net_pnl'])+delta,category=category,first_future_I_any=str(fi.index[0].date()) if len(fi) else None,first_future_Q_any=str(fq.index[0].date()) if len(fq) else None,first_I_same_structure=sic[0]['date'] if sic else None,first_Q_same_structure=same[0]['date'] if same else None,first_Q_flow=same[0]['state'] if same else 'original_structure_ended_or_no_Q',same_structure_Q=len(same),same_structure_Q_while_paused=sum(not x['ACT_on'] for x in same),first_original_account_resume=resume,first_market_feasible_same_Q=next((x['next_day_order_event'] for x in same if x['market_proxy'].startswith('market_proxy_feasible')),None),first_actual_order_any=actual.iloc[0].decision_at if len(actual) else None,first_actual_fill_any=actual.iloc[0].first_fill if len(actual) else None,first_actual_fill_same=actualsame.iloc[0].first_fill if len(actualsame) else None,unknown_signal_days=len(b['unknown_days']))
 results.append(result);curves+=ar+br;audits.append(dict(case=e['case_id'],ACT=al,E0=bl,seed=a['seed']));chron.append(dict(case=e['case_id'],same_Q_days=len(same),after_Q_days=len(fq)));print(json.dumps(dict(stage=stage,case=e['case_id'],delta=str(delta),coincident=coincident,category=category,seconds=time.monotonic()-t)),flush=True)
 pd.DataFrame(H.encoded(results)).to_csv(dest/'events.csv',index=False)
 if time.monotonic()-t>300:raise TimeoutError('300second local calculation budget')
pd.DataFrame(H.encoded(curves)).to_parquet(dest/'daily-local-equity.parquet',index=False);pd.DataFrame(H.encoded(qrows)).to_csv(dest/'Q-recovery-flow.csv',index=False)
with gzip.open(dest/'audit.json.gz','wt') as f:json.dump(H.encoded(audits),f,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/events.csv',dtype=str).fillna('');fu=pd.read_csv(dest/'events.csv',dtype=str).fillna('').set_index('case');pd.testing.assert_frame_equal(sm.set_index('case'),fu.loc[sm['case']],check_exact=True)
 for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():assert sha(p)==expected,p
save(dest/'VERIFICATION.json',dict(passed=True,stage=stage,events=len(results),sample_full_equal=stage=='full',baseline_receipts_exact=True,unique_actual_pause_batches=events.exit_request_at.nunique(),independent_daily_nav_cash_shares_fees_rights=True,no_buys_no_cash_injection=True,coincident_E0_identity=True,load_seconds=loadsec,total_seconds=time.monotonic()-t,new_portfolio_paths=0))
