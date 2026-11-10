"""Render final certified-prefix audit report and seal; no strategy/history."""
from pathlib import Path
from decimal import Decimal as D
import json,sys
sys.dont_write_bytecode=True
import accounting_core as au
O=Path(__file__).resolve().parent;R=O.parent
def n(x):return f'{D(x):,.2f}'
def main():
    r=au.read(O/'INDEPENDENT_M12_VS_M7_PREFIX.json');assert r['verdict']=='PASS_CERTIFIED_PREFIX_ACCOUNTING_AND_SAVED_BRANCH_SEMANTICS'
    a=r['M12'];b=r['M7'];sem=r['saved_semantics'];sel=r['selection_summary'];block=r['atomic_block_cause'];co={x['cohort']:x for x in r['cohorts']};startup=co['SEPT_STARTUP_SEED_OPEN_0923_0930'];special={x['name']:x for x in r['special_fixed_groups']};s24=special['SEP24_MATURE'];s71=special['STARTUP_MATURE_SAME_DAY_HEALTHY_FUNDING']
    winners=au.read(O/'STARTUP_19_STRONG_WINNER_PATHS.json');miss=[x for x in winners if not x['candidate_captured']]
    givebacks=au.read(O/'HEALTHY_ROUND_GIVEBACK_PATHS.json');gb={x['opportunity_key']:x for x in givebacks};shui=gb['600779.SH|2024-09-23'];silver=gb['300085.SZ|2024-09-23'];chang=gb['000158.SZ|2024-09-23']
    fund=r['funding'];atr=r['actual_attribution'];plans=au.read(O/'FUNDING_PLAN_SELECTION_AUDIT.json')
    lines=[
    '# M12 最小 A：认证前22日独立后审',
    '',
    '## 结论与不可外推范围',
    '**账务通过，全部认证保存分支语义通过。完整93日经济试验未完成。**',
    '唯一冻结原 M7 为对照；双方严格同窗 2024-09-02 至 2024-10-10，共22个交易日。M12在10/11原生预检触发 688200.SH UNADMITTED_EQUITY_EVENT，账户原子回滚。目录名 once_20250120 不代表已运行到1月20日。',
    f"M12同窗实际账户多赚 **{n(r['delta']['NAV'])}元**，收益率高 **{n(r['delta']['return_pct'])}个百分点**。但尚未覆盖11/6后的主经济检验、10/23–10/29光伏固定窗口、11/7后954轮或12/5机器人边界。因此不能认定已解决后期回撤或整段有效。",
    '未混入旧INVALID V11、corrected V11绩效或任何新v2试验。V11 v2仅提供纯账务函数来源。后审没有import候选/Data、没有history、没有联网、没有改策略/准入/行情。',
    '',
    '## 同窗实际账户',
    '| 指标 | M12 | 原M7 |',
    '|---|---:|---:|',
    f"| NAV | {n(a['NAV'])} | {n(b['NAV'])} |",
    f"| 实际总PnL（含期末持仓标记） | {n(a['profit'])} | {n(b['profit'])} |",
    f"| 收益率 | {n(a['return_pct'])}% | {n(b['return_pct'])}% |",
    f"| 费用 | {n(a['trading']['fees'])} | {n(b['trading']['fees'])} |",
    f"| 最大close回撤 | {n(a['max_close_drawdown_pct'])}% | {n(b['max_close_drawdown_pct'])}% |",
    f"| 平均 / 最大close仓位 | {n(a['exposure_stats']['mean_close_weight_pct'])}% / {n(a['exposure_stats']['max_close_weight_pct'])}% | {n(b['exposure_stats']['mean_close_weight_pct'])}% / {n(b['exposure_stats']['max_close_weight_pct'])}% |",
    f"| 期末现金 | {n(a['cash'])} | {n(b['cash'])} |",
    f"| 平均close现金 | {n(r['cash_statistics']['M12']['mean_close_cash'])} | {n(r['cash_statistics']['M7']['mean_close_cash'])} |",
    f"| 真实订单 / ADD订单 | {a['trading']['orders']} / {a['rounds']['actual_add_orders']} | {b['trading']['orders']} / {b['rounds']['actual_add_orders']} |",
    f"| 已开轮 / 未平轮 | {a['rounds']['total']} / {a['rounds']['open']} | {b['rounds']['total']} / {b['rounds']['open']} |",
    f"| 已平轮PnL | {n(a['rounds']['closed_net'])} | {n(b['rounds']['closed_net'])} |",
    f"| 未平轮标记PnL | {n(a['rounds']['open_marked_net'])} | {n(b['rounds']['open_marked_net'])} |",
    '',
    f"领先中，已平轮净利差为{n(D(a['rounds']['closed_net'])-D(b['rounds']['closed_net']))}元，未平轮标记差为{n(D(a['rounds']['open_marked_net'])-D(b['rounds']['open_marked_net']))}元。不能把未平轮强行结算，或沿用其他试验105/130的未平数量。",
    f"10/8到10/10账户回落：M12 {n(r['peak_reversal']['M12']['oct8_to_end_PnL'])}元，M7 {n(r['peak_reversal']['M7']['oct8_to_end_PnL'])}元。总体回吐少，但个别老赢家仍可多回吐。",
    '',
    '## 9/24与固定强赢家',
    f"原9/24的28个MATURE：M12 **{s24['captured']}/28全部同日捕获**，零延迟；同窗实际PnL {n(s24['candidate_actual_PnL'])}元，对照{n(s24['baseline_common_PnL'])}元；后续ADD {s24['candidate_ADD_orders']}次对{ s24['baseline_ADD_orders']}次，M12仍有{s24['candidate_open']}轮未平。",
    '这是实际输出结论，不是“当天没有原融资所以必须全保留”的逻辑推断。ADD/EVENT的q下限可独立于健康donor融资绑定，本规则没有无融资日豁免。',
    f"固定9/23–9/30启动窗口222轮：捕获{startup['captured']}轮，均同日；未捕获71轮。同窗PnL为{n(startup['candidate_actual_pnl_on_fixed_keys'])}元，对照{n(startup['baseline_pnl'])}元。原固定19强赢家捕获17个，不是全抓住。",
    '',
    '| 未捕获固定强赢家 | 原SEED OPEN | 原同窗已实现PnL（机会成本） |',
    '|---|---|---:|']
    for x in miss:lines.append(f"| {x['name']} {x['sid']} | {x['baseline_seed_OPEN']} | {n(x['baseline_common_pnl'])} |")
    lines += [
    '',
    f"上述两轮合计{n(sum((D(x['baseline_common_pnl']) for x in miss),D(0)))}元原同窗盈利未捕获。原健康融资同日MATURE固定71轮全部未捕获；原同窗PnL为{n(s71['baseline_common_PnL'])}元。此前全期封存的+36,641.99元是Jan20口径，不能与本次Oct10口径混用。",
    '71轮分组只是原账户“同日存在健康融资”交集，不是donor定向支付、新规则必然应删或孤立因果收益归因。',
    '',
    '## 领先主要来自哪些真实轮',
    '下列均为相同原机会身份的实际成交/权益/标记路径差额，不把未交易原亏损当收益。',
    '| 轮 | M12 PnL | M7 PnL | 差额 | ADD次数 M12/M7 | 退出或持仓差异 |',
    '|---|---:|---:|---:|---:|---|']
    for x in r['matched_top5']:
        state=(x['M12_exit'] or 'M12未平')+' / '+(x['M7_exit'] or 'M7未平')
        lines.append(f"| {x['name']} | {n(x['M12_PnL'])} | {n(x['M7_PnL'])} | {n(x['delta'])} | {x['M12_ADD']}/{x['M7_ADD']} | {state} |")
    lines += [
    f"前5轮差额合计{n(sum((D(x['delta']) for x in r['matched_top5']),D(0)))}元，大于全账户领先，因为其他轮与错失机会抵消了一部分。具体订单序号见MATCHED_ACTUAL_ROUND_PATH_DELTAS及MATERIAL_STOCK_ACTUAL_ORDER_TRACES。",
    f"完整身份分解：同身份实际路径差额{n(atr['matched_actual_path_delta'])}元，减去未捕获原轮参考PnL{n(atr['unmatched_baseline_reference_PnL'])}元，加上候选新身份实际PnL{n(atr['candidate_new_actual_PnL'])}元，严格回到{n(r['delta']['NAV'])}元。这个代数式不是给过滤器记一笔虚构现金收益。",
    '',
    '## 老赢家额外回吐与新的ADD成本',
    f"**水井坊出现额外回吐**：10/8到10/10 M12回落{n(-D(shui['M12_oct8_to_end']))}元，对照回落{n(-D(shui['M7_oct8_to_end']))}元，多回吐{n(-D(shui['extra_oct8_to_end_delta']))}元。三个共同OPEN快照均H=true；M12累计ADD4次，原M7为2次。到10/10该轮M12净利3,833.45元，原M7 7,060.18元。",
    f"银之杰同段回吐{n(-D(silver['M12_oct8_to_end']))}元，对照{n(-D(silver['M7_oct8_to_end']))}元，没有额外回吐。常山北明期末同轮少赚2,971.76元，但10/8后是涨{n(chang['M12_oct8_to_end'])}元对原涨{n(chang['M7_oct8_to_end'])}元，属于少涨1,554元，不能写成这两天回吐。",
    '新扩张层也有代价：赢合科技同轮差额-5,790.94元（ADD2对0），天赐材料-5,034.02元（ADD3对2），璞泰来-4,297.70元（ADD3对1），均仍未平。健康是当时状态，不保证将来收益；本因子不是利润覆盖或亏损封顶。',
    '',
    '## 真实等待、融资与固定退让',
    f"已认证21次OPEN共评估29个分支；对应原N请求-日出现{sel['full_request_day_occurrences']}次，最终退让{sel['total_removed_request_day_occurrences']}次。不是1839个不同股票或永久删除。",
    f"CLOSE固定链删除1831次，9/25 OPEN再退8个；1839条等待/原拒绝日志对应699个原机会身份：1826条资金WAIT、13条原attempt_budget拒绝。699中只有1个在截止前后来成交，实际PnL -1,181.17元，其余尚未成交不应赋予虚构收益。",
    '9/25：full N=101，CLOSE留9个，OPEN只留1个且当日该新票没有成交；9/26、9/27、9/30、10/8、10/9分别退到空N。10/10保留2个N。逐计划全链、原D和shadow/final q/y均见明细。',
    f"真实融资卖单{fund['M12']['actual_donor_orders']}笔对{fund['M7']['actual_donor_orders']}笔，净筹资{n(fund['M12']['actual_funding_net'])}元对{n(fund['M7']['actual_funding_net'])}元，少{n(D(fund['M7']['actual_funding_net'])-D(fund['M12']['actual_funding_net']))}元；ADD实际买款{n(fund['M12']['actual_ADD_buy_cost'])}元对{n(fund['M7']['actual_ADD_buy_cost'])}元。",
    '保留原desired与整数预约残余；没有把TRANSFERS.M_actual_buy_cost误当全部买款。DAILY_CASH_DEMAND_EXPOSURE保留各日原D、实际买款、现金和融资记录。',
    '',
    '## 688200阻断：Q0保留票路径，不是坏持仓',
    '**两账户从未成交688200，也没有688200持仓或轮。** M12的9/26原A票仍pending+RETAINED，原M7则在10/8因为原尝试预算不够取消。',
    f"独立读同一封存行情并按dated费率复算：10/8 raw OPEN=129.60，200股按原滑点买价129.66480，费用{n(block['dated_fee'])}元，全款{n(block['all_in_cost'])}元。M7原预算{n(block['M7_original_budget'])}元，差{n(block['M7_shortfall'])}元；M12原预算{n(block['M12_original_budget'])}元，多{n(block['M12_headroom'])}元。两者都保持各自原signal日NAV和预算，差异来自此前真实账户路径，非重置预算或非法保活。",
    '10/11该原保留票仍属于原生preflight目标，遇除息/因子变化，而688200事件未进入这次冻结准入集合，原guard因此正确阻断。10/10登记持仓为0，不能产生任何股息权益。',
    '本地已存在精确公告/adapter的六份封存证据，独立事实审查通过；这解释缺口但没有倒改旧输入、补记旧交易或把新v2结果带入本报告。后续精确准入/新实验属于另一批准与封存。',
    '输出核验没有10/11订单、账本、OPEN选择、WAIT或partial commit；最后22份CLOSE簿、21份OPEN决定及待处理票一致。独立审查过的原子恢复源码绑定不变。未重放失败步骤，故不声称直接比较了失败瞬间的全部内存快照。',
    '',
    '## 审计覆盖与来源',
    f"- 所有{a['trading']['orders']}笔候选订单与{b['trading']['orders']}笔同窗基准订单：dated费用、整手、T+1、现金、权益、库存、NAV、清算NAV、行业与逐轮PnL独立复算。",
    '- 48个本窗有效已准入现金事件 × 两账户 = 96项核验，包括零持仓的缺失应计负空间。完整Jan20预设的534项在本次不可用，未伪称已审全期。',
    '- 367笔候选买入角色及1150条候选持仓角色，454笔原M7买入角色及1254条基准持仓角色，均按原M5取得时角色复核。',
    '- 7GB保存簿逐分支读取，22份book与2213个branch全部内容hash、原D/K/U/X/T/envelope/floor算术、身份、bar_q和固定末位退让通过。最大单branch原文约5.53MB，未整文件json.loads。',
    '- 全部CLOSE比较、21次共同OPEN锚点、29个OPEN投影逐健康lot/逐ADD-EVENT请求比较通过；CLOSE失败枝未OPEN复活，空N严格等于P0。',
    '- 1839条WAIT/原拒绝身份与预算保持、原preflight覆盖、实际订单绑定、CP/EVENT消费一次通过。预测prefix、q/y与实际结果偏离为0。',
    '- 完整来源与输出manifest通过，旧引擎SHA256：2e37d2a20e33760ffdb1b1b9ba84f8edce7492a3162880ba800759d8773cdd72。',
    '- 保存数字审计与独立静态/poison测试分层。单靠候选自报H/PASS不能证明数据来源无未来；原全日OHLC no_fill及输入非PIT限制保留。',
    '',
    '## 结果文件',
    '- INDEPENDENT_M12_VS_M7_PREFIX.json：账户、同窗、阻断和综合结论。',
    '- SAVED_FUNDING_SEMANTICS.json、FUNDING_PLAN_SELECTION_AUDIT、FUNDING_QUANTITY_COMPARISON：全分支审计及每项q/y。',
    '- FIXED_OPPORTUNITY_COMPARISON、STARTUP_19_STRONG_WINNER_PATHS、FIXED_MATURE_OPPORTUNITY_COSTS：固定原身份和错失代价。',
    '- MATCHED_ACTUAL_ROUND_PATH_DELTAS、HEALTHY_ROUND_GIVEBACK_PATHS、MATERIAL_STOCK_ACTUAL_ORDER_TRACES：真实增益与回吐。',
    '- ATOMIC_BLOCK_688200_CAUSE_AUDIT、ATOMIC_ROLLBACK_PREFIX_AUDIT：阻断及未部分提交证据。',
    '- FINAL_AUDIT_SEAL.json：本次报告、数据与审计源码hash。',
    '',
    '**经济判断：启动段出现可核实的收益改善，同时付出漏赢家与个别老赢家额外回吐的代价；由于10/11提前阻断，最重要的11/6后检验尚无答案。**',
    ]
    (O/'INDEPENDENT_READOUT.md').write_text('\n'.join(lines)+'\n')
    sources={p.name:au.sha(p) for p in O.glob('*.py')}
    au.save('FINAL_AUDIT_SEAL',dict(verdict=r['verdict'],scope='Only certified 22-session prefix through 2024-10-10; original frozen M12 run blocked 2024-10-11',engine_sha256=block.get('engine_sha256','2e37d2a20e33760ffdb1b1b9ba84f8edce7492a3162880ba800759d8773cdd72'),auditor_source_hashes=sources,candidate_output=r['candidate_output'],baseline=str(au.BASE),source_output_integrity=r['hashes'],files={p.name:au.sha(p) for p in O.iterdir() if p.is_file() and p.name!='FINAL_AUDIT_SEAL.json'},no_v2_results=True))
    seal=au.read(O/'FINAL_AUDIT_SEAL.json');assert all(au.sha(O/n)==h for n,h in seal['files'].items())
    print(json.dumps(dict(verdict=r['verdict'],report=str(O/'INDEPENDENT_READOUT.md'),report_sha256=au.sha(O/'INDEPENDENT_READOUT.md'),seal_sha256=au.sha(O/'FINAL_AUDIT_SEAL.json'),stream_auditor_sha256=au.sha(O/'audit_streamed_branches.py'),account_auditor_sha256=au.sha(O/'audit_partial_outputs.py')),ensure_ascii=False))
if __name__=='__main__':main()
