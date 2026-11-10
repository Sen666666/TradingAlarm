"""Existing current L0 records only. Conservative admission proof, no trading replay."""
from pathlib import Path
import json,gzip,collections,time
from decimal import Decimal as D
from types import SimpleNamespace
from bisect import bisect_right
import pandas as pd,numpy as np
import adapter as M
Z=D(0)
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def lines(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def audit(sec,r):
 t=time.monotonic();O=M.O;src=O.parent/'lr1-cp1-add-preflight-20261031';out=O/'lock-audit'/sec;out.mkdir(parents=True,exist_ok=False)
 dsall=lines(src/sec/'full/results/daily.jsonl.gz');days=sorted({x['at'] for x in dsall});stamp=pd.DatetimeIndex([pd.Timestamp(x[:10]) for x in days]);ix={s:i for i,s in enumerate(days)}
 qual=collections.defaultdict(set);active=collections.defaultdict(bool);witness=collections.defaultdict(dict)
 refs=O.parent/'rb1-act-finite-20261031'
 for stage in ['off','on']:
  root=refs/sec/stage/'accounts-v2';on={}
  for p in root.glob('*__S0_*.json'):
   ob=M.read(p)
   for a in ob['audit_log']:
    if a['kind']=='risk_checkpoint':on[p.stem,a['at']]=bool(a['on'])
  for a in lines(root/'decisions.jsonl.gz'):
   at=a['at'];active[at]|=on.get((a['account'],at),False)
   for sid in a['eligible']:qual[at].add(sid);witness[at][sid]=f'{stage}/{a["account"]}'
 epoch={};event={};valid={};event_known={}
 for sid in r.market.lines:
  f=r.facts.f[sid];js=f.index.searchsorted(stamp,side='right')-1;prev=None;n=0;es=[];ev=[];vs=[]
  it=f.i_target.to_numpy();seg=f.segment_id.to_numpy();ib=f.i_buy.to_numpy()
  ks=[]
  for d,j in zip(stamp,js):
   key=(bool(it[j]),int(seg[j])) if j>=0 else (False,-1)
   if key!=prev:n+=1;prev=key
   ks.append(bool(j>=0 and f.index[j]==d));es.append((key[1],n));vs.append(key[0]);ev.append(bool(j>=0 and f.index[j]==d and bool(ib[j])))
  epoch[sid]=es;event[sid]=ev;valid[sid]=vs;event_known[sid]=ks
 cycles=pd.read_csv(src/sec/'analysis/campaigns.csv');records=[];windows=[];summary=[];checks=0
 for stress in ['base','cost2','delay1']:
  aid='L0_'+stress;ob=gz(src/sec/'full/results'/f'{aid}.json.gz');ds=[x for x in dsall if x['account']==aid];byat={x['at']:x for x in ds};dec={x['at']:x for x in ob['decisions']};trades=ob['trades'];first={(x['security_id'],x['at']):x for x in trades if x['side']=='buy'}
  for tr in trades:
   if tr['side']=='buy':assert tuple(tr['epoch'])==epoch[tr['security_id']][ix[tr['signal_at']]];checks+=1
  cashdebits=collections.defaultdict(lambda:Z)
  for a in ob['audit']:
   if a['kind']=='expense':cashdebits[a['at']]+=D(a['cny_amount'])
   elif a['kind']=='fill' and a['receipt']['side']=='sell':cashdebits[a['receipt']['at']]+=max(Z,D(a['receipt']['fees_cny'])-D(a['receipt']['gross_cny']))
  closed=cycles[cycles.account.eq(aid)&cycles.closed.eq(True)];cs=collections.Counter();candidate_by_at=collections.defaultdict(list)
  for c in closed.to_dict('records'):
   tr=first[c['symbol'],c['entry_at']];old=tuple(tr['epoch']);j=bisect_right(days,c['exit_at']);sid=c['symbol'];cid=f'{aid}|{sid}|{c["entry_at"]}'
   if j>=len(days):cs['no_post_exit_decision']+=1;continue
   if not valid[sid][j] or epoch[sid][j]!=old:cs['clear_already_outside_original_I_epoch']+=1;continue
   cs['closed_core_same_I_window']+=1;end=j;fres=0
   while end<len(days) and valid[sid][end] and epoch[sid][end]==old:
    at=days[end];d=byat[at];end+=1
    if sid in d['positions']:cs['unexpected_nonflat']+=1;continue
    cs['same_I_flat_stock_days']+=1
    status='ACT_off' if not d['on'] else 'I_event_unknown_no_cached_row' if not event_known[sid][end-1] else 'no_new_native_I' if not event[sid][end-1] else None
    if status is None:
     fres+=1
     if sid not in qual[at]:status='Q_not_true_or_unknown_in_active_reference' if active[at] else 'Q_unknown_all_reference_ACT_off'
     elif sid in d['pending_sells']:status='own_pending_exit'
     elif D(d['order_reserved'])!=0:status='pending_buy_identity_not_fully_logged_unknown'
     else:status='Q_true_lock_candidate'
    rec=dict(account=aid,cycle=cid,symbol=sid,entry=c['entry_at'],clear=c['exit_at'],at=at,epoch=old,status=status,Q_witness=witness[at].get(sid),nav=d['nav'],available=d['available'])
    records.append(rec);cs[status]+=1
    if status=='Q_true_lock_candidate':candidate_by_at[at].append(rec)
   subsequent=[x for x in trades if x['side']=='buy' and x['security_id']==sid and x['at']>c['exit_at'] and tuple(x['epoch'])!=old]
   re=subsequent[0]['at'] if subsequent else None
   windows.append(dict(account=aid,cycle=cid,symbol=sid,entry=c['entry_at'],clear=c['exit_at'],I_epoch=old,first_flat_decision=days[j],I_window_end=days[end] if end<len(days) else None,end_censored=end==len(days),new_I_ACT_on_days=fres,natural_new_I_epoch_actual_reentry=re))
   cs['natural_epoch_change_actual_reentry']+=int(re is not None)
  dummy=SimpleNamespace(cost_multiplier=2 if stress=='cost2' else 1);M.C.activate(dummy)
  for at,recs in candidate_by_at.items():
   d=byat[at];nav=D(d['nav']);close=M.N.iso(at);oi=bisect_right(r.market.sessions['A'],close)
   if oi>=len(r.market.sessions['A']) or r.market.sessions['A'][oi].date()>pd.Timestamp('2026-10-27').date():
    for x in recs:x['status']='next_execution_outside_current_window';cs['next_execution_outside_current_window']+=1
    continue
   opening=r.market.sessions['A'][oi];existing=Z;bad_existing=False
   for i in dec[at]['intents']:
    if i.get('size_reject'):continue
    if i['kind']!='core' or i.get('risk_budget') is None:bad_existing=True;break
    existing+=D(i['budget'])+D(i['risk_budget'])
   debit=sum((v for when,v in cashdebits.items() if close<M.N.iso(when)<=opening),Z);ready=[]
   for x in recs:
    sid=x['symbol'];quote=r.market.quote(sid,close);floor=r.facts.floor(sid,close,'I')
    if quote is None or floor is None:x['status']='quote_or_floor_unknown';cs[x['status']]+=1;continue
    i=dict(sid=sid,quote=quote,floor=floor,kind='core',weight=1.,group=1,clock=M.C.A.Clock(close,opening,close.date()),epoch=tuple(x['epoch']),reason='I_early_probe')
    M.LR.resize_core(i,nav,r.facts.factor(sid,close))
    if i.get('size_reject'):x['status']='co_block_'+i['size_reject'];cs[x['status']]+=1;continue
    raw=r.market.raw[sid];day=pd.Timestamp(opening.date())
    if day not in raw.index or not np.isfinite(raw.loc[day,'open']) or raw.loc[day,'open']<=0:x['status']='next_open_unknown';cs[x['status']]+=1;continue
    p,why=M.LR.preview(i,D(str(raw.loc[day,'open'])),r.facts.factor(sid,opening),r.market.quantity(sid,opening),r.market.fees(sid,opening))
    if why:x['status']='co_block_'+why;cs[x['status']]+=1;continue
    w=r.market.window(sid,opening,'buy',dummy.cost_multiplier)
    if w is None or w.buy_allowed is None:x['status']='next_execution_proxy_unknown';cs[x['status']]+=1;continue
    if not w.buy_allowed or w.capacity_shares<w.quantity.fill_step:x['status']='co_block_next_execution_proxy';cs[x['status']]+=1;continue
    x.update(next_execution=str(opening),frozen_budget=str(i['budget']),risk_budget=str(i['risk_budget']),frozen_share_cap=i['cap'],fee_inclusive_cash_upper_bound=str(i['budget']+i['risk_budget']),existing_orders_cash_upper_bound=str(existing),known_cash_debits=str(debit));ready.append(x)
   new=sum((D(x['fee_inclusive_cash_upper_bound']) for x in ready),Z);free=D(d['available'])-D('.1')*nav-existing-debit;pass_all=not bad_existing and free>=new
   for x in ready:
    x['all_locked_candidates_joint_cash_upper_bound']=str(new);x['cash_after_reserve_and_existing_upper_bound']=str(free)
    x['status']=('lock_only_intent_proven_execution_requires_original_delay' if stress=='delay1' else 'lock_only_and_next_execution_proven') if pass_all else 'resource_exclusivity_unknown_sufficient_bound_failed'
    cs[x['status']]+=1
  # Main stages are non-overlapping final record labels; prechecks separately named.
  final=collections.Counter(x['status'] for x in records if x['account']==aid)
  summary.append(dict(sector=sec,account=aid,all_closed_cycles=len(closed),same_I_closed_core_windows=cs['closed_core_same_I_window'],same_I_flat_stock_days=cs['same_I_flat_stock_days'],new_I_ACT_on_days=sum(x['new_I_ACT_on_days'] for x in windows if x['account']==aid),natural_epoch_change_actual_reentry_windows=cs['natural_epoch_change_actual_reentry'],final_stock_day_status=dict(final),precheck_counts=dict(cs)))
 pd.DataFrame(M.N.encoded(records)).to_csv(out/'STOCK_DAYS.csv',index=False);pd.DataFrame(M.N.encoded(windows)).to_csv(out/'WINDOWS.csv',index=False);M.save(out/'SUMMARY.json',summary);M.save(out/'VERIFICATION.json',dict(passed=True,actual_core_fill_epoch_checks=checks,read_existing_L0_and_reference_eligible_only=True,no_new_account_or_unlock_paths=True,no_new_indicator=True,conservative_cash_proof_is_sufficient_not_necessary=True,normal_cost_execution_uses_existing_daily_HLV_proxy=True,delay_proves_intent_only_not_invented_next_fill=True,seconds=time.monotonic()-t))
 print('LOCK_AUDIT',sec,'seconds',time.monotonic()-t,'windows',sum(x['same_I_closed_core_windows'] for x in summary),flush=True)
