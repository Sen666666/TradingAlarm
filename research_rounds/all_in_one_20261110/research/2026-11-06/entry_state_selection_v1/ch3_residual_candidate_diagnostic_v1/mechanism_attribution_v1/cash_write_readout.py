#!/usr/bin/env python3
"""Render cash attribution tables; no source economics is executed."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import csv,json,hashlib
P=Path(__file__).resolve().parent

def read(n):
 with (P/n).open() as h:return list(csv.DictReader(h))
def num(v,n=2):return '—' if v in ('',None) else f'{D(v):,.{n}f}'
def pct(v):return '—' if v in ('',None) else f'{D(v)*100:,.2f}%'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(v) for v in row)+' |' for row in rows])
def primary(x):return x['comparison']=='CH3_RM_MINUS_RAW_MOM11'
summary=read('cash_summary.csv');means=read('cash_mean_decomposition.csv');conc=read('cash_concentration.csv');stocks=read('cash_stock_comparison.csv');pairs=read('cash_unique_same_exit_decomposition.csv');deletion=read('cash_leave_one_stock_out.csv');coverage=read('cash_round_coverage.csv');arms=read('cash_arm_metrics.csv');classes=read('cash_path_class_summary.csv')
lines=['# CH3 对同窗原始动量：全部路径金额归因','',
'## 结论','',
'这是封存经济输出的事后描述性归因，不是新增经济测试、账户回测、因果识别或样本外验证。主比较 CH3_RM − RAW_MOM11 已控制共同的 11 月评分窗，原 PVR（A_UNION_B）仅保留作参照。',
'',
'- 2024 出生窗初层可用闭合的金额均值差为 +77.66 元。223 组同股、同退出日、不同入场且双方证据可用的唯一配对贡献 +68,132.54 元，其中数量 +19,008.60 元、各自单股费后盈利 +49,123.94 元。数量不是这个配对子集正差的主要项，且不能把这个分解叫资金分配优化。',
'- 固定全股绝对贡献排序中，银之杰的实际净差 +90,597.13 元大于全部可用片段小计差 +90,088.49 元。它属于不同实际入场，不是对原利润的移植。删除它后，可用片段小计差为 −508.64 元，但重新计算双方均值后仍为 +7.01 元，不能混淆总额与均值。',
'- 2024 完整可判定集合的净差为 +119,486.60 元，删除任一股后的范围仍为 +28,889.48 至 +154,616.06 元。另有 69 只股票至少一臂执行或财务未知，它们的完整股差保留 UNKNOWN；其已观察片段差 −29,398.11 元只解释可用小计与完整集合为何不同，不表示未知路径赔了这么多。',
'- 2022 初层可用片段总额差 −1,089.32 元，均值差却 +0.90 元；完整可判定集合差仅 +1,017.01 元。两臂初层期望仍负，2024 亏家均亏 CH3 为 −1,732.39 元、RAW 为 −1,710.55 元，不能宣称亏损改善。',
'- 2024 完整股前 10 个绝对差的有符号和为 +119,332.16 元，接近总净差，但其绝对和只占全股绝对差 24.66%。这说明净差受到少数大路径与广泛正负抵消共同影响，不能解释成整个差异质量都由十只股票决定。',
'',
'## 预先冻结口径与恒等式','',
'计算前冻结 `cash_contract.json`，SHA-256 为 b7e5b50a1d6b1a0003dce7abb50f17f1088adc1c03db4dd6f1678912afe1705a。覆盖 2022 全年出生和 2024-09 至 12 出生，路径仍沿原经济结果管理至 2026-06-30；未调用原经济引擎。',
'',
'1. 全市场事件中的全部股票进入底表，逐股保留全部许可轮；未参与和 NOFILL 明确列示。每臂可用闭合金额小计只有在至少存在一轮可用闭合时才有值，无可用观察时留空。',
'2. 整股差只在双方全部许可均为可用闭合或显式 NOFILL 时可判定。无许可/仅 NOFILL 可确认零参与金额；只要任一轮执行 UNKNOWN、财务 UNKNOWN 或其他未闭合，整股差即 UNKNOWN。共同 event 的未知路径即使一致也不被推断为已知零净差。',
'3. 先按相同 event_id 对齐并核对动作、权益账和结果恒等，再对剩余路径按 sid + exit_day 配对。双方各恰有一条且均证据可用才进入同退出分解；重复或未知不强配。',
'4. 令 q 为各自实际初始入场股数，p 为该路径自身初层净额/q。精确对称分解：Δ(qp) = (qC−qR)(pC+pR)/2 + (pC−pR)(qC+qR)/2。p 包含各自费用和 NET80，所以它不只是裸价差，也不能解释为切换数量时保持不变的收益。FULL 有追加，仅报告其实际毛净，不冒充初始数量分解。',
'5. 毛净恒等式：净额 = 原 open 毛额 − 滑点 − 费用 + NET80 = 成交毛额 − 费用 + NET80。每条可用路径及其汇总都检查。',
'6. 均值恒等式：SC/NC − SR/NR = (SC−SR)(1/NC+1/NR)/2 + (1/NC−1/NR)(SC+SR)/2。第二项只是观察样本数的算术分量，不是删失改善或选股价值。',
'',
'`observed_subtotal_bridge_*` 是两个已观察行集合相减的加法桥接。在桥接代数中空集合和为零，但不把未观察路径收益设为零，也不赋给该股完整净差。所有含未知的股票必须结合 `complete_status` 使用。',
'',
'## 三臂可用闭合全貌','']
lines.append(table(['出生窗','臂','层','N','赢/负/零','净胜率','均净元','均收益率','赢家总净','亏家总净','均亏元','执行未知','闭合财务未知','NOFILL'],[[x['window'],x['arm'],x['layer'],x['usable_closed'],f"{x['winners']}/{x['losers']}/{x['zeros']}",pct(x['win_rate']),num(x['mean_net']),pct(x['mean_return']),num(x['winner_net']),num(x['loser_net']),num(x['mean_loss']),x['execution_unknown'],x['closed_financial_unknown'],x['nofill']] for x in arms]))
lines+=['','初层和 FULL 可用轮数相同，但金额、赢家和收益率各自计算。零收益轮本次均为 0；没有删除亏损和未知。均亏接近或盈亏比升高均不构成入口目标达成。','','## 可用片段与完整可判定整股必须分开','']
lines.append(table(['窗','比较参照','层','全股票','任一臂有许可','完整可判定股票','其中有许可','未知股','可用小计差','完整股差','未知股已有片段桥接','完整正/负/平'],[[x['window'],x['comparison'].split('_MINUS_')[1],x['layer'],x['all_market_stocks'],x['stocks_any_permission'],x['complete_stocks'],x['complete_stocks_any_permission'],x['unknown_stocks'],num(x['observed_subtotal_delta']),num(x['complete_stock_net_delta']),num(x['unknown_stock_observed_subtotal_bridge']),f"{x['complete_positive_stocks']}/{x['complete_negative_stocks']}/{x['complete_zero_stocks']}"] for x in summary]))
lines+=['','完整可判定集合含双方均无许可的已知零股；不能把这些零股作为实际交易胜率分母。2022/2024 主比较分别有 140/385 只双方无许可股票。原 PVR 参照与 RAW 主比较的未知集合不同，不得混用总体。','','## 共同 event 与剩余路径覆盖','']
lines.append(table(['窗','比较参照','共同event','其中双方可用','唯一同退出异入场配对','C未配对可用轮','R未配对可用轮'],[[x['window'],x['comparison'].split('_MINUS_')[1],x['common_events'],x['common_usable_events'],x['same_exit_unique_pairs'],x['c_unmatched_usable'],x['r_unmatched_usable']] for x in summary if x['layer']=='core']))
lines+=['','全部 5,955 个共同 event 的标准化动作、CLAIM_LEDGER、CLAIMS 和经济结果逐项恒等；包括 UNKNOWN/NOFILL，未把它们转成已知收益。主比较 2022/2024 可用共同 event 为 2,096/947，各自净差严格为零。','','主比较完整轮次分类如下。所有未匹配轮次的 event、日期、状态、可用自身净额均在 `cash_round_coverage.csv`；未发现需要强配的重复同退出组（该分类为 0 并未虚构配对）。','']
rows=[]
for w in ['2022','2024_924']:
 for arm in ['CH3_RM','RAW_MOM11']:
  count=Counter(x['classification'] for x in coverage if primary(x) and x['window']==w and x['arm']==arm)
  for kind,n in sorted(count.items()):rows.append([w,arm,kind,n])
lines.append(table(['窗','臂','分类','轮数'],rows))
lines+=['','## 毛净差归因','']
rows=[]
for x in summary:
 w=x['window'];ra=x['comparison'].split('_MINUS_')[1];layer=x['layer']
 c=next(z for z in arms if z['window']==w and z['arm']=='CH3_RM' and z['layer']==layer);r=next(z for z in arms if z['window']==w and z['arm']==ra and z['layer']==layer)
 rows.append([w,ra,layer]+[num(D(c['observed_'+k])-D(r['observed_'+k])) for k in ['raw','slippage','gross','fees','net80','net']])
lines.append(table(['窗','参照','层','Δ原open毛额','Δ滑点','Δ成交毛额','Δ费用','ΔNET80','Δ可用净小计'],rows))
lines+=['','这些差分别来自各臂自己的全部可用路径，未知路径未填零。金额合计不对应资金受限共享账户，不能称为可实现利润。','','## 2024 均值差和精确数量/单股盈利分解','']
lines.append(table(['窗','参照','层','均值差元','同退出数量均值项','同退出单股均值项','同退出合计均值项','未匹配均值项','样本数均值项'],[[x['window'],x['comparison'].split('_MINUS_')[1],x['layer'],num(x['mean_delta']),num(x['same_exit_quantity_mean_component']),num(x['same_exit_per_share_mean_component']),num(x['same_exit_total_mean_component']),num(x['unmatched_mean_component']),num(x['observed_count_mean_component'])] for x in means]))
lines+=['','FULL 的数量/单股栏 — 表示该分解不适用，不是 FULL 收益未知。初层配对分解以真实入场初始数量计算，未将原路径利润移植到新时点；浮点源值按 Decimal 读入，分解误差小于 1e−30 元。','','主比较 2024 的 223 组同退出配对净差为 +68,132.54 元，其中数量 +19,008.60、单股费后盈利 +49,123.94。银之杰一组贡献数量 +32,853.00、单股 +57,744.13；去掉这一组后，配对净差 −22,464.59，数量 −13,844.40、单股 −8,620.19。这只是固定删除任一贡献检视中的极值，不是提出剔除银之杰的新策略。','','数量也有明显抵消：长盛轴承同退出实际数量 CH3 700 股、RAW 1,200 股，净差 −35,129.45，其中数量 −34,736.90。北方稀土数量贡献 +13,079.49。不能把部分正数量项泛化为普遍更优仓位。','','## 固定全股集中度与逐股删除','']
lines.append(table(['窗','层','总体','前K绝对排序','前K有符号和','前K绝对和','占全股绝对和','总净差','删任一股净差最小','最大'],[[x['window'],x['layer'],x['scope'],x['top_k'],num(x['top_signed']),num(x['top_absolute']),pct(x['share_absolute']),num(x['total_signed']),num(x['delete_one_min']),num(x['delete_one_max'])] for x in conc if primary(x) and x['scope'] in ['COMPLETE_STOCK_DELTA','OBSERVED_SUBTOTAL_BRIDGE_NOT_FULL_STOCK_DELTA']]))
lines+=['','排序覆盖全部完整可判定股（包括负差和平局），并固定报告前 1/5/10。另列全市场股的可用片段桥接，仅为缺失口径的会计核对，不是完整股排序。没有按净利润高低定义 beta 组或筛选门。','','重新移除股票后，同时重新计算双方分母的均值差范围：','']
rows=[]
for w in ['2022','2024_924']:
 for layer in ['core','full']:
  zz=[x for x in deletion if primary(x) and x['window']==w and x['layer']==layer]
  low=min(zz,key=lambda x:D(x['observed_mean_gap_after_deletion']));high=max(zz,key=lambda x:D(x['observed_mean_gap_after_deletion']))
  rows.append([w,layer,num(low['observed_mean_gap_after_deletion']),low['name'],num(high['observed_mean_gap_after_deletion']),high['name']])
lines.append(table(['窗','层','最小重算均值差','删除股','最大重算均值差','删除股'],rows))
lines+=['','注意：`cash_concentration.csv` 的 OBSERVED_MEAN_GAP_ADDITIVE_CONTRIBUTION 是固定原分母的加法贡献；其 delete_one 字段仅删除该加法项，不是重算均值。重算分母的逐股删除以 `cash_leave_one_stock_out.csv` 和上表为准。','','### 2024 完整可判定股绝对差前十（描述，非选股）','']
z=sorted([x for x in stocks if primary(x) and x['window']=='2024_924' and x['complete_known']=='True'],key=lambda x:(-abs(D(x['core_complete_delta_net'])),x['sid']))[:10]
lines.append(table(['代码','股票','CH3可用初层自身净额','RAW可用初层自身净额','整股差','CH3/RAW可用轮','路径类'],[[x['sid'],x['name'],num(x['c_core_observed_net']),num(x['r_core_observed_net']),num(x['core_complete_delta_net']),f"{x['c_usable_closed']}/{x['r_usable_closed']}",x['path_class']] for x in z]))
lines+=['','没有可用闭合的观察小计栏显示 —，不代表该股无许可；是否已知零参与必须读路径类与 `c_participation`/`r_participation`。本表国民技术、电气风电、山子高科的 RAW 为无许可，上海电气的 CH3 为无许可，因此它们的完整股差可判定；欧陆通有执行未知，故不进入这张完整股表。全量表仍保留欧陆通及其他未知。','','### 2024 唯一同退出配对绝对净差前十（所有配对另附）','']
z=sorted([x for x in pairs if primary(x) and x['window']=='2024_924'],key=lambda x:(-abs(D(x['core_delta_net'])),x['sid']))[:10]
lines.append(table(['股票','CH3入场/股数','RAW入场/股数','共同退出','CH3/RAW自身初层收益率','净差','数量项','单股费后项'],[[x['name'],f"{x['c_entry_day']} / {num(x['c_entry_q'],0)}",f"{x['r_entry_day']} / {num(x['r_entry_q'],0)}",x['exit_day'],f"{pct(x['c_core_return'])} / {pct(x['r_core_return'])}",num(x['core_delta_net']),num(x['core_quantity_component']),num(x['core_per_share_component'])] for x in z]))
lines+=['','## 无许可、同股异路径与未知的完整划分','']
lines.append(table(['窗','路径类','股票数','完整可判定','未知股','可用片段桥接','可判定完整股差','C/R可用轮'],[[x['window'],x['path_class'],x['stocks'],x['complete_stocks'],x['unknown_stocks'],num(x['observed_subtotal_bridge']),num(x['known_complete_stock_net_delta']),f"{x['c_observed_n']}/{x['r_observed_n']}"] for x in classes if primary(x) and x['layer']=='core']))
lines+=['','2024 主比较：CH3 无许可而 RAW 有许可/未决的股票 82 只，其中 77 只完整可判定、5 只未知；RAW 无许可而 CH3 有许可/未决的 92 只，其中 84 只完整可判定、8 只未知。两侧不是“一个旧 event 消失就丢失一只股”的计数。股票可能有多轮，同股异事件集合全部归在自身路径里。','','## 能与不能得出的下一步','',
'- 可以：将全体共同 event、全体唯一同退出配对或全候选股的身份与事前特征连接，保持预先声明的分母和未知状态，描述何种排序变化对应哪些实际路径变化。',
'- 不能：由银之杰或前十贡献反推 beta 分组、波动阈值、行业门槛、数量缩放、卖点或新选股门；不能把后验删除当作一个可执行策略。',
'- 不能：由这些独立路径金额推导共享账户收益、资金分配优化、因果性去 beta 增益，或将 CH3 当前修订历史和未知发布时钟称为 PIT/OOS。',
'- 新假设若要行动，必须在不使用这里的赢家来定门的前提下另行冻结定义、样本和验证口径，并取得新的独立证据；这份金额归因本身没有给出可晋级的替换规则。',
'',
'## 复算与文件','',
'运行：`PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/repos/my-quant/.conda/envs/dev/bin/python cash_compute.py`，随后同一解释器运行 `cash_write_readout.py`。这两个脚本只写本目录 cash_* 文件，不调用经济引擎、不安装软件、不更改任何封存源文件。',
'',
'- cash_contract.json：事前冻结定义。',
'- cash_compute.py：只读归因实现；cash_write_readout.py：本报告生成器。',
'- cash_arm_stock_totals.csv：9,216 条股臂记录，保留每只股票全部许可与状态、CORE/FULL 可用和完整金额、毛额/滑点/费用/NET80、赢负零。',
'- cash_stock_comparison.csv：6,144 条全股比较；只将 complete_known=True 的 *_complete_delta_* 当完整股差。',
'- cash_unique_same_exit_decomposition.csv：1,168 组跨两个比较的严格唯一配对，保留双方 event、signal/entry 日期、entry_q、自身净额、收益率及精确数量/单股分解。',
'- cash_round_coverage.csv：16,323 条比较内路径身份与配对/未匹配/未知分类。',
'- cash_common_event_qa.csv：5,955 组共同 event 的动作、权益与结果恒等。',
'- cash_arm_metrics.csv、cash_summary.csv、cash_mean_decomposition.csv、cash_path_class_summary.csv：三臂、整体、均值和路径类汇总。',
'- cash_concentration.csv、cash_ranked_stock_deltas.csv、cash_leave_one_stock_out.csv：全部贡献排序、固定前1/5/10和每只股删除。',
'- cash_source_manifest.json：159 份封存输出的完整哈希和直接输入清单；cash_qa.json：所有源文件计算前后不变、分解恒等和未知传播自检。',
'',
'本报告自检 PASS 不替代独立审查。全部金额在 CSV 保留高精度，展示按分四舍五入；源经济值本身仍受原研究的执行和权益证据边界约束。']
(P/'cash_readout.md').write_text('\n'.join(lines)+'\n')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(P.glob('cash_*')) if p.is_file() and p.name!='cash_output_manifest.json'}
(P/'cash_output_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(P/'cash_readout.md')
print('bytes', (P/'cash_readout.md').stat().st_size, 'files',len(manifest))
