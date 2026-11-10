"""Existing-ledger read audit only. Never import or run consumer/indicator code."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import json,gzip,hashlib,time
import pandas as pd
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=Path(__file__).resolve().parent
C=R/'account_comparison_continuous_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
U=W/'universe-cp1-inputs-20261031'
END='2026-05-15'; Z=D(0); TOL=D('0.00000001'); sources={}; started=time.monotonic()
def hashfile(p,expected=None):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();s=sources.setdefault(str(p),dict(sha256=h))
 if expected is not None:s['expected_sha256']=expected;s['matches_expected']=h==expected;assert h==expected,('source drift',p)
 return h
def read(p,expected=None):
 hashfile(p,expected);return json.loads(Path(p).read_text())
def para(p,expected=None):hashfile(p,expected);return pd.read_parquet(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v)for v in x]
 if isinstance(x,D):return str(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 if isinstance(x,Path):return str(x)
 return x
def dump(name,x):
 with (O/name).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def csv(name,rows):
 assert not (O/name).exists();pd.DataFrame(rows).to_csv(O/name,index=False)
protocol=read(O/'FROZEN_PROTOCOL.json');hashfile(Path(__file__))
fp=R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv';hashfile(fp);old=pd.read_csv(fp);old=old[old.account.eq('PVR')].copy()
lp=C/'run_1200000/pair/PVR.json.gz';hashfile(lp);x=json.load(gzip.open(lp,'rt'))
done=read(C/'run_1200000/DONE.json');assert done['last_event'][:10]==END
pre=read(C/'run_1200000/PREDECLARED.json')
for p in [C/'run_continuous.py',C/'inputs/continuous_inputs.py',R/'selection_entry_diagnosis_v1/diagnose_first_entries.py',R/'selection_entry_diagnosis_v1/supplement_checks.py',W/'case-stage-ledger-20261031/v3/joint_v3.py',Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py')]:hashfile(p)
manifest={z['symbol']:z for z in read(U/'STOCK_MANIFEST.json')}
union_manifests=[W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')]
union_refs=defaultdict(list)
for p in union_manifests:
 for r in read(p):
  if not r['industry']:union_refs[r['sid']].append((r['output_path'],r['output_sha256']))
for r in read(C/'inputs/H1_MANIFEST.json'):
 if not r['industry']:union_refs[r['sid']].append((r['receipt_path'],r['receipt_sha256']))
# Original ledger transaction/event replay for accounting verification, not strategy replay.
ls={z['id']:z for z in x['layers']};buys={z['layer']:z for z in x['trades']if z['side']=='buy'}
assert len(ls)==len(buys)==3630
live=defaultdict(dict);current={};rounds=[];layer_round={};qty=defaultdict(int);cash=defaultdict(lambda:Z);div=defaultdict(lambda:Z)
traces=[];actions=[];split_alloc=[];ev=[];decisions={(d['at'][:10],i['sid'],i['kind']):i for d in x['decisions'] for i in d['intents']}
for j,t in enumerate(x['trades']):ev.append((t['at'],1,j,'trade',t))
for j,t in enumerate(x['audit']):
 if t['kind']=='dividend_accrual':ev.append((t['receivable']['ex_at'],0,j,'dividend',t['receivable']))
 if t['kind'] in ['split','split_fraction_floor_proxy']:ev.append((t['at'],0,j,'split',t))
for at,_,j,kind,t in sorted(ev):
 assert at[:10]<=END
 if kind=='trade':
  sid=t['security_id'];before=sum(live[sid].values())
  if t['side']=='buy':
   lid=t['layer'];l=ls[lid];assert lid not in layer_round
   if not before:
    r=dict(round_id=f'PVR:{sid}:{lid}',account='PVR',sid=sid,first_layer=lid,signal_day=l['signal_at'][:10],entry_day=at[:10],entry_at=at,closed_day=None,closed_at=None,first_kind=l['kind'],first_reason=t['reason'],layer_ids=[],sell_reasons=set(),partial_sell_while_stock_held_n=0,mobile_exit_while_core_held_n=0,management_end=END)
    rounds.append(r);current[sid]=r
   r=current[sid];r['layer_ids'].append(lid);layer_round[lid]=r['round_id'];live[sid][lid]=int(t['shares']);qty[lid]=int(t['shares']);cash[lid]-=D(t['gross_cny'])+D(t['fees_cny'])
   traces.append(dict(round_id=r['round_id'],layer=lid,at=at,side='buy',shares=t['shares'],net_cash=-(D(t['gross_cny'])+D(t['fees_cny'])),source_trade_index=j,reason=t['reason'],stock_qty_before=before,stock_qty_after=sum(live[sid].values())))
  else:
   r=current[sid];assert before>0
   assert sum(p['shares']for p in t['parts'])==t['shares']
   assert abs(sum((D(p['net_cash'])for p in t['parts']),Z)-(D(t['gross_cny'])-D(t['fees_cny'])))<TOL
   for p in t['parts']:
    lid=p['layer'];assert layer_round[lid]==r['round_id'];assert live[sid][lid]>=p['shares'];live[sid][lid]-=p['shares'];qty[lid]-=p['shares'];cash[lid]+=D(p['net_cash']);r['sell_reasons'].add(p['reason'])
    traces.append(dict(round_id=r['round_id'],layer=lid,at=at,side='sell',shares=p['shares'],net_cash=D(p['net_cash']),source_trade_index=j,reason=p['reason'],stock_qty_before=before,stock_qty_after=sum(live[sid].values())))
   after=sum(live[sid].values())
   if after:
    r['partial_sell_while_stock_held_n']+=1
    if any(p['kind']=='add'for p in t['parts'])and any(q>0 and ls[k]['kind']=='core'for k,q in live[sid].items()):r['mobile_exit_while_core_held_n']+=1
   else:r['closed_day']=at[:10];r['closed_at']=at;del current[sid]
  live[sid]={k:v for k,v in live[sid].items()if v>0}
 elif kind=='split':
  sid=t['sid'];v=live[sid];before=sum(v.values());ratio=D(t['ratio']);target=int(D(before)*ratio);ks=sorted(v);parts=[int(D(v[k])*ratio)for k in ks];remain=target-sum(parts)
  for jj in range(remain):parts[jj%len(parts)]+=1
  for k,q in zip(ks,parts):
   split_alloc.append(dict(round_id=layer_round[k],layer=k,at=at,event_id=t['event_id'],old_qty=v[k],new_qty=q,ratio=ratio,source_kind=t['kind']));v[k]=q;qty[k]=q
  actions.append(dict(kind=kind,at=at,sid=sid,event_id=t['event_id'],stock_qty_before=before,stock_qty_after=target,source_kind=t['kind']))
 else:
  sid=t['security_id'];v=live[sid];q=sum(v.values());assert q>0
  for lid,n in v.items():
   value=D(t['net_local'])*D(n)/D(q);div[lid]+=value
   actions.append(dict(kind=kind,at=at,sid=sid,event_id=t['event_id'],round_id=layer_round[lid],layer=lid,shares=n,net_accrual=value,paid_at=t.get('paid_at'),entitlement_basis=t['entitlement_basis'],source_id=t['source_id']))
layerqa=[]
for lid,l in ls.items():
 casherr=cash[lid]-D(l['cash']);diverr=div[lid]-D(l['dividend']);assert abs(casherr)<TOL,(lid,'cash',casherr);assert abs(diverr)<TOL,(lid,'dividend',diverr);assert qty[lid]==l['qty'],(lid,'qty',qty[lid],l['qty'])
 layerqa.append(dict(round_id=layer_round[lid],layer=lid,sid=l['sid'],kind=l['kind'],opened=l['opened'],closed=l['closed'],end_qty=qty[lid],trade_net_cash=cash[lid],dividend_accrual=div[lid],old_layer_cash=l['cash'],old_layer_dividend=l['dividend'],cash_error=casherr,dividend_error=diverr))
assert len(rounds)==len(old)==2693
of={int(r['first_layer']):r for r in old.to_dict('records')};maxpnlerr=0
for r in rounds:
 ids=r['layer_ids'];l=ls[r['first_layer']];f=of[r['first_layer']];assert f['sid']==r['sid'] and f['entry_day']==r['entry_day'];assert f['layers']==len(ids)
 close=max(ls[k]['closed']for k in ids)if all(ls[k]['closed']for k in ids)else None;assert close==r['closed_at'];assert bool(f['closed'])==bool(close)
 r['closed']=close is not None;r['closed_in_entry_year']=bool(close and close[:4]==r['entry_day'][:4]);r['cross_year']=bool(close and not r['closed_in_entry_year']);r['year']=int(r['entry_day'][:4]);r['layers']=len(ids)
 r['round_trade_cash']=sum((cash[k]for k in ids),Z);r['round_dividend_accrual']=sum((div[k]for k in ids),Z);r['round_pnl']=r['round_trade_cash']+r['round_dividend_accrual']if close else None
 r['round_cost']=sum((D(buys[k]['gross_cny'])+D(buys[k]['fees_cny'])for k in ids),Z)
 r['round_return_on_cumulative_cost']=float(r['round_pnl']/r['round_cost'])if close else None;r['old_csv_pnl_error']=float(r['round_pnl'])-f['round_pnl']if close else None
 if close:maxpnlerr=max(maxpnlerr,abs(r['old_csv_pnl_error']));assert abs(r['old_csv_pnl_error'])<1e-7
 r['sell_reasons']='|'.join(sorted(r['sell_reasons']));r['layer_ids']='|'.join(map(str,ids));r['source_status']='ORIGINAL_LEDGER_AND_MANIFEST';r['financial_status']='OLD_PROXY_ONLY_NOT_NET80_CERTIFIED';r['real_tradability']='UNKNOWN'
 di=decisions[(r['signal_day'],r['sid'],r['first_kind'])];r['decision_CP1_id']=di.get('CP1_id');r['original_PVR_score']=di.get('PVR_score');r['sector']=x['metadata'][str(r['first_layer'])]['sector']
print('LEDGER_QA_PASS',len(rounds),len(ls),len(traces),maxpnlerr,flush=True)
# Read original native facts and CP receipts. No canonical data is consulted.
by=defaultdict(list)
for r in rounds:by[r['sid']].append(r)
market_events=[];sourceqa=[];cp_trace_rows=[];historyrows=[];decision_days=pd.DatetimeIndex([d['at'][:10]for d in x['decisions']]);history_fields={}
for no,(sid,rr)in enumerate(sorted(by.items())):
 m=manifest[sid];q=para(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]).loc[:END];c=para(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']]).loc[:END];assert q.index.equals(c.index)and q.index.is_unique and q.index.is_monotonic_increasing
 receipts={}
 for p,h in union_refs[sid]+[(m['refs']['receipts'],m['output_sha256'][m['refs']['receipts']])]:
  for z in read(p,h):
   d=z['confirmed_day']
   if '2022-01-01'<=d<=END:assert d not in receipts;receipts[d]=z
 expected=set(c.loc['2022-01-01':].index[c.loc['2022-01-01':].receipt.eq(True)].strftime('%Y-%m-%d'));assert set(receipts)==expected,(sid,'CP dates')
 active=False;key=None;start=None;known=False;ibn=cpn=0;prev_i=None;prev_seg=None;rows={}
 for day,v in q.iterrows():
  d=day.strftime('%Y-%m-%d');i=v.i_target;sg=v.segment_id;on=pd.notna(i)and i>0;ib=v.i_buy;cp=c.at[day,'receipt'];ready=c.at[day,'ready']
  new=on and(not active or sg!=prev_seg)
  if new:
   start=d;key=f'{sid}|{sg}|{d}';known=prev_i==0 and sg==prev_seg;ibn=cpn=0
  if on:
   if pd.notna(ib)and bool(ib):ibn+=1
   if pd.notna(cp)and bool(cp):cpn+=1
  else:key=None;start=None;known=False;ibn=cpn=0
  row=dict(day=d,i_target=int(i)if pd.notna(i)else None,i_buy=bool(ib)if pd.notna(ib)else None,cp_receipt=bool(cp)if pd.notna(cp)else None,cp_ready=bool(ready)if pd.notna(ready)else None,i_key=key,i_start_day=start,i_start_observed_0to1=bool(known),market_i_buy_ordinal=ibn if on and known else None,market_cp_ordinal=cpn if on and known else None)
  if not on:row['market_i_buy_class']='OUTSIDE_I';row['market_cp_class']='OUTSIDE_I'
  else:
   row['market_i_buy_class']='NON_I_BUY_DAY'if pd.notna(ib)and not bool(ib)else 'UNKNOWN'if pd.isna(ib)or not known else 'FIRST_I_BUY'if ibn==1 else 'LATER_I_BUY'
   row['market_cp_class']='NO_CP_RECEIPT_DAY'if pd.notna(cp)and not bool(cp)else 'UNKNOWN'if pd.isna(cp)or not known else 'FIRST_CP_RECEIPT'if cpn==1 else 'LATER_CP_RECEIPT'
  if d in receipts:
   cr=receipts[d];row['canonical_CP1_id']=cr['receipt_id'];row['cp_trace_unknown_n']=len(cr.get('trace_unknown',[]));row['cp_previous_market_receipt_id']=cr.get('previous_market_receipt_id');row['cp_formation_start_exclusive']=cr['formation_start_exclusive'];row['cp_formation_end_inclusive']=cr['formation_end_inclusive']
  else:row['canonical_CP1_id']=None;row['cp_trace_unknown_n']=None;row['cp_previous_market_receipt_id']=None
  rows[d]=row;active=on;prev_i=i;prev_seg=sg
 selectedkeys=set()
 for r in sorted(rr,key=lambda v:(v['entry_at'],v['first_layer'])):
  row=rows.get(r['signal_day']);assert row is not None,(sid,r['signal_day']);r.update({k:v for k,v in row.items()if k!='day'});selectedkeys.add(r['i_key'])
  if r['decision_CP1_id']:assert r['canonical_CP1_id']==r['decision_CP1_id'],(sid,r['signal_day'],'CP id')
  if r['first_kind']=='add':assert r['cp_receipt'] and r['canonical_CP1_id']
  lo=pd.Timestamp(r['entry_day']);hi=pd.Timestamp(r['closed_day']or END);helddays=decision_days[(decision_days>=lo)&(decision_days<=hi)];v=q.reindex(helddays)
  r['held_source_absent_days']=int((~helddays.isin(q.index)).sum());r['held_raw_close_bad_days']=int((~np.isfinite(v.raw_close)|v.raw_close.le(0)).sum());r['held_factor_bad_days']=int((~np.isfinite(v.factor)|v.factor.le(0)).sum());r['equity_entitlement_status']='OLD_ACCRUAL_PROXY_INDEPENDENT_ENTITLEMENT_UNCERTIFIED';r['source_fact_first_day']=str(q.index[0].date());r['actual_account_history_start']='2022-01-01'
 for d,row in rows.items():
  if row['i_key']in selectedkeys and row['i_key'] and(row['i_buy']or row['cp_receipt']or d==row['i_start_day']):market_events.append(dict(sid=sid,**row))
 sourceqa.append(dict(sid=sid,facts_path=m['refs']['facts'],CP1_path=m['refs']['CP1'],facts_start=str(q.index[0].date()),facts_end=str(q.index[-1].date()),facts_rows=len(q),receipt_union_rows=len(receipts),receipt_dates_exact=True))
 if(no+1)%200==0:print('SIGNALS',no+1,'elapsed',round(time.monotonic()-started,1),flush=True)
# Actual round order is observed account inventory history, not market signal order.
for sid,rr in by.items():
 seen=Counter();previous=None
 for r in sorted(rr,key=lambda v:(v['entry_at'],v['first_layer'])):
  key=r['i_key']
  if key and r['i_start_observed_0to1']:
   seen[key]+=1;r['actual_round_ordinal_in_i']=seen[key];r['actual_round_in_i_class']='FIRST_ACTUAL_ROUND_IN_I'if seen[key]==1 else 'REPEAT_ACTUAL_ROUND_IN_I'
  else:r['actual_round_ordinal_in_i']=None;r['actual_round_in_i_class']='UNKNOWN_I'
  if previous is None:r['reentry_class']='FIRST_OBSERVED_ACCOUNT_ROUND'
  elif key and previous['i_key']==key:r['reentry_class']='SAME_I_AFTER_FULL_EXIT'
  elif key and previous['i_key']and r['i_start_observed_0to1']:r['reentry_class']='NEW_I_AFTER_FULL_EXIT'
  else:r['reentry_class']='UNKNOWN_I_REENTRY'
  r['previous_round_id']=previous['round_id']if previous else None;r['previous_round_closed_day']=previous['closed_day']if previous else None
  previous=r
f=pd.DataFrame(rounds).sort_values(['entry_day','sid','first_layer']);f['round_pnl_numeric']=pd.to_numeric(f.round_pnl,errors='coerce')
# Group selection fixed before output. No outcome-dependent threshold or sorting.
groups=[]
def metric(g):
 closed=g[g.closed];p=closed.round_pnl_numeric
 return dict(n=len(g),closed_n=len(closed),unclosed_n=int((~g.closed).sum()),win_n=int(p.gt(0).sum()),loss_n=int(p.lt(0).sum()),zero_n=int(p.eq(0).sum()),win_rate=float(p.gt(0).mean())if len(p)else None,closed_proxy_pnl_cny=str(sum((D(v)for v in closed.round_pnl),Z)),closed_trade_cash_cny=str(sum((D(v)for v in closed.round_trade_cash),Z)),closed_dividend_accrual_cny=str(sum((D(v)for v in closed.round_dividend_accrual),Z)),mean_round_return=float(closed.round_return_on_cumulative_cost.mean())if len(closed)else None,cross_year_n=int(closed.cross_year.sum()),source_unknown_n=int(g.market_i_buy_class.eq('UNKNOWN').sum()),held_source_gap_rounds=int(g.held_source_absent_days.gt(0).sum()),NET80_certified_n=0)
windows=protocol['entry_windows']
for window,(lo,hi)in windows.items():
 g=f[f.entry_day.between(lo,hi)];groups.append(dict(window=window,dimension='ALL',value='ALL',**metric(g)))
 dims=[['market_i_buy_class'],['market_cp_class'],['actual_round_in_i_class'],['reentry_class'],['first_kind'],['first_reason'],['market_i_buy_class','first_kind'],['market_cp_class','first_kind'],['actual_round_in_i_class','market_i_buy_class'],['actual_round_in_i_class','market_cp_class'],['market_i_buy_class','market_cp_class']]
 for dim in dims:
  for val,v in g.groupby(dim,dropna=False,sort=True):
   if not isinstance(val,tuple):val=(val,)
   groups.append(dict(window=window,dimension=' x '.join(dim),value=' | '.join(map(str,val)),**metric(v)))
# Samples chosen by chronology, one per requested category; no PnL sorting.
samples=[]
for window,(lo,hi)in windows.items():
 g=f[f.entry_day.between(lo,hi)]
 for dim in ['market_i_buy_class','market_cp_class','actual_round_in_i_class','reentry_class','first_kind']:
  for val,v in g.groupby(dim,sort=True):samples.append(dict(sample_window=window,sample_dimension=dim,sample_value=val,**v.iloc[0].to_dict()))
summary=dict(status='OLD_PROXY_AUDIT_COMPLETE_NOT_NET80_CERTIFIED',management_end=END,account_runs=0,indicator_runs=0,new_trades=0,existing_rounds=len(f),existing_layers=len(ls),trade_count=len(x['trades']),layer_allocated_trade_rows=len(traces),all_round_identity=True,max_old_csv_pnl_error=maxpnlerr,max_layer_cash_error=max(abs(D(z['cash_error']))for z in layerqa),max_layer_dividend_error=max(abs(D(z['dividend_error']))for z in layerqa),all_layer_final_quantities_exact=True,original_receipt_dates_and_consumed_ids_exact=True,account_open_rounds=int((~f.closed).sum()),signal_I_unknown_rounds=int(f.market_i_buy_class.eq('UNKNOWN').sum()),signal_outside_I_rounds=int(f.market_i_buy_class.eq('OUTSIDE_I').sum()),partial_sells_while_stock_held=int(f.partial_sell_while_stock_held_n.sum()),mobile_exits_while_core_held=int(f.mobile_exit_while_core_held_n.sum()),dividend_accrual_events=sum(z['kind']=='dividend_accrual'for z in x['audit']),dividend_events_paid_at_unknown=sum(z['kind']=='dividend_accrual'and z['receivable'].get('paid_at')is None for z in x['audit']),split_layer_allocation_rows=len(split_alloc),actual_split_events=sum(z['kind'] in ['split','split_fraction_floor_proxy'] for z in x['audit']),observed_source_gap_rounds=int(f.held_source_absent_days.gt(0).sum()),fixed_universe_n=1709,PIT=False,real_tradability_certified=False,NET80_financially_certified=False,windows=[g for g in groups if g['dimension']=='ALL'],seconds=round(time.monotonic()-started,2))
f=f.drop(columns=['round_pnl_numeric']);csv('ALL_PVR_ROUNDS.csv',f);csv('GROUPED_OUTCOMES.csv',groups);csv('LAYER_LEDGER_RECONCILIATION.csv',layerqa);csv('ROUND_TRADE_ALLOCATIONS.csv',traces);csv('CORPORATE_ACTION_ALLOCATIONS.csv',actions);csv('SPLIT_LAYER_ALLOCATIONS.csv',split_alloc);csv('MARKET_I_SIGNAL_HISTORY.csv',market_events);csv('ORIGINAL_SOURCE_QA.csv',sourceqa);csv('CHRONOLOGICAL_SAMPLES.csv',samples);csv('OPEN_ROUNDS.csv',f[~f.closed]);csv('CROSS_YEAR_ROUNDS.csv',f[f.cross_year]);dump('SUMMARY_QA.json',summary);dump('SOURCE_SHA256.json',sources)
lines=['# 旧 PVR 连续消费者 I 内首 / 重复首仓核验','',f'统一管理终点：{END}。只读取旧账，不运行消费者、指标或新交易。冻结分组见 FROZEN_PROTOCOL.json。','', '## 全部完整回合结果（元）']
for g in groups:
 if g['dimension']=='ALL':lines.append(f"- {g['window']}：{g['n']} 回合，已闭 {g['closed_n']}，未闭 {g['unclosed_n']}，胜率 {g['win_rate']:.2%}，旧 proxy 净额 {float(g['closed_proxy_pnl_cny']):,.2f}，跨年闭仓 {g['cross_year_n']}。")
lines+=['','## 口径与边界','- 0→0 按实际成交股数重建，逐层买入净现金、卖出分配、拆股股数、红利应计与原 layer 对齐；不是把 mobile 退出当整只股票退出。','- I 从原始 facts 全前史同 source segment 的已观测 0→1 起算；market_i_buy_ordinal 和 market_cp_ordinal 统计市场事件，actual_round_ordinal_in_i 单独统计已成交股票完整回合。','- NON_I_BUY_DAY 与 NO_CP_RECEIPT_DAY 各自独立；add 的原 canonical receipt ID 已逐一对齐。只读原 CP receipts union，不重新生成 receipt。','- FIRST_ACTUAL_ROUND_IN_I 只说明 2022-01-01 账户成立后的首次实际回合，不宣称此前市场没有信号或其他账户没交易。','- 2022 全年和 2024 全年、2024-09 至 12 均用 2026-05-15 管理终点，2022 不再限定当年末已闭。','- round_pnl 是旧账买卖净现金 + 应计红利，不是已到账现金。241 项原红利应计事件的 paid_at 均未认证；原账含权益假设、分数股向下取整 proxy、非按比例定增 proxy。','- 原始持有日 facts 缺行/无效价另列，不冒充已证明逐日 raw-mark 可得，也不把未知补为 0。此次没有新 NET80 同等独立权益、停复牌、真实可成交性全审计，因此所有回合 financial_status 均为 OLD_PROXY_ONLY_NOT_NET80_CERTIFIED。','- 原账户是未来筛定 1709 标的固定池，非 PIT。所有胜率/净额仅是已消费历史描述，不是筛选后新账或因果收益。','','## 文件','- ALL_PVR_ROUNDS.csv：完整回合、市场 I/CP 序号、实际回合序号、首层种类/真实原因、跨年和未知字段。','- GROUPED_OUTCOMES.csv：预先冻结的全部分层；未闭和未知独立。','- ROUND_TRADE_ALLOCATIONS.csv / LAYER_LEDGER_RECONCILIATION.csv：每一笔交易到 layer / 回合的账桥。','- CORPORATE_ACTION_ALLOCATIONS.csv / SPLIT_LAYER_ALLOCATIONS.csv：原权益应计与数量核对，非独立权益真实性认证。','- MARKET_I_SIGNAL_HISTORY.csv：涉及 I 的完整市场事件序列，包含窗口前史。','- CHRONOLOGICAL_SAMPLES.csv：每类按时间选首例，未按金额选例。','- SOURCE_SHA256.json / SUMMARY_QA.json：可复核源 hash 与 QA。']
with (O/'READOUT.md').open('x')as h:h.write('\n'.join(lines)+'\n')
dump('OUTPUT_SHA256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()})
print(json.dumps(clean(summary),ensure_ascii=False),flush=True)
print(pd.DataFrame(groups).query("dimension in ['market_i_buy_class','market_cp_class','actual_round_in_i_class','first_kind']").to_string(index=False),flush=True)
