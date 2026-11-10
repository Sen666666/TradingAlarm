"""Pure branch/source checks; optional native CLASS build, no Account init."""
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import datetime
import argparse,ast,copy,hashlib,json,sys
import mobile_authorization_adapter as M
O=Path(__file__).parent;AT=datetime.fromisoformat('2022-12-01T15:10:00+08:00')
def sample(r=-.1,c=9,ema=10,ready_R=True,ready_P=True):
 return dict(day='2022-12-01',ready_R=ready_R,ready_P=ready_P,close=c,EMA20=ema if ready_P else None,RS20=r if ready_R else None,
  sector='SEC',source_segment=0,source_max_day='2022-12-01',anchor_day='2022-11-03' if ready_R else None,unknown_reason=None)
class Provider:
 manifest_sha256='0'*64
 def __init__(self,q=None):self.q=q if q is not None else sample();self.calls=0
 def at(self,sid,at):self.calls+=1;return self.q
class AccountStub:
 def __init__(self,pending=(),core_only=False):
  self.label='B';self.risk_state={'on':True};self.sell_layers={'S':set(pending)};self.calls=[]
  self.layers=[dict(id=1,kind='core',qty=100)]+([] if core_only else [dict(id=2,kind='add',qty=100),dict(id=3,kind='add',qty=200)])
  self.jmeta={1:dict(role='core'),2:dict(role='mobile'),3:dict(role='mobile')};self.old_order_created_at='2022-11-30 CLOSE'
 def live(self,sid):return self.layers
 def sell(self,sid,clock,quote,ids,reason):self.calls.append((tuple(ids),reason));self.sell_layers[sid].update(ids)
 def cancel_buy(self,*args):raise AssertionError('Overlay must never cancel existing native obligations')
class Hooks(M.MobileHooks):
 mobile_overlay_provider=Provider()
 def __init__(self,arm='JOINT'):self.mobile_overlay_arm=arm;self.mobile_overlay_log=[];self.sector_by_sid={'S':'SEC'};self.funding=[]
checks=[];cases=0
for r in [-.1,0,.1]:
 for c in [9,10,11]:
  for rr,pp in [(False,False),(False,True),(True,False),(True,True)]:
   q=sample(r,c,10,rr,pp)
   for arm in M.ARMS:
    actual=M.predicate(q,arm)['denies_mobile']
    expected=False if arm=='BASE' else rr and r<=0 if arm=='R_ONLY' else pp and c<10 if arm=='P_ONLY' else rr and pp and r<=0 and c<10
    assert actual==expected;(cases:=cases+1)
checks.append('144_truth_cases_AND_not_OR_RS_equality_weak_price_equality_not_weak_unready_keeps_native')
row=NS(close=9,segment_id=0,i_target=True);Hooks.mobile_overlay_provider=Provider(sample())
h=Hooks();a=AccountStub(pending=[3]);before=copy.deepcopy(a.layers)
assert h._mobile_authorization_exit(a,'S',AT,row,None,None)
assert a.calls==[((2,),'mobile_authorization_JOINT')] and a.layers==before and a.old_order_created_at=='2022-11-30 CLOSE'
assert h.mobile_overlay_log[-1]['prior_pending_layer_ids']==[3]
assert not h._mobile_authorization_exit(a,'S',AT,row,None,None) and len(a.calls)==1
checks.append('Only_unlocked_role_mobile_targeted_CORE_and_prior_CP_reason_clock_preserved_no_repeat_sell')
provider=Provider(sample());Hooks.mobile_overlay_provider=provider;h=Hooks();a=AccountStub(core_only=True)
assert not h._mobile_authorization_exit(a,'S',AT,row,None,None) and provider.calls==0 and not a.calls
checks.append('CORE_only_hold_does_not_even_request_context')
Hooks.mobile_overlay_provider=Provider(sample());h=Hooks();a=AccountStub()
assert not h._mobile_role_allowed(a,'S',AT,row,{'receipt_id':'fresh_native_CP'})
assert len(h.funding)==1 and h.funding[0]['role']=='mobile'
Hooks.mobile_overlay_provider.q['RS20']=1
assert h._mobile_role_allowed(a,'S',AT,row,{'receipt_id':'new_fresh_native_CP'})
assert h.mobile_overlay_log[0]['context']['RS20']==-.1,'historical log alias mutated'
checks.append('No_permission_latch_fresh_CP_can_compete_after_false_and_logs_deepcopy')
for q in [sample(ready_R=False,ready_P=False),dict(sample(ready_R=False,ready_P=False),sector=None,source_max_day=None,close=None,source_segment=None)]:
 Hooks.mobile_overlay_provider=Provider(q);h=Hooks();a=AccountStub(pending=[2]);state=copy.deepcopy(a.sell_layers)
 assert not h._mobile_authorization_exit(a,'S',AT,row,None,None)
 assert h._mobile_role_allowed(a,'S',AT,row,{'receipt_id':'fresh_native_CP'}) and a.sell_layers==state and not a.calls
