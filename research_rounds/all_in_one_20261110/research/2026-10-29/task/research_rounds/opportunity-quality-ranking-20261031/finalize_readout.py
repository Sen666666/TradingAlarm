"""Finalize saved read-only statistics; never load a strategy/account runner."""
from pathlib import Path
import csv
import hashlib
import json

O = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_atomic(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(value)
    tmp.replace(path)


def pct(x):
    return 'N/A' if x is None else f'{x:.2f}'


def main():
    all_rows, comparisons, summaries = [], [], {}
    for win in ['2022', '2025_26']:
        den = read(O / win / 'DENOMINATORS.json')
        assert sha(O / win / 'CANDIDATES.jsonl.gz') == den['candidate_file_SHA256']
        assert den['all_original_fresh_receipts'] == den['candidates'] + sum(den['exclusion_counts'].values())
        for variant in ['all_events', 'first_stock_attempt_within_window', 'first_complete_attempt']:
            for h in [21, 63]:
                s = read(O / win / variant / f'SUMMARY_{h}.json')
                summaries[win, variant, h] = s
                assert sum(q['events'] for q in s['H1_quintiles'].values()) == s['market']['events']
                groups = {'market_ALL': s['market']}
                groups.update({f'H1_Q{q}': v for q, v in s['H1_quintiles'].items()})
                for ref, a in s['accounts'].items():
                    assert a['selected']['events'] + a['not_selected']['events'] == s['market']['events']
                    if variant == 'all_events':
                        assert a['selected']['events'] == den['selected'][ref]['events']
                    groups.update({f'{ref}_{label}': a[label] for label in ['selected', 'not_selected', 'ACT_paused_candidates', 'ACT_unpaused_candidates']})
                    comparisons.append(dict(window=win, variant=variant, horizon=h,
                                            comparison=ref + '_selected_minus_not', **a['matched_selected_minus_not']))
                for group, v in groups.items():
                    row = {k: v.get(k) for k in [
                        'events', 'unique_stocks', 'candidate_dates', 'labelled_events', 'labelled_dates',
                        'censored', 'event_mean_pct', 'event_median_pct', 'positive_fraction',
                        'mean_positive_pct', 'mean_negative_pct', 'MAE_mean_pct', 'MFE_mean_pct',
                        'right_tail_fraction', 'date_equal_mean_pct', 'date_equal_positive_fraction',
                        'date_equal_right_tail_fraction', 'mean_calendar_days']}
                    row['censored'] = json.dumps(row['censored'], sort_keys=True)
                    all_rows.append(dict(window=win, variant=variant, horizon=h, group=group, **row))
                # ALL FIVE groups must coexist, including on the first-candidate versions.
                qs = s['H1_quintiles']
                days = sorted(set.intersection(*(set(q['daily']) for q in qs.values())))
                left = [qs['1']['daily'][d]['mean_pct'] for d in days]
                right = [qs['5']['daily'][d]['mean_pct'] for d in days]
                delta = [a-b for a, b in zip(left, right)]
                import statistics as st
                comparisons.append(dict(window=win, variant=variant, horizon=h,
                    comparison='H1_Q1_minus_Q5_ALL_FIVE_COMMON_DATES', common_dates=len(days),
                    left_date_equal_mean_pct=st.mean(left) if left else None,
                    right_date_equal_mean_pct=st.mean(right) if right else None,
                    mean_same_day_difference_pct=st.mean(delta) if delta else None,
                    median_same_day_difference_pct=st.median(delta) if delta else None,
                    days_left_mean_higher_fraction=st.mean(x > 0 for x in delta) if delta else None))
    for name, rows in [('METRICS_ALL_GROUPS.csv', all_rows), ('MATCHED_COMPARISONS.csv', comparisons)]:
        from io import StringIO
        f = StringIO()
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        write_atomic(O / name, f.getvalue())
    write_atomic(O / 'PRIMARY_SAME_DAY_COMPARISONS.json', json.dumps(comparisons, ensure_ascii=False, indent=2) + '\n')
    match = {(r['window'], r['variant'], r['horizon'], r['comparison']): r for r in comparisons}
    text = [
        '机会质量／H1排序／实际资金选择：只读诊断｜2026-10-31',
        '范围：固定2022及2025-07-01至2026-06-30；0条新账户路径，0项交易规则变更。',
        '',
        '候选和统计口径',
        '候选=当日原生fresh canonical stock CP1 + 原continuing个股Q通过 + 原行业confirmed/expanded attempt有效且authorization_usable。两账的市场Q、canonical CP1、H1顺序逐项一致。',
        '原Q保留market-buyable、I有效、company_cap_cny>100亿元、issuer/sector/H1/行业状态就绪等原条件；不额外要求fresh I、当天行业新CP1、绝对收益正或Top3。自身持仓/core锁/pending/cash/预算及ACT不筛掉共同机会。',
        '“获资”仅指同股／授权日／canonical receipt随后有实际confirmed-pool mobile买入；预留未成、probe mobile、core迁池均不算。标签和同日分组用授权日而非成交日。相同授权日core/probe另标，不把未获confirmed说成绝对未参与。',
        '21观察为主，63为补充。授权收盘作锚，随后k个同源segment有效复权收盘；终值收益、MAE/MFE均为收盘价格标签，MAE/MFE含0基线；右尾=MFE>=30%。不含费用、成交可得性或实际保护退出，不是政策收益或可交易胜率。',
        '先冻结候选／每日H1五等分后才算标签。Q1最高，代码固定并列；每日numpy.array_split，N<5允许空档。H1主比较仅五档同时非空的共同日期，逐日等权；获资比较只在当天两组都存在时逐日等权，非不同日期池化均值。',
        'first_stock_attempt_within_window每股×原行业attempt仅取窗内首候选，保留原日五档、不重排；继承历史attempt左删失另记，first_complete_attempt再剔除继承attempt。去重仍不是独立试验，前向窗口高度重叠。',
        ''
    ]
    for win in ['2022', '2025_26']:
        d = read(O / win / 'DENOMINATORS.json')
        text += [f"{win}分母：原fresh {d['all_original_fresh_receipts']}；排除{d['exclusion_counts']}；合格{d['candidates']}事件／{d['unique_stocks']}股／{d['candidate_dates']}日。",
                 f"窗内每股×attempt首候选{d['first_stock_attempt_in_window']}，其中继承左删失{d['first_inherited_left_censored']}；完整新attempt首候选{d['first_complete_attempt']}。实际confirmed新买B3={d['selected']['B3']['events']}，Bdiag={d['selected']['B_diag']['events']}。"]
    text += ['', '21观察主表（事件等权；百分数）',
             '窗口 | 事件/股/日 | 均值 | 中位 | 正收益比例 | 平均正/平均负 | +30%MFE比例 | 平均MAE/MFE | 日期等权均值']
    for win in ['2022', '2025_26']:
        m = summaries[win, 'all_events', 21]['market']
        text.append(f"{win} | {m['events']}/{m['unique_stocks']}/{m['candidate_dates']} | {pct(m['event_mean_pct'])} | {pct(m['event_median_pct'])} | {pct(100*m['positive_fraction'])} | {pct(m['mean_positive_pct'])}/{pct(m['mean_negative_pct'])} | {pct(100*m['right_tail_fraction'])} | {pct(m['MAE_mean_pct'])}/{pct(m['MFE_mean_pct'])} | {pct(m['date_equal_mean_pct'])}")
    text += ['', '21观察H1同日五档（五档共存日期等权；Q1→Q5）']
    for win in ['2022', '2025_26']:
        c = summaries[win, 'all_events', 21]['common_quintile_dates']
        text.append(f"{win}：{c['common_dates']}日；" + '/'.join(pct(c['date_equal_means_pct'][str(q)]) for q in range(1, 6)) + '%。')
    text += ['2022 Q1虽有10.47%右尾窗口（Q5 3.74%），平均负幅度亦-12.11%（Q5 -8.29%）；不能把净收益无优势误写成完全没有尾部识别。',
             '', '21观察实际获资−同日未获资（逐日等权；百分点）',
             '窗口 | 参考 | 同日数 | 获资/未获资均值 | 差 | 日差中位 | 获资较好日占比']
    for win in ['2022', '2025_26']:
        for ref in ['B3', 'B_diag']:
            a = match[win, 'all_events', 21, ref + '_selected_minus_not']
            text.append(f"{win} | {ref} | {a['common_dates']} | {pct(a['left_date_equal_mean_pct'])}/{pct(a['right_date_equal_mean_pct'])} | {pct(a['mean_same_day_difference_pct'])} | {pct(a['median_same_day_difference_pct'])} | {pct(100*a['days_left_mean_higher_fraction'])}%")
    text += ['', 'ACT与“未获资”边界']
    for win in ['2022', '2025_26']:
        s = summaries[win, 'all_events', 21]
        for ref, a in s['accounts'].items():
            p = a['ACT_paused_candidates']
            text.append(f"{win}/{ref}：ACT收盘暂停候选{p['events']}／{p['candidate_dates']}日；有候选但无任何候选receipt后来获confirmed成交的授权日{a['all_candidate_dates_without_any_confirmed_fill']}；未获confirmed但同receipt有probe mobile={a['unselected_but_probe_mobile_funded_events']}，同股同授权日有core={a['unselected_but_same_stock_core_funded_events']}（后两者可重叠，不相加）。")
    text += ['ACT标记为授权日账本收盘on状态，非开盘状态或每一意图瞬时ACT状态；2022 Bdiag总暂停39个账户收盘，其中32日有1965候选，全部保留。这些候选21观察均值+5.94%，仅说明暂停期间仍存在后视价格机会，不能据此推断取消ACT的账户收益。',
             '', '首候选去重：21观察（同日差；百分点）',
             '窗口/版本 | 事件 | 机会事件均值 | H1 Q1−Q5/五档共同日 | B3差/共同日 | Bdiag差/共同日']
    for win in ['2022', '2025_26']:
        for variant in ['first_stock_attempt_within_window', 'first_complete_attempt']:
            s = summaries[win, variant, 21]
            a = [match[win, variant, 21, x] for x in ['H1_Q1_minus_Q5_ALL_FIVE_COMMON_DATES', 'B3_selected_minus_not', 'B_diag_selected_minus_not']]
            text.append(f"{win}/{variant} | {s['market']['events']} | {pct(s['market']['event_mean_pct'])} | " + ' | '.join(f"{pct(x['mean_same_day_difference_pct'])}/{x['common_dates']}" for x in a))
    text += ['B3去重后2022差为正而全事件为负，且仅22/29个共同日，不能把Bdiag结论套给所有资金政策。正样本Bdiag全事件均值优势由较大上涨拉动，日差中位仍为负；“多数日期更好”和“平均更好”不同。',
             '', '63观察补充（不据此选尺度）',
             '窗口 | 候选事件均值/中位/正收益%/右尾% | H1最高−最低同日差 | B3获资差 | Bdiag获资差']
    for win in ['2022', '2025_26']:
        m = summaries[win, 'all_events', 63]['market']
        a = [match[win, 'all_events', 63, x] for x in ['H1_Q1_minus_Q5_ALL_FIVE_COMMON_DATES', 'B3_selected_minus_not', 'B_diag_selected_minus_not']]
        text.append(f"{win} | {pct(m['event_mean_pct'])}/{pct(m['event_median_pct'])}/{pct(100*m['positive_fraction'])}/{pct(100*m['right_tail_fraction'])} | " + ' | '.join(pct(x['mean_same_day_difference_pct']) for x in a))
    text += ['', '证据裁决与停止边界',
             '① 2022候选总体比2025—26弱：21观察终值均值负、中位更负，日期等权亦负。但2022首候选去重后事件均值转正（+0.35%；完整新attempt +1.33%），不能说当时没有好机会，也不能以重复receipt作独立样本扩大确信。',
             '② 2022 H1五档没有稳定净优势，Bdiag实际获资相对同日未获资更弱且两种去重仍同向；2025—26 H1和Bdiag的均值优势则存在。支持研究选择/资金分配的状态依赖，不足以把差额全部归H1排序：选中是自身持仓/锁/ACT/预算/合法执行共同结果，并非随机分配。没有统计显著性或独立样本主张。',
             '③ 价格MFE只表潜力，无法识别保护退出能否保住利润。已获资2022前向终值较弱，反对把全部亏损简单归过早退出；仍不能据这些固定窗口标签估算换仓/持有政策收益。禁止未来标签回流信号、筛最优回看期或全知换仓。',
             '', '价格源、删失及工程证据',
             '同源归档signal.parquet的原eligible_prices复权close；1659股逐个验证原缓存声明截至2026-06-30的close与segment完全一致。用原signal未来尾至2026-10-22等实际可得日期计算标签，21/63两窗均实际完整、censored=0；这是查得结果，不是变长终点/缺失补值。',
             '部分复用407参考facts有2026-10-23/26/27额外尾，超出该缓存声明日期。首次全文件比较因此拒绝；extra-reference-tail-alignment.log保留。最终只核声明共同前缀，标签统一原signal源，未混用额外尾或改信号。PRICE_SOURCE_AUDIT.json逐股保存hash、声明日期和忽略尾行数。',
             '候选冻结11.29秒；读取同源价格和标签26.92秒；汇总1.25秒；主要实际计算合计39.46秒。未新建指标、未重算I/CP1/状态、未跑账户。当前没有数据/权限/连接阻塞。',
             '局限：今日snapshot母体及映射非PIT、历史已消费；同股/同日/前向区间高度相关；标签不含执行/费用/保护退出。未获confirmed不等于未持有该股或绝对未参与。当前两参考未获实盘认证。',
             '', '文件：PROTOCOL.txt、CANDIDATE_FREEZE.json、LABEL_FREEZE.json、PRICE_SOURCE_AUDIT.json；两窗CANDIDATES/PRICE_LABELS.jsonl.gz；METRICS_ALL_GROUPS.csv（完整五档/选择/ACT及去重21/63统计）、MATCHED_COMPARISONS.csv、PRIMARY_SAME_DAY_COMPARISONS.json、各窗各版本SUMMARY_21/63.json。',
             '原SUMMARY的内嵌Q1_minus_Q5采用仅Q1/Q5交集；去重时可能不同于五档共同日。本READOUT及PRIMARY_SAME_DAY_COMPARISONS明确使用五档共同日，原文件保留不覆盖。',
             '下一决策由主审基于机会总体与同日选择两层证据定合同；此轮至此收口，不自动改排序/退出/风险，不新增账户路径。']
    write_atomic(O / 'READOUT.txt', '\n'.join(text) + '\n')
    manifest = {}
    for pattern in ['*.py', '*.txt', '*.csv', '*.json', '*/*.jsonl.gz', '*/*.json', '*/*/SUMMARY_*.json']:
        for p in O.glob(pattern):
            if p.name != 'FINAL_EVIDENCE.json': manifest[str(p.relative_to(O))] = sha(p)
    write_atomic(O / 'FINAL_EVIDENCE.json', json.dumps(dict(readonly=True, new_account_paths=0,
        all_candidate_price_labels=29938, unique_price_series=1659,
        no_policy_changes=True, no_remaining_execution_blocker=True, SHA256=manifest), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(metrics_rows=len(all_rows), matched_rows=len(comparisons),
        readout_SHA256=sha(O/'READOUT.txt'), final_evidence_SHA256=sha(O/'FINAL_EVIDENCE.json'))))


if __name__ == '__main__':
    main()
