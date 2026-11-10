"""Render already sealed analysis tables; no strategy/economic execution."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import csv,json,hashlib,argparse
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
MONTH=R/'native_dmi_two_month_continuous_v1/analysis'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(out):
 manifest=json.loads((out/'OUTPUT_SHA256.json').read_text())
 for n,h in manifest.items():assert sha(out/n)==h
 s=json.loads((out/'SUMMARY.json').read_text());lines=[]
 def put(x=''):lines.append(x)
 def num(x):return 'NA' if x is None or x=='' else f'{float(x):,.2f}'
 def pct(x):return 'NA' if x is None or x=='' else f'{float(x)*100:.2f}%'
 def rows(n):return list(csv.DictReader((out/(n+'.csv')).open()))
 def stat_text(a):return f"{a['wins']}胜/{a['losses']}负/{a['flat']}平，共{a['n']}个；胜率{pct(a['win_rate'])}，均赢{num(a['mean_win'])}，均亏{num(a['mean_loss'])}，赔率{num(a['payoff_ratio'])}，净额{num(a['net_pnl'])}；≥30%费后尾部{a['fee_net_30pct_tail_count']}个，尾部净额{num(a['fee_net_30pct_tail_pnl'])}"
 put('# 1月建仓后续：原生账本独立分支分析')
 put('\n截止 2026-05-15。分析程序经济运行次数为 0；仅重放已封存成交/公司行动账目并重建估值，不执行策略。金额均为人民币。')
 if not s['analyzed_DMI_branches']:put('\n**本文件只有原 PVR 基线，不能称作 DMI 结果。DMI 未在本分析中读取。**')
 put('\n## 账户边界与可比性')
 put('- PVR_ORIGINAL 为原完整共享现金账户。DMI_FROM_2022JAN 和 DMI_FROM_2026JAN 是不同分支，绝不拼接为单一DMI账户。')
 put('- 2026分支继承原PVR截至2025-12-31状态，并不是2022分支走到2026年的状态。表中其2022—2025为原PVR继承历史，不是DMI处理期。')
 put('- 同一2026-05-15终点给2022和2026一月cohort的成熟时间不同，不能直接横比为同等暴露期。固定未来1709股/90行业池为NON-PIT，OPEN±5bp条件研究账，不代表实盘可成交。')
 put('- DMI持续使用冻结同sector+角色排序；原ACT、原ADD、共享现金、后续全池信号/保护/退出保持原生。没有增加盈利加仓门、强平、训练或调参。')
 put('\n## 全账户与年度')
 for label,a in s['full_accounts'].items():
  put(f"\n### {label}")
  put(f"初始NAV {num(a['start_nav'])} → 期末 {num(a['end_nav'])}，全期收益{pct(a['return_fraction'])}，最大回撤{pct(a['max_drawdown_fraction'])}（{a['drawdown_peak_day']} → {a['drawdown_trough_day']}）。费用{num(a['fees'])}，价格中嵌入滑点{num(a['embedded_price_slippage'])}。")
  put(f"期末可用现金{num(a['ending_available'])}，库存{num(float(a['remaining_buy_cost'])+float(a['unrealized_inventory_minus_remaining_buy_cost']))}，股息应收{num(a['ending_dividend_receivable'])}，卖出应收{num(a['ending_sale_receivable'])}；{a['end_stocks']}股/{a['end_layers']}活层。平均库存/NAV {pct(a['mean_inventory_fraction'])}，最大单股/NAV {pct(a['max_stock_NAV_fraction'])}。")
  put('全账户完整round：'+stat_text(a['closed_rounds'])+'。')
  put(f"另有{a['open_rounds']}个未闭round，原账估值净额{num(a['open_round_marked_pnl'])}，不计入胜率或完整尾部。")
  put('| 年份 | 起点NAV | 终点NAV | 收益 | 年内回撤 | 费用 | 年末现金 | 年末库存 | 年末股数 |')
  put('|---|---:|---:|---:|---:|---:|---:|---:|---:|')
  for r in rows('ANNUAL_NAV_FEES'):
   if r['account']==label:put(f"|{r['year']}{'截至5/15' if r['partial_year']=='True' else ''}|{num(r['start_nav'])}|{num(r['end_nav'])}|{pct(r['return_fraction'])}|{pct(r['max_drawdown_fraction'])}|{num(r['fees'])}|{num(r['final_available'])}|{num(r['final_inventory'])}|{r['final_stock_count']}|")
 put('\n## 2026日历期间归因，不用整生涯替代')
 for r in rows('2026_PERIOD_CONTRIBUTIONS'):
  put(f"- {r['account']} {r['period']}，锚点{r['anchor']}：NAV增量{num(r['NAV_change'])} = 锚点继承活层{num(r['inherited_live_layer_contribution'])} + 锚点后新层{num(r['new_layer_contribution'])}；该段收益{pct(r['return_fraction'])}，费用{num(r['fees'])}。")
 ms=json.loads((MONTH/'SUMMARY.json').read_text());mh=sha(MONTH/'SUMMARY.json');mm=json.loads((MONTH/'OUTPUT_SHA256.json').read_text());assert mh==mm['SUMMARY.json']
 for m in ms['summaries']:
  if m['window']!='2026Jan':continue
  label='PVR_ORIGINAL' if m['arm']=='PVR' else 'DMI_FROM_2026JAN'
  if label not in s['full_accounts']:continue
  put(f"- {label} 2026一月：NAV增量{num(m['month_NAV_change'])} = 2025年末继承活层{num(m['inherited_live_layer_month_contribution'])} + 一月新层{num(m['new_layer_month_contribution'])}；来自原已审一月账，非整round生涯收益。")
 put('\n## DMI实际候选未知分母')
 for label,a in s['full_accounts'].items():
  if 'actual_DMI_candidate_counts' not in a:continue
  c=a['actual_DMI_candidate_counts'];put(f"- {label} 实际重排候选stock-days {c['candidate_stock_days']}，DMI已知{c['known_stock_days']}，已知且可交换{c['known_mutable_stock_days']}，DMI未知固定原槽{c['UNKNOWN_fixed_slot_stock_days']}（{pct(c['UNKNOWN_fraction'])}），实际排名移动{c['actual_moved_stock_days']}。")
 put('这些是实际排序候选分母，不是1709×日期的原始feature格、不等于信号未知或未闭账目；多角色共存仍按audit一行一个stock-day计。')
 put('\n## 固定一月cohort：两套分母')
 for key,c in s['January_cohorts'].items():
  put(f"\n### {key}")
  put(f"固定{c['cohort_rounds']}个一月首BUY round，涉及{c['unique_stocks']}只股票；月内重复round {c['within_January_repeated_rounds']}个。")
  put('- 完整round：'+stat_text(c['complete_rounds'])+'。')
  put('- 首BUY层独立闭合：'+stat_text(c['closed_first_BUY_layers'])+'。')
  put(f"- 一月已闭{c['January_closed_rounds']['n']}个、净{num(c['January_closed_rounds']['net_pnl'])}；一月后闭{c['post_January_closed_rounds']['n']}个、净{num(c['post_January_closed_rounds']['net_pnl'])}。")
  put(f"- 未闭round {c['open_rounds']}个，标记净额{num(c['open_marked_pnl'])}；首BUY层未闭{c['open_first_BUY_layers']}个，首层已闭但round未闭{c['first_layer_closed_round_still_open']}个。闭合账目UNKNOWN {c['closed_bookkeeping_UNKNOWN']}个；外部历史可交易性/分红实际付款证据仍UNKNOWN，不据此删除样本。最晚闭合{c['last_cohort_close']}。")
  put(f"- 该账户一月股票集合在二月起另有{c['post_January_reentry_rounds']}个重入round、涉及{c['post_January_reentry_unique_stocks']}股，其中未闭{c['post_January_reentry_open']}个。已闭重入：{stat_text(c['post_January_reentry_closed'])}。这些后继round不加入上面一月胜率。")
 put('\n完整round收益分母为该round所有BUY本金+买入费用（包含ADD）；首层只用该层BUY本金+费用。round PnL含已记账股息，费用已净计。尾部定义为闭合净回报≥30%，不是MFE。')
 put('\n## 尾部身份与新增/丢失')
 for r in rows('JANUARY_COMPLETE_FEE_NET_30PCT_TAILS'):
  put(f"- {r['account']} {r['cohort']}：{r['sid']} {r['opened']} → {r['closed']}，净{num(r['pnl'])}，费后{pct(r['return_on_all_buy_cost'])}，{r['buy_fills']}次BUY、{r['sell_fills']}次SELL。")
 comp=rows('JANUARY_IDENTITY_COMPARISON') if (out/'JANUARY_IDENTITY_COMPARISON.csv').stat().st_size>1 else []
 for y in s['analyzed_DMI_branches']:
  cc=[r for r in comp if r['cohort']==y];counts=Counter(r['presence'] for r in cc)
  put(f"- {y}按精确sid+opened对照：双方同身份{counts['BOTH']}，DMI新增{counts['DMI_ONLY']}，PVR独有/丢失{counts['PVR_ONLY']}。相同股票不同opened仍是不同事件，不合并收益。")
  for r in cc:
   if r['presence']!='BOTH' and (r['PVR_closed_winner']=='True' or r['DMI_closed_winner']=='True'):
    tag='DMI' if r['presence']=='DMI_ONLY' else 'PVR';put(f"  - {r['presence']}闭合赢家：{r['sid']} {r['opened']}，净{num(r[tag+'_pnl'])}，回报{pct(r[tag+'_return'])}，尾部={r[tag+'_complete_tail30']}。")
 put('\n## 2024-09-24实际早参与与2026科技路径')
 pp=rows('2024_0924_ACTUAL_EARLY_PARTICIPATION')
 for label in s['full_accounts']:
  aa=[r for r in pp if r['account']==label];held=[r for r in aa if r['participated']=='True'];buy=[r for r in aa if int(r['early_BUY_fills'])>0]
  put(f"- {label}，9/24至10/8六交易日：实际持有{len(held)}只股票，实际BUY涉及{len(buy)}股/{sum(int(r['early_BUY_fills']) for r in aa)}笔；新开round {sum(int(r.get('early_NEW_rounds',0)) for r in aa)}个、持有中ADD {sum(int(r.get('early_ADD_fills',0)) for r in aa)}笔、其他持有中BUY {sum(int(r.get('early_OTHER_buy_while_held',0)) for r in aa)}笔，含9/23已持有库存。分母/全体观察股票由9/23—10/15本账户实际持仓或交易定义，非MFE赢家集。2026分支此段属于原PVR继承历史。")
 for r in rows('JIANGFENG_KEMA_ROUNDS'):
  if r['opened'][:10]<'2026-01-01' and r['closed'] and r['closed'][:10]<'2026-01-01':continue
  put(f"- {r['account']} {'江丰电子' if r['sid']=='300666.SZ' else '珂玛科技'} {r['sid']}：{r['opened']} → {r['closed'] or '未闭'}，BUY {r['buy_fills']}笔/SELL {r['sell_fills']}笔，净{num(r['pnl'])}，回报{pct(r['return_on_all_buy_cost'])}。")
 put('注意原native kind=add也可能成为0→有仓的新round首BUY。上述新开/持有中ADD按实际round首层identity互斥划分，不按kind直接推断；原kind计数另列CSV。原生joint_v3.py:243–255规定mobile由新CP1+continuing Q触发，无held条件，并直接写kind=add；因此mobile可以成为首BUY，不能把kind当生命周期。')
 put('更广科技路径仅按冻结行业中与江丰/珂玛同sector的实际账户股票描述，见TECH_SECTOR_ROUNDS与ACTUAL_CASE_DAILY_POSITIONS；不以未来涨幅替代实际参与。')
 put('\n## 估值陈旧性与账目对账')
 for label,vs in s['valuation'].items():
  for d,v in vs.items():put(f"- {label} {d}：持仓{v['held']}股，旧价{v['stale_count']}股，旧价库存金额{num(v['stale_value'])}，最长{v['max_stale_sessions']}个共同交易日。")
 for r in rows('FINAL_AND_JANUARY_VALUATION'):
  if r['stale']=='True':put(f"  - {r['account']} {r['cutoff']} {r['sid']}：{r['shares']}股，mark {r['mark']}，最后有效观察{r['last_valid_observed_bar']}，陈旧{r['stale_common_sessions']}个交易日，库存{num(r['inventory_value'])}。缺bar原因UNKNOWN，不能称停牌。")
 put('所有每日NAV恒等式、原始mark库存重建、层→round→期末NAV、成交费用及2026期间贡献桥均已通过。封存源读前/读后hash不变。可用现金与股息应收分列，未将应收视作可花现金。不存在为分析新建的UNKNOWN锁存或任意剔除闭合round。')
 put('\n## 交付文件')
 put('- SUMMARY.json：全账户、分母、胜率、赔率、尾部、估值披露与来源哈希。')
 put('- ANNUAL_NAV_FEES.csv / DAILY_EQUITY_RISK.csv：年度与每日账户路径。')
 put('- JANUARY_COHORT_ROUNDS.csv / JANUARY_FIRST_BUY_LAYERS.csv / JANUARY_STOCK_EVENT_CHAINS.csv：冻结cohort、独立首层和互斥后继链。')
 put('- JANUARY_IDENTITY_COMPARISON.csv / JANUARY_COMPLETE_FEE_NET_30PCT_TAILS.csv：精确身份及尾部。')
 put('- ALL_ACTUAL_TRADES.csv / ALL_ROUNDS.csv / ALL_LAYERS.csv：可追踪账目明细。')
 put('- 2026_PERIOD_CONTRIBUTIONS.csv / 2026_LAYER_PERIOD_CONTRIBUTIONS.csv：继承库存与新层的期间归因。')
 put('- FINAL_AND_JANUARY_VALUATION.csv：每一持仓的观察日、mark、数量、金额和陈旧时长。')
 put('- 2024_0924_ACTUAL_EARLY_PARTICIPATION.csv / ACTUAL_CASE_DAILY_POSITIONS.csv / TECH_SECTOR_ROUNDS.csv：真实成交/持仓的案例路径。')
 report=out/'REPORT.md';assert not report.exists();report.write_text('\n'.join(lines)+'\n')
 (out/'REPORT_SOURCE_SHA256.json').write_text(json.dumps({'analysis_output_manifest':sha(out/'OUTPUT_SHA256.json'),'monthly_summary':mh,'renderer':sha(Path(__file__)),'REPORT.md':sha(report)},indent=2))
 print(str(report))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--analysis',type=Path,required=True);args=ap.parse_args();main(args.analysis)
