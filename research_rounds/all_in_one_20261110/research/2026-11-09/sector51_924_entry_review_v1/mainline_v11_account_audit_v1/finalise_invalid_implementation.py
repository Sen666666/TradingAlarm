"""Finalize factual audit of INVALID V11 execution. Reads files only; no strategy import."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import hashlib,json,ast,sys
sys.dont_write_bytecode=True
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;R=O.parent;C=R/'mainline_candidate_v11_structural_maturity_entry';P=C/'once_20250120';B=R/'mainline_m7_cash_batch_design_v6/once_20260630'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,v):(O/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
def sm(rs,k):return sum((D(r.get(k,0) or 0) for r in rs),D(0))
# Approval and source identities, including preserved failed startup wrapper.
ap=read(C/'EXPERIMENT_APPROVAL.json');fr=read(C/'FROZEN_INPUTS.json');started=read(C/'RUN_STARTED.json');status=read(C/'RUN_STATUS.json');qa=read(C/'SYNTHETIC_QA.json');startfail=read(C/'STARTUP_ATTEMPTS.json')
assert ap['approved'] and ap['one_shot'] and ap['end']=='2025-01-20' and ap['initial_cash']=='1200000'
for p,h in ap['code_hashes'].items():assert sha(p)==h,('approval_hash',p)
assert fr['hashes']==read(P/'SOURCE_HASHES.json') and fr['code_hashes']==ap['code_hashes']
assert started['engine_sha256']==sha(C/'engine.py')==qa['engine_sha256'] and started['qa_sha256']==sha(C/'SYNTHETIC_QA.json')
assert sha(R/'mainline_structural_maturity_design_v1/DESIGN.md')==ap['formula_design_sha256']
src=(C/'run_approved_once.py').read_text();ast.parse(src)
assert 'data=m.Data()' in src and 'run_days=[d for d in data.days if m.day(d)<="2025-01-20"]' in src and src.count('pending=e.atomic_step(d,pending,prev)')==1
assert 'with (O/"RUN_STARTED.json").open("x")' in src and src.index('data=m.Data()')<src.index('with (O/"RUN_STARTED.json").open("x")')
assert startfail==[dict(result='PRE_HISTORY_LOADER_ARGUMENT_ASSERTION',history_days=0,run_started=False,reason='Sealed Data requires original END 2026-06-30; keep exact Data() and bound execution loop to 2025-01-20',strategy_changed=False)]
assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='Data' and any(isinstance(a,ast.Constant) and a.value=='2025-01-20' for a in n.args) for n in ast.walk(ast.parse((C/'run_approved_once_startup_failed.py').read_text())))
freeze=dict(result='PASS',engine_sha256=sha(C/'engine.py'),runner_sha256=sha(C/'run_approved_once.py'),approval_sha256=sha(C/'EXPERIMENT_APPROVAL.json'),frozen_manifest_sha256=sha(C/'FROZEN_INPUTS.json'),status_sha256=sha(C/'RUN_STATUS.json'),original_source_manifest_equal=True,startup_attempts=startfail,planned_execution_days=fr['execution_days'],actual_committed_days=status['days'],actual_end=status['last']['day'],no_strategy_imported_by_audit=True)
save('RUNNER_FREEZE_REVIEW',freeze)
# Real, sealed CP input scalar. The source is a local input; no Data object or model call.
cp=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/CP1/601336.SH.parquet')
assert sha(cp)==fr['hashes'][str(cp)]
z=pd.read_parquet(cp);v=z.loc['2024-09-23'].get('receipt');candidate=z.loc['2024-09-23'].get('candidate')
# Reproduce exactly the frozen scalar dispatch, not the trading algorithm.
old_bool_state=(1 if v else 0) if type(v) is bool or type(v).__name__=='bool_' else -1
assert isinstance(v,np.bool_) and bool(v) and old_bool_state==-1
shadow_source=(C/'shadow.py').read_text();assert "if type(value) is bool or type(value).__name__ == 'bool_':" in shadow_source
cp_events=read(P/'ENTRY_CP_EVENTS.json');decisions=read(P/'ENTRY_GATE_DECISIONS.json');orders=read(P/'ORDERS.json');seed=[o for o in orders if o['side']=='BUY_SEED'];entry=read(O/'ENTRY_EVIDENCE_AUDIT.json')
events=Counter(x['event'] for x in cp_events);states=Counter(x.get('CP_state') for x in decisions if 'CP_state' in x)
assert events['CREATED']==0 and set(states)=={-1} and all(o.get('entry_evidence_id') is None for o in seed)
assert all(r['F']==1 and r['CP_state']==-1 for r in entry['actual_seed_rows'] if r['phase']=='MATURE')
semantics=dict(result='FAIL',experiment_verdict='INVALID_IMPLEMENTATION',reason='Frozen shadow.bool_state rejects the real NumPy boolean scalar type. Every observed CP stream value becomes unknown, so the intended CP admission branch never operates.',actual_interpreter=sys.executable,pandas_version=pd.__version__,numpy_version=np.__version__,local_sample=dict(sid='601336.SH',day='2024-09-23',file=str(cp),file_sha256=sha(cp),receipt_repr=repr(v),receipt_type=str(type(v)),receipt_type_name=type(v).__name__,type_is_python_bool=type(v) is bool,isinstance_numpy_bool_=isinstance(v,np.bool_),frozen_parser_result=old_bool_state,actual_receipt_true=bool(v),candidate=str(candidate)),entry_CP_event_counts=dict(events),CP_state_counts={str(k):v for k,v in states.items()},seed_orders=len(seed),seed_evidence_ids_present=sum(o.get('entry_evidence_id') is not None for o in seed),mature_seed_orders=sum(r['phase']=='MATURE' for r in entry['actual_seed_rows']),mature_all_F_only=True,scope='Accounting can be reconciled, but this is not a valid test of the fixed F OR valid shadow-CP hypothesis. All performance/capture numbers below describe the erroneous implementation only. No acceptance/rejection of the intended trading hypothesis is justified.')
save('IMPLEMENTATION_SEMANTIC_FAILURE',semantics)
# Specific immutable evidence for inherited Q0 split-scope rejection.
sid='605499.SH';families=['ORDERS','ATTEMPTS','HOLDINGS','CAPITAL_LOTS','EQUITY_EVENTS','RETRY_TICKETS','PENDING_AT_END','ENTRY_CP_EVENTS','ENTRY_GATE_DECISIONS']
evidence={n:[x for x in read(P/(n+'.json')) if x.get('sid')==sid] for n in families}
evidence['TICKET_STATE']=read(P/'TICKET_STATE.json')[sid]
evidence['ENTRY_ARCHIVE']=[x for x in read(P/'ENTRY_ARCHIVE.json') if x['identity']['sid']==sid]
evidence['ENTRY_SHADOW_PRESENT']=sid in read(P/'ENTRY_SHADOWS.json')
assert all(not evidence[n] for n in ['ORDERS','ATTEMPTS','HOLDINGS','CAPITAL_LOTS','EQUITY_EVENTS','PENDING_AT_END'])
assert evidence['TICKET_STATE']['status']=='CANCELLED' and evidence['TICKET_STATE']['ever_seeded'] is False and not evidence['ENTRY_SHADOW_PRESENT']
base_retry=[x for x in read(B/'RETRY_TICKETS.json') if x['sid']==sid and x['day']<='2024-10-09']
block=dict(result='CONFIRMED_ORIGINAL_GUARD_REJECTION',block_day='2024-10-09',committed_through='2024-10-08',reason=status['atomic_block']['reason'],runtime_error=status['runtime_error'],explanation='At 2024-09-30 the never-seeded original ticket was cancelled by original OPEN attempt-budget rejection. The inherited Q0 guard is unconditional on the 2024-10-09 split date and requires a live never-seeded ticket. It rejects this cancelled-ticket path before any economic event or trade. No new missing-company-action conclusion and no guard relaxation are implied.',source_guard=str(R/'mainline_m7_downturn_q0_split_v3/engine.py'),guard_sha256=sha(R/'mainline_m7_downturn_q0_split_v3/engine.py'),candidate=evidence,baseline_retry_through_event=base_retry,candidate_original_NAV=evidence['TICKET_STATE']['nav0'],candidate_original_budget=evidence['TICKET_STATE']['budget'],baseline_original_NAV=base_retry[0]['original_nav'],baseline_original_budget=2*D(base_retry[0]['original_nav'])/100,record_snapshot_limitation='Internal snapshots are not directly exported. No claim that all later guard conditions pass; the observed rejection is the first live-ticket check only.')
save('BLOCKER_605499_FACTS',block)
# Explain all real account amounts without assigning unearned blocked baseline profits/losses.
b=read(O/'M7_COMMON_ROUNDS.json');c=read(O/'V11_ACTUAL_ROUNDS.json');bb={x['opportunity_key']:x for x in b};cc={x['opportunity_key']:x for x in c};sealed={x['opportunity_key'] for x in read(R/'mainline_tail_capture_baseline_v1/ALL_OPPORTUNITIES.json')}
matched=[x for x in c if x['opportunity_key'] in bb];early_fixed=[x for x in c if x['opportunity_key'] in sealed and x['opportunity_key'] not in bb];new=[x for x in c if x['opportunity_key'] not in sealed];loss=[x for x in b if not x['open_at_cutoff'] and D(x['marked_net_pnl'])<0];matched_loss=[x for x in loss if x['opportunity_key'] in cc];untraded_loss=[x for x in loss if x['opportunity_key'] not in cc];c_loss=[x for x in c if not x['open_at_cutoff'] and D(x['marked_net_pnl'])<0]
assert sm(matched,'marked_net_pnl')+sm(early_fixed,'marked_net_pnl')+sm(new,'marked_net_pnl')==sm(c,'marked_net_pnl')
lossdiag=dict(scope='Descriptive erroneous-implementation accounting only. Later loss labels are not signals and no filter gain is inferred.',baseline_closed_negative_count=len(loss),baseline_closed_negative_pnl=sm(loss,'marked_net_pnl'),matched_negative_count=len(matched_loss),matched_baseline_pnl=sm(matched_loss,'marked_net_pnl'),candidate_actual_pnl_on_same_identities=sm([cc[x['opportunity_key']] for x in matched_loss],'marked_net_pnl'),untraded_negative_count=len(untraded_loss),untraded_baseline_loss_reference_only=sm(untraded_loss,'marked_net_pnl'),candidate_own_closed_negative_count=len(c_loss),candidate_own_closed_negative_pnl=sm(c_loss,'marked_net_pnl'),all_same_identity_negative_paths_unchanged=all(D(x['marked_net_pnl'])==D(cc[x['opportunity_key']]['marked_net_pnl']) for x in matched_loss))
save('ACTUAL_NEGATIVE_ROUND_DIAGNOSTIC',lossdiag);save('FIXED_OPPORTUNITIES_CAPTURED_BEFORE_BASELINE_ENTRY',early_fixed)
attribution=dict(matched_common_count=len(matched),matched_common_actual_pnl=sm(matched,'marked_net_pnl'),fixed_identity_baseline_entry_after_common_frontier_count=len(early_fixed),fixed_identity_baseline_entry_after_common_frontier_actual_pnl=sm(early_fixed,'marked_net_pnl'),new_to_full_sealed_baseline_count=len(new),new_actual_pnl=sm(new,'marked_net_pnl'),total_candidate_rounds=len(c),total_actual_pnl=sm(c,'marked_net_pnl'),all_actual_orders_partition_reconciled=True)
save('ACTUAL_ACCOUNT_ATTRIBUTION',attribution)
result=read(O/'INDEPENDENT_V11_VS_M7.json');result['verdict']='INVALID_IMPLEMENTATION';result['accounting_verdict']='PASS_SAVED_OUTPUT_ACCOUNTING';result['implementation_semantics']='FAIL';result['implementation_failure']=semantics;result['runner_freeze_review']=freeze;result['actual_account_attribution']=attribution;result['negative_round_diagnostic']=lossdiag
result['limits'].insert(0,'INVALID_IMPLEMENTATION: actual NumPy bool receipts were mapped to UNKNOWN; do not use this prefix to evaluate the intended fixed F OR CP hypothesis.')
for x in result['cohorts']:
    x['evaluation_status']='NOT_OBSERVABLE_AT_ATOMIC_CUTOFF' if not x['baseline_common_frontier_count'] else 'ERROR_IMPLEMENTATION_PREFIX_ONLY_NOT_HYPOTHESIS_TEST'
save('INDEPENDENT_V11_VS_M7',result)
entry['accounting_evidence_status']='PASS_INTERNAL_RECORDS_ONLY';entry['strategy_semantics_status']='FAIL_SEE_IMPLEMENTATION_SEMANTIC_FAILURE';save('ENTRY_EVIDENCE_AUDIT',entry)
A=result['V11'];M=result['M7']
text=f'''# V11 单次账户独立审计：账务通过，候选语义失败

**总判定：INVALID_IMPLEMENTATION。** 固定设计要求 MATURE 新 SEED 使用 F OR 有效影子 CP；实际 NumPy 布尔标量被错误识别为未知，CP 通路从未运行。本报告所有收益、捕获和损失数字，仅用于描述和追溯错误实现，不能据此接受或否定固定假设，也不能把少赚 28,012.30 元称为该假设的策略结果。

## 可认证边界

- 实际提交范围：2024-09-02 至 2024-10-08，20 个交易日、581 笔订单。2024-10-09 原子阻断，未提交未来日/半日经济订单和日志。
- V11 61 个输出文件、9,091 个源文件哈希通过；M7 59 个输出文件、9,081 个源文件哈希通过。批准代码、运行包装、设计、冻结输入清单与结果源清单吻合。
- Decimal 逐日现金、费率、dated lot、T+1、逐lot库存/市值、capital lot 分解、股息应收/支付、NAV、清算NAV、行业及逐轮PnL自洽。
- 首次包装 Data(end=2025-01-20) 在进入任何历史日和 RUN_STARTED 前触发封存加载器参数断言。保留了失败包装/批准快照和 STARTUP_ATTEMPTS。随后按原 Data() 读取缓存，93日执行列表明确截到2025-01-20；实际只提交20日。审计未运行策略、未实例化Data、未联网。

## 实现语义失败证据

实际解释器当前为 pandas {pd.__version__}、NumPy {np.__version__}。本地封存的新华保险 601336.SH CP 文件 2024-09-23 receipt 为真实 np.True_，candidate={candidate}。标量类型是 numpy.bool、类名 bool，而非 bool_，且不是 Python 内建 bool。冻结 shadow.bool_state 只接受内建 bool 或类名 bool_，因而错误输出 U。

结果中 CREATED=0，UNKNOWN_GAP=5,002；全部4,992条有CP_state的决策均为-1，281笔SEED入场证据ID全空，99笔MATURE成交全部依靠F=1。三值公式与现金账表本身能自洽，但实际输入已错，不能认证它是固定F∨CP候选。原源/引擎/结果保持不变，未放宽guard或重新回放。

## 同日账户事实（截至2024-10-08）

| 项目 | 错误V11实现 | M7同日 |
|---|---:|---:|
| NAV | {D(A['NAV']):,.6f} | {D(M['NAV']):,.6f} |
| 净收益率 | {D(A['return_pct']):.6f}% | {D(M['return_pct']):.6f}% |
| 最大收盘回撤 | {D(A['max_close_drawdown_pct']):.6f}% | {D(M['max_close_drawdown_pct']):.6f}% |
| 费用 | {D(A['trading']['fees']):,.6f} | {D(M['trading']['fees']):,.6f} |
| 成交单数 / ADD数 | 581 / 55 | 733 / 60 |
| 平均收盘仓位 | {D(A['exposure_stats']['mean_close_weight_pct']):.4f}% | {D(M['exposure_stats']['mean_close_weight_pct']):.4f}% |
| 最大收盘仓位 | {D(A['exposure_stats']['max_close_weight_pct']):.4f}% | {D(M['exposure_stats']['max_close_weight_pct']):.4f}% |
| 末日开放轮 | 71 | 71 |

NAV差为−28,012.300110，费用少1,165.873830。截止点在大涨阶段，不能将这20日低回撤与基线1月20日的20.09%回撤比较。

## 605499 原子阻断事实

605499.SH 原B票signal为9/26。9/27因原资本上限拒绝后保留；9/30 OPEN又违反原attempt_budget，按既有规则取消。候选原NAV=1,265,458.508643，2%原预算=25,309.170173；基线同票原NAV=1,286,392.514978，2%预算=25,727.850300，9/30只受现金/参考额度拒绝而继续保留，10/8为PAUSED。

候选截至10/8：无该股成交、轮次、持仓、capital lot或股息权益；票status=CANCELLED、ever_seeded=false、plan=null，影子已归档取消。10/9继承的q0_guard在首项要求“live never-seeded ticket”，所以报Q0_SPLIT_SCOPE_LIVE_NEVER_SEEDED_TICKET_REQUIRED。该guard当日无条件调用，不能因为零持仓便认定已准入其余路径，也不能假称又缺了新公司行动事实。内部record snapshot不直接导出，本审计不宣称后续guard条件已经通过。详见BLOCKER_605499_FACTS.json。

## 固定机会与可观察范围

- 封存1677个sid+原signal_day身份全部保留；基线截至10/8实际开过的353轮中，错误实现成交263个相同身份，25延迟、238同日；余90未成交。
- 9/23–9/30原启动222轮全部进入可观察入场范围：成交174（78.38%），149同日、25延迟（最长3交易间隔），48未成交。此处不是完整趋势终局：候选这些身份仍有55个开放轮。
- 光伏10/23–29的34轮、11/7起954轮均尚未进入共同认证范围，**不评估、不是捕获率0、不是避免亏损成功**。
- 全窗固定top正收益十分位62个赢家中，42个原入场已发生，捕获36；只看同日marked PnL为基线221,216.67、错误实现166,358.58。排序身份来自封存评估标签，不能作为当时信号，也不能把尚未发生的20个列成漏抓。
- 账户实际281轮拆为：263个共同前缀身份实际PnL324,512.875701；4个封存基线在10/8以后才入场、但候选已提前成交的同身份实际PnL7,087.931608；14个不在完整1677基线中的新身份实际PnL13,843.808146。合计345,444.615455，与现金账户利润精确闭环。开放轮单列，不虚构卖出。

## 几个固定赢家的错误路径代价

以下均截至10/8，**不是正确F∨CP假设的效果**：

- 新华保险：原9/23入场，错误实现9/25才买，同尺度实际成交价高15.4317%；原300股改为200股，原路径9/24有ADD，错误路径无ADD且9/27按MAINLINE_EXPANSION_SURPLUS融资迁出。同日PnL13,681.17降至736.92。
- 常山北明：9/24同价同量700股入场，但原路径9/26有ADD，错误路径无ADD；同日PnL3,108.89降至1,866.33。
- 拓维信息：9/24同价同量500股入场，原路径两次ADD，错误路径无ADD；同日PnL3,363.53降至2,081.05。
- 大名城：原9/24入场，错误实现截至10/8未成交；原同日marked PnL7,865.83仅是机会参考，不算候选赚取或损失的现金。
- 聚和材料、禾望电气等10月后续机会尚未发生，不能报错过或保留。

## 是否真的让原亏损轮少亏

共同前缀基线107个已平负轮合计−20,548.36。错误实现参与其中71个，相同身份的实际PnL恰与基线相同，均合计−14,074.79，**已参与的这71轮没有少亏**。另36个未成交的原亏损−6,473.57只能列为未参与参考，不能直接当新增账户利润。错误实现自身已平负轮76个合计−14,705.85；新路径亦有亏损。完整现金/ADD/退出与再分配后的账户结果已经包含所有这些变化，不能再次加回被挡原亏损。

## 交付与限制

核心结果：INDEPENDENT_V11_VS_M7.json；冻结包装：RUNNER_FREEZE_REVIEW.json；语义失败：IMPLEMENTATION_SEMANTIC_FAILURE.json；阻断：BLOCKER_605499_FACTS.json。FIXED_OPPORTUNITY_COMPARISON、FIXED_WINNER_COMPARISON、ACTUAL_ACCOUNT_ATTRIBUTION与实际逐轮/开放轮文件可追溯至真实orders。

本次是已观察开发窗且实现无效，不是OOS、PIT、实盘可执行性或本金保障证明。GATE*中的固定等待价差只属于既有描述诊断，不是本候选成交；本报告15.4317%来自两条实际成交价及各自持仓factor，而不是等待报价填充。源事实及原费用代理限制原样保留。
'''
(O/'INDEPENDENT_READOUT.md').write_text(text)
save('FINAL_AUDIT_SEAL',dict(verdict='INVALID_IMPLEMENTATION',accounting='PASS',semantics='FAIL',files={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name not in ['FINAL_AUDIT_SEAL.json','AUDIT_SEAL.json']}))
print(json.dumps(dict(verdict='INVALID_IMPLEMENTATION',accounting='PASS',semantics='FAIL',common_end='2024-10-08',blocker=block['reason'],matched_loss_paths_unchanged=lossdiag['all_same_identity_negative_paths_unchanged']),ensure_ascii=False))
