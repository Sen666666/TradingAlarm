"""Report only saved thin-analysis results and bind later independent receipts."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib
O=Path(__file__).resolve().parent;T=O.parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n')
def num(v,d=2):return f'{D(str(v)):.{d}f}'
arms=['B','UNIFORM50','A_ONLY','A_OR_B'];s={w:read(O/f'full_{w}_v1/SUMMARY.json') for w in ['long','strong']};per=read(O/'full_long_v1/ALL_PERIODS.json');ph=read(O/'full_long_v1/FIXED_PHASE_WEALTH.json');coverage=read(O/'ORIGINAL_B_BUY_CONFIRMATION_COVERAGE.json')['totals']
F=T/'independent_review/trend_confirmation_full_ledger_v1/FULL_TWO_WINDOWS_FINANCE_PVR_CA_AUDIT.json';L=T/'independent_review/trend_actual_consumption_v1/FINAL_ACTUAL_CONSUMPTION_REVIEW_INDEX.json'
scope=dict(financial_receipt=str(F),financial_SHA256=sha(F),financial_status=read(F)['status'],logic_receipt=str(L),logic_SHA256=sha(L),logic_status=read(L)['status'],long_exact_math='FAIL11_KEYS26_MULTIPLIER_INTENTS; 3 actual filled orders',strong_exact_math='FAIL9_KEYS11_MULTIPLIER_INTENTS; 0 actual reserve/fill hits',total_exact_boundary_keys=20,total_multiplier_differences=37,corrected_whole_account_counterfactual='NOT_RUN_NOT_PROVEN_IDENTICAL',supersedes='Earlier protocol/analysis SOURCE_BINDING strict_math referred only to then-complete strong 9keys/11m/0reserve. Applying that wording to long is incorrect. Original outputs retained as history; this new addendum is controlling.',economic_scope='Report actual frozen pandas implementation only; no corrected-math profit, no causal economic effect of the mismatch demonstrated.',derived_statistics_review='PENDING, original financial independent PASS does not automatically certify new reporting groups.')
save(O/'FINAL_REVIEW_SCOPE_ADDENDUM.json',scope)
lines=['本轮入场数量确认插件：冻结实现结果，不晋升','',
'结论：本次A/布林确认后保原量、否则半量的可插拔机制，没有修复2022—23绝对亏损，也没有修复924后大幅损耗。它保留原E0/I_target/PVR/退出与ACT恢复；所得证据只针对这项冻结实现，不能泛化为所有MA、EMA、布林工具无效。应停止扩展或按结果调参本版，回到持续授权、买错纠偏与已有仓位管理的具体失效点。',
'',
'long为2022Jan4–2024Dec31连续726个CLOSE，各臂自身跨年、不重置，初始100万元。strong为2025Jul1–2026Jun30独立fresh100万元/242CLOSE；不是完整25/26自然年，也不与long拼接为连续2022—26。当前1709A股开发快照池，非PIT/OOS/H股/120万元实盘证明。',
'',
'全窗口实际结果（ret%、全局收盘最大回撤%、全日历实际费用元、平均lag市值暴露%、平均CLOSE名义mark-floor风险%）：']
matrix=[]
for w in ['long','strong']:
 lines.append(w)
 for arm in arms:
  a=s[w][arm];m=a['account_metrics'];c=a['whole_calendar'];row=dict(window=w,arm=arm,return_pct=m['return_pct'],global_close_maxDD_pct=m['global_DD']['percent'],whole_calendar_fees=m['fees'],mean_lag_market_exposure_pct=c['mean_lag_exposure_pct'],mean_close_nominal_mark_floor_risk_pct=c['mean_close_nominal_risk_pct']);matrix.append(row)
  lines.append(f"{arm}: "+' / '.join(num(row[k],4 if 'pct' in k else 2) for k in list(row)[2:]))
lines+=['','长期年度（实际期末财富元 / 年度净收益元 / 按自身年初权益的年度收益%）：']
for arm in arms:
 for r in per:
  if r['grain']=='year' and r['arm']==arm:lines.append(f"{arm} {r['period']}: {num(r['end_NAV'])} / {num(r['wealth_change'])} / {num(r['return_pct'],4)}")
 r=next(r for r in per if r['grain']=='year' and r['arm']==arm and r['period']=='2023');lines.append(f"{arm} 2022–23累计：{num((D(r['end_NAV'])/D(1000000)-1)*100,4)}%")
bad=['2022-01','2022-03','2022-04','2022-12','2023-05','2024-11'];selected=[]
lines+=['','原No60最差六个月（相同固定诊断月，不生成实时信号）；后加2023Apr盈利反例。每项为自身月收益% / 平均lag市值暴露%：']
for month in bad+['2023-04']:
 lines.append(month)
 for arm in arms:
  r=next(r for r in per if r['grain']=='month' and r['arm']==arm and r['period']==month);selected.append(r);lines.append(f"{arm}: {num(r['return_pct'],4)} / {num(r['mean_lag_exposure_pct'],4)}")
lines+=['亏损月的资金暴露通常仍高，例如2024Nov四臂平均lag市值暴露均约86.4%—86.7%，A_ONLY月亏13.9243%弱于B的13.5236%；2022Dec A_ONLY亏12.5059%而B亏11.8613%。部分月份亏损减小不构成整体改进。2023Apr反例中B盈利19.3298%，A_ONLY仅11.5884%、A_OR_B13.9380%，说明同样高资金暴露下原赢家收益也被损伤。此处不把市值暴露等同真实风险。',
'','固定924：六close 2024Sep24–Oct8、其后Oct9–Dec31，按各自实际期初权益：']
for arm in arms:
 r=ph[arm]['924_six_closes']['account_own_NAV_period'];p=ph[arm]['post924']['account_own_NAV_period'];b=ph[arm]['post924_old_vs_new_layers'];g=b['groups'];lines.append(f"{arm}: 六close收益{num(r['return_pct'],4)}%；post收益{num(p['return_pct'],4)}%、财富变化{num(p['wealth_change'])}元；Oct8实际持有层后续{num(g['actually_held_at_boundary']['wealth'])}元，之后新增{g['new_fill_after_boundary']['layers']}层贡献{num(g['new_fill_after_boundary']['wealth'])}元。")
lines+=['A_ONLY post按自身权益亏20.7187%，A_OR_B亏20.8386%，与B亏20.7510%基本相当。绝对元损耗因进入区间的财富不同而变化，不能当成每单位质量改善。层贡献是该账户实际原路径的区间财富，不是删单可实现省损。',
'','主损耗是否已经通过确认（直接复用其他臂现成modifier日志，未重算features）：']
for k,v in coverage.items():
 lines.append(k)
 for g,x in v['groups'].items():lines.append(f"{g}: 买层{x['actual_buy_layers']}，买款{num(x['actual_buy_cash'])}元，截至固定cutoff贡献{num(x['contribution_through_cutoff'])}元；正层贡献{num(x['positive_layer_contribution'])}元、负层贡献{num(x['negative_layer_contribution'])}元。")
lines+=['2022–23的1557个真实买层中1180个A_TRUE；post303层中292个A_TRUE，贡献−114881.90元，而其余可见false/B-only组净贡献为正。故主亏损路径大多已通过A确认，这项量确认无法识别它们。保留12/1个无其他臂同sid/day日志的unmatched，不假装全覆盖。确认日志是冻结pandas值、事后关联，不是省损或独立可交易机会。',
'','强窗资金再分配、赢家和半导体：',
'UNIFORM50平均lag市值暴露87.4451% vs B88.0175%（242日，含初始空仓0）；平均持股104.93 vs73.86只，真实买fill1781 vs1171，真实总交易3038 vs2058，买入股票865 vs671，费用25217.79 vs22720.03元。每项原合法计划半量后，后续候选可补位，因此不是账户半仓或同风险对照。6030条半量不足最小单位是重复计划事件，不叫6030次独立漏买。',
'名义风险另见NOMINAL_RISK_SEPARATE_READOUT.json：UNIFORM50强窗原daily平均mark-floor风险8.1231% vs B8.5855%，并未减半；每个实际buy的平均初始名义风险/原decision NAV为0.06208% vs0.10631%。后者被更多fill周转，不能当成同时账户风险或最大可能损失，缺口、滑点和费用不保证保本。']
sp=read(O/'full_strong_v1/FIXED_PHASE_WEALTH.json');comp=read(O/'full_strong_v1/BASELINE_STOCK_COMPARISONS.json')
for arm in arms[1:]:
 g=comp[arm]['stock_cohorts'];lines.append(f"{arm}与B实际路径财富差：共同资助股票{num(g['common_funded']['delta'])}元；新资助{g['candidate_new_funded']['stocks']}股贡献{num(g['candidate_new_funded']['delta'])}元；不再资助的B股票差{num(g['lost_baseline_funded']['delta'])}元。该分组是已发生路径分解，非对单股/单笔的因果alpha。")
for arm in arms:
 r=sp[arm]['strict_semiconductor_2026H1'];lines.append(f"严格H1半导体{arm}: 原固定URFI881121/126成员，期内财富{num(r['interval_wealth'])}元，实际买款{num(r['actual_buy_cash'])}元、{r['buy_fills']}个buyfill，平均收盘权重{num(r['mean_close_weight_pct'],4)}%、峰值{num(r['peak_close_weight_pct'],4)}%。")
lines+=['严格半导体不是将电子化学品/元件混入后的宽口径；本机制没有使该固定目标组变为盈利。原16固定正反股票与6个行为案例的core/mobile实际层、原83/94固定订单匹配、原存量与新层的H1桥另见FIXED_COHORT_SUPPLEMENT.json。新资助股票或原赢家资金减少可同时发生，不能用新得到少数赢家替代全账户验收。',
'','简单基准仅复用旧审查：同日期long ETF510300 B&H−15.1672%/DD31.8889%，MA63_90 +11.1602%/DD11.4348%，CASH0；strong B&H+28.8331%/DD7.4390%，MA63+13.6272%/DD9.9046%，CASH0。不同资产、费用合同和资金暴露，不能称单因子alpha。原rawOPEN+成交容量等为execution proxy，涨跌停队列/竞价等未真实核实，execution_verified=false。',
'','审查与限制：原双窗财务/PVR/CA独审PASS，仅认证冻结实现账本；完整receipt见FINAL_REVIEW_SCOPE_ADDENDUM.json。精确数学分类有long11键/26m差异/3实际fill，strong9键/11m/0reserve，共20键/37m；实际时钟和pandas逐prefix复现单列PASS，不能称精确数学全PASS，也不能声称修正后的整账一致。早期SOURCE_BINDING 9/11/0措辞只适用then-complete strong，现由最终addendum明确更新，旧文件保留身份。未修数值、未调参、未跑整账反事实。新增月/阶段/日志join与名义风险为薄分析，独审状态另以append收据绑定。',
'','可复核路径：full_long_v1、full_strong_v1中的SUMMARY/ALL_PERIODS/ALL_MONTHS/ALL_YEARS/FIXED_PHASE_WEALTH/BASELINE_STOCK_COMPARISONS/CAPITAL_REALLOCATION_MONTHS；ORIGINAL_B_BUY_CONFIRMATION_COVERAGE.json；NOMINAL_RISK_SEPARATE_READOUT.json；FIXED_COHORT_SUPPLEMENT.json。所有输入原book、daily/balances/确认日志已bind SHA；0新账户事件。']
(O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
with (O/'PERFORMANCE_MATRIX.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
with (O/'FIXED_SIX_BAD_MONTHS_PLUS_APR2023.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
save(O/'REPORT_DELIVERABLE_BINDING.json',dict(files={str(p.relative_to(O)):sha(p) for p in [O/'READOUT.txt',O/'PERFORMANCE_MATRIX.csv',O/'FIXED_SIX_BAD_MONTHS_PLUS_APR2023.csv',O/'FINAL_REVIEW_SCOPE_ADDENDUM.json',O/'ORIGINAL_B_BUY_CONFIRMATION_COVERAGE.json',O/'NOMINAL_RISK_SEPARATE_READOUT.json']},new_account_events=0,producer_files_modified=0,derived_review='PENDING'))
print('WROTE_READOUT',len(lines),flush=True)
