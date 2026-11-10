"""Exactly 14x2 authorized independent paths. Requires an explicit reviewed gate file."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,time as dt
import json,gzip,time,argparse,traceback,math
import pandas as pd
import inputs as I
import conditional_engine as E
J=I.J;Z=D(0)

def clean(x):
 x=I.canon(x)
 def f(v):
  if isinstance(v,dict):return {k:f(w)for k,w in v.items()}
  if isinstance(v,list):return [f(w)for w in v]
  if isinstance(v,float)and not math.isfinite(v):return None
  return v
 return f(x)
def save(p,x):
 assert not p.exists(),('never overwrite',p);p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def gz(p,x):
 assert not p.exists()
 with gzip.open(p,'wt')as f:json.dump(clean(x),f,ensure_ascii=False,allow_nan=False)
def event(r,at,opens,closes):
 m=r.market;a=r.account;phase='OPEN'if at in opens else'CLOSE'if at in closes else'ACTION';m.set_phase(at,phase)
 a.settle_due(at);r._actions(at);r._payments(a,at)
 if phase=='OPEN':
  bef=a.balance(at,m.marks(at,a.positions));n=len(a.trades);r.opening(a,at);aft=a.balance(at,m.marks(at,a.positions));tr=a.trades[n:]
  flow=sum((D(t['gross_cny'])-D(t['fees_cny'])if t['side']=='sell'else-D(t['gross_cny'])-D(t['fees_cny'])for t in tr),Z)
  gap=aft['available']+aft['order_reserved']+aft['sale_receivable']-bef['available']-bef['order_reserved']-bef['sale_receivable']-flow
  assert abs(gap)<D('1e-8'),('cash bridge',r.case['round_id'],r.arm,at,gap)
  r.open_checks.append(dict(at=at,gap=gap,trades=len(tr)))
 if phase=='CLOSE':r.planning(at)
 book=r.cost_book.sync(a)
 if phase=='CLOSE':
  d=r.daily[-1];sid=r.sid;raw=m._raw_source[sid];day=pd.Timestamp(at.date());observed=day in raw.index
  def px(key):
   v=float(raw.loc[day,key])if observed else float('nan')
   return D(str(raw.loc[day,key]))if math.isfinite(v)and v>0 else None
  d.update(remaining_stock_cost=book.cost,stock_round=book.round,raw_row_present=observed,observed_raw_today=px('close')is not None,raw_close_today=px('close'),raw_low_today=px('low'),close_factor=r.facts.factor(sid,at),raw_mark_source_day=str(r.facts.row(sid,at).name.date()),cost_basis_convention='BUY_FEES_INCLUDED_DIVIDENDS_EXCLUDED',seed_layers_cumulative=[dict(z)for z in a.layers if z.get('common_probe')and str(z['signal_at'].date())==r.case['signal_day']])

def summarize(r):
 a=r.account;c=r.case;sid=r.sid;daily=r.daily;last=daily[-1];rounds=[];cur=None;qty=0;layer_round={}
 for j in a.journal:
  k=j['kind']
  if k=='real_buy_fill':
   if qty==0:
    cur=dict(round=len(rounds)+1,opened=j['at'],signal=j['signal_at'],first_role=j['role'],layers=[],trade_cash=Z,fees=Z,closed=None);rounds.append(cur)
   qty+=j['shares'];cur['layers'].append(j['layer']);layer_round[j['layer']]=cur['round'];cur['trade_cash']-=D(j['shares'])*j['price']+j['fees'];cur['fees']+=j['fees']
  elif k=='real_sell_fill':
   assert cur is not None and qty>=j['shares'];qty-=j['shares'];cur['trade_cash']+=D(j['shares'])*j['price']-j['fees'];cur['fees']+=j['fees']
   if qty==0:cur['closed']=j['at']
  elif k=='actual_split':qty=int(D(qty)*j['ratio'])
 assert qty==a.quantity(sid)
 finalprice=last['inventory']/D(qty)if qty else Z
 for rr in rounds:
  ll=[z for z in a.layers if z['id']in rr['layers']];rr['remaining_qty']=sum(z['qty']for z in ll);rr['dividend_accrual']=sum((z['dividend']for z in ll),Z);rr['terminal_mark']=D(rr['remaining_qty'])*finalprice;rr['net']=rr['trade_cash']+rr['dividend_accrual']+rr['terminal_mark']
  rr['status']=('CLOSED_WIN'if rr['net']>0 else'CLOSED_LOSS'if rr['net']<0 else'CLOSED_FLAT')if rr['closed']else('OPEN_POSITIVE'if rr['net']>0 else'OPEN_NEGATIVE'if rr['net']<0 else'OPEN_FLAT')
  rr['prior_filled_round_count']=rr['round']-1
  rr['origin']='SEED_MOBILE'if str(rr['signal'].date())==c['signal_day']else ('LATER_FIRST_'if rr['round']==1 else'REENTRY_')+('CORE'if rr['first_role']=='core'else'MOBILE')
  rr['holding_common_closes']=sum(any(z['id']in rr['layers']for z in d['layers'])for d in daily)
  rr['cost_common_close_days']=sum((d['remaining_stock_cost']for d in daily if d['stock_round']==rr['round']and d['positions'].get(sid,0)),Z)
 assert abs(sum((rr['net']for rr in rounds),Z)-(last['nav']-D(c['seed_nav'])))<D('1e-8'),('round NAV reconcile',c['round_id'],r.arm)
 seedlayers=[z for z in a.layers if z.get('common_probe')and str(z['signal_at'].date())==c['signal_day']];ids={z['id']for z in seedlayers};seedtr=[t for t in a.trades if t['side']=='buy'and t['layer']in ids];seedsells=[t for t in a.trades if t['side']=='sell'and any(p['layer']in ids for p in t['parts'])];triggers=[v for v in a.audit_log if v.get('kind')=='pilot_layer_exit'and ids.intersection(v.get('layers',[]))]
 seedqty=sum(z['qty']for z in seedlayers);seednet=sum((z['cash']+z['dividend']for z in seedlayers),Z)+D(seedqty)*finalprice
 seedentry=min((z['opened']for z in seedlayers),default=None);seedexit=max((z['closed']for z in seedlayers),default=None)if seedlayers and all(z['closed']for z in seedlayers)else None
 initial_cost=sum((D(t['gross_cny'])+D(t['fees_cny'])for t in seedtr),Z)
 first_fee=sum((D(t['fees_cny'])for t in seedtr),Z)+sum((D(t['fees_cny'])*D(sum(p['shares']for p in t['parts']if p['layer']in ids))/D(t['shares'])for t in seedsells),Z)
 mae=None;first_recovery=None;held_after_old=0
 if seedlayers:
  adjusted_price=sum((D(t['shares'])*D(t['price'])*r.facts.factors.factor_at(sid,str(t['at'].date()))for t in seedtr),Z)/D(sum(t['shares']for t in seedtr))
  low_ratios=[D(t['price'])*r.facts.factors.factor_at(sid,str(t['at'].date()))/adjusted_price-1 for t in seedsells]
  for d in daily:
   held=any(z['id']in ids for z in d['layers'])
   if held and str(d['at'].date())>=c['exit_day']:held_after_old+=1
   if held and d['raw_low_today']is not None:low_ratios.append(d['raw_low_today']*d['close_factor']/adjusted_price-1)
   ss=d.get('seed_layers_cumulative',[])
   if ss and not first_recovery:
    q=sum(z['qty']for z in ss);px=d['raw_close_today']
    if not q or px is not None:
     net=sum((z['cash']+z['dividend']for z in ss),Z)
     if q:
      px*=D('.9995');fee=J.LR.fees(q,px,r.market.fees(sid,d['at']),'sell',r.market.rules.get('security_metadata',{}).get(sid,{}).get('par_value'));net+=D(q)*px-fee
     if net>0:first_recovery=d['at']
  mae=min(low_ratios)if low_ratios else None
 seed_status='NO_ENTRY'if not seedlayers else('CLOSED_WIN'if seednet>0 else'CLOSED_LOSS'if seednet<0 else'CLOSED_FLAT')if seedexit else('OPEN_POSITIVE'if seednet>0 else'OPEN_NEGATIVE'if seednet<0 else'OPEN_FLAT')
 result=dict(round_id=c['round_id'],sid=sid,name=c['name'],arm=r.arm,seed_signal=c['signal_day'],seed_NAV=c['seed_nav'],seed_status=seed_status,seed_initial_cost=initial_cost,seed_original_qty=c['buy_shares'],seed_proxy_qty=sum(z['initial_qty']for z in seedlayers),seed_entry=seedentry,seed_first_trigger=triggers[0]['at']if triggers else None,seed_first_trigger_reason=triggers[0]['reason']if triggers else None,seed_first_proxy_sell=seedsells[0]['at']if seedsells else None,seed_complete_proxy_exit=seedexit,seed_net_including_terminal_mark=seednet if seedlayers else None,seed_fees=first_fee,seed_visible_low_and_proxy_sell_MAE_fraction=mae,seed_MAE_scope='observed held-day lows plus executed proxy sells, no missing-bar invented observations',seed_first_close_accrual_plus_net_liquidation_recovery=first_recovery,seed_recovery_is_paper_not_settled_or_T1_executable=True,seed_held_closes_after_original_CP_exit=held_after_old,closed_wins=sum(x['status']=='CLOSED_WIN'for x in rounds),closed_losses=sum(x['status']=='CLOSED_LOSS'for x in rounds),open_positive=sum(x['status']=='OPEN_POSITIVE'for x in rounds),open_negative=sum(x['status']=='OPEN_NEGATIVE'for x in rounds),all_rounds=len(rounds),CORE_reentry_rounds=sum(x['origin']=='REENTRY_CORE'for x in rounds),MOBILE_reentry_rounds=sum(x['origin']=='REENTRY_MOBILE'for x in rounds),later_first_CORE_rounds=sum(x['origin']=='LATER_FIRST_CORE'for x in rounds),later_first_MOBILE_rounds=sum(x['origin']=='LATER_FIRST_MOBILE'for x in rounds),ending_NAV=last['nav'],marked_net=last['nav']-D(c['seed_nav']),ending_qty=qty,ending_pending_exit=sid in a.exits,fees=sum((D(t['fees_cny'])for t in a.trades),Z),holding_common_closes=sum(bool(d['positions'].get(sid))for d in daily),cost_common_close_days=sum((d['remaining_stock_cost']for d in daily),Z),proxy_tradability='UNKNOWN',original_first_layer_net=c['first_layer_net_pnl'],original_first_layer_exit=c['exit_day'],whole_account_or_OOS=False)
 return result,rounds

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--execute-reviewed',action='store_true');args=ap.parse_args();assert args.execute_reviewed
 gate=json.loads((I.O/'REVIEW_APPROVED.json').read_text());assert gate['passed']
 for p,h in gate['code_hashes'].items():assert I.sha(p)==h,('reviewed code drift',p)
 source_freeze=Path(gate['source_freeze_path']);assert source_freeze.parent.resolve()==I.O.resolve()
 assert I.sha(source_freeze)==gate['source_freeze_sha256'],('reviewed source manifest drift',source_freeze)
 for p,h in json.loads(source_freeze.read_text()).items():assert I.sha(p)==h,('reviewed input source drift',p)
 out=I.O/'run';assert not out.exists(),'one bounded run only, do not overwrite or implicitly rerun';out.mkdir();started=time.monotonic();allsummary=[];allround=[]
 try:
  data=I.load();freeze=dict(I.SOURCES);save(out/'SOURCE_FREEZE.json',freeze);save(out/'ORIGINAL_FIXED_FACTS.json',data['cases']);save(out/'PREDECLARED.json',dict(case_ids=I.IDS,arms=E.ARMS,cutoff=I.END,whole_account_runs=0,independent_condition_paths=28,forced_terminal_liquidations=0,case_replacements=0,parameter_scans=0,contract_sha256=I.sha(I.O/'CONTRACT.md')))
  for c in data['cases']:
   for arm in E.ARMS:
    r=E.Runner(*I.single(data,c['sid']),c,arm);r.warm(data['calendar']);seed=E.seed_plan(r);start=J.M.N.iso(c['signal_day']+'T15:10:00+08:00');finish=J.M.N.iso(I.END+'T15:10:00+08:00');m=r.market
    opens={t for t in m.sessions['A']if start<t<=finish};closes={t for t in m.cutoffs if start<t<=finish};actions={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ)for d in r.actions_by_date};events=sorted(opens|closes|{t for t in actions if start<t<=finish})
    # Seed CLOSE was already processed; enrich its no-position cost row.
    r.daily[-1].update(remaining_stock_cost=Z,stock_round=0,observed_raw_today=True,raw_close_today=None,raw_low_today=None,close_factor=None)
    for t in events:event(r,t,opens,closes)
    sm,rr=summarize(r);allsummary.append(sm);allround.extend(dict(round_id=c['round_id'],arm=arm,**x)for x in rr)
    path=out/f"{c['round_id']}_{arm}";path.mkdir()
    gz(path/'PATH.json.gz',dict(case=c,seed=seed,summary=sm,rounds=rr,daily=r.daily,trades=r.account.trades,layers=r.account.layers,journal=r.account.journal,audit=r.account.audit_log,funding=r.funding,opportunities=r.opportunities,decisions=r.account.decisions,industry=r.stage_events,profit_gate=r.profit_events,open_risks=r.open_risks,open_checks=r.open_checks,proxy_windows=m.exec_rows,ending_budget=r.account.budget.__dict__,ending_settlements=r.account.settlements,ending_dividends=r.account.dividends))
    print('PATH_DONE',c['round_id'],c['name'],arm,sm['seed_status'],sm['marked_net'],'seconds',round(time.monotonic()-started,1),flush=True)
  save(out/'SUMMARY.json',allsummary);save(out/'ALL_STOCK_ROUNDS.json',allround);pd.DataFrame(clean(allsummary)).to_csv(out/'SUMMARY.csv',index=False);pd.DataFrame(clean(allround)).to_csv(out/'ALL_STOCK_ROUNDS.csv',index=False)
  for p,h in freeze.items():assert I.sha(p)==h,('source changed',p)
  save(out/'DONE.json',dict(passed=True,seconds=time.monotonic()-started,paths=len(allsummary),fixed_cases=len(data['cases']),sources_unchanged=len(freeze),original_accounts_rerun=0,all_round_NAV_bridges=True,all_OPEN_cash_bridges=True,forced_terminal_sales=0,real_orders=False));save(out/'OUTPUT_HASHES.json',{str(p.relative_to(out)):I.sha(p)for p in out.rglob('*')if p.is_file()})
 except BaseException:
  if 'r'in locals():
   a=r.account
   gz(out/'PARTIAL_FAILED_CASE_DIAGNOSTIC.json.gz',dict(partial_event_not_resumable=True,case=r.case,arm=r.arm,daily=r.daily,trades=a.trades,layers=a.layers,journal=a.journal,audit=a.audit_log,decisions=a.decisions,funding=r.funding,opportunities=r.opportunities,industry=r.stage_events,profit_gate=r.profit_events,open_risks=r.open_risks,open_checks=r.open_checks,positions=a.positions,buys=a.buys,exits=a.exits,settlements=a.settlements,dividends=a.dividends,available=a.available,core_epoch=a.core_epoch,budget=a.budget.__dict__))
  save(out/'FAILURE.json',dict(traceback=traceback.format_exc(),round_id=c.get('round_id')if 'c'in locals()else None,arm=arm if 'arm'in locals()else None,last_event=str(t)if't'in locals()else None,completed_paths=len(allsummary),auto_retry=False));raise
if __name__=='__main__':main()
