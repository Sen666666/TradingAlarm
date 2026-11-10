"""Branch, priority and source checks. Zero native Account or financial runs."""
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import datetime
import json,hashlib
import trend_exit_adapter as M

O=Path(__file__).resolve().parent
AT=datetime.fromisoformat('2024-01-02T15:10:00+08:00')
def q(close=10,line=9,status='READY'):
 return dict(status=status,day='2024-01-02',causal_close=close,line=line,source_segment=0,source_max_day='2024-01-02',unknown_reason='fixture_unknown' if status=='UNKNOWN' else None)
class Provider:
 manifest_sha256='0'*64
 def __init__(self,v=None):self.v=v or q()
 def at(self,sid,at,indicator):return dict(self.v)
class Account:
 def __init__(self,pending=()):
  self.label='B';self.risk_state={'on':True};self.sell_layers={'S':set(pending)};self.calls=[]
  self.layers=[dict(id=1,kind='core',qty=100),dict(id=2,kind='add',qty=100)]
 def live(self,sid):return self.layers
 def sell(self,sid,clock,quote,ids,reason):
  self.calls.append((tuple(ids),reason));self.sell_layers['S'].update(ids)
class Hooks(M.EarlyHooks):
 trend_exit_provider=Provider()
 def __init__(self,ind):
  self.trend_exit_indicator=ind;self.trend_exit_arm='EARLY_'+ind;self.trend_exit_log=[]

checks=[]
for ind in M.INDICATORS:
 h=Hooks(ind);a=Account();Hooks.trend_exit_provider=Provider(q(10,11))
 assert h._trend_early_exit(a,'S',AT,NS(close=10,segment_id=0,i_target=True),None,None)
 assert a.calls==[((1,2),'trend_early_'+ind)]
 checks.append(ind+'_current_close_below_requests_original_native_sell')
 h=Hooks(ind);a=Account();Hooks.trend_exit_provider=Provider(q(10,10))
 assert not h._trend_early_exit(a,'S',AT,NS(close=10,segment_id=0,i_target=True),None,None) and not a.calls
 h=Hooks(ind);a=Account();Hooks.trend_exit_provider=Provider(q(None,None,'UNKNOWN'))
 assert not h._trend_early_exit(a,'S',AT,NS(close=10,segment_id=0,i_target=True),None,None) and not a.calls
checks.append('all_four_equality_retains_unknown_keeps_original_I_CP_behavior')
Hooks.trend_exit_provider=Provider(q(10,-1));h=Hooks('BOLL20_LOWER');a=Account()
assert not h._trend_early_exit(a,'S',AT,NS(close=10,segment_id=0,i_target=True),None,None) and not a.calls
checks.append('finite_zero_or_negative_Boll_lower_is_valid_no_extra_exit')

Hooks.trend_exit_provider=Provider(q(10,11));h=Hooks('EMA20');a=Account(pending=[2])
assert h._trend_early_exit(a,'S',AT,NS(close=10,segment_id=0,i_target=True),None,None)
assert a.calls==[((1,),'trend_early_EMA20')]
assert h.trend_exit_log[-1]['prior_pending_layer_ids']==[2]
checks.append('same_day_or_prior_CP_pending_mobile_reason_preserved_only_core_added')
h=Hooks('EMA20');a=Account(pending=[1,2])
assert not h._trend_early_exit(a,'S',AT,NS(close=10,segment_id=0,i_target=True),None,None) and not a.calls
checks.append('all_layers_already_exit_locked_no_duplicate_or_resurrection')

for delta in [dict(causal_close=11),dict(source_segment=1),dict(source_max_day='2099-01-01'),dict(day='2024-01-01')]:
 bad=dict(q(),**delta)
 try:M.provider_value(Provider(bad),'S',AT,'EMA20',NS(close=10,segment_id=0))
 except AssertionError:pass
 else:raise AssertionError('bad provider accepted')
checks.append('provider_wrong_close_segment_future_or_stale_day_rejected')

old,new=M.patched_planning_source()
hook='   self._trend_early_exit(a,sid,at,row,clock,quote)\n'
assert new.replace(hook,'')==old
assert old.count("if not a.risk_state['on'] or not bool(row.i_target):")==new.count("if not a.risk_state['on'] or not bool(row.i_target):")==1
assert new.index("if not a.risk_state['on']") < new.index("if D(str(row.close))<=x['floor']") < new.index('self._trend_early_exit(') < new.index('a.sync(at);self.industry(a,at)')
assert new.index("if cp is not None and bool(cp.receipt):x['floor']=max")<new.index('self._trend_early_exit(')
checks.append('one_insertion_only_original_ACT_I_CP_old_floor_ratchet_and_all_entry_body_exact')
assert set(M.ARMS)=={'BASELINE',*[f'EARLY_{x}' for x in M.INDICATORS]}
checks.append('grace_and_unbounded_replace_unavailable_from_active_API')

for n,v in [('PLANNING_PATCH.diff',M.source_patch_diff()),('DERIVED_PLANNING.py',new)]:
 with (O/n).open('x') as f:f.write(v)
result=dict(passed=True,checks=checks,check_count=len(checks),native_accounts_created=0,native_OPEN_events=0,native_CLOSE_events=0,new_financial_paths=0,indicator_models_computed=0,
 scope='Pure policy/priority checks and single source insertion, not native prefix/restart/account validation.',
 source_SHA256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(M.__file__),Path(__file__),M.NATIVE_PLANNING]})
with (O/'PURE_ADAPTER_CHECKS.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
