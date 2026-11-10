from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
import copy,json,pickle
import pandas as pd
import test_unified as T
U=T.U;passed=[]
def check(name,f):f();passed.append(name)
def repair_exact():
 a=NS(market='market',facts='facts',layers=[],positions={},quantity=0)
 r=NS(source_freeze={'f':'h'},market='m',facts='f',accounts={'PVR':a},other=1)
 snapshot={'source_freeze':dict(r.source_freeze),'runner':{'source_freeze':dict(r.source_freeze),'other':1},'accounts':{'PVR':dict(layers=[],positions={},quantity=0)}}
 # Simulate the exact native first-fill lazy fields, not arbitrary repair.
 a.layers=[dict(qty=100)];a.positions={'X':100};a._ix={'X':a.layers};a._ixn=1;a._buy_filling=None;a._deferred_buy_cancels=[]
 removed=U.prune_restore_keys(r,snapshot)
 assert set(removed['accounts']['PVR'])=={'_ix','_ixn','_buy_filling','_deferred_buy_cancels'} and not removed['runner']
 r.__dict__.update(snapshot['runner']);a.__dict__.update(snapshot['accounts']['PVR'])
 assert {k:v for k,v in vars(a).items() if k not in ('market','facts')}==snapshot['accounts']['PVR']
 assert a.market=='market' and a.facts=='facts' and not hasattr(a,'_ix') and a.layers==[] and a.positions=={}
 # Unknown keys cannot be silently removed; source mismatch is checked first.
 a.unknown_cache=1
 try:U.prune_restore_keys(r,snapshot)
 except AssertionError:pass
 else:raise AssertionError('unknown key silently erased')
 assert a.unknown_cache==1
 del a.unknown_cache;a._ix={};bad=copy.deepcopy(snapshot);bad['source_freeze']={'f':'CHANGED'}
 try:U.prune_restore_keys(r,bad)
 except AssertionError:pass
 else:raise AssertionError('source mismatch allowed')
 assert hasattr(a,'_ix')
check('only_four_proven_lazy_keys_removed_freeze_first_unknown_fails',repair_exact)
def disk_evidence():
 pre=pickle.loads((U.HERE/'first_day_check/restart_gate/checkpoint.pkl').read_bytes())
 old=pickle.loads((U.BASE/'no_loss_add_v1/run_1200000/latest_checkpoint/checkpoint.pkl').read_bytes())
 assert set(old['accounts']['PVR'])-set(pre['accounts']['PVR'])=={'_ix','_ixn','_buy_filling','_deferred_buy_cancels'}
 assert not(set(old['runner'])-set(pre['runner']))
check('on_disk_empty_vs_baseline_end_proves_four_exact_keys',disk_evidence)
def unknown_audit():
 for variant in ('missing','nan','nonpositive','factor_nan','factor_zero','qty_zero','pending'):
  b=T.budget();T.lot(b,cost=8);a=T.FakeAccount(b);r=T.runner(b,a);a.promotion_candidates=[T.intent()]
  if variant=='missing':r.market.raw={'X':pd.DataFrame({'open':[]},index=pd.DatetimeIndex([]))}
  else:r.market.raw={'X':pd.DataFrame({'open':[float('nan') if variant=='nan' else 0. if variant=='nonpositive' else 11.]},index=[pd.Timestamp(T.AT.date())])}
  if variant.startswith('factor'):r.facts.factor=lambda sid,at:D('NaN') if variant=='factor_nan' else D(0)
  if variant=='qty_zero':b.lots=[];a.layers=[];a.positions={}
  if variant=='pending':a.exits['X']=object()
  r.promote_open_candidates(a,T.AT)
  assert len(r.promotion_events)==1 and not r.promotion_events[0]['moved']
  expected={'missing':'missing_open','nan':'invalid_open','nonpositive':'invalid_open','factor_nan':'invalid_factor','factor_zero':'invalid_factor','qty_zero':'post_sell_qty_zero','pending':'real_buy_or_exit_pending'}[variant]
  assert r.promotion_events[0]['reason']==expected,(variant,r.promotion_events)
check('each_promotion_only_missing_invalid_or_blocked_candidate_audited',unknown_audit)
result=dict(passed=True,count=len(passed),tests=passed,implementation_sha256=U.source_hashes()[str(Path(U.__file__))],scope='restart repair and promotion observability only; no account history execution')
Path(__file__).with_name('REPAIR_RESULTS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
