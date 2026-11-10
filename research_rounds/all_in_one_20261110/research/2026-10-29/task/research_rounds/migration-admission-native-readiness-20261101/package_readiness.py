"""Package only already-persisted readiness evidence; never runs an account."""
from pathlib import Path
import json,hashlib,shutil,inspect
import native_adapter as N
O=N.O;IO=N.IO;J=N.J

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())

def main():
    native=read(O/'NATIVE_GATE.json');identity=read(O/'IDENTITY_GATE.json')
    assert native['passed'] and identity['passed']
    assert identity['full_financial_paths']==identity['decoupled_historical_events']==0
    contract=N.static_contract()
    for p,h in identity['source_freeze'].items():assert sha(p)==h,('frozen source/input changed',p)
    audit=Path('/tmp/migration-2x2-independent.1M9sgv')
    for name in ('AUDIT_REPORT.txt','11TESTS.json','MATRIX_EVIDENCE.json'):
        dest=O/'prior-independent-audit'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(audit/name,dest);assert sha(dest)==sha(audit/name)
    IO.write_json(O/'STATIC_GATE.json',contract)
    key='''ISOLATED POLICY: original singlepass Bdiag + decoupled admission.
No native ledger callback changes. No two-pass planner import.
New request and route sources are copied byte-for-byte from the reviewed 2x2.
The budget is the original ledger authorization view, not a synthetic executor.
\n'''
    key+=inspect.getsource(N.enable)+'\n'+inspect.getsource(N.DecoupledBudget)+'\n'
    key+=inspect.getsource(N.CoupledRunner)+'\n'+inspect.getsource(N.DecoupledRunner)+'\n'
    key+='\nEXACT ROUTE (ONLY MIGRATION/ADMISSION GATE CHANGED)\n'+N.ROUTE.read_text()
    key+='\nREQUEST SOURCE LOCATOR\n'+str(N.MODEL.resolve())+':210 (entire request retained in file)\n'
    key+='\nUNCHANGED NATIVE CALLBACKS\n'
    for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view'):
        fn=getattr(J.Account,name);key+=f'{name}: {inspect.getsourcefile(fn)}:{fn.__code__.co_firstlineno}\n'
    IO.write_bytes(O/'KEY_FUNCTIONS.txt',key.encode())
    # Retain failed check results honestly: only fixtures/comparator changed;
    # the policy adapter/model/route and completed original prefix were not rerun.
    IO.write_json(O/'FAILURE_HISTORY.json',dict(
        native_fixture_draft=['missing risk_budget on synthetic core intent',
                              'null native window event ID on synthetic core',
                              'synthetic exit cutoff initially preceded actual buy; adjusted forward within same session'],
        comparator_draft=['nested FillReceipt.at omitted when filtering original audit; 7/3 records mistakenly included',
                          'receipt field can be string/None outside fill audit',
                          'set serialization order compared as list order; now exact membership, preserving ordered lists'],
        changed_trade_or_execution_policy=False,
        original_short_prefix_runs=1,physical_short_prefix_runs=1,
        original_completed_prefix_restored_not_replayed=True,
        failed_drafts_retained_under='failure/fixture-draft',
        input_loads_repeated_for_isolated_checker_restarts=True))
    timing={}
    for name in ('prefix-full-source','prefix-physical-source'):
        timing[name]=read(O/'identity-only'/name/'DONE.json')['run_seconds']
    IO.write_json(O/'READINESS.json',dict(
        ready_for_independent_review=True,independent_native_review_pending=True,
        native_lifecycle_tests=native['tests'],native_gate_seconds=native['seconds'],
        actual_native_callbacks=True,synthetic_budget_fill_sell_for_real_trades=False,
        original_policy_identity=identity['counts'],original_policy_prefix_scope=identity['window'],
        prefix_and_restore_guards=True,source_sha256=N.source_freeze(),
        original_policy_only_prefix_seconds=timing,
        new_decoupled_historical_paths=0,full_financial_paths=0,
        original_baselines_modified=False,two_pass_promoted=False,
        blockers=[],not_yet_established=['whole-window policy behavior/returns',
          'whether new admissions strand old probe and impede trials',
          'whether added permission worsens weak-market loss or crowds original winners',
          'live executability and PIT data'],
        next_step='independent review of this frozen native package; no full paths are launched'))
    text=f'''原单遍Bdiag＋迁池/新准入解耦：native readiness

工程门通过，待独立审查；未运行解耦历史账户或完整收益路径。
真实原生账本{native['tests']}项测试通过（{native['seconds']:.3f}s）：reserve/fill/partial、单订单最低佣金、T+1、
cancel请求/ack占用、晚到fill、持仓+余单split同域、receipt去重、结算、后续合法迁池、硬容量及损坏镜像拒绝。
预算模型fill/sell未用于真实成交。撤单在原历史引擎同步完成；测试显式保留请求至native ack之间的占用，
不声称模拟了真实券商异步系统。

原政策身份段仅2025/7/1–7/2（2收盘+首次开盘）：38笔真实成交、78条journal、198条audit、2条decision，
五类流水与旧保存账逐项一致。物理截断侧全部原生账户字段/集合成员相同；两侧已落盘。
完整状态恢复相同；错误policy/route恢复拒绝。新解耦partial-pending原生fixture亦通过带身份checkpoint恢复。
原政策完整输入侧只跑一次，物理截断侧只跑一次；后续比较器修订均从原检查点恢复。
实际短段运行秒数：{json.dumps(timing,ensure_ascii=False)}。输入读取未重算指标；检查器修订造成缓存重复读取已记。

唯一新经济政策仍是route/request不再要求旧probe整迁成功；原best-effort调用/副作用保留。
Native Account、planning、opening、所有成交/撤单/split/镜像回调原文不改；原core-first预留即抑制同股mobile。
新订单并不使旧probe迁走或免占额。真实小新单可进一步挤占整迁所需余量，后来迁池重新检查。

已预注册下一两窗比较指标见CONTRACT.txt，含新增/失去真实获资股与attempt、旧probe等待及右删失、
新试错阻挡、无未来筛选的机会覆盖、两pool曝险/损耗、closed/open肥尾、NAV/DD/费用，
以及弱市新增损失和原赢家被挤出。该文件不是启动两窗授权。

当前无未解释接口阻塞；等待独立审查。原数据/日线成交代理/非PIT/未见样本限制不变，未获实盘认证。
'''
    IO.write_bytes(O/'READOUT.txt',text.encode())
    source_files=[O/'native_adapter.py',O/'test_native.py',O/'check_identity.py',O/'package_readiness.py',O/'CONTRACT.txt',N.MODEL,N.ROUTE]
    IO.write_json(O/'FREEZE.json',dict(scope='native readiness ONLY; source stable before independent review',
         source_sha256={str(p.resolve()):sha(p) for p in source_files},
         original_inputs_and_dependencies=identity['source_freeze'],
         new_policy_version='singlepass-migration-admission-decoupled-native-1',
         no_financial_run=True))
    files=[p for p in O.rglob('*') if p.is_file() and p.name!='ARTIFACT_SHA256.json' and '__pycache__' not in p.parts]
    IO.write_json(O/'ARTIFACT_SHA256.json',{str(p.relative_to(O)):sha(p) for p in sorted(files)})
    print('READINESS_FROZEN',len(files),sha(O/'native_adapter.py'),flush=True)

if __name__=='__main__':main()
