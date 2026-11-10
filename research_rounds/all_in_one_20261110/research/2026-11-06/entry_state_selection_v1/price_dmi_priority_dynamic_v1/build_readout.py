"""Final prose/tables from sealed saved reports only. No economic execution."""
from pathlib import Path
import json
from collections import Counter
import pandas as pd
from runtime import O,SOURCE,sha,read
from run_economic import save


def fmt(x,n=2):return 'UNKNOWN' if x is None else f'{x:,.{n}f}'
def pct(x):return 'UNKNOWN' if x is None else f'{100*x:.4f}%'
def change(a,b,formatter=fmt):return formatter(a)+' → '+formatter(b)
def table(lines,headers,rows):
    lines.append('| '+' | '.join(headers)+' |');lines.append('| '+' | '.join(['---']*len(headers))+' |')
    lines.extend('| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in rows);lines.append('')


def main():
    audit=read(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json')
    assert read(O/'independent_audit/FINAL_POSTERIOR_COMPLETION.json')['status']=='PASS_BOTH_WINDOWS_FINAL_POSTERIOR'
    for n,h in audit['reviewed_code_sha256'].items():assert sha(O/n)==h,('FROZEN_CODE_DRIFT',n)
    summaries={};round_metrics={};stocks={};cases={};post={};ranks={};final={}
    for w in ['2022','2024']:
        folder=O/('report_'+w)
        for n,h in read(folder/'OUTPUT_SHA256.json').items():assert sha(folder/n)==h
        for n,h in read(folder/'CASE_OUTPUT_SHA256.json').items():assert sha(folder/n)==h
        post[w]=read(O/'independent_audit'/('POSTERIOR_'+w+'.json'))
        assert post[w]['status']=='PASS_INDEPENDENT_POST_ECONOMIC_AUDIT'
        assert read(O/'independent_audit'/('SOURCE_BINDINGS_'+w+'.json'))['status']=='PASS_POSTERIOR_ACTUAL_SOURCE_BINDINGS_AND_FROZEN_ORIGINAL_SEAL'
        summaries[w]=read(folder/'SUMMARY.json');assert not summaries[w]['adapter_blockers']
        round_metrics[w]=read(folder/'ROUND_METRICS.json');stocks[w]=read(folder/'STOCK_METRICS.json')
        cases[w]=read(folder/'REQUESTED_STOCK_CASES.json');ranks[w]=read(O/('dmi_'+w)/'DMI_RANK_AUDIT.json')
        complete=read(O/('dmi_'+w)/'COMPLETE_SAVED_SNAPSHOT.json')
        assert complete['output_seal_sha256']==sha(O/('dmi_'+w)/'OUTPUT_SEAL.json')
        for n,h in read(O/('dmi_'+w)/'OUTPUT_SEAL.json').items():assert sha(O/('dmi_'+w)/n)==h
        assert (O/('DMI_RUN_ONCE_'+w+'.json')).exists()
        final[w]=dict(economic_executions=1,complete=complete,pre_baseline_exact_sha256=sha(O/('baseline_exact_'+w)/'EXACT_QA.json'),posterior_audit_sha256=sha(O/'independent_audit'/('POSTERIOR_'+w+'.json')),source_binding_sha256=sha(O/'independent_audit'/('SOURCE_BINDINGS_'+w+'.json')))
    def metric(w,arm,cohort='ALL_FIXED_1709',lane='ALL',role='FIRST_PROBE_INDEPENDENT_DATED_FEES'):
        return next(r for r in round_metrics[w] if r['arm']==arm and r['cohort']==cohort and r['lane']==lane and r['role']==role and r['coverage_filter']=='FINANCIALLY_COVERED_CLOSED')
    def stock(w,arm,cohort='ALL_FIXED_1709'):
        return next(r for r in stocks[w] if r['arm']==arm and r['cohort']==cohort)
    lines=['# 固定 PRICE 槽内 DMI 优先序：两窗逐股动态验证','',
      '## 结论','',
      '在这两个已经看过的开发窗口里，DMI 排序相对原联合 PVR 排序的共同可比股票全轮净额增量均为正：2022 +11,765.24 元，2024 +113,936.48 元。但不构成全面改善，更不能称为全账户收益。',
      '2022 用户熟悉的独立首仓口径胜率由 28.8932% 微降到 28.8140%，每轮亏损仅缩小 4.51 元；2024 胜率由 46.4266% 到 46.8698%，每轮净额增 21.51 元，但盈亏比由 3.1311 微降到 3.1198。2024 的共同股票全轮增量更明显，仍伴随 AB 通道净额下降和具体赢家被延后。',
      '因此，这次验证支持“该排序确实改变了动态机会与经济路径，且两个固定窗口的共同股净额为正增量”，不支持“普遍提高胜率、稳定显著优于原版、可以直接替代生产或代表真实账户”。没有按结果修改公式、选参或重跑。','',
      '## 唯一变动与不变边界','',
      '- 原对照是 A+B+PRICE 联合策略，不是 AB-only。两侧相同逐股责任、预算 24,000/48,000 元、风险 3,000 元、5bp、dated lot/fee、权益与 NET80、保护、PROBE/CONFIRMED 和止损后新证重入。',
      '- 每个动态当日真实可行同行业队列先用原 PVR key 建立数字槽；AB 全部锁槽；只将 d 与原 PVR 均 known 的 PRICE 身份按 (-d, -PVR, sid) 放回其原 PRICE 数字槽；UNKNOWN 保持原位，仍 rank≤2。没有 d>0 或 ADX 门禁，没有新退出。',
      '- DMI 用冻结 Wilder 竞争 DM、N=14、首 14 变化 SMA 后 RMA(1/14)，d=(A−B)/(A+B)，严格零分母为 0，缺失/无效/来源段断开重启，UNKNOWN 不填 0。完整前缀从 2013 开始，不跨 2026-05-18 切源续接。',
      '- 全部 37,456 PRICE 市场 receipts 已补特征：2022 24,733 张、2024 12,723 张，联合 1,628 股，全部 d known。原 6,528 静态候选的 13 个 DMI 输出列 exact 不变。其余固定股票没有这两窗的 PRICE receipt，并未被排除出 1,709 股报告。','',
      '## 用户熟悉口径：联合全通道独立首仓','',
      '固定 1,709 股内，采用有实际买入、首仓独立 dated fee、闭合净额已知且权益覆盖的回合。胜率分母是下表闭合轮数，不是所有发信、所有已进入轮数或股票数。UNKNOWN/未闭合不补零。盈亏比=平均盈利/平均亏损绝对值；利润因子=盈利总和/亏损总和绝对值。','']
    rows=[]
    for w in ['2022','2024']:
        b,j=metric(w,'baseline'),metric(w,'joint')
        rows.append([w,change(b['known_count'],j['known_count'],lambda x:str(x)),change(b['win_rate'],j['win_rate'],pct),change(b['net_per_known_unit'],j['net_per_known_unit']),change(b['payoff_mean_win_over_abs_mean_loss'],j['payoff_mean_win_over_abs_mean_loss'],lambda x:fmt(x,4)),change(b['profit_factor'],j['profit_factor'],lambda x:fmt(x,4))])
    table(lines,['窗口','闭合轮数 旧→新','胜率 旧→新','每轮净额/元 旧→新','盈亏比 旧→新','利润因子 旧→新'],rows)
    lines+=['## 严格共同可比股票：全轮主比较','', '这里要求同一股票在旧、新两侧均无 UNKNOWN 总额且财务覆盖；包含共同集合内明确未进入的零结果。金额是各股票所有回合的条件净额。两窗单独报告，不相加为一条账户曲线。','']
    rows=[]
    for w,s in summaries.items():rows.append([w,s['common_comparable_stocks'],fmt(s['old_net_common']),fmt(s['new_net_common']),fmt(s['common_delta']),fmt(s['common_lane_deltas']['PRICE']),fmt(s['common_lane_deltas']['AB'])])
    table(lines,['窗口','共同股票','旧联合净额','新联合净额','净增量','PRICE 新−旧','AB 新−旧'],rows)
    lines+=['共同股票的独立首仓口径也单列，不能用它替换上面的全 1,709 股闭合首仓口径：','']
    rows=[]
    for w in ['2022','2024']:
        b,j=metric(w,'baseline','COMMON_COMPARABLE_STOCKS'),metric(w,'joint','COMMON_COMPARABLE_STOCKS')
        rows.append([w,change(b['known_count'],j['known_count'],str),change(b['win_rate'],j['win_rate'],pct),change(b['net_per_known_unit'],j['net_per_known_unit']),change(b['payoff_mean_win_over_abs_mean_loss'],j['payoff_mean_win_over_abs_mean_loss'],lambda x:fmt(x,4))])
    table(lines,['窗口','首仓闭合轮数','首仓胜率','首仓每轮净额','首仓盈亏比'],rows)
    lines+=['## 全轮与 PRICE 子通道','', '全部为权益覆盖的已知闭合轮。FULL 包含真实发生的加仓与该轮整体现金/权益；独立首仓与 FULL 不是同一个经济口径。完整 48 组/窗指标保存在 ROUND_METRICS.json。','']
    rows=[]
    for w in ['2022','2024']:
        for cohort,label in [('ALL_FIXED_1709','全固定股'),('COMMON_COMPARABLE_STOCKS','共同股')]:
            for lane in ['ALL','PRICE']:
                b,j=metric(w,'baseline',cohort,lane,'FULL_ROUND'),metric(w,'joint',cohort,lane,'FULL_ROUND')
                rows.append([w,label,lane,change(b['known_count'],j['known_count'],str),change(b['win_rate'],j['win_rate'],pct),change(b['net_per_known_unit'],j['net_per_known_unit']),change(b['payoff_mean_win_over_abs_mean_loss'],j['payoff_mean_win_over_abs_mean_loss'],lambda x:fmt(x,4)),change(b['profit_factor'],j['profit_factor'],lambda x:fmt(x,4))])
    table(lines,['窗口','股票范围','通道','全轮闭合数','全轮胜率','全轮每轮净额','全轮盈亏比','全轮利润因子'],rows)
    rows=[]
    for w in ['2022','2024']:
        b,j=metric(w,'baseline',lane='PRICE'),metric(w,'joint',lane='PRICE')
        rows.append([w,change(b['known_count'],j['known_count'],str),change(b['win_rate'],j['win_rate'],pct),change(b['net_per_known_unit'],j['net_per_known_unit']),change(b['payoff_mean_win_over_abs_mean_loss'],j['payoff_mean_win_over_abs_mean_loss'],lambda x:fmt(x,4))])
    table(lines,['窗口','PRICE独立首仓闭合数','PRICE首仓胜率','PRICE首仓每轮净额','PRICE首仓盈亏比'],rows)
    lines+=['## 全部分母、UNKNOWN 与参与尾部','']
    rows=[]
    for w in ['2022','2024']:
        b,j=stock(w,'baseline'),stock(w,'joint')
        rows.append([w,change(b['entered_stocks'],j['entered_stocks'],str),change(b['never_entered_stocks'],j['never_entered_stocks'],str),change(b['unknown_stocks'],j['unknown_stocks'],str),change(b['financial_uncovered_stocks'],j['financial_uncovered_stocks'],str),change(b['repeated_participation_stocks'],j['repeated_participation_stocks'],str)])
    table(lines,['窗口/固定1709股','实际参与股','明确未进入股','UNKNOWN股','权益未覆盖股','参与多轮股'],rows)
    lines+=['实际参与股与明确未进入股不会强行加到 1,709：存在未确认买入却仍有 UNKNOWN 责任的股票。UNKNOWN 主集合来自 stock liability，并与轮状态及执行簿在途责任逐项对账，两窗差异均为零。两侧均没有 OPEN_CENSORED，但仍有未知责任。','',
      '以下尾部分位数是共同股票范围内“当侧实际参与且总额已知”的逐股所有回合净额；当侧参与股分母可以不同。它不是逐轮分布，也不是只挑盈利回合。全固定股分布与全部逐股记录另存。','']
    rows=[]
    for w in ['2022','2024']:
        for arm,label in [('baseline','旧PVR'),('joint','新DMI')]:
            x=stock(w,arm,'COMMON_COMPARABLE_STOCKS')['known_participant_distribution'];q=x['quantiles']
            rows.append([w,label,x['known_count'],fmt(q['0.01']),fmt(q['0.05']),fmt(q['0.5']),fmt(q['0.9']),fmt(q['0.95']),fmt(q['0.99']),fmt(q['1'])])
    table(lines,['窗口','臂','已知参与股数','P01','P05','中位数','P90','P95','P99','最大值'],rows)
    lines+=['尾部没有全面改善：共同集合内实际参与股分母 2022 为 993→995、2024 为 1370→1372；2024 P05 −3,649.32→−3,839.24 恶化，P95 13,760.51→13,444.46 下移；2022 P95 9,317.64→9,247.51、P99 23,769.37→23,242.81 也下移。各臂的已参与股票分布不是同一闭合轮样本。','', '## 槽位挤占、AB 路径和动态域覆盖','']
    rows=[]
    for w,s in summaries.items():
        z=[r for r in ranks[w] if r['owner_lane']=='PRICE'];p=post[w]['rank']
        old=pd.read_csv(SOURCE/('economic_'+w)/'joint/ROUNDS.csv');new=pd.read_csv(O/('dmi_'+w)/'joint/ROUNDS.csv')
        ob=int(old.owner_lane.eq('AB').sum());nb=int(new.owner_lane.eq('AB').sum());ret=s['retained_ab_path_exact']['retained_events']
        rows.append([w,len(ranks[w]),len(z),p['new_price_feasible_keys_vs_static'],sum(r['dmi_selected'] and not r['original_selected'] for r in z),sum(not r['PVR_known'] for r in z),sum(r['dmi_selected'] and not r['PVR_known'] for r in z),f'{ob}→{nb}',ret])
    table(lines,['窗口','动态可行总行','PRICE行','旧静态域外PRICE键','当日队列换入槽身份','PVR未知PRICE行','PVR未知获槽','AB获槽旧→新','保留AB事件'],rows)
    lines+=['两窗所有 AB 数字槽与 UNKNOWN 数字槽移动数均为 0，行业当日 PRICE 名额不变。然而持仓路径先改变后，会改变未来哪些 AB 可竞争、哪些同股请求被已有 PRICE/UNKNOWN 阻塞。因此 AB 实际进入事件集合允许不同；这不是锁槽失效。保留的同一 AB 事件的所有动作字段、权益经济字段和退出结果独立 exact 通过。',
      'AB 通道净额的变化包含新增、丢失和延后路径，不全部称为“直接挤占”。逐请求原因、blocking round 和原/新结果见 REQUEST_DISPLACEMENT.json。','']
    for w,s in summaries.items():
        u=s['unknown'];lines.append(f"- {w}：UNKNOWN {u['old']}→{u['new']}，新变未知 {len(u['newly_unknown'])} 股，解除未知 {len(u['no_longer_unknown'])} 股。新变未知：{', '.join(u['newly_unknown'])}。解除：{', '.join(u['no_longer_unknown'])}。")
    lines+=['','## 共同可比净额改善/恶化各前五','', '公司名称取冻结名单，股票代码作为稳定身份。完整真实进入/退出顺序与后续参与见逐窗 REQUESTED_STOCK_CASES.md/json。','']
    for w in ['2022','2024']:
        for key,label in [('improved_top5','改善前五'),('worsened_top5','恶化前五')]:
            lines+=['### '+w+' '+label,''];rows=[]
            for c in cases[w][key]:
                d=c['difference'];rows.append([c['name']+' '+c['sid'],fmt(c['old_stock']['known_total_pnl']),fmt(c['new_stock']['known_total_pnl']),fmt(d['joint_minus_baseline']),str(c['old_participation']['entered_rounds'])+'→'+str(c['new_participation']['entered_rounds']),fmt(d['lane_contributions']['AB']),fmt(d['lane_contributions']['PRICE'])])
            table(lines,['股票','旧净额','新净额','差额','轮数','AB差','PRICE差'],rows)
    lines+=['## 指定股票：真实动态结果，不沿用静态标签','']
    for w in ['2022','2024']:
        lines+=['### '+w,'']
        for c in cases[w]['named_cases']:
            d=c['difference'];lines.append(f"- {c['name']} {c['sid']}：{change(c['old_stock']['known_total_pnl'],c['new_stock']['known_total_pnl'])} 元，差额 {fmt(d['joint_minus_baseline'])}；轮数 {c['old_participation']['entered_rounds']}→{c['new_participation']['entered_rounds']}。AB 差 {fmt(d['lane_contributions']['AB'])}，PRICE 差 {fmt(d['lane_contributions']['PRICE'])}。")
            for arm,label in [('baseline','旧'),('joint','新')]:
                dates=[r['owner_lane']+' '+str(r['entry_day'])[:10] for r in c['actual_entered_paths'][arm]]
                lines.append('  - '+label+'实际进入：'+('；'.join(dates) if dates else '未进入'))
        lines.append('')
    lines+=['2024 拓尔思从 PRICE 转为次日 AB；拓斯达与机器人是延后首次 PRICE 接入，但少赚约 10,002.79 / 7,294.46 元。2024 四只指定股票在新臂都只有一次实际进入；不能把“旧臂入场日期之后仍观察到新臂入场”称为新臂止损后重入，也不能当作原机会已完全挽回。歌尔 2024 换成较晚 AB 后少亏 630.28 元；2022 两边都停在未准入权益 UNKNOWN，不能编造总净额。','',
      '语义澄清：原 v1 病例中的“之后新轮再次参与”只表示两臂入场日期的比较，不证明同一新臂曾退出后再入。v1 文件与其 seal 保留，准确解释以 independent_audit/CASE_SEMANTIC_NOTE.json 及本报告为准。','', '## 执行次数、审查与证据','',
      '- 原联合基线每窗各实际执行一次，2022 4,127 轮/9,611 动作，2024 1,950 轮/4,647 动作；全列、顺序、NaN、数值与原保存输出 exact，权益尾部/执行簿同样 exact。最初系统解释器缺 parquet 依赖的两次准备失败未进入经济循环，原证据保留。',
      '- 基线末尾仅因两个符号链接逻辑路径的字典查键发生后处理错误。账本已完整保存；按原 verify_inputs 的 resolve 规则旁路恢复 QA，一对一映射、inode 与 hash 均独立认证。没有重新执行循环或放松数值比较。',
      '- 新 DMI 各窗只执行一次。独立审计、授权与输入锁在运行前通过；运行后再次核源码/输入/协议/授权；原账本、排序审计、完整 OUTPUT_SEAL 和完成标记均保存。后验报告与病例不调用经济消费者。',
      '- 独审重构每个动态队列、核对所有新动态可行候选特征、dated fee/T+1、现金/权益 NET80、保留 AB event、UNKNOWN、全部 48 组回合指标及逐股尾部，两个窗口均 PASS。冻结 v3 八份源码未改。','']
    table(lines,['窗口','新回合/动作','新完整快照seal','后验审查'],[[w,f"{read(O/('dmi_'+w)/'ECONOMIC_LOOP_COMPLETE.json')['rounds']}/{read(O/('dmi_'+w)/'ECONOMIC_LOOP_COMPLETE.json')['actions']}",final[w]['complete']['output_seal_sha256'],post[w]['status']] for w in ['2022','2024']])
    lines+=['## 限制与下一步边界','',
      '1. 静态 1,709 名单、此前见过的开发数据与权益场景不是严格 PIT/盲测。本次没有增加新窗口，不因结果扫描参数。',
      '2. 执行是 conditional next-common OPEN full-fill 代理。真实订单、ACK、成交、历史可交易性没有得到验证；涨跌停、流动性、部分成交等不能从代理收益推断。',
      '3. 每股独立责任账没有共享现金账户约束。表中逐股金额求和不是 120 万账户收益率，也不是投资回报承诺。',
      '4. 2022 出生为全年，2024 出生为 9–12 月，持仓/权益尾部与原基线同到 2026-06-30；没有扩展 2026 出生经济。',
      '5. 两窗共同股净额正增量只是本次固定对照观察。UNKNOWN 与覆盖变化、收益尾部和具体赢家代价都保留，不能据此宣称全面提高选择质量或自动上线。','',
      '## 文件索引','',
      '- `DYNAMIC_PROTOCOL.json`：唯一数学/经济合同；`REVIEW_CODE_SHA256_v3.json`：冻结八源码。',
      '- `features/`：全候选特征、来源、前缀/旧特征回归及封存。',
      '- `baseline_exact_2022/`、`baseline_exact_2024/`：原联合一次回归及 exact QA。',
      '- `dmi_2022/`、`dmi_2024/`：唯一新臂完整保存账、排序审计和快照seal。',
      '- `report_2022/`、`report_2024/`：主比较、48组回合指标、全部逐股参与、逐请求挤占、所需病例。',
      '- `independent_audit/`：两窗保存账与后验/来源绑定审计。','']
    with (O/'READOUT.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    save(O/'FINAL_RUN_SEAL.json',dict(status='COMPLETE_TWO_FIXED_DMI_DYNAMIC_COMPARISONS_POST_AUDIT_PASS',readout_sha256=sha(O/'READOUT.md'),readout_builder_sha256=sha(__file__),case_script_sha256=sha(O/'cases_saved.py'),frozen_code_sha256=audit['reviewed_code_sha256'],frozen_input_manifest_sha256=sha(O/'REVIEW_INPUT_SHA256.json'),authorization_sha256=sha(O/'ROOT_DMI_AUTHORIZATION.json'),pre_audit_sha256=sha(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json'),final_posterior_audit_sha256=sha(O/'independent_audit/FINAL_POSTERIOR_COMPLETION.json'),case_semantic_note_sha256=sha(O/'independent_audit/CASE_SEMANTIC_NOTE.json'),windows=final,no_parameter_scan=True,no_extra_window=True,no_account_return_claim=True,new_economic_runs_per_window=1))
    print('FINAL_READOUT_READY',sha(O/'READOUT.md'),flush=True)
if __name__=='__main__':main()
