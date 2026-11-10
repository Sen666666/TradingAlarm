"""Private original-body compatibility for native stress multiplier Decimal1.5."""
from decimal import Decimal as D
from dataclasses import replace
from pathlib import Path
import inspect,textwrap,hashlib,sys
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'market_gross_admission_native_v1'))
import gross_adapter as C
J=C.J
NativeFeeSchedule=J.Account._fee.__globals__['FeeSchedule']
FastMarket=J.M.E.FastMarket
FrozenMarket=FastMarket.__mro__[1]

FEE_ORIGINAL=textwrap.dedent(inspect.getsource(NativeFeeSchedule.incremental))
FEE_DERIVED=FEE_ORIGINAL.replace('if multiplier not in (1, 2):',"if multiplier not in (1, D('1.5'), 2):")
assert FEE_DERIVED!=FEE_ORIGINAL and FEE_DERIVED.replace("if multiplier not in (1, D('1.5'), 2):",'if multiplier not in (1, 2):')==FEE_ORIGINAL
fee_env=dict(NativeFeeSchedule.incremental.__globals__,D=D)
exec(compile(FEE_DERIVED,str(O/'derived_fee_guard.py'),'exec'),fee_env)
class StressFeeSchedule(NativeFeeSchedule):
 incremental=fee_env['incremental']

BASE_ORIGINAL=textwrap.dedent(inspect.getsource(FrozenMarket.window))
BASE_DERIVED=BASE_ORIGINAL.replace("if cost_multiplier == 2 and policy['stress_slippage']:","if cost_multiplier != 1 and policy['stress_slippage']:").replace('slip *= 2','slip *= cost_multiplier')
assert BASE_DERIVED!=BASE_ORIGINAL
assert BASE_DERIVED.replace("if cost_multiplier != 1 and policy['stress_slippage']:","if cost_multiplier == 2 and policy['stress_slippage']:").replace('slip *= cost_multiplier','slip *= 2')==BASE_ORIGINAL
base_env=dict(FrozenMarket.window.__globals__)
exec(compile(BASE_DERIVED,str(O/'derived_native_stress_window.py'),'exec'),base_env)
reference_window=base_env['window']

FAST_ORIGINAL=textwrap.dedent(inspect.getsource(FastMarket.window))
FAST_DERIVED=FAST_ORIGINAL.replace("if cost_multiplier==2 and policy['stress_slippage']:slip*=2","if cost_multiplier!=1 and policy['stress_slippage']:slip*=cost_multiplier")
FAST_DERIVED=FAST_DERIVED.replace('super().window(sid,at,side,cost_multiplier)','_original_stress_reference(self,sid,at,side,cost_multiplier)')
assert FAST_DERIVED!=FAST_ORIGINAL
assert FAST_DERIVED.replace("if cost_multiplier!=1 and policy['stress_slippage']:slip*=cost_multiplier","if cost_multiplier==2 and policy['stress_slippage']:slip*=2").replace('_original_stress_reference(self,sid,at,side,cost_multiplier)','super().window(sid,at,side,cost_multiplier)')==FAST_ORIGINAL
fast_env=dict(FastMarket.window.__globals__,_original_stress_reference=reference_window)
exec(compile(FAST_DERIVED,str(O/'derived_fast_stress_window.py'),'exec'),fast_env)

class StressMarket(FastMarket):
 window=fast_env['window']
 def fees(self,sid,at):
  f=super().fees(sid,at)
  if not isinstance(f,StressFeeSchedule):f=StressFeeSchedule(f.schedule_id,f.components);self.fc[sid]=f
  return f
 def quote(self,sid,at):
  q=super().quote(sid,at)
  if q is not None and not isinstance(q.fees,StressFeeSchedule):
   q=replace(q,fees=StressFeeSchedule(q.fees.schedule_id,q.fees.components));self.qc[sid]=q
  return q

OPEN_ORIGINAL=textwrap.dedent(inspect.getsource(J.Runner.opening))
OPEN_DERIVED=OPEN_ORIGINAL.replace("self.market.window(sid,at,'sell',1)","self.market.window(sid,at,'sell',a.cost_multiplier)").replace("self.market.window(sid,at,'buy',1)","self.market.window(sid,at,'buy',a.cost_multiplier)")
assert OPEN_DERIVED.replace("self.market.window(sid,at,'sell',a.cost_multiplier)","self.market.window(sid,at,'sell',1)").replace("self.market.window(sid,at,'buy',a.cost_multiplier)","self.market.window(sid,at,'buy',1)")==OPEN_ORIGINAL and OPEN_DERIVED!=OPEN_ORIGINAL
open_env=dict(J.Runner.opening.__globals__)
exec(compile(OPEN_DERIVED,str(O/'derived_cost_opening.py'),'exec'),open_env)
cost_opening=open_env['opening']

def wrap_shared(shared):
 b,m,f=shared
 assert type(m)is FastMarket,'use original existing market, no new loader'
 m.__class__=StressMarket
 # Only derived quote/fee/window caches differ; source arrays/rules unchanged.
 m.cache_at=None;m.window_verified=set()
 return b,m,f

def source_receipt():
 return dict(original_fee_source=inspect.getsourcefile(NativeFeeSchedule),original_window_source=inspect.getsourcefile(FastMarket),fee_guard_only_extension=True,fee_rate_accrual_inherited_original=True,window_inverse_diff_exact=True,opening_only_actual_cost_argument_diff=True,stored_original_source_SHA256={str(Path(inspect.getsourcefile(x)).resolve()):hashlib.sha256(Path(inspect.getsourcefile(x)).read_bytes()).hexdigest()for x in(NativeFeeSchedule,FastMarket,FrozenMarket,J.Runner)})