checks.append('Unknown_including_missing_current_source_sectorNone_keeps_native_and_never_unlocks_pending')
for delta in [dict(day='2022-11-30'),dict(source_max_day='2099-01-01'),dict(close=8),dict(source_segment=1),dict(sector='wrong')]:
 try:M.provider_value(Provider(dict(sample(),**delta)),'S',AT,row,'SEC')
 except AssertionError:pass
 else:raise AssertionError('bad provider accepted')
checks.append('Known_context_wrong_day_future_price_segment_sector_refused')
old,new=M.patched_planning_source();ast.parse(new)
held="   self._mobile_authorization_exit(a,sid,at,row,clock,quote)\n"
role="    if role=='mobile' and not self._mobile_role_allowed(a,sid,at,self.facts.row(sid,at),cpr):continue\n"
assert new.replace(held,'').replace(role,'')==old
assert new.index("if not a.risk_state['on']")<new.index("if D(str(row.close))<=x['floor']")<new.index("if cp is not None and bool(cp.receipt)")<new.index('self._mobile_authorization_exit(')<new.index('a.sync(at);self.industry(a,at)')
assert new.index("if sid in a.exits:why.append('exit_pending')")<new.index('for role in roles:')<new.index('self._mobile_role_allowed(')<new.index('a.pending.append(i)')
assert "self.facts.row(sid,at),cpr" in role
checks.append('Exactly_two_source_insertions_hard_exit_order_ratchet_entry_Q_receipt_barriers_and_nonmobile_body_unchanged_correct_sid_row')
for name,body in [('DERIVED_PLANNING_DRAFT.py',new),('PLANNING_PATCH_DRAFT.diff',M.source_patch_diff())]:
 with (O/name).open('x') as f:f.write(body)
p=argparse.ArgumentParser();p.add_argument('--build-native-class',action='store_true');args=p.parse_args()
build=None
if args.build_native_class:
 sys.path.insert(0,'/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility');import native_adapter as A
 sys.path.insert(0,str(O.parent));from context_provider import ContextProvider
 provider=ContextProvider();cls=M.build_runner_class(A,provider,'JOINT')
 assert issubclass(cls,A.Runner) and cls.opening is A.J.Runner.opening and cls.route is A.P.ROUTES[True]
 build=dict(status='NATIVE_CLASS_BUILT_NOT_INSTANTIATED',arm='JOINT',provider_manifest_sha256=provider.manifest_sha256,native_accounts_created=0,native_events=0)
result=dict(status='PASS_SOURCE_AND_PURE_BRANCH_ONLY',truth_cases=cases,checks=checks,native_class_build=build,native_accounts_created=0,native_OPEN_events=0,native_CLOSE_events=0,
 new_financial_paths=0,limits='Not a native prefix/restart or full account validation; root must freeze provider/domain and perform its execution gates.',
 source_sha256={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in [Path(M.__file__),Path(__file__),M.NATIVE_PLANNING,O.parent/'context_provider.py']})
with (O/'SOURCE_AND_BRANCH_CHECKS.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
