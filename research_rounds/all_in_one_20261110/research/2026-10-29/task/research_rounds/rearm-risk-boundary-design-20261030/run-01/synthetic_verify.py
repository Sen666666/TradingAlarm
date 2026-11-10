"""Frozen v2 units and REAL original offline-ledger contract calls; no history/PnL."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import sys,json,csv,hashlib,time,importlib.util
from math import isclose
from risk_boundary_v2 import RiskBoundary,NegativeReceipt

T0=time.monotonic();O=Path(__file__).resolve().parent
assert not (O/'TEST_RESULTS.json').exists(),'Preserve prior run results'
ORIG=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=[O/'SPECIFICATION.txt',O/'risk_boundary_v2.py',Path(__file__),ORIG/'sector_account.py',ORIG/'test_sector_account.py',ORIG/'sector_stock_admission.py']
(O/'TEST_FREEZE.json').write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'before_test_execution':True,'no_historical_inputs':True,'sha256':{str(p):sha(p) for p in files}},ensure_ascii=False,indent=2))
tests=[];trace=[];execution=[]
def new(shares=100,pending=False):return RiskBoundary(cycle_id='synthetic-cycle',symbol='A',source_id='synthetic-source0',unit_id='economic-unit-A',shares=shares,e0_floor=80.,buy_pending=pending)
def neg(n,bar=None):return NegativeReceipt(f'A|source0|bar{n}|negative','A','synthetic-source0',n if bar is None else bar)
def step(case,c,bar,price,**kw):
 r=c.on_close(bar=bar,raw_close=price,factor=kw.pop('factor',1.),unit_id=kw.pop('unit_id','economic-unit-A'),**kw);r['case']=case;trace.append(r);return r
def armed(case):
 c=new();step(case,c,1,100.,negative=neg(1),sigma=.02);assert c.phase=='PROTECTED';return c
def passed(case,level,expected,actual):tests.append(dict(case=case,level=level,status='PASS',expected=expected,actual=actual))

case='handoff_newhigh_independent_warning_rearms';c=armed(case);old=c.boundary
step(case,c,2,105.,updated_floor=96.);assert c.phase=='OBSERVING'
step(case,c,3,120.);assert c.phase=='OBSERVING'
step(case,c,4,115.,negative=neg(4),sigma=.02)
assert c.phase=='PROTECTED' and c.episodes==2 and c.boundary>old and c.boundary>c.e0_floor
passed(case,'controller_unit','安全交接后仅后续新负收据再保护','交接→新高不武装→第4观察新收据建立第二轮B')

case='persistent_negative_state_is_not_new_receipt';c=armed(case);step(case,c,2,105.,updated_floor=96.)
for b in [3,4,5]:step(case,c,b,110.,direction_state=-1)
assert c.phase=='OBSERVING' and c.episodes==1
passed(case,'controller_unit','持续负方向状态不得造新收据','连续3观察direction=-1仍观察，保护轮数1')

case='same_day_handoff_and_duplicate_id_no_loop';c=armed(case)
step(case,c,2,105.,updated_floor=96.,negative=neg(2),sigma=.02);assert c.phase=='OBSERVING' and c.episodes==1
step(case,c,2,105.,negative=neg(2),sigma=.02);step(case,c,3,110.,negative=neg(2),sigma=.02)
assert c.phase=='OBSERVING' and c.episodes==1
step(case,c,4,110.,negative=neg(4),sigma=.02);b=c.boundary
step(case,c,4,110.,negative=neg(4),sigma=.2)
assert c.episodes==2 and c.boundary==b
passed(case,'controller_unit','同日不循环、重复ID不重播','交接日收据/同日重复/次日重播均未再武装；后续独立ID才激活')

case='handoff_and_dominated_candidate_never_weaken';c=armed(case);step(case,c,2,105.,updated_floor=96.)
r=step(case,c,3,100.,negative=neg(3),sigma=.1)
assert c.phase=='OBSERVING' and c.episodes==1 and r['protection_after']==96.
r=step(case,c,4,110.,negative=neg(4),sigma=.02)
assert c.phase=='PROTECTED' and r['protection_after']>=96.
passed(case,'controller_unit','B<=floor不激活；再保护不弱于旧保护','弱候选被原floor支配；后续强候选才激活，无保护下降')

case='active_boundary_does_not_reset_on_new_receipt';c=armed(case);b=c.boundary
step(case,c,2,99.,negative=neg(2),sigma=.5)
assert c.phase=='PROTECTED' and c.boundary==b and c.episodes==1
passed(case,'controller_unit','保护仍有效时不得用新警报下移/重设','新收据已消费，B完全不变')

case='unknown_event_scale_price_separate';c=new()
step(case,c,0,100.,event_feed_known=False)
step(case,c,1,100.,negative=neg(1),sigma=None)
step(case,c,2,100.,negative=neg(1),sigma=.02);assert c.phase=='OBSERVING'
step(case,c,3,100.,negative=neg(3),sigma=.02);b=c.boundary
step(case,c,4,None,event_feed_known=False);assert c.phase=='PROTECTED' and c.boundary==b
r=step(case,c,5,94.,event_feed_known=False)
assert c.exit_locked and c.exit_reason=='risk_boundary' and 'negative_sigma_unknown' in c.issues and 'price_or_factor_unknown' in c.issues
passed(case,'controller_unit','缺失分别报未知；不能补旧收据；缺事件不挡已有B','三类未知保留；更后独立收据可建B；已知价格94仍锁定退出')

case='split_economic_units_do_not_false_cross';c=armed(case);b=c.boundary
c.sync_execution(shares=200,buy_pending=False,exit_order_pending=False)
r=step(case,c,2,50.,factor=2.,updated_floor=80.)
assert r['economic_close']==100. and not c.exit_locked and c.boundary==b
r=step(case,c,3,47.,factor=2.)
assert r['economic_close']==94. and c.exit_locked
passed(case,'normalization_unit_only','拆股原始价减半而同经济价格不穿线','raw50×factor2=100不触发；真实经济价94才触发；未冒称权益集成')

case='cash_dividend_normalization_is_not_price_damage';c=armed(case);b=c.boundary
r=step(case,c,2,94.,factor=100./94.)
assert isclose(r['economic_close'],100.) and not c.exit_locked and c.boundary==b
passed(case,'normalization_unit_only','已验证因子下除息不造经济价格损伤','合成raw94×已给因子恢复100，无穿线；股息应收接口未测试')

case='mixed_or_unknown_unit_never_compared_as_raw_drop';c=armed(case);b=c.boundary
r=step(case,c,2,50.,unit_id='unmapped-new-basis')
assert not c.exit_locked and c.boundary==b and 'economic_unit_unknown' in r['current_unknown']
r=step(case,c,3,None,factor=None,unit_id='unmapped-new-basis',original_exit=True)
assert c.exit_locked and c.exit_reason=='original_exit'
passed(case,'controller_unit','混合单位标未知，不假穿；原退出仍优先','未知单位保留B/未知标志；原退出无需等单位修复即可锁定')

case='original_exit_priority_and_rebound_cannot_cancel';c=armed(case)
step(case,c,2,94.,original_exit=True);step(case,c,3,120.,updated_floor=110.,negative=neg(3),sigma=.02)
assert c.exit_locked and c.exit_reason=='original_exit' and c.intent_count==1 and c.shares==100
passed(case,'controller_unit','原退出优先，反弹不撤销，未成交仍持有','唯一退出意图保持，实际100股未被虚拟清仓')

# REAL original ledger functions, with explicitly synthetic quotes and windows.
sys.path.insert(0,str(ORIG));spec=importlib.util.spec_from_file_location('original_synthetic_ledger_helpers',ORIG/'test_sector_account.py');Q=importlib.util.module_from_spec(spec);spec.loader.exec_module(Q)
from sector_account import SectorAccount
from decimal import Decimal as D
case='partial_buy_cancel_blocked_partial_and_complete_real_ledger'
a=SectorAccount(initial_cash=D('100000'));ok,_=a.reserve_budget(quote=Q.quote(price=100),clock=Q.CLOCK,gross_budget_cny=D('25000'));assert ok
fill=a.fill_buy('A',Q.window(price=100,capacity=100));assert fill.shares==100 and a.quantity('A')==100 and 'A' in a.buys
c=new(shares=a.quantity('A'),pending=True);step(case,c,1,100.,negative=neg(1),sigma=.02)
r=step(case,c,2,95.);assert c.exit_locked and r['desired_cancel_buy'] and r['desired_submit_exit']
decision=Q.T+timedelta(days=1,hours=2);earliest=Q.T+timedelta(days=2)
a.request_exit(Q.quote(price=95),Q.admission.Clock(decision,earliest,decision.date()))
assert 'A' not in a.buys and a.quantity('A')==100 and 'A' in a.exits
c.sync_execution(shares=a.quantity('A'),buy_pending='A' in a.buys,exit_order_pending='A' in a.exits)
execution.append(dict(stage='real_request_exit_cancelled_buy',shares=a.quantity('A'),buy_pending='A' in a.buys,exit_pending='A' in a.exits,phase=c.phase))
blocked=a.fill_exit('A',Q.window(price=94,at=earliest,sell_allowed=False,eid='blocked-sell'));assert blocked is None and a.quantity('A')==100
c.sync_execution(shares=a.quantity('A'),buy_pending=False,exit_order_pending=True);assert c.phase=='EXIT_PENDING'
execution.append(dict(stage='real_sell_blocked',shares=a.quantity('A'),exit_pending='A' in a.exits,phase=c.phase))
partial=a.fill_exit('A',Q.window(price=94,at=earliest+timedelta(days=1),capacity=40,eid='partial-sell'));assert partial.shares==40 and a.quantity('A')==60
c.sync_execution(shares=a.quantity('A'),buy_pending=False,exit_order_pending='A' in a.exits);assert c.phase=='EXIT_PENDING'
execution.append(dict(stage='real_partial_sell',shares=a.quantity('A'),exit_pending='A' in a.exits,phase=c.phase))
last=a.fill_exit('A',Q.window(price=94,at=earliest+timedelta(days=2),eid='complete-sell'));assert last.shares==60 and a.quantity('A')==0
c.sync_execution(shares=a.quantity('A'),buy_pending='A' in a.buys,exit_order_pending='A' in a.exits);assert c.phase=='CLOSED'
execution.append(dict(stage='real_completed_sell',shares=a.quantity('A'),exit_pending='A' in a.exits,phase=c.phase))
passed(case,'real_original_offline_ledger_functions','部分持仓风险不消失；原函数撤余买单；不可卖/部分仍承担责任，真清仓才关闭','原reserve/fill_buy/request_exit/fill_exit实调用：100股+未完买→撤余单→不可卖100→卖40剩60→卖60后CLOSED')

case='missing_execution_snapshot_is_not_flat';c=armed(case);c.sync_execution(shares=None,buy_pending=None,exit_order_pending=None)
r=step(case,c,2,94.)
assert c.exit_locked and r['actual_holding_responsibility'] and not r['desired_submit_exit'] and r['execution_status_refresh_required']
passed(case,'controller_unit','缺股数确认不能假清仓/假提交','风险意图锁定，保留责任并要求刷新执行状态，不模拟成交')

unsupported=[
 dict(interface='new_controller_to_product_scheduler',status='NOT_IMPLEMENTED',reason='本轮没有修改产品接线，离线函数测试不代替完整调度集成'),
 dict(interface='broker_async_cancel_ack_and_late_fill',status='UNKNOWN',reason='原离线cancel_buy同步生效，无券商撤单回报/迟到成交接口，未用桩冒充'),
 dict(interface='real_corporate_action_factor_rights_share_mapping',status='NOT_RUN',reason='仅同单位归一化夹具；未读取真实行情/权益数据或串联公司行动账'),
 dict(interface='v2_native_event_cache_adapter_historical_behavior',status='NOT_RUN',reason='规范已定义身份字段，尚未把新版本接历史事件；v1十三例不可沿用')]
assert all(r['protection_after']>=r['protection_before'] for r in trace)
with (O/'TEST_CASES.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(tests[0]));w.writeheader();w.writerows(tests)
(O/'STATE_TRACE.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2))
(O/'OFFLINE_EXECUTION_TRACE.json').write_text(json.dumps(execution,ensure_ascii=False,indent=2))
(O/'INTERFACE_GAPS.json').write_text(json.dumps(unsupported,ensure_ascii=False,indent=2))
freeze=json.loads((O/'TEST_FREEZE.json').read_text());assert all(sha(p)==h for p,h in freeze['sha256'].items())
summary=dict(passed_defined_tests=True,defined_tests=len(tests),levels={x:sum(t['level']==x for t in tests) for x in sorted(set(t['level'] for t in tests))},unsupported_not_counted_as_pass=unsupported,trace_observations=len(trace),protection_decreases=0,source_hashes_unchanged=True,historical_market_files_read=0,new_historical_trigger_checks=0,profit_tests=0,product_changes=0,old_v1_coverage_not_reused=True,seconds=time.monotonic()-T0)
(O/'TEST_RESULTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))
