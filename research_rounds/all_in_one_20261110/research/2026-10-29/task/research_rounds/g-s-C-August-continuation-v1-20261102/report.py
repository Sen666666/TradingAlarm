"""Concise audited-saved-object readout. No strategy or account invocation."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,os
P=Path(__file__).resolve().parent;W=P.parent
def rd(p):return json.loads(Path(p).read_text())
def n(v):return f'{D(v):,.2f}'
def pct(v):return f'{D(v)*100:.4f}%'
def main():
 out=P/'analysis';verify=rd(out/'VERIFICATION.json');assert verify['passed'] and verify['all_four_complete'];rr=rd(out/'RESULTS.json');r={z['cell']:z for z in rr}
 old=rd(W/'g-s-C-AugSep-continuation-readiness-20261102/OLD_SC_PVR_MONTHLY.json');lines=['四个自有Jul31账户连续至Aug29；未重置、未执行September，原金融代码与参数不变。','', '账户 | Jul31 NAV | Aug29 NAV | Aug区间收益 | Jul1以来收益 | Aug DD | 全程DD | Aug平均曝险 | Aug费用']
 for c in ['C10','C20','C10_R0','C20_R0']:
  x=r[c];lines.append(' | '.join([c,n(x['initial_Jul31_NAV']),n(x['terminal_NAV']),pct(x['August_return']),pct(x['continuous_Jul1_return']),pct(x['August_max_close_DD']),pct(x['continuous_max_close_DD']),pct(x['August_mean_exposure']),n(x['August_fee'])]))
 lines+=['','旧SC/PVR仅作同母体、同原起点连续参考；当前C替换了多项许可/配置/退出语义，不是仅排序的一因子对照。']
 for c in ['SC','PVR_SLOT1']:
  x=next(z for z in old[c] if z['month']=='2025-08');lines.append(c+' Aug '+str(round(D(x['month_return_pct']),4))+'%；Jul1→Aug29财富 '+n(x['end_NAV'])+'。')
 ref=rd(P/'OLD_AUGUST_TRADE_REFERENCE.json')
 for c,v in ref.items():lines.append(c+' Aug平均曝险 '+str(round(D(v['month']['mean_close_exposure_pct']),4))+'%；买/卖毛款 '+n(v['actual_buy_gross'])+' / '+n(v['actual_sell_gross'])+'；实际费用 '+n(v['actual_fees'])+'。')
 lines+=['','R0两条对照的本月差额包含各自July遗留状态反馈，不能当作Aug1才切开关的局部反事实：']
 for base,on in [('C10','C10_R0'),('C20','C20_R0')]:
  x,y=r[base],r[on];end=D(y['terminal_NAV'])-D(x['terminal_NAV']);start=D(y['initial_Jul31_NAV'])-D(x['initial_Jul31_NAV']);lines.append(on+' 对 '+base+'：末财富差 '+n(end)+'，月初已存在差 '+n(start)+'，August财富变化差 '+n(end-start)+'。')
 for c in ['C10','C20','C10_R0','C20_R0']:
  x=r[c];p=x['pnl'];a=x['August_accounting_change'];lines+=['',c+' 全账累计：实际卖出净损益 '+n(p['realized_actual_sales_net_buy_and_sell_fees'])+'；剩余未实现 '+n(p['unrealized_mark_minus_remaining_net_buy_cost'])+'；确认股息 '+n(p['booked_dividends'])+'（应收不可花 '+n(p['dividend_receivable'])+'）；零股核销 '+n(p['fractional_writeoff'])+'。',
   'August变化：实际卖出净损益 '+n(a['realized_actual_sales_net_buy_and_sell_fees'])+'；未实现变化 '+n(a['unrealized_mark_minus_remaining_net_buy_cost'])+'；股息 '+n(a['booked_dividends'])+'。累计闭合层正/负贡献 '+n(p['closed_layer_positive'])+' / '+n(p['closed_layer_negative'])+'；未平层贡献 '+n(p['open_layer_contribution'])+'，其中已卖部分 '+n(p['open_layer_realized_partials'])+'、股息 '+n(p['open_layer_dividends'])+'，不可全称浮盈。',
   'August买/卖毛款 '+n(x['August_buy_gross'])+' / '+n(x['August_sell_gross'])+'；实际买/卖fill '+str(x['August_buy_fills'])+'/'+str(x['August_sell_fills'])+'；新获资股票 '+str(x['August_funded_stocks'])+'；同开盘双向 '+str(len(x['same_open_roundtrips']))+'组；同买入日后请求退出 '+str(len(x['same_buy_day_exit_request_layers']))+'层。',
   'August正贡献前3 '+', '.join(z['name']+' '+n(z['August_contribution']) for z in x['top_positive'][:3])+'；负前3 '+', '.join(z['name']+' '+n(z['August_contribution']) for z in x['top_negative'][:3])+'。',
   '完整July→August首股票×市场context freshCP1/股票Q/市场许可母体 '+str(x['first_opportunity_groups'])+'组，后来同context真实获资 '+str(x['first_opportunity_funded'])+'；这是市场资格而非全约束合法订单。未获资另分市场context已结束/仍未结束，不全称期末删失。']
  ss=rd(out/(c+'-STOCKS.json'));chains=rd(out/(c+'-ACTUAL_CHAINS.json'))
  for name in ['上纬新材','德福科技','淳中科技']:
   stock=next((z for z in ss if z['name']==name),None);chain=next(z for z in chains if z['name']==name);buy=[z for z in chain['actual_trades'] if z['side']=='buy'];lines.append('固定对照 '+name+'：累计贡献 '+n(stock['contribution'] if stock else 0)+'，August贡献 '+n(stock['August_contribution'] if stock else 0)+'；首次实际买 '+(buy[0]['at'] if buy else '无')+'。')
 lines+=['','持续赢家及迁移的实际链（不是逐元现金归因）：',
  '华胜天成截至Aug29四臂均已全清；累计实际净已实现分别为C10 19711.87、C20 62555.12、C10_R0 18359.08、C20_R0 58625.09元。欧陆通亦均全清，净已实现分别15811.06、18349.84、15811.06、17080.45元；证明有实际兑现，也呈现不同持有/筹资路径。',
  'C10 Aug13 CLOSE安排华胜6800股，Aug14实卖毛额109561.19并同开盘净结算109477.48；同一证书实际C买入鼎通/特发/光库/中际/太辰光/中瓷。Aug27 CLOSE再次安排华胜4000股，Aug28实卖毛额98070.94，同证书买移远/长芯/威胜/剑桥/美格/永鼎/岩山。',
  'C10 Aug20 CLOSE安排欧陆通400股，Aug21实卖毛额99150.40并净结算99074.64，同证书实际C买光迅/海能达/通宇。C20卖出较分步；具体每个原生卖单、来源层/理由、结算及所有目标角色见ACTUAL_FUNDING_FLOWS。',
  '另有明确未兑现筹资目标：C20 Aug22计划中国软件1800/东华软件3900，Aug25欧陆通200股实际卖出52115.93、净结算52076.11；这两个原目标在原有效窗内所有角色均零实际买入，C路由直接记录account_risk6，T回退另含probe_risk.5。源证据C20-AUG25-SOLD_WITHOUT_ORIGINAL_TARGET_BUY.json。它说明收盘联立可行与开盘实际资源重验之间存在执行取舍，不推算取消该卖单的反事实收益，也不自动判为实现错误。',
  '这些是原筹资目标与同证书买入的原生关联；一个批次可共享多笔来源，另有原可用现金，不能重复加总同批买款或称某一卖单独自支付全部新买。目标买入同时另列core/T等非C角色，避免零C成交被误称完全没有买。',
  '淳中科技四臂July–August均零实际成交。父线程有限独核C10两臂Aug各10个fresh/Q，9个成熟S计划0，必要界指向account_risk6；这不是全约束反事实，也未证明单独抬限即可合法买入。旧PVR同月实际已实现27602.60。证据/tmp/August-C10-limited-readonly-20261102/FINAL_READOUT.json。',
  '当前证据说明：新C能够持有并兑现部分持续上涨股，却仍错过另一些合法强机会，并把有效旧仓频繁挪至新目标。四臂均未在August弥补相对旧SC/PVR的连续财富差距。R0在C10两月净付出11261.72、在C20净增加12348.23，不能作普遍晋升；也不能把差距单归费用或排序。应先评审回到较好冻结参照研究最小增量，暂停继续给新C叠修补。']
 lines+=['','证据与限制：'+str(verify['event_states'])+'个新事件状态的七财务桥逐项0；全部四个Aug1完整输入/物理十通道截断/跨进程门已通过。原July来源与账户状态不改。',
  '执行通道中断2次，旧会话失去句柄且无退出码；最后成功CP重新核SHA/完整恢复后严格后续接续。第二次另有父线程独立进程/检查点证据/tmp/August-progress-readonly-20261102/STATUS.json；本线程未调用进程盘点。旧日志及未完成压缩件在interruption-1、interruption-2；没有重新空仓或重放已提交日。旧running标记原样留史，完成状态以新返回码、COMPLETED及PROGRESS为准。',
  '为防磁盘耗尽，本轮已完成非当前状态以gzip无损存储；每文件原SHA及解压回读核同见LOSSLESS_OUTPUT_ARCHIVE.json。Aug1技术前缀、当前终态、原July来源均保留原格式。金融源码未因归档改变；归档只是输出格式。',
  '当前快照回看非PIT；当日H/L/volume参与执行代理，非真实开盘可得性认证。所有月份/股票保留；未按未来赢家配名单，没有以少亏或更多参与自动判优。September未执行，Sep12定向转增仍未开发。',
  '下一研究判断应同时看持续赢家资金到位/持有/退出重入与合计假启动损耗；不能只在新C内部宣布R0改良，也不能把旧PVR浮盈当最终已兑现。这里只交完整有限窗口结果，不自动追加策略或日期。']
 (P/'REPORT.txt').write_text('\n'.join(lines)+'\n')
 (P/'AUDIT_ENTRY.txt').write_text('金融代码 august_runtime.py SHA '+hashlib.sha256((P/'august_runtime.py').read_bytes()).hexdigest()+'\nAUTHORIZATION.json / INPUT_IDENTITY.json / ALL_FOUR_PREFIX_GATES.json\n各runs/<cell>/PROGRESS.json和终态pickle/provenance/JSON；中间完整字节见LOSSLESS_OUTPUT_ARCHIVE.json\nanalysis/VERIFICATION.json七桥；RESULTS及每档STOCKS/SECTORS/LAYERS/SALES/DAILY/EXIT_REASONS/FIRST_OPPORTUNITIES/ACTUAL_CHAINS\n所有原July数据/源/账不改，先复用旧独审，仅核本次horizon及新交互。\n')
 print('FOUR_AUGUST_REPORT_READY',flush=True)
if __name__=='__main__':main()
