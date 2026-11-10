"""Meaningful policy/patch checks only. Zero native Account/event/run calls."""
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import datetime, timedelta
from decimal import Decimal as D
import json, hashlib, pickle
import pandas as pd
import trend_exit_adapter as M

O=Path(__file__).resolve().parent
CAL=['2024-01-02','2024-01-03','2024-01-04','2024-01-05','2024-01-08','2024-01-09','2024-01-10','2024-01-11','2024-01-12','2024-01-15','2024-01-16','2024-01-17']
AT=lambda i:datetime.fromisoformat(CAL[i]+'T15:10:00+08:00')
def q(close=10,line=9,status='READY',day=CAL[0]):
 return dict(status=status,day=day,causal_close=close,line=line,source_segment=0,source_max_day=day,unknown_reason='fixture_unknown' if status=='UNKNOWN' else None)
CHECKS=[]
def check(name, fn):
 fn();CHECKS.append(name)
def call(c,i=0,I=False,close=10,line=9,status='READY',ref=8,cores=None,pending=False):
 return c.decide('B','S',AT(i),I,q(close,line,status,CAL[i]),ref,cores or {1:8},exit_pending=pending)

def early():
 for ind in M.INDICATORS:
  c=M.ExitController('EARLY_'+ind,CAL)
  assert call(c,I=True,close=10,line=11)['request_reason']=='trend_early_'+ind
  assert call(c,I=False,close=12,line=11)['request_reason']=='I_structure_exit'
  assert call(c,I=True,close=10,line=10)['request_reason'] is None
  assert call(c,I=True,status='UNKNOWN',line=None)['request_reason'] is None
  assert call(c,I=False,status='UNKNOWN',line=None)['request_reason']=='I_structure_exit'
  assert not c.state
check('four_early_OR_original_I_equality_and_unknown_fallback',early)

def sixgrace():
 for ind in ('EMA20','EMA60'):
  for h in (3,5,10):
   c=M.ExitController(f'GRACE_{ind}_H{h}',CAL)
   first=call(c);assert first['hold_only'] and first['request_reason'] is None
   state=pickle.loads(pickle.dumps(c.state))
   for i in range(1,h):
    x=call(c,i=i,I=True);assert x['hold_only'] and x['request_reason'] is None
    assert c.state['B|S']['start_day']==CAL[0]
   assert call(c,i=h,I=True)['request_reason']==f'grace_deadline_{ind}_H{h}'
   assert call(c,i=h+1,I=True,close=20)['request_reason']==f'grace_deadline_{ind}_H{h}'
   assert c.state['B|S']['start_day']==state['B|S']['start_day']
check('six_grace_fixed_native_calendar_deadlines_I_recovery_no_renewal',sixgrace)

def no_permission():
 for kw in [dict(status='UNKNOWN',line=None),dict(ref=None),dict(close=8,ref=8),dict(close=10,line=11),dict(pending=True)]:
  c=M.ExitController('GRACE_EMA20_H3',CAL)
  x=call(c,**kw);assert x['request_reason']=='I_structure_exit' and not c.state
check('unknown_equal_breached_original_I_EMA_break_existing_exit_no_grace',no_permission)

def locked():
 c=M.ExitController('GRACE_EMA20_H5',CAL);call(c)
 assert call(c,i=1,close=7)['request_reason']=='grace_original_I_reference_breach'
 assert call(c,i=2,I=True,close=20)['request_reason']=='grace_original_I_reference_breach'
 c.reconcile('B',set(),{'S'},set(),AT(2));assert c.active('B','S')
 c.reconcile('B',set(),set(),{'S'},AT(2));assert c.active('B','S')
 c.reconcile('B',set(),set(),set(),AT(2));assert not c.active('B','S')
 assert call(c,i=3)['state']['start_day']==CAL[3]
check('locked_request_survives_recovery_and_only_real_flat_rearms',locked)

def frozen():
 c=M.ExitController('GRACE_EMA60_H3',CAL);call(c,ref=8,cores={1:8.5})
 x=call(c,i=1,I=True,ref=1,cores={1:1})
 assert x['state']['frozen_original_I_reference']==8 and x['state']['frozen_core_references']=={'1':8.5}
 raw=pickle.dumps(c);cc=pickle.loads(raw)
 assert call(c,i=3,I=True)==call(cc,i=3,I=True)
check('frozen_original_references_and_policy_state_pickle_roundtrip',frozen)

class Provider:
 manifest_sha256='0'*64
 def __init__(self, value=None):self.value=value or q()
 def at(self,sid,at,indicator):return dict(self.value,day=str(at.date()))

