"""Condense already-saved cohort evidence; no formula or account replay."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import sys,statistics
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import analyze as A
Z=D(0)
def money(x):return f'{D(x):,.2f}'
def main():
 ev=A.read(HERE/'EVENTS.json');su=A.read(HERE/'SUMMARY.json');checks=A.read(HERE/'CHECKS.json');pre=A.read(HERE/'NO_OPPORTUNITY_SALE_PREVIEWS.json')
 layer=A.read(A.MONTH/'july_end_analysis/ALL_LAYERS.json');sale=A.read(A.MONTH/'july_end_analysis/ALL_SALE_PARTS.json');ctx=A.read(A.ENG/'DAILY_RESOURCE_CONTEXT.json');roles={};controls={};cash={};extra={}
 lines=['七月CP1重置证据→新增资本：全母体只读审查','',
 '先给否定证据：repair是普遍的市场事件，但不是这两账主要已观察损耗来源。禁止repair凭据卖健康旧仓也挡不住铁建Jul29：原第一笔13828股、D={}已全量合法。没有新经济路径、指标、正式规则或参数。','',
 '固定母体为全Jul1—31的3336张canonical fresh CP1，含未配置、Q未知。两档同一市场母体，不能当6672独立机会。',
 '860 RESET_SEEK_REPAIR（741股）：333负事件+低锚，287只有已见负事件，240只见低锚；后者并不等于此前有失败交易。',
 '2221 UP_CONTINUATION（1049股）；178 SEEK起源未知（178股）；77已知start后的首次（77股）。股票在类别间重叠。',
 'repair中133张外层root继承未知，但低锚重置本身已可见；UP中1617张root继承未知，原生phase=UP仍可读取，不能伪造完整历史。178张未知不并入UP或repair。',
 'recipe：只读原phase/reset_reason/delta_frontier/segment/I字段；E0_down_reset及lower_anchor之后第一张SEEK凭据归repair，receipt_consumed不重置市场证明。未重置UP凭据归延续。CP1.e0_valid实际是原i_target，不是新的原E0失效定义。','']
 lines+=['源码native_c.py:350—363在fresh合法receipt后统一计算max_q=floor(决策NAV×10%/含滑点价)，不读CP1的SEEK/UP或重置原因。TARGET_SIZE_DESCRIPTIVE核：C10 repair/UP原raw目标中位数分别9.94995%/9.95067%NAV；C20为9.95316%/9.94829%。这是尚未联立裁剪的目标，不是获准或成交，最小单位也可能使raw_max=0。说明同映射是普遍代码机制，不只是铁建特例。','']
 for arm,events in ev.items():
  rp=defaultdict(lambda:dict(layers=0,buy=Z,realized=Z,unrealized=Z,dividend=Z,contribution=Z,entry_class=Counter()))
  for e in events:
   for l in e['actual_layers']:
    k=e['classification']['kind']+'|'+l['role']+'|'+l['pool']+'|'+l['purpose'];v=rp[k];v['layers']+=1;v['buy']+=D(l['buy_gross']);v['realized']+=D(l['realized_trade_PNL']);v['unrealized']+=D(l['unrealized_net_buy_cost']);v['dividend']+=D(l['booked_dividend_income']);v['contribution']+=D(l['total_contribution']);v['entry_class'][l['entry_class']]+=1
  roles[arm]=dict(rp)
  lines.append(arm+'：事件类别 / 正C计划 / C实预留 / C实成交 / 所有关联角色层(首次/追加/再入) / 实际买款 / 实现 / 未实现 / 股息AR')
  for k,g in su[arm].items():lines.append(f"{k}: {g['events']} / {g['C_positive']} / {g['C_actual_reserved']} / {g['C_actual_filled']} / {g['layers']}{g['entry_classes']} / {money(g['actual_buy_gross'])} / {money(g['actual_realized'])} / {money(g['unrealized'])} / {money(g['booked_dividend'])}")
  lines.append('closed正/closed负/open层总贡献：')
  for k,g in su[arm].items():lines.append(f"  {k}: {money(g['closed_positive'])} / {money(g['closed_negative'])} / {money(g['open_layer_contribution'])}")
  lines.append('role/pool不能混：')
  for k,v in rp.items():lines.append(f"  {k}: 层{v['layers']}，买{money(v['buy'])}，净贡献{money(v['contribution'])}，{dict(v['entry_class'])}")
  c=checks[arm];lines.append(f"完整原生买层{c['actual_layer_total']}，其中{c['layers_with_same_signal_fresh_receipt']}层可连到本母体；另{len(c['core_only_or_nonfresh_layers'])}层core-only/非fresh单列，不硬塞CP1分类。8张Q未知、False=0。")
  pv=pre[arm];lines.append(f"repair正计划无D校验{len(pv)}条：单独该原数量通过{sum(v['standalone_no_sale']['ok']for v in pv)}，保留原早先Q前缀且全批D为空通过{sum(v['fixed_original_Q_prefix_no_sale']['ok']for v in pv)}。后者失败可能含早先Q冲突，不冒称该receipt独占因；Q为原计划数，不冒充实际fill量。")
  extra[arm]=dict(negative_reset_rows=c['native_CP_negative_reset_count'],negative_reset_I_still_valid=c['negative_reset_with_I_still_valid'],
   repair_subtypes=dict(Counter('negative_and_low' if e['classification']['negative_reset_observed']and e['classification']['lower_anchor_observed']else 'negative_only'if e['classification']['negative_reset_observed']else 'low_only'for e in events if e['classification']['kind']=='RESET_SEEK_REPAIR')),
   repair_unfunded_events=sum(not e['actual_layers']for e in events if e['classification']['kind']=='RESET_SEEK_REPAIR'))
  # No-source-laundering ledger appendix, not a counterfactual cash replay.
  episode=[]
  for day in ('2025-07-28','2025-07-29'):
   ss=[v for v in sale[arm]if v['at'][:10]==day];bb=[v for v in layer[arm]if v['opened'][:10]==day];g=defaultdict(lambda:Z)
   for v in ss:g[v['reason']]+=D(v['net_cash'])
   episode.append(dict(day=day,actual_sale_parts=ss,sale_net_by_original_reason=dict(g),actual_buy_cost=sum((D(v['buy_cost'])for v in bb),Z),actual_buy_layers=bb))
  cash[arm]=dict(actual_episode=episode,Jul29_actual_available=next(c['available']for c in ctx[arm]if c['day']=='2025-07-29'),historical_opportunity_sales_not_relabelled_as_independent=True,
    cash_fungible_no_unique_historical_source_assignment=True,no_counterfactual_path_without_past_sales_claimed=True)
  # Fixed posthoc positive controls: original candidate list preserved, below-prior-UP repair is
  # used only to expose the strongest old-high-veto counterexample, never for trade eligibility.
  cc=[]
  for x in A.read(HERE/'POSITIVE_CONTROL_CANDIDATES.json')[arm]:
   e=x['repair_event'];prior=[z for z in x['all_stock_receipt_events']if z['day']<e['day']and z['classification']['kind']=='UP_CONTINUATION']
   if prior and e['classification']['signal_close']<max(z['classification']['signal_close']for z in prior):cc.append(x)
  controls[arm]=cc
 A.save('ROLE_POOL_GROUPS.json',roles);A.save('ADDITIONAL_COUNTS.json',extra);A.save('NORMAL_PULLBACK_POSITIVE_CONTROLS.json',controls);A.save('CASH_PROVENANCE_EPISODE.json',cash)
 lines+=['','解释边界与关键反例',
 'repair市场事件860张中，实际层各18：15首次参与、1追加、2再入（其中1是微小core再入，另1才是铁建mobile）。不能把860张当重复买失败股，也不能把市场repair叫账户恢复。',
 'C10 repair实际新增74.99万，归属层净+485.96；C20新增64.84万、净+1877.88。UP组分别新增384.95万/324.50万、净−78264.25/−37049.73。来源、角色、资本量和期末删失不同，不能推出UP预测更差或small-repair政策有效；只能否定“这类repair解释了主要七月损耗”。',
 '铁建：C10首次UP层买96249.66、净−11355.25；Jul29 repair再入层买91310.43、净−2532.87（均实际已闭合）。铁建主要亏损早于repair；删除第二层损失不是可执行反事实收益。',
 '反例平安电工：Jul4 repair首次实际买94822.39，最终净+4302.11；之后Jul9负事件、Jul14低锚，Jul16再次repair，原同源close39.2974低于Jul8的41.3544；Jul17 UP新凭据已到43.2272，Jul23为54.5456。Jul16这张未获C资金，不能把此前老层利润归给它；若等下一证明才允许大目标，确有继续涨快、预算又拥挤的代价。',
 '反例德福科技：Jul8 UP close37.8844→Jul11负事件/14低锚→Jul17 repair close37.0141（尚未回旧高）→Jul21 UP40.4250→Jul31为50.4330。原账实际早先core/probe及小mobile层整月共+3928.80，Jul17 repair与后来UP仍未获C扩张资金。此为真实赢家的正常回撤价路，不是“给repair钱一定赚”的交易证明；也反驳恢复必须回原高的硬门。',
 '上述控制是确定性后视逻辑反例，不是独立验证集；全部正例候选列表留存，不只挑两股。月底后未知，未做持续年限判定。','',
 '便宜必要性检查：不让repair凭据出售健康旧仓',
 'C10 Jul29铁建原第一项q=13828、D={}，全部原B/J约束通过；reserve现金底线后余46176.30，风险55414.47/56031.90、余617.43元，股资本余3.30元；不是靠放宽risk或借不存在款项。该凭据在本批前没有旧授权，故不需为它新卖健康仓。C20 q14376也在原第一项D={}通过。此门挡不住核心case，停止把它当解法，不补条件。',
 '但真实闲置现金不等于历史从未卖健康旧仓：附录完整列Jul28/29实际CP1退出与actionable_S_funding现金。后者没有改名为独立退出；资金可追溯但现金可互换，未声称移除过去筹资后的账户仍相同，也未把其他目标此前筹资变成该repair新授权。若要永久按现金历史来源禁用，会是另一个更大政策，当前没有测试。','',
 '原生身份可复用范围',
 '可直接复用：canonical receipt_id/前一市场receipt链、原source/segment、I结构(原C_demand receipt_binding内可得时)、原E0_episode、F1行业context/permit。',
 '不能互相替代：E0_episode/I结构会跨CP1负事件而仍有效；canonical形成区间和receipt_consumed是凭据积累/消费钟，不是市场repair重置ID。',
 '现CP1无显式完整reset-context字段；本报告诊断ID仅由已见sid/segment/重置日/原原因组成。root继承未知保留未知，没导出完整前史补猜。未来如接策略，需原生持久该身份、严格as-of导入，不可拿这份诊断字符串冒充已存在字段。','',
 '唯一最小候选轮廓（不冻结、不实现）',
 '把“市场资格仍在”“首次repair新机会”“同一已知重置片段之后再次真实UP前沿凭据”分开。首次repair不自动获得满stock目标；其有限新增金额尚待合同审查，不能先定2%。未买股票也独立积累市场证据，不能以首次成交获特权；同根后续新canonical+新frontier可讨论扩大，现有现金/真实保护风险/股行业上限继续逐单付费。',
 '不要求收复旧高、不禁止重入、不拿浮盈作保护信用、不因market proof弱便改原退出。新的负事件/低锚身份如何重复重置、继承未知如何处理必须先唯一规定；普通UP回撤和receipt消费不能随意重置。',
 '最强反例：真趋势低位repair后次日跳涨/最小200股高于有限试仓；不断UP的新凭据也可来自单轮急涨并迅速回落（本月主要损耗正是此组）；无持仓也要成熟，已有赢家正常回撤不得永久锁小仓。先在同前缀赢家/假启动/跌后真恢复合成说明主动资本到位及损耗代价，再决定是否值得任何经济验证。',
 '当前证据不足支持把此候选列为主要修复：repair并非主要损耗且有真实盈利反例。只保留可因果辨识的状态差异；不启动新规则覆盖率评估或新收益路径。','',
 '验证与交付',
 'analyze.py仅扫描原CP1已算字段并连接两现账；首次输出17.375秒。verify.py覆盖消费不重置、UP普通回撤、负事件但I未失效、低锚、清除后start、继承未知，并核Jul8/22/29表级前缀分类/身份逐项一致；这不是另跑原金融物理截断分支。未运行账户，已审金融输入物理截断证据复用。',
 'EVENTS.json保留全部3336×2事件、原许可/目标/订单/实际层及当窗后续同源价路。后续观察长短不齐/末端删失，未拿变长终点做策略收益或胜率。ROLE_POOL_GROUPS及CHECKS有全层分母和已实现/未实现/股息桥。open层总贡献并非未实现：例如C10 repair open层−5592.02包含此前部分实卖，实际剩余未实现仅+4.79，不能混称浮亏。',
 'NO_OPPORTUNITY_SALE_PREVIEWS仅原量固定状态合法性；不能累加，也不是可同时执行资金或可实现盈亏。原金融checkpoint/源适配器/指标不改。首次verify遇tuple键序列化错误，原失败日志与脚本保留failures/01，无账户或分类结果变更。']
 (HERE/'REPORT.txt').write_text('\n'.join(lines)+'\n')
 print('REPORT_READY',flush=True)
if __name__=='__main__':main()
