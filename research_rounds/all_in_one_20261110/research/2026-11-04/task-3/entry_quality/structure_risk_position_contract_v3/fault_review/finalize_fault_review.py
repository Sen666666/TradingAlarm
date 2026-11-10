"""Bind human formula/fault review; no account, model or stress-engine calls."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent;P=O.parent;C=P/'designer/MINIMUM_MATH_CONTRACT.md'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
code=C.read_text();card_sha=sha(C)
assert all(x in code for x in ['同股全部层同价','Φ_market','Λ','UNKNOWN_NO_GRANT','DENY_ZERO','不能超冻结cap','CP UNKNOWN'])
assert 'postfill' in code and 'V_proj' in code and 'A_proj' in code
f=json.loads((O/'FAULT_SCENARIOS.json').read_text());assert len(f['cases'])==23 and [x['id']for x in f['cases']]==['F'+str(i).zfill(2)for i in range(1,24)]
readout='''# v3公式与故障预期独立审查

结论：所选初值已经构成可计算的待检数学合同；本轮纸面公式及故障预期审查通过。没有实现native执行，也没有回测、收益改善、参数最优或尾险覆盖的经济通过。本结论不授权任何新账户或后续运行。

原23例逐项映射到当前合同：触线无成交/T+1/停牌责任保留；partial买卖与ACK按真实余量；同logical order最低佣金跨partial只累计一次；H放宽先占旧仓责任；共同情景合全行业/全账户而不假独立；STAR/BJ/主板按dated frozen rule的minimum和step；split单位和应收现金分开；真实陈旧/缺失字段UNKNOWN不冒充0容量；I/CP同槽去重；OPEN只缩量不扩信号cap。

具体离散算术只涉及固定输入。原费表component的3次partial增量为5/0/1，非15元；frozen STAR200/1、BJ100/1、主板100/100在cap237分别237/237/200。单点Vk60000、B150、原费用/5bp、signalcap100例，独立OPEN12预算不容最小手为0；独立OPEN9.5虽局部可200仍不得超过100信号cap。这不是交易路径或收益估计。F10/F11的共同损失是已给定operator输入，用于核聚合，不是从新历史数据计算的压力结果；部分零费例只隔离单位/状态，非完整证券费用报价。

新增F24附件指出并修正：同sid不同层只能有一个G1/G2压力价，基于全存量/未ACK待买/拟合同中真实计划线的共同min基准；宽I提案会改变旧stock压力，须全量重算。P逐层计划线只作参考，不称同步物理市场价。Φ_market是当前共同情景压力；Λ包含不同request时点的历史责任锁，不伪称同期market loss。两者都报告，授权用Λ。

待买与fill后使用相同raw mark/H/factor/共同压力价/费组，pendingφ=postfill liveφ+已知入场slip/fee。一般grant实现必须全量postfill投影V_proj/A_proj、所有行业T与责任，费用从pending一次转D/真实成本，不能分母扣后责任再留同一成本。prefill表达只作恒等audit，避免跨行业分母因手续费缩小被漏掉。

ACT剩余空间与有限.8/.64情景是待检候选。忽略费时新高gross≤20/36≈55.56%NAV仅为必要最宽上界，退出线更宽/锁/费/行业门会更紧；接近ACT线，新买可早于ACT触发归0；episode恢复重新开空间也不是初始本金floor。有限两期仍可被多日不可成交击穿。没有据此选择新参数或宣称赢家保留。

本次不复算父线程具体原股票LOCAL数字或7OPEN全户必要下界；这些另由对应独审收据负责。所有LOCAL数量必须再经完整组合、行业、流动性、source cap才可能grant，不把原层损益或本表算术当候选账户收益。
'''
(O/'FINAL_READOUT.md').write_text(readout)
paths=[C,O/'FAULT_SCENARIOS.json',O/'FAULT_SCENARIOS.md',O/'build_fault_spec.py',O/'COMMON_PRICE_AND_PENDING_BRIDGE_ADDENDUM.md',O/'FINAL_READOUT.md',Path(__file__)]
for p in [P/'designer/SOURCE_BINDING.json',P/'designer/ARITHMETIC_CASES.json']:
 if p.is_file():paths.append(p)
out=dict(status='PASS_FORMULA_AND_FAULT_SPEC_NOT_IMPLEMENTATION_OR_ECONOMIC_VALIDATION',reviewed_contract_sha256=card_sha,base_fault_expectations=23,additional_common_price_fault='F24 conceptual annex, no new stress engine',scope='Paper formula/symbolic and fixed single-snapshot arithmetic cross-review; original23 expected decision/state/liability mappings, then same-sid price and pending/postfill bridge only.',observed_repairs=['One common G1/G2price per sid, includes all real/pending/proposal trueH; P reference distinguished.','Φ_market versus historical request-reservedΛ separated; live/exit ownership disjoint.','Raw mark/p buy price separated; exact pending-to-fill entry-cost bridge; complete postfill V/A/T/obligation projection chosen.','Original dated rules/minfee/ACK/CA/sourcecap retained; risk book estimates do not modify native cash/NAV.'],remaining_logic_blocks=[],native_fault_cases_executed=0,new_models=0,new_accounts=0,new_backtests=0,new_parameter_scans=0,new_price_path_simulations=0,new_returns_computed=0,implementation_validated=False,economic_effectiveness_validated=False,future_runs_authorized_by_this_review=False,limits=['Fault table specifies expected behavior, not executed native24-case test results.','Only fixed arithmetic and source rule reads were executed; no historical replay or complete candidate pressure run.','Original data completeness, actual market execution, extreme tail adequacy and source/holding policy effects remain separately testable risks.','ParentLOCALcase numbers and7OPENnecessary bounds not independently recalculated here.'],source_sha256={str(p.resolve()):sha(p)for p in paths},technical_note='Initial fault-table authoring had one unmatched-parenthesis syntax failure before any specification arithmetic ran; corrected only local audit script, no source/model/financial events.')
assert sha(C)==card_sha
q=O/'FINAL_FAULT_REVIEW.json';assert not q.exists();q.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(out['status'],sha(q),card_sha,sha(O/'FINAL_READOUT.md'))
