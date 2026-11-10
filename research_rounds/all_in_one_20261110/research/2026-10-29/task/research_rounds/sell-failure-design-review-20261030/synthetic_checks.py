"""Nine fixed behavior checks; no history, financial outcomes, or price feeds."""
from pathlib import Path
from math import exp,sqrt,isclose,nan,inf
import json,csv,time,hashlib
from minimal_boundary import BoundaryState

T=time.monotonic();O=Path(__file__).resolve().parent
assert not (O/'SYNTHETIC_RESULTS.json').exists(),'Preserve prior runs; do not overwrite'
rows=[];cases=[];P=100.;SIGMA=.02;B=P*exp(-sqrt(5)*SIGMA)
def start(case):
 s=BoundaryState(80.);add(case,s,close=P,event=-1,sigma=SIGMA);return s
def add(case,s,**kw):
 r=s.step(**kw);r['case']=case;rows.append(r);return r
def done(case,expected,actual):cases.append(dict(case=case,expected=expected,actual=actual,passed=True))

c='1_warning_then_flat';s=start(c)
for p in [100.,100.,100.]:add(c,s,close=p)
assert s.active and not s.exit_locked and s.requests==0 and s.boundary==B
done(c,'边界固定；横盘不触发、不按时间增加压力','B固定；0退出请求')

c='2_continuous_decline_cross_boundary';s=start(c)
for p in [98.,96.,95.]:add(c,s,close=p)
assert s.exit_locked and s.exit_reason=='warning_boundary' and s.exit_decision==4 and s.requests==1
done(c,'首次收盘<=B才锁定额外退出，下一合法时点执行','95首次穿B；第4观察锁定1次请求')

c='3_V_repair_without_crossing';s=start(c)
for p in [98.,96.,99.,100.]:add(c,s,close=p)
assert not s.exit_locked and s.active and s.boundary==B
done(c,'未穿B的V形不退出，也不凭价格修复自动抹掉边界','0请求；边界保留')

c='4_cross_then_repair_cannot_cancel';s=start(c);add(c,s,close=95.)
add(c,s,close=102.,event=1,updated_e0_floor=97.)
assert s.exit_locked and s.exit_reason=='warning_boundary' and s.exit_decision==2 and s.requests==1
done(c,'先穿B后反弹/正event不可取消退出或重复请求','原第2观察退出保持锁定；请求仍1次')

c='5_positive_event_floor_below_boundary';s=start(c)
r=add(c,s,close=99.,event=1,updated_e0_floor=90.)
assert s.active and not s.handed_off and not s.exit_locked and r['effective_stop_after']==B
done(c,'正event但新floor<B不能移交；有效保护仍max(floor,B)','floor=90<B；B仍生效')

c='6_safe_handoff_and_original_floor_priority';s=start(c)
r=add(c,s,close=100.,event=1,updated_e0_floor=96.5)
assert s.handed_off and not s.active and not s.exit_locked and r['effective_stop_after']==96.5 and r['effective_stop_after']>=r['effective_stop_before']
add(c,s,close=95.)
assert s.exit_locked and s.exit_reason=='original_floor' and s.requests==1
done(c,'floor>=B方可移交；以后原floor保护不弱于B','96.5安全接管；随后95由原floor退出')

c='7_repeat_warning_never_lowers_boundary';s=start(c)
add(c,s,close=97.,event=-1,sigma=.2)
assert s.boundary==B and s.warning_price==P and s.warning_sigma==SIGMA and s.active and s.repeat_warnings_ignored==1
add(c,s,close=95.)
assert s.exit_locked and s.exit_reason=='warning_boundary'
done(c,'重复警报不得改P/σ或下移B；仍按第一次边界检查','较低P/较大σ被忽略；仍在原B触发')

c='8_unknown_sigma_keep_original_protection';unknowns=[]
for sig in [None,nan,0.,-1.,inf]:
 s=BoundaryState(80.);add(c,s,close=100.,event=-1,sigma=sig)
 add(c,s,close=90.,event=-1,sigma=.02)
 assert s.unknown_scale and s.warning_seen and s.boundary is None and not s.active and not s.exit_locked
 add(c,s,close=79.)
 assert s.exit_locked and s.exit_reason=='original_floor';unknowns.append(str(sig))
done(c,'缺失/不可用首次σ标未知，不用后日尺度补；原floor继续工作','None/NaN/0/负/Inf均未知；79仍按原floor退出')

c='9_warning_day_shock_blind_spot';s=BoundaryState(80.)
add(c,s,close=200.);r=add(c,s,close=100.,event=-1,sigma=SIGMA)
assert not s.exit_locked and s.boundary==B and r['effective_stop_before']==80.
add(c,s,close=100.)
assert not s.exit_locked and s.requests==0
done(c,'警报当日冲击已发生；新边界不倒填到冲击之前','200到100当日不由新B提前退出；100生成B，之后横盘不触发')

with (O/'synthetic-trace.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with (O/'synthetic-expectations.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(cases[0]));w.writeheader();w.writerows(cases)
summary=dict(passed=True,cases=cases,case_count=len(cases),observations=len(rows),fixture=dict(warning_price=P,sigma=SIGMA,boundary=B,original_floor=80.),state_machine_only=True,native_E0_event_generator_tested=False,real_market_files_read=0,historical_trigger_checks=0,return_or_profit_tests=0,product_changes=0,models_or_parameter_search=0,seconds=time.monotonic()-T,sha256={n:hashlib.sha256((O/n).read_bytes()).hexdigest() for n in ['minimal_boundary.py','synthetic_checks.py','synthetic-trace.csv','synthetic-expectations.csv']})
(O/'SYNTHETIC_RESULTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False))
