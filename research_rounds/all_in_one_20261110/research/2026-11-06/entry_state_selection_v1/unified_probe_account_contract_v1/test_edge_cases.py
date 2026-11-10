"""Extra adverse-state tests, separate from native two-day first-entry run."""
from pathlib import Path
import json,copy
from decimal import Decimal as D
from types import SimpleNamespace as NS
import pandas as pd
import test_unified as T
U=T.U;passed=[]
def check(name,f):f();passed.append(name)
def joint_snapshot_order():
 results=[]
 for order in [('A','B'),('B','A')]:
  b=T.budget();T.lot(b,'A',cost=8);T.lot(b,'B',cost=8);a=T.FakeAccount(b);r=T.runner(b,a)
  a.promotion_candidates=[T.intent(s) for s in order];r.market.raw={s:pd.DataFrame({'open':[11.]},index=[pd.Timestamp(T.AT.date())]) for s in order}
  seen=[];original=r.promote_candidate
  def observed(*args,**kwargs):
   assert all(x.pool=='probe' for x in b.lots),'mutated before every eligibility proof frozen'
   proof=original(*args,**kwargs);seen.append((args[1]['sid'],proof['reason'],proof['verdict']['net_profit']));return proof
  r.promote_candidate=observed;r.promote_open_candidates(a,T.AT)
  results.append((seen,[(x.stock,x.pool,x.qty,x.floor) for x in b.lots],b.cash,b.nav,b.resources(),b.resources(sector='S'),b.promotion_seen,b.consumed,b.audit,a.jmeta,r.promotion_events))
 assert results[0]==results[1]
check('every_proof_precedes_any_commit_reverse_queue_exact_state_and_audit',joint_snapshot_order)
def confirmed_cannot_skip():
 for attempt,pool in [('old','probe'),('a','probe'),('old','confirmed')]:
  b=T.budget();T.lot(b,cost=8,attempt=attempt,pool=pool);a=T.FakeAccount(b);r=T.runner(b,a);out,_=r.route(a,T.intent(),T.preview(),T.AT)
  assert not out or out[1]=='probe'
  assert not b.confirmed_stock_lot('X','S')
 b=T.budget();T.lot(b,cost=8);a=T.FakeAccount(b);r=T.runner(b,a);r.promote_candidate(a,T.intent(),D(11),T.AT);assert b.confirmed_stock_lot('X','S')
 out,_=r.route(a,T.intent(),T.preview(),T.AT);assert out and out[1]=='confirmed'
check('confirmed_requires_current_attempt_explicit_real_confirmed_layer',confirmed_cannot_skip)
def fresh_reuse():
 b=T.budget();T.lot(b,cost=8);a=T.FakeAccount(b);r=T.runner(b,a);i=T.intent();first=r.promote_candidate(a,i,D(11),T.AT);assert first['moved']
 # No invented second promotion, even if same CP is presented again.
 r.promote_candidate(a,i,D(11),T.AT);assert len([x for x in r.promotion_events if x['moved']])==1
 out,_=r.route(a,i,T.preview(),T.AT);assert out and i['CP1_id'] in b.consumed
 out,why=r.route(a,T.intent(),T.preview(),T.AT);assert not out and why=='no_fresh_stock_CP1'
check('promotion_receipt_dedup_but_native_buy_consumes_once',fresh_reuse)
def signal_risk_freeze():
 b=T.budget();a=T.FakeAccount(b);r=T.runner(b,a);r.opportunities=[];r.rank_mode='PVR_SLOT1';r.accounts={'PVR':a}
 i=T.intent();i.update(quote=NS(par_value=None,raw_price=D(100),quantity=T.RULE,fees=T.FEES),budget=D(24000),cap=200,floor=D(1),kind='add',rank=1)
 a.pending=[i];a.decisions=[{}]
 old=U.N.Runner.planning;U.N.Runner.planning=lambda *args:None
 try:r.planning(T.DEC)
 finally:U.N.Runner.planning=old
 assert i['cap']==0,'minimum risk > .25% at signal must not be revived by favorable OPEN'
 x,why=U.LR.preview(i,D(10),D(1),T.RULE,T.FEES);assert not x and why=='open_minimum_exceeds_frozen_contract'
check('signal_min_unit_risk_failure_not_rescued_by_lower_next_open',signal_risk_freeze)
def proposal_industry_arm():
 # Pure formulas only: shows why a separate arm is different; main stays ALL2%.
 nav=1200000.;confirmed=120000.;probe=0.;new=10000.;level_cap=.2
 main=confirmed+probe+new<=.02*nav
 proposed=(probe+new<=.02*nav and confirmed+probe+new<=level_cap*nav)
 assert not main and proposed
check('proposed_industry_split_formula_is_separate_unvalidated_arm',proposal_industry_arm)
result=dict(passed=True,count=len(passed),tests=passed,implementation_sha256=U.source_hashes()[str(Path(U.__file__))],scope='synthetic adverse state tests; proposed industry arm formulas only')
Path(__file__).with_name('EDGE_CASE_RESULTS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
