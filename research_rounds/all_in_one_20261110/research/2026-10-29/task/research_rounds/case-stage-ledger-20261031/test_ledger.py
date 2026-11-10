"""Actual original ledger role/quantity tests; not v2 budget acceptance."""
import wire as W
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from dataclasses import replace
import math,time,json
T=W.load('case_stage_original_ledger_test_helpers',W.RR/'rs-h1-execution-20261025/code/test_sector_account.py');D=W.D;BASE=T.T;out=[]
market=SimpleNamespace(protocol={'fractional_split_policy':'floor_position_fraction_writeoff'})
facts=SimpleNamespace(factor=lambda *_:D(1),floor=lambda *_:D(8),structure_lookup={})
def account():return W.CaseAccount('L0',market,facts,False)
def meta(kind='add',sid='A',floor=9,budget=4000,cap=400,at=BASE,receipt='cp1'):
 q=T.quote(sid,price=10,fees=T.MINIMUM);return dict(sid=sid,kind=kind,quote=q,clock=T.admission.Clock(at,at+timedelta(days=1),at.date()),floor=D(str(floor)),budget=D(budget),cap=cap,epoch=(0,1),reason='fixture_mobile' if kind=='add' else 'fixture_core',score=None,weight=1.,group=0,risk_budget=D(2500),receipt_id=receipt)
def window(day=1,price=10,capacity=10**8,at=None):
 at=at or BASE+timedelta(days=day);return T.window(at=at,price=price,capacity=capacity,fees=T.MINIMUM,eid='A|'+at.isoformat(),cash_due_at=at)
def reserve_once(a,i,q,p=D(10)):
 rid=i['receipt_id']
 if rid in a.mobile_CP1_consumed:raise ValueError('receipt already consumed across all routes')
 # Quantity/route selected before this irreversible receipt consumption.
 if q<=0 or q>i['cap']:raise ValueError('quantity not legally funded')
 oid=a.reserve_quantity(i,q,p,T.MINIMUM,i['clock'].earliest_execution_at);a.mobile_CP1_consumed.add(rid);return oid
def case(n,fn):
 detail=fn();out.append(dict(name=n,passed=True,actual=detail));print(n,'PASS',flush=True)
def mobile_no_core_lock():
 a=account();a.core_epoch['A']=(0,1);i=meta();reserve_once(a,i,400);r=a.fill_buy('A',window());assert r.shares==400 and a.live('A')[0]['kind']=='add' and a.core_epoch['A']==(0,1);assert a.available==D(995995);a.check();return dict(shares=400,fee=str(r.fees_cny),core_lock_unchanged=True,ledger_accepts_mobile_without_core=True)
case('mobile_real_fill_without_core_despite_core_lock',mobile_no_core_lock)
def partial_cancel():
 a=account();i=meta();reserve_once(a,i,400);r=a.fill_buy('A',window(capacity=100));assert r.shares==100 and a.quantity('A')==100 and 'A' in a.buys;before=a.available;a.cancel_buy('A');assert a.available>before and a.quantity('A')==100 and not a.buys
 try:reserve_once(a,i,400);raise AssertionError('old CP1 resurrected')
 except ValueError:pass
 a.check();return dict(actual_shares=100,unfilled_remainder_cancelled=True,used_receipt_not_refunded=True)
case('partial_fill_cancel_retains_actual_exposure_and_receipt',partial_cancel)
def real_reentry():
 a=account();i=meta();reserve_once(a,i,400);a.fill_buy('A',window());at=BASE+timedelta(days=2);clock=T.admission.Clock(at,at+timedelta(days=1),at.date());a.sell('A',clock,T.quote(price=9,fees=T.MINIMUM),[x['id'] for x in a.live('A')],'CP1_add_protection');r=a.fill_exit('A',window(day=3,price=9));a.settle_due(BASE+timedelta(days=3));assert r and not a.quantity('A')
 j=meta(at=BASE+timedelta(days=4),receipt='cp2');reserve_once(a,j,400);r=a.fill_buy('A',window(day=5));a.check();assert r and a.quantity('A')==400 and len(a.mobile_CP1_consumed)==2;return dict(fills=len(a.trades),new_receipt_reentry=True,structure_cash=sum((x['cash']+x['dividend'] for x in a.layers),D(0)).to_eng_string())
case('mobile_full_exit_and_fresh_CP1_reentry_real_ledger',real_reentry)
def sizing_core():
 i=meta(kind='core',floor=8,budget=100000,cap=10000);W.LR.resize_core(i,D(1000000),D(1));a=account();a.pending=[];v,why=W.LR.preview(i,D(10),D(1),T.RULE,T.MINIMUM);assert not why and v['maxq']>=100;q=v['maxq'];assert W.LR.protection_risk(q,v['price'],v['floor'],T.MINIMUM)<=D(2500);assert q*v['price']<=D(100000)
 return dict(core_quantity=q,risk=str(W.LR.protection_risk(q,v['price'],v['floor'],T.MINIMUM)),cap=str(i['budget']),original_risk_0_25_and_stock10=True)
case('original_core_risk_and_nominal_cap_quantity',sizing_core)
def mobile_2pct():
 i=meta(budget=20000,cap=2000);v,why=W.LR.preview(i,D(10),D(1),T.RULE,T.MINIMUM);assert not why and v['maxq']*v['price']<=D(20000);a=account();reserve_once(a,i,v['maxq'],v['price']);r=a.fill_buy('A',T.window(price=v['price'],at=BASE+timedelta(days=1),fees=T.MINIMUM,raw_open=D(10),cash_due_at=BASE+timedelta(days=1)));assert r.shares==v['maxq'];return dict(shares=r.shares,gross=str(r.gross_cny),fees=str(r.fees_cny),nominal_2pct=True)
case('mobile_2pct_target_original_fee_and_lot_preview',mobile_2pct)
def corp_actions():
 a=account();i=meta();reserve_once(a,i,400);a.fill_buy('A',window());at=BASE+timedelta(days=2);a.accrue_dividend(event_id='d',sid='A',currency='CNY',net_local=D(40),ex_at=at,paid_at=None,source_id='explicit',entitlement_basis='actual400');assert a.available==D(995995) and a.layers[0]['dividend']==40
 a.split(event_id='s',sid='A',ratio=D(2),at=at,new_shares_sellable_at=at+timedelta(days=1));a.check();assert a.quantity('A')==800 and a.layers[0]['qty']==800;return dict(shares=800,receivable=str(a.layers[0]['dividend']),cash_not_fabricated=True)
case('actual_dividend_split_layer_share_conservation',corp_actions)
W.save('LEDGER_ONLY_TESTS',dict(passed=True,tests=out,real_original_ledger=True,v2_budget_NOT_tested=True,route_and_grant_and_pool_tests_pending=True));print('LEDGER_ONLY_DONE',len(out),flush=True)
