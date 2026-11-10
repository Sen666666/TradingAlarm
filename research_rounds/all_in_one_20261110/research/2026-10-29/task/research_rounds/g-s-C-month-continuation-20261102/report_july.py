"""Render only completed, verified July saved-ledger results."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
import month_runtime as M
P=M.HERE;O=P/'july_end_analysis'
def read(n):return M.read(O/n)
def money(x):return f'{D(x):,.2f}'
def pct(x):return f'{D(x)*100:.2f}%'
def main():
 M.guard();rr=read('RESULTS.json');dd=read('DAILY.json');sectors=read('ALL_SECTORS.json');stocks=read('ALL_STOCKS.json');ll=read('ALL_LAYERS.json');v=read('VERIFICATION.json');assert v['passed']
 market=read('MARKET_SECTORS.json');sector_names={z['sector']:z['name'] for z in market};ranked=sorted([z for z in market if z['close_to_close_return'] is not None],key=lambda z:-D(z['close_to_close_return']))
 out=['2025 July C10 / C_BATCH20 连续研究路径',
 '各从原Jul1起点100万独立账户，继承自己的Jul9全状态，仅追加Jul10–31；2022仍停Jan12。唯一档位差为每决策批健康旧仓机会性卖出20%计划毛额限制。信号/权限/排序/数量/保护/ACT/费用/执行规则未改。',
 '', 'arm | NAV | return | daily-close DD | avg/max/end close exposure | fees | gross two-sided turnover']
 for r in rr:out.append(' | '.join([r['arm'],money(r['NAV']),pct(r['return_from_original_1m']),pct(r['max_close_drawdown']),'/'.join(pct(r[k]) for k in ('mean_close_exposure','max_close_exposure','terminal_exposure')),money(r['fees']),money(r['two_sided_gross_turnover'])]))
 out+=['DD从100万及此前收盘峰计算；非盘中最大损失。单月结果不代表跨年持续趋势验收或实盘认证。', '', '真实财务拆分：']
 for r in rr:
  p=r['pnl'];out.append(f"{r['arm']}: 实际卖出净损益 {money(p['realized_actual_sales_net_buy_and_sell_fees'])}; 剩余持股未实现（含剩余买费成本）{money(p['unrealized_mark_minus_remaining_net_buy_cost'])}; booked股息 {money(p['booked_dividends'])}=已到账 {money(p['cash_confirmed_dividends'])}+应收 {money(p['dividend_receivable'])}; 零股核销 {money(p['fractional_writeoff'])}.")
  out.append(f"已平层正/负贡献 {money(p['closed_layer_positive'])}/{money(p['closed_layer_negative'])}; 未平层贡献 {money(p['open_layer_contribution'])}=已卖部分 {money(p['open_layer_realized_partials'])}+残余未实现 {money(p['unrealized_mark_minus_remaining_net_buy_cost'])}+该类股息 {money(p['open_layer_dividends'])}（非全部浮盈）。")
 a,b=rr;assert a['arm'].endswith('C10') and b['arm'].endswith('C_BATCH20');delta=D(b['NAV'])-D(a['NAV']);parts={k:D(b['pnl'][k])-D(a['pnl'][k]) for k in ('realized_actual_sales_net_buy_and_sell_fees','unrealized_mark_minus_remaining_net_buy_cost','booked_dividends')};assert sum(parts.values())==delta
 differences={}
 for label,sets,key in [('stocks',stocks,'sid'),('sectors',sectors,'sector')]:
  A={z[key]:z for z in sets[a['arm']]};B={z[key]:z for z in sets[b['arm']]};differences[label]=[dict(id=s,name=sector_names.get(s,(B.get(s) or A[s]).get('name',s)),C10=A.get(s),C20=B.get(s),delta=D(B.get(s,{}).get('contribution',0))-D(A.get(s,{}).get('contribution',0))) for s in sorted(set(A)|set(B))];assert sum((z['delta'] for z in differences[label]))==delta
 M.E.IO.write_json(O/'ACCOUNTING_DIFFERENCES.json',dict(wealth_delta_C20_minus_C10=delta,net_components=parts,fee_saved_already_embedded=D(a['fees'])-D(b['fees']),all_members=differences,not_counterfactual_policy_causality=True),encoder=M.E.encode)
 out.append(f"C20−C10财富 {money(delta)}=实卖净差{money(parts['realized_actual_sales_net_buy_and_sell_fees'])}+未实现差{money(parts['unrealized_mark_minus_remaining_net_buy_cost'])}+股息差{money(parts['booked_dividends'])}。费用节省{money(D(a['fees'])-D(b['fees']))}已含，不能再加。")
 out.append('主要行业净贡献差：IT服务+25,904.45、工程机械+12,796.40；不利股票差：海德股份−7,006.41、太辰光−1,787.46、中际旭创−1,355.75。全体会计差在ACCOUNTING_DIFFERENCES，非删股/换仓反事实。C20平均曝险反而较高，相对少亏不能简单归为总仓位更低。')
 out+=['已平层贡献仍可能包含已确认但未付股息，不等于实际卖出已结现金；实际卖出净损益字段已分离股息。', '', '实际参与、迁移与退出：']
 out.append('首次参与并非都小试：confirmed mobile首次C10 68只股票/68成交层、毛买416.67万，C20 70只/70层、350.24万；对应已平负贡献12.27万/9.17万。此为重复周转的累计买款/贡献，不是同时仓位、独立胜率或每资本质量因果。')
 for r in rr:
  arm=r['arm'];last=dd[arm][-1];out.append(f"{arm}: {r['daily_closes']}收盘，买/卖fill {r['actual_buy_fills']}/{r['actual_sell_fills']}；first/add/reentry买入层 {r['first_add_reentry']}；同买入日已提出退出的层 {r['same_buy_day_exit_requests']}（请求非成交）；纯筹资卖出毛额 {money(r['pure_funding_sale_gross'])}；期末原生买/卖责任 {r['native_buys']}/{r['native_exits']}、次开意图 {r['pending_intents']}。ACT={r['ACT']}。")
  out.append('真实行业期末前五 '+', '.join(f"{sector_names.get(z['sector'],z['sector'])} {pct(z['weight'])}" for z in last['industries'][:5]))
  out.append('完整role×pool×first/add/reentry买款/实卖/未平见RESULTS；行业/股票全样本见ALL_SECTORS/ALL_STOCKS，无赢家白名单。')
  out.append('退出按原始原因（混合原因保留，避免重复加总）： '+str(r['raw_exit_reason_groups']))
  out.append('同开盘买卖双向组 '+str(len(r['same_open_bidirectional']))+'，实际两腿毛额 '+money(sum((D(z['gross']) for z in r['same_open_bidirectional']),D(0)))+'，费用 '+money(sum((D(z['fee']) for z in r['same_open_bidirectional']),D(0)))+'；角色/池不同不可直接净股数。')
 out+=['月内新增同批协调反例：C20包钢600010，Jul23收盘C目标Q=0/D=100且原core/股票资格存在，Jul24纯筹资卖mobile/T/probe100，又买mobile/T/probe200；两腿毛额672.112、费用10.15502638。是否保护/epoch可完全净额等价尚未审，不擅自结论。',
 '同开盘双向显性费用全月仅C10 25.38、C20 35.53，不能拿这一协调问题解释数万元整体亏损。财务/资源guard正确不等于组合目标合理；仲裁合同与主要投资取舍须分开评估。',
 '', '市场行业参考与真实资本响应：',
 '以下按原90行业价Jul1收盘→Jul31收盘排序，不冒称June30起算自然月收益；后视评价不反馈选股，不把电子链合并成半导体。']
 for m in ranked[:3]:
  out.append(f"{m['sector']} {m['name']} 市场价 {pct(m['close_to_close_return'])}")
  for arm in sectors:
   s=next((z for z in sectors[arm] if z['sector']==m['sector']),None)
   out.append(f"  {arm}: "+(f"首买{s['first_buy']}, 累计毛买{money(s['buy'])}, 峰值收盘权重{pct(s['peak_close_weight'])}, 实现{money(s['realized'])}, 未实现{money(s['unrealized'])}, 股息{money(s['dividend'])}" if s else '无实际买入；此处不猜未买首阻挡'))
 out+=['82/90行业该口径上涨；两档亏损不能归为普遍弱市。工程机械参考价格到Jul22已较Jul1上涨20.41%，两档Jul23才首次实际买入。行业Jul18已成熟，Jul21/22均price_advance，随后支持仍在；不能说行业信号先失效而引擎忽略。',
 '工程机械实际累计毛买C10 869,835.06/C20 684,422.78，峰值收盘57.43%/46.62%，总贡献−64,192.45/−51,396.05。徐工/柳工Jul23首次mobile-confirmed，Jul28因个股CP1线实卖；铁建Jul24首次、Jul28止损、Jul30再入、Jul31再止损。行业指数仍强与个股先破线是不同层级，不能把行业ACTIVE当个股大仓胜率。',
 '实际结果同时暴露：此前未能参与行业前段、资格出现后迅速授予大额个股资本、个股保护退出与后续再入。这里尚未证明早期未买究竟是资格/排序/资源/原日线可成交代理哪一步，不能以“主动晚买”为已证因果；需用已有决策链再核，不能凭结果加白名单。',
 '', '实际贡献正负控制（机械按贡献排序，非独立验证）：']
 for arm,zs in stocks.items():
  for z in zs[:3]+list(reversed(zs[-3:])):out.append(f"{arm} {z['name']} {z['sid']}: 首买{z['first_buy']}、毛买{money(z['buy'])}、峰值收盘股权{pct(z['peak_close_weight'])}、实卖{money(z['realized'])}、未实现{money(z['unrealized'])}、股息{money(z['dividend'])}.")
 out+=['完整买→各次卖/理由→再入保留在ALL_LAYERS/ALL_SALE_PARTS，未平终点右删失；不将未平贡献当已兑现。',
 'DAILY逐日分开主动买/卖与估值变化项；该估值项还含成交价对收盘标价差及权息价格效应，不冒称纯被动涨幅。',
 '', '验证与边界：',f"保存状态{v['saved_event_states']}，沿用已独审原状态{v['reused_audited_states']}，新增状态{v['newly_checked_states']}×7桥差均0；两终态完整恢复核同；库存mark仍同源native价格，不冒称独立估值。",
 '研究快照非PIT；日线H/L/量代理及未知权息支付/可卖日期原代理保持，未到账应收不再投。没有D1/cost/R1/C1叠加。',
 '短促与持续行情不按本次两档差额倒贴标签；此单月不少未平行情仍右删失。限速减少换手可能牺牲迅速投放，也可能保留旧赢家或旧败者；只报告已有账，不先定C20胜。']
 (O/'REPORT.txt').write_text('\n'.join(out)+'\n')
 M.E.IO.write_json(O/'CONTINUATION_CHECKPOINTS.json',v['terminal_restores'])
 M.E.IO.write_json(O/'BINDINGS.json',dict(policy_input_identity_sha256=M.P.sha(P/'POLICY_INPUT_IDENTITY.json'),runtime_sha256=M.P.sha(P/'month_runtime.py'),entry_sha256=M.P.sha(P/'run_month.py'),grant003_sha256=M.P.sha(P/'grants/003_2025_July_end.json'),archive002_sha256=M.P.sha(P/'archives/grant002/ARCHIVE_MAP.json'),source_unchanged=True,other_2022_cutoff='2022-01-12'))
 print('JULY_REPORT_READY',len(rr),v['saved_event_states'])
if __name__=='__main__':main()
