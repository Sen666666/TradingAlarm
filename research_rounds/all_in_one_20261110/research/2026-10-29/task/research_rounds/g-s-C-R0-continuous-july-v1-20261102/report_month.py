"""Saved results only; no financial events."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
P=Path(__file__).resolve().parent;O=P/'analysis';B=P.parent/'g-s-C-month-continuation-20261102/july_end_analysis'
def read(p):return json.loads(Path(p).read_text())
def num(x):return f'{D(x):,.2f}'
def pct(x):return f'{D(x)*100:.4f}%'
def main():
 rows=read(O/'RESULTS.json');old=read(B/'RESULTS.json');vv=read(O/'VERIFICATION.json');assert vv['passed'];lines=['2025年7月连续原100万元起点：C授权逐股风险保持（R0）','只新增R0执行政策。C10/C_BATCH20各自原起点连续，不拼Jul22局部回放。原基线账户未重跑。','两日前缀门：OFF完整对象等原前缀；ON完整/物理截断和跨进程恢复核同。新来源证书身份及其派生哈希以完整底层正文验证后归一。','']
 for r in rows:
  m=r['mode'];o=next(z for z in old if z['arm']=='2025_26-'+m);delta=r['vs_original'];p=r['pnl'];lines += [m+':',f"原策略收益 {pct(o['return_from_original_1m'])} → +R0 {pct(r['return_from_1m'])}；NAV {num(o['NAV'])} → {num(r['NAV'])}，差 {num(delta['NAV_difference'])}。",f"收盘最大回撤 {pct(o['max_close_drawdown'])} → {pct(r['max_close_DD'])}；平均/峰值曝险 {pct(r['mean_close_exposure'])}/{pct(r['max_close_exposure'])}（原 {pct(o['mean_close_exposure'])}/{pct(o['max_close_exposure'])}）。",f"真实买款 {num(r['buy_gross'])} / 卖款 {num(r['sell_gross'])} / 费用 {num(r['fees'])}；相对原买款差 {num(delta['buy_gross_difference'])}、卖款差 {num(delta['sell_gross_difference'])}、费用差 {num(delta['fee_difference'])}。",f"收盘名义风险/NAV平均 {pct(r['mean_close_nominal_risk_NAV'])}、峰值 {pct(r['max_close_nominal_risk_NAV'])}（含原执行锁；旧仓价格变化可使存量高于新买限额，并非R0承诺全账户回撤上限）。",f"实际卖出净损益 {num(p['realized_actual_sales_net_buy_and_sell_fees'])}；剩余持股未实现 {num(p['unrealized_mark_minus_remaining_net_buy_cost'])}；股息已确认总额 {num(p['booked_dividends'])}=已到账 {num(p['cash_confirmed_dividends'])}+应收 {num(p['dividend_receivable'])}；零股核销 {num(p['fractional_writeoff'])}。",f"已平层正/负贡献 {num(p['closed_layer_positive'])}/{num(p['closed_layer_negative'])}；未平层贡献 {num(p['open_layer_contribution'])}，其中已卖部分 {num(p['open_layer_realized_partials'])}、股息 {num(p['open_layer_dividends'])}。未平层贡献不等于浮盈。",f"实际获资股票 {r['actual_funded_stocks']}，新增/失去股票 {len(delta['new_funded_stocks'])}/{len(delta['lost_funded_stocks'])}；买/卖fill {r['buy_fills']}/{r['sell_fills']}。",'全股贡献差额前5正/负（是完整账户差额归因，不是删除交易反事实）：']
  ds=delta['stock_differences']
  for z in ds[:5]+list(reversed(ds[-5:])):lines.append(f" {z['sid']} {z['name']}：差 {num(z['contribution_difference'])}，原/新买款 {num(z['old_buy'])}/{num(z['new_buy'])}，原/新首次买 {z['old_first']}/{z['new_first']}")
  lines.append('角色/池/首次追加重入分母与正负贡献：')
  for z in r['role_pool_first_add_reentry']:lines.append(f" {z['role']}/{z['pool']}/{z['entry_class']}: {z['layers']}层/{z['stocks']}股，买款{num(z['buy_gross'])}，已平正/负{num(z['closed_positive'])}/{num(z['closed_negative'])}，未平贡献{num(z['open_contribution'])}")
  lines += [f"ACT: {r['ACT']}",f"期末pending {r['pending_intents']}，原生待买/待卖 {r['active_native_buys']}/{r['active_native_exits']}。",'']
 lines += ['完成臂：'+','.join(vv['completed_modes'])+'。未列的臂不代表完成或被删除；C20当前完整状态见运行阻断记录。',f"财务检查：{vv['event_states']}个新路径保存事件，每事件沿已核独立7项现金/股数/权益/费用/贡献核验；完整分析未推进账户。",'研究限制：同一当前快照1709身份/90行业、原量价和权息代理、日线执行代理、非PIT/非独立未见样本；风险保持不保证止损价格或最大回撤。后排资源反馈、旧筹资未自动撤销及赢家跳空缩量的代价均保留。','当前只完成固定月度比较，不据单月晋升或调整参数。']
 (P/'REPORT.txt').write_text('\n'.join(lines)+'\n')
 files=[P/'month_r0.py',P/'run_july.py',P/'INPUT_IDENTITY.json',P/'CONTINUATION_AUTHORIZATION.json',P/'TWO_DAY_GATE.json',O/'RESULTS.json',O/'VERIFICATION.json',P/'REPORT.txt']
 (P/'AUDIT_ENTRY.txt').write_text('\n'.join(str(f)+' SHA256 '+hashlib.sha256(f.read_bytes()).hexdigest() for f in files)+'\nExact invocation: python -B analyze_month.py; python -B report_month.py (read-only saved accounts)\nFormal checkpoints: runs/{C10,C_BATCH20}/PROGRESS.json; every original ACTION/OPEN/CLOSE checkpoint/provenance/event snapshot retained.\n')
 print('\n'.join(lines[:4]))
if __name__=='__main__':main()
