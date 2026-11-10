"""Compact C1 readout over the two frozen saved paths; no new experiment."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,csv,gzip
O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def f(v):return f'{float(v):.2f}'
def wan(v):return f'{float(v)/10000:.4f}'
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 assert read(O/'FINAL_VERIFICATION.json')['passed'];allc=read(O/'COMPARISON.json');text=['C1冻结资金收缩政策：两窗normal完成｜2026-11-01',
 '裁决：保留为风险菜单，不晋升统一默认。2022损失/DD减少，但2025—26收益和DD同时逊于原Bdiag；不能以低曝险称信号识别改善。不调20%/10%/60%函数或排序/退出救结果，不自动扩压力/参数/年份。',
 '', '范围与合同',
 '相对原Bdiag只改变confirmed资本比例：H=max(初始1m,截至决策收盘的真实NAV最高值)，D=max(0,1-NAV/H)，c=.10+.50*max(0,1-D/.20)。c冻结至下决策，原开盘真实cash/fee/equity/risk基数保留；原ACT phase峰与H分开。裁剪/request/迁池统一c；旧confirmed因c下降超限不强卖，新迁池不得豁免。试探仍原10%/.5%风险、行业2%及原stock/sector限制。',
 '两窗各1m新账户、原市场暖机：完整2022，2025-07-01至2026-06-30连续，不在3/31重置。1709/90固定当前snapshot，原I/Q/CP1/stage/H1/退出/ACT与normal代理不变；无R1、新stage、cost或D1。Bdiag旧账只读复用。',
 '', '主矩阵（收益/DD/曝险为%；费用元）',
 '窗口/政策 | 净收益 | DD | 平均/峰值曝险 | 费用 | 买/卖fill | ACT暂停收盘']
 metrics=[];tails=[];bridges=[]
 for r in allc:
  w=r['window']
  for ref in ['Bdiag','C1']:
   m=r[ref];text.append(f"{w}/{ref} | {f(m['return_pct'])} | {f(m['global_DD']['percent'])} | {f(m['mean_exposure_pct'])}/{f(m['peak_exposure_pct'])} | {f(m['fees'])} | {m['buy_fills']}/{m['sell_fills']} | {m['paused_closes']}")
   metrics.append(dict(window=w,policy=ref,return_pct=m['return_pct'],DD_pct=m['global_DD']['percent'],mean_exposure_pct=m['mean_exposure_pct'],peak_exposure_pct=m['peak_exposure_pct'],fees=m['fees'],buy_fills=m['buy_fills'],sell_fills=m['sell_fills'],paused_closes=m['paused_closes']))
   es=read(O/'analysis'/w/ref/'LAYERS.json');tail=[e for e in es if D(e['cost']) and D(e['net'])/D(e['cost'])>=D('.3')];tails.append(dict(window=w,policy=ref,closed_tail=sum((D(e['net']) for e in tail if not e['qty']),D(0)),open_tail=sum((D(e['net']) for e in tail if e['qty']),D(0)),all_tail=sum((D(e['net']) for e in tail),D(0))))
  a,b=r['Bdiag']['whole_layers'],r['C1']['whole_layers'];delta={k:D(b[k])-D(a[k]) for k in ['closed_positive','closed_negative','open_net']};net=sum(delta.values(),D(0));assert abs(net-(D(r['C1']['return_pct'])-D(r['Bdiag']['return_pct']))*10000)<D('.00000001');bridges.append(dict(window=w,**delta,total_NAV_difference=net))
 text+=['2022的C1平均曝险低22.62个百分点；正窗低12.67个百分点却DD高0.42个百分点。只是控制新增容量，不能保证控制旧仓回撤或提高预测。正窗C1盈利444185.70元=闭合层净贡献91173.98元+未平层净贡献353011.72元（79.47%），原Bdiag盈利51.5350万元含未平32.3398万元；未平不称已锁定利润。',
 '', '实际新增confirmed mobile（不把core迁池当新买；金额万元）',
 '窗口/政策 | 层数 | 真实新买款含费 | 闭合正 | 闭合负 | 未平净贡献']
 for r in allc:
  for ref in ['Bdiag','C1']:
   m=r[ref]['new_confirmed_mobile'];text.append(f"{r['window']}/{ref} | {m['layers']} | {wan(m['buy_cash'])} | {wan(m['closed_positive'])} | {wan(m['closed_negative'])} | {wan(m['open_net'])}")
 text+=['2022 confirmed负贡献减少23.2085万元，但probe/core等其余层闭合负从8.2727增至10.0613万元，试探失败并未消失。正窗confirmed负减少12.7162万元，闭合正也减少21.4729万元；不把减少亏损单独当成总体成功。',
 '', '严格终值差桥C1−Bdiag（万元，三项互斥；费用已在层cash，不再另加）',
 '窗口 | 闭合正贡献差 | 闭合负贡献差 | 未平贡献差 | 合计NAV差']
 for r in bridges:text.append(f"{r['window']} | {wan(r['closed_positive'])} | {wan(r['closed_negative'])} | {wan(r['open_net'])} | {wan(r['total_NAV_difference'])}")
 text+=['尾部贡献沿既有“实际层净贡献/含费买款>=30%”事后口径，不是价格MFE、不参与线上。闭合与未平分开：',
 '窗口/政策 | 闭合尾部 | 未平尾部 | 合计（万元）']
 for r in tails:text.append(f"{r['window']}/{r['policy']} | {wan(r['closed_tail'])} | {wan(r['open_tail'])} | {wan(r['all_tail'])}")
 text+=['尾部标签与正负/未平桥有重叠，只作另一个描述维度，不相加。正窗总尾部贡献减少17.9469万元，但不能把每笔基准赢家差额全归一个被挡买单；持仓/资金竞争/后续路径已不同。基准前10贡献股两账逐一对照及C1实际前10链均保存。',
 '', '亏损累积后的存量/新层（严格区间财富桥）',
 '各窗取C1首次达到D10%这一原函数锚点收盘；两账用同日期但各自真实持仓。旧层按该日已含费权益估值作基准，后续新层用其整层贡献。不是把旧层全生命周期亏损都归到收缩期。',
 '窗口/政策 | 边界日 | 当时持有旧层后来贡献 | 边界后新层贡献 | 区间NAV变化（万元）']
 for r in allc:
  for x in read(O/'analysis'/r['window']/'FIRST_D10_POST_BOUNDARY_WEALTH_BRIDGE.json'):
   p=x['parts'];text.append(f"{r['window']}/{x['reference']} | {x['boundary']} | {wan(p.get('held_at_first_C1_D10_close',0))} | {wan(p.get('new_actual_layers_after_boundary',0))} | {wan(x['interval_NAV_change'])}")
 text+=['2022收缩期损耗减少主要体现在后来新增层；正窗11/21之后C1新层净贡献并不低于基准，主要差额来自两账当时已经不同的旧book后来贡献。C1不强卖旧仓，不能把这项差额说成C1直接卖飞赢家。CONFIRMED_BUYS_ON_SAME_C1_DATES.json另列按C1相同日历DD档两账实际买款与层损益，非独立机制因果分解。',
 '', 'cap/全程DD/ACT phase及恢复',
 '窗口 | 旧confirmed高于新cap日 | 最大超额元 | 最低c | 全程H末值']
 for r in allc:
  c=r['cap'];text.append(f"{r['window']} | {c['over_cap_closes']} | {f(c['max_over_cap_cny'])} | {f(D(c['minimum_c'])*100)}% | {f(c['H_end'])}")
 text+=['2022两账全程最坏DD均12/29：Bdiag33.27%、C1 20.34%。Bdiag最坏ACT phase DD为5/9的21.39%，且6/17恢复重设phase峰；C1只有12/27一次pause、没有resume，H全程1m不变。正窗两账最坏全程/phase DD均12/4、前峰均9/1；都未ACT暂停。实际C1两窗没有ACT resume实例，恢复时不洗H由合成及独审真实planning反例覆盖，不冒称历史已暴露。',
 '2022未恢复到35%/60%函数锚点，也无ACT resume，恢复时延N/A而非0。正窗17个35%/60%上穿里，15次下一市场观察日出现真实fresh confirmed新买；6/15、6/24新峰后至期末未出现，分别仅10/4个后续市场观察（6/15若含当日才为11）、标右删失，不叫永不恢复。5次35%上穿为12/25、3/24、4/15、4/22、4/29，均下一观察日新买。',
 '恢复新买不等于恢复高参与：9/1后confirmed市值/NAV回到9/1水平，要到次年6/16才再次观察到；此比例包含价格变动，不能当纯主动净加仓。全部恢复里程碑、首次actual fill、原生占用曲线及限制另存。10%底座和60%恢复都不保证剩余现金/行业/stock/Q或最小单位可用。',
 '', '迁池阻塞与试探代价',
 '只对真实行业事件已报告confirmed_unfunded、且当天仍有当前attempt的probe层、目标池确实容不下的记录去重追踪。',
 '窗口 | 涉及probe层/股票 | 后迁入/先退出/期末未决 | 后迁入者等待中位/最长市场观察']
 for r in allc:
  m=read(O/'analysis'/r['window']/'MIGRATION_WAIT_LOTS.json')['summary'];text.append(f"{r['window']} | {m['layers']}/{m['stocks']} | {m['migrated']}/{m['exited']}/{m['censored']} | {m['migration_lag_median']}/{m['migration_lag_max']}")
 text+=['等待中位3/2、最长70/28只针对后来迁入的43/35层，不代表全部89/51层；正窗另2层期末右删失。2022/正窗分别有96/63个具该probe占用的实际行业迁池失败事件；另外191/120个收盘在静态占用上容不下相应当前attempt probe，不将每一天都算真实尝试。旧attempt保守占用、股保护、资金及pool仍可共存。',
 '原funding日志把多条route拒因合并，不能精确给“独占因为旧probe阻塞的新机会数”；该项unknown，未为补字段重跑/插日志。记录的40503/62453是含pool/probe拒因的open×stock×role请求，不是独立CP1机会或独占归因。',
 '', '三条原强行情（固定后视镜案例，C1无特权）',
 '行业/季度/政策 | 当季实际新买款万元 | 峰值实际权重% | 峰值日']
 for x in read(O/'analysis/2025_26/THREE_FROZEN_STRONG_CASES.json'):text.append(f"{x['industry']}/{x['window'][0][:7]}/{x['reference']} | {wan(x['all_buy_cash'])} | {f(x['actual_peak_weight_pct'])} | {x['peak_day']}")
 text+=['能源Q3仍只华友一笔1.8921万元，两账峰值比例差主要是NAV分母；军工Q4从17.1881万/11.66%降至13.7007万/8.82%；油气Q1仍仅0.2003万/0.1544%与0.2986万/0.2109%，C1没有修复原主升小仓问题。正窗C1全期仍保留其他赢家，不能只按三案例否定所有机会捕获。',
 '', '最早真实经济分歧与审计',
 '2022 1/5首个已知收盘D0.7552%、c58.1120%，次开盘300364从基准1100股变300股；正窗7/2收盘D0.8526%、c57.8684%，7/3的600397从3000变2600股。连续函数从小回撤已介入，并非等严重亏损才开始；这些早期离散资金竞争也影响后来book。保持冻结，不加噪声区/冷却救结果。',
 '17/17本机真实对象/公式/账务/待单/恢复测试及独审无阻断；三处cap逆替换与原Bdiag一致，固定c60两窗技术短段均与旧账和五流水完全同。两条C1物理前缀/同身份重启、484收盘H及c独立复算、8季度checkpoint源hash/资金股数/累计状态通过。',
 '2022在新暂停要求到达时末账已落盘，核PID60949为本任务Ts后待独审，再同进程CONT收尾；没有重跑年度。正窗新账户一次连续到6/30，3/31季度pickle与后续H累计行数证明未重置。原基准未重跑，原文件及冻结源码不改。',
 '原循环计时（含逐日核账/例行检查点，首段+续段）2022约165.33秒、正窗180.35秒；输入加载日志68.18/73.69秒。TIMING.json的load_seconds字段误名，实际记录从加载开始的累计阶段时长261.15/286.90秒，不能当纯加载耗时；保留原日志不覆盖。',
 '当前无执行/权限/连接阻塞。全部历史已消费，当前snapshot非PIT；日线HLV/open成交代理及同开盘卖款复用、分红到账/送转可卖时间代理仍在；收益含未平权益，C1不是实盘认证。完整quarter/资本/贡献/恢复/原始账见analysis与runs目录；此轮完成后不自动扩实验。']
 (O/'RESULTS.txt').write_text('\n'.join(text)+'\n')
 for name,rs in [('MATRIX.csv',metrics),('TAIL_CONTRIBUTIONS.csv',tails),('NAV_DIFFERENCE_BRIDGE.csv',bridges)]:
  with (O/name).open('w') as h:w=csv.DictWriter(h,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
 save(O/'FINAL_STATUS.json',dict(completed_windows=2,new_C1_normal_paths=2,baseline_paths_rerun=0,no_additional_policy_or_pressure=True,decision='risk_menu_only_not_unified_promotion',wiring_audit='independent-wiring-audit/EVIDENCE.json',final_verification='FINAL_VERIFICATION.json',original_2022_same_process_resumed_not_replayed=True,execution_blockers=[],unidentified='exclusive probe rejection count unavailable from merged reasons'))
 select=[O/'adapter_c1.py',O/'run.py',O/'CONTRACT.txt',O/'KEY_FUNCTIONS.txt',O/'SYNTHETIC_GATE.json',O/'FINAL_VERIFICATION.json',O/'FINAL_STATUS.json',O/'RESULTS.txt',O/'MATRIX.csv',O/'TAIL_CONTRIBUTIONS.csv',O/'NAV_DIFFERENCE_BRIDGE.csv',O/'COMPARISON.json',O/'independent-wiring-audit/EVIDENCE.json']
 for w in ['2022','2025_26']:
  select += list((O/'analysis'/w).rglob('*.json'))
  select += [O/'runs'/w/'pair'/f for f in ['B.json.gz','daily.jsonl.gz','C1.json','balances.jsonl.gz','funding.jsonl.gz']]
  select += list((O/'runs'/w).glob('checkpoint-*.provenance.json'))
 manifest={str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in select}
 save(O/'DELIVERABLE_SHA256.json',manifest);print('RESULTS_SHA256',manifest['RESULTS.txt'],'evidence_files',len(manifest))
if __name__=='__main__':main()