def provider_checks():
 row=NS(close=10,segment_id=0)
 assert M.provider_value(Provider(), 'S', AT(0),'EMA20',row)['status']=='READY'
 for delta in [dict(causal_close=11),dict(source_segment=1),dict(source_max_day='2099-01-01')]:
  try:M.provider_value(Provider(dict(q(),**delta)),'S',AT(0),'EMA20',row)
  except AssertionError:pass
  else:raise AssertionError('bad provider accepted')
 un=M.provider_value(Provider(q(close=None,line=None,status='UNKNOWN')),'S',AT(0),'EMA20',row)
 assert un['status']=='UNKNOWN' and un['causal_close']==10
check('strict_provider_coordinate_segment_future_and_unknown_original_close',provider_checks)

class Account:
 def __init__(self,core_ref=8,mobile_floor=11):
  self.label='B';self.risk_state={'on':True};self.positions={'S':1};self.buys={'S':'original_pending'};self.exits={};self.sell_layers={};self.calls=[]
  self.layers=[dict(id=1,sid='S',kind='core',qty=100,floor=D(core_ref)),dict(id=2,sid='S',kind='add',qty=100,floor=D(mobile_floor))]
  self.jmeta={1:dict(last_core_line=str(core_ref)),2:dict(last_core_line='8')}
 def live(self,sid):return [x for x in self.layers if x['sid']==sid and x['qty']]
 def sell(self,sid,clock,quote,ids,reason):
  self.sell_layers.setdefault(sid,set()).update(ids);self.exits[sid]='native-order'
  self.calls.append(('sell',tuple(ids),reason))
 def cancel_buy(self,sid):
  if sid in self.buys:self.calls.append(('cancel_buy',sid));self.buys.pop(sid)

class Hooks(M.TrendHooks):
 trend_exit_provider=Provider()
 def __init__(self):
  self.trend_exit_controller=M.ExitController('GRACE_EMA20_H3',CAL)
  f=pd.DataFrame([dict(close=10,i_target=True,i_floor=9,segment_id=0),dict(close=10,i_target=False,i_floor=float('nan'),segment_id=0)],index=pd.to_datetime(['2024-01-01','2024-01-02']))
  self.facts=NS(f={'S':f})

def cp_stays():
 r=Hooks();a=Account();row=NS(i_target=False,close=10,segment_id=0)
 consumed=r._trend_manage_position(a,'S',AT(0),row,None,None)
 assert consumed is False,'native CP loop incorrectly skipped during Ioff grace'
 assert ('sell',(2,),'CP1_add_protection') in a.calls
 assert ('cancel_buy','S') in a.calls and 1 not in a.sell_layers['S']
 assert r._trend_bans_new(a,'S') and a.jmeta[1]['pending_I_exit_reference'] is True
 # Native original loop would skip pending mobile and retain/update other lines.
check('Ioff_grace_mobile_CP_old_floor_retained_and_all_new_capital_banned',cp_stays)

def core_guard():
 r=Hooks();a=Account(core_ref=10,mobile_floor=9);row=NS(i_target=False,close=10,segment_id=0)
 assert r._trend_manage_position(a,'S',AT(0),row,None,None) is False
 assert ('sell',(1,),'grace_core_reference_breach') in a.calls
 assert 2 not in a.sell_layers['S']
 assert r.trend_exit_controller.state['B|S']['frozen_core_references']['1']==10
check('new_explicit_grace_core_reference_guard_not_original_core_stop',core_guard)

def act_priority():
 r=Hooks();a=Account();a.risk_state['on']=False
 assert r._trend_manage_position(a,'S',AT(0),NS(i_target=False,close=10,segment_id=0),None,None)
 assert a.calls==[('sell',(1,2),'ACT_pause')]
 assert not r.trend_exit_controller.state
check('native_ACT_priority_no_grace_permission_or_execution_change',act_priority)

def same_segment():
 r=Hooks();row=NS(segment_id=1)
 assert M._last_valid_I_reference(r,'S',AT(0),row) is None
check('original_I_reference_never_crosses_source_segment',same_segment)

old,new=M.patched_planning_source()
assert "if D(str(row.close))<=x['floor']:a.sell" in new
assert "if event[sid].q is True and not held" in new
assert "if cpr and continuing[sid].q is True" in new
assert "self.facts.packet(at,'I')" in new
assert new.count("trend_grace_HOLD_ONLY")==1
CHECKS.append('three_exact_patch_edits_roundtrip_original_CP_entry_eligibility_body')

for name,value in [('PLANNING_PATCH.diff',M.source_patch_diff()),('DERIVED_PLANNING.py',new)]:
 with (O/name).open('x') as f:f.write(value)
result=dict(passed=True,checks=CHECKS,check_count=len(CHECKS),native_accounts_created=0,native_OPEN_events=0,native_CLOSE_events=0,new_financial_paths=0,indicator_models_computed=0,
 scope='Pure state/branch tests and exact source transformation. Not native prefix/restart/account validation.',
 source_SHA256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(M.__file__),Path(__file__),M.NATIVE_PLANNING]})
with (O/'PURE_ADAPTER_CHECKS.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
