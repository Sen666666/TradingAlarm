"""Render a human readout from completed sealed outputs only. No economic imports."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O/'report'
assert (O/'COMPLETION.json').exists()
m=pd.read_csv(R/'PERFORMANCE.csv');z=pd.read_csv(R/'CORE_AND_FULL_ROUNDS.csv',low_memory=False);p=pd.read_csv(R/'BASELINE_SAME_STOCK_PARTICIPATION.csv');u=pd.read_csv(R/'UNKNOWN_REASON_BREAKDOWN.csv')
arms=['A_UNION_B','RAW_MOM11','CH3_RM'];labels={'A_UNION_B':'原PVR','RAW_MOM11':'同窗原始动量','CH3_RM':'CH3残差'}
windows=['2022','2024_924'];wlabels={'2022':'2022全年出生','2024_924':'2024年9–12月出生'}
def val(v,d=2):return '—' if pd.isna(v) else f'{v:,.{d}f}'
def pct(v):return '—' if pd.isna(v) else f'{v*100:.2f}%'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def row(w,a,l,scope='EVIDENCE_USABLE_CLOSED'):
 return m[(m.window==w)&(m.arm==a)&(m.layer==l)&(m.scope==scope)].iloc[0]
lines=['# 固定三臂逐股条件生命周期比较', '', '## 结论', '',
'这一次固定比较没有支持“用CH3残差替换原PVR可提高初层净胜率”。证据可用闭合样本中，CH3初层净胜率在2022出生窗由31.88%降至31.15%，在2024年9–12月出生窗由40.40%降至38.22%；同11月原始动量分别为31.04%和38.11%。CH3与原始动量的胜率很接近。',
'2024出生窗CH3初层平均净额从1,081.88元升至1,130.77元，但平均初层净收益率从4.6770%到4.6744%，并未提高；执行UNKNOWN从27增至53、可用闭合数从1,312降至1,282。更高的金额均值、盈亏比不能抵消更低的胜率，也不能绕过样本缺失非随机的问题。2022出生窗三臂平均净额和平均净收益率均为负。',
'原PVR的2024可用初层≥50%尾部为64只。CH3保留39个同event，另16只在其他时点实际参与，9只在该出生窗完全无许可；因此不是“少了25个旧event，就漏了25只股票”。55只实际参与中，52只与原持有区间确认重叠。', '',
'## 范围与口径', '',
'- “2022”“2024”均指出生窗：2022-01-01至2022-12-31，以及2024-09-01至2024-12-31；所有路径管理至2026-06-30。它们不是2022/2024年度账户收益。',
'- 三臂独立逐股条件生命周期，不共享账户、资金或持仓槽位；FAST独立保持不变，本次未纳入。只比较原A+B出生事件。',
'- 每个消费者在各自实时状态下，按FLAT、I资格、PVR已知和close可行性压紧队列，采用同一K=min(2,自身当组合法数)规则。实际合法数、许可数和成交数可以不同。',
'- CH3与原始动量仅重排共同已知支持域；UNKNOWN保持本动态队列原PVR可行位置，不当0分。所有19,795个潜在市场事件的14,635个股月都有预计算特征，缺缓存强报错。',
'- 初层：实际FULL路径的原始买入股数，在该FULL的入场/退出时点独立按dated fee计费、分配自有初层NET80。不是额外的独立CORE生命周期。FULL包含原规则追加。',
'- 净胜率以对应层净额>0为胜，净额<0为负，零另列。期望同时给平均净额CNY及等权平均单轮净收益率；盈亏比=平均赢家净额/绝对平均亏家净额。',
'- “全部条件闭合”保留财务覆盖不足的闭合结果；“证据可用闭合”另剔除闭合财务UNKNOWN。未闭合执行UNKNOWN、NOFILL、CENSORED不填0或算亏。不同臂的可用样本并非随机删失，结果是描述性比较。',
'- 所谓毛额仍是条件成交的模型值：原始open毛损益 − 双边各5bp滑点影响 − dated费用 + NET80 = 净额。成交毛额已含滑点、未扣费用。逐股金额求和不是可实现账户利润或收益率。', '',
'## 证据可用闭合：初层与FULL分开', '']
rows=[]
for w in windows:
 for layer in ['core','full']:
  for a in arms:
   r=row(w,a,layer);rows.append([wlabels[w],labels[a],'初层' if layer=='core' else 'FULL',int(r.closed),int(r.wins),pct(r.net_win_rate),val(r.mean_net_cny),pct(r.mean_return),val(r.payoff_cny),int(r.tail_ge50)])
lines += [table(['出生窗','排序','层','闭合N','净赢N','净胜率','均净CNY','平均净收益率','盈亏比','≥50%尾N'],rows),'',
'净额为零的轮次在上述12个组内均为0。平均净收益率使用每轮自身买入现金作为分母，不能用平均净额除以一个固定名义仓位代替。', '',
'## 全部许可与未知：不得只看可用样本', '']
rows=[]
for w in windows:
 for a in arms:
  r=row(w,a,'full','ALL_CONDITIONAL_EXECUTION');g=z[(z.window==w)&(z.arm==a)]
  rows.append([wlabels[w],labels[a],int(r.admitted),int(r.filled),int(r.closed),int(r.execution_unknown),int(r.financial_unknown_closed),int(r.nofill),int(r.censored),int(g.status_feature.ne('CALENDAR_COMPUTABLE_RELEASE_UNKNOWN').sum()),int(g.evidence_usable_closed.sum())])
lines += [table(['出生窗','排序','全部许可','确认入场','条件闭合','执行UNKNOWN','闭合财务UNKNOWN','NOFILL','CENSORED','入选特征UNKNOWN','可用闭合'],rows),'',
'闭合财务UNKNOWN属于条件闭合的子集；入选特征UNKNOWN是另一维度，不能与执行/财务UNKNOWN相加。原PVR、原始动量、CH3的动态合法候选数，2022分别为5,728/5,708/5,715，2024出生窗为3,505/3,575/3,557。',
'UNKNOWN变化主要来自不同排序进入了原有权益事实尚未覆盖的路径：2022 FACTOR_PATH_UNKNOWN为65/115/110，另FACTOR_AT_ENTRY_UNKNOWN为1/4/5；2024 UNADMITTED_ACTION_PATH_UNKNOWN为9/25/31，入场未准入权益UNKNOWN为0/2/1。以上顺序均为原PVR/原始动量/CH3。所有失败发生阶段、状态和覆盖原因见UNKNOWN_REASON_BREAKDOWN.csv。闭合财务UNKNOWN原因均为ACTION_RAW_RESPONSE_EMPTY;RIGHTS_EMPTY。没有扩展436/165条原准入权益事实去改善新臂。', '',
'## 全部条件闭合：保留财务未知的对照', '']
rows=[]
for w in windows:
 for layer in ['core','full']:
  for a in arms:
   r=row(w,a,layer,'ALL_CONDITIONAL_EXECUTION');rows.append([wlabels[w],labels[a],'初层' if layer=='core' else 'FULL',int(r.closed),pct(r.net_win_rate),val(r.mean_net_cny),pct(r.mean_return),val(r.payoff_cny),int(r.tail_ge50)])
lines += [table(['出生窗','排序','层','条件闭合N','净胜率','均净CNY','平均净收益率','盈亏比','条件≥50%尾N'],rows),'',
'例如2024原PVR初层全部条件尾为66，证据可用尾为64；CH3为59和58。主尾部保留讨论使用64的可用分母，不混用66。', '',
'## 原初层≥50%尾：实际同股参与', '']
rows=[]
for w in windows:
 for a in arms[1:]:
  g=p[(p.window==w)&(p.arm==a)&p.baseline_core_tail50]
  rows.append([wlabels[w],labels[a],len(g),int(g.same_event_entry_confirmed.sum()),int(g.participation.eq('SAME_STOCK_OTHER_ENTRY').sum()),int(g.participation.eq('NO_CONFIRMED_PARTICIPATION').sum()),int(g.participation.eq('PARTICIPATION_UNKNOWN').sum()),int(g.any_same_stock_actual_entry.sum()),int(g.confirmed_overlap_rounds.gt(0).sum()),int(g.confirmed_full_cover_rounds.gt(0).sum())])
lines += [table(['出生窗','替代排序','原尾N','同event实际入场','其他时点同股入场','无确认参与','入场不可判断','任意实际参与','确认区间重叠','确认全区间覆盖'],rows),'',
'2022原44只初层尾均在两种替代排序中有该股实际入场，但不保证同一时点或同样收益；CH3仅34个旧event保留，原始动量38个。2024 CH3的9只无参与在本次输出中均为该股无任何许可，不是UNKNOWN冒充未参与。区间重叠不是收益保留，其他时点买到同股也可能亏损。UNKNOWN路径只用已确认持有前缀判断重叠，不把冻结状态延伸到管理终点。',
'在全部1,312个2024原PVR证据可用闭合事件中，CH3为798个同event实际入场、380个同股其他时点入场、134个无确认参与；原始动量分别789/383/140。这个分组以原事件计数，不等于唯一股票数。', '',
'### 2024实际同股毛净案例', '',
'以下是CH3自己的实际路径，不移植原PVR收益，也不以旧event消失判定完全错失：','']
rows=[]
for sid in ['300085.SZ','600111.SH','002625.SZ','300102.SZ']:
 g=z[(z.window=='2024_924')&(z.arm=='CH3_RM')&(z.sid==sid)]
 for r in g.to_dict('records'):
  rows.append([r['name'],sid,r['entry_day'],r['exit_day'],pct(r['core_return']),val(r['core_gross_after_slippage_pnl']),val(r['core_fees']),val(r['core_dividend_net80']),val(r['core_net']),val(r['net_pnl'])])
lines += [table(['股票','代码','实际入场','实际退出','初层净收益率','初层成交毛额','初层费用','初层NET80','初层净额','FULL净额'],rows),'',
'- 银之杰：原09-12出生event未保留，但CH3选择09-05出生并于09-06入场，实际初层净收益+383.35%，不是完全错失原+400.01%的股票。',
'- 北方稀土：CH3更早的实际路径初层+138.65%，原尾event初层+105.88%；属于其他时点实际参与。',
'- 光启技术：虽有同股区间重叠，CH3初层−1.76%、FULL净额−1,860.14元；不能把原+117.92%直接继承给它。',
'- 乾照光电：CH3后来才入场，和原尾区间不重叠，实际初层−19.95%；“买到过同股”不等于捕获原行情。',
'- CH3本窗无许可的9只原可用初层尾：永新光学、拓维信息、上海电气、巨轮智能、安克创新、利欧股份、华懋科技、睿创微纳、广和通。', '',
'## 盈亏金额与毛净恒等式：证据可用闭合', '']
rows=[]
for w in windows:
 for layer in ['core','full']:
  for a in arms:
   r=row(w,a,layer);rows.append([wlabels[w],labels[a],'初层' if layer=='core' else 'FULL',int(r.wins),val(r.winner_total_cny),val(r.winner_mean_cny),int(r.losses),val(r.loser_total_cny),val(r.loser_mean_cny),val(r.payoff_cny)])
lines += [table(['出生窗','排序','层','赢家N','赢家总净CNY','平均赢CNY','亏家N','亏家总净CNY','平均亏CNY','盈亏比'],rows),'']
rows=[]
for w in windows:
 for layer in ['core','full']:
  for a in arms:
   r=row(w,a,layer);rows.append([wlabels[w],labels[a],'初层' if layer=='core' else 'FULL',val(r.gross_raw_open_sum),val(r.slippage_drag_sum),val(r.gross_after_slippage_sum),val(r.fees_sum),val(r.dividend_net80_sum),val(r.independent_net_sum)])
lines += [table(['出生窗','排序','层','原open毛损益','滑点影响','成交毛损益','费用','NET80','净额合计'],rows),'',
'每行满足原open毛损益−滑点影响−费用+NET80=净额合计；也等于赢家总净+亏家总净。显示值四舍五入到分，精确逐轮恒等式以CSV及独立审计为准。这些金额只是独立逐股账本的描述性求和，不是资金受限共享账户结果。', '',
'## 审核、运行与边界', '',
'- 全市场特征覆盖19,795事件/14,635股月，新增6,615股月；原8,020特征一致，14,635前缀截断与未来污染测试通过；独立QR复算11,929个已知股月。',
'- 单次固定运行，6份冻结实施文件与最终开跑前独审哈希一致；每窗原PVR先逐表复现DECISIONS/ACTIONS/ROUNDS/END_STATES/REGISTRATIONS/CLAIM_LEDGER/PROFIT_GATES及claims/bridges，再运行两种替代排序。原PVR可用闭合严格复现2,616/1,312。',
'- 5,491个共同市场event的实际动作、权益认领与结果一致。无参数搜索、符号翻转或看到结果后重跑。所有经济输出和表格封存保留。',
'- 退出仍为原I_STRUCTURE_EXIT条件；原尺寸、原追加门槛、双边5bp滑点、dated手续费、登记股数和NET80未改。新路径缺权益或执行证据仍UNKNOWN，不扩事实、不补0。',
'- 因子是当前修订CH3历史，发布时钟未知；m−1虽然不入11月评分，仍参与36月回归，不能宣称当年月初可获得。当前静态股票池/行业映射及复权close也不支持PIT或已认证总股东回报结论。',
'- 本次不提供替换原排序的证据：胜率未改善、2022期望仍负、2024均值/尾部和UNKNOWN变化需要同时看。它也不能证明月度多空残差动量文献对这套日级出生/退出策略有效。', '',
'## 文件索引', '',
'- report/PERFORMANCE.csv：全部条件执行、证据可用闭合、闭合财务未知，初层/FULL分开。',
'- report/CORE_AND_FULL_ROUNDS.csv：全量逐轮价格、数量、费用、权益、毛净与特征状态。',
'- report/FULL_STATUS_COVERAGE.csv；report/UNKNOWN_REASON_BREAKDOWN.csv：完整状态与未知原因。',
'- report/BASELINE_TAIL50_PARTICIPATION.csv；report/BASELINE_SAME_STOCK_PARTICIPATION.csv：原尾及全原事件的同股参与。',
'- report/2024_ACTUAL_SAME_STOCK_GROSS_NET.csv；report/BASELINE_SAME_STOCK_ROUND_PAIRS.csv：每对原事件与替代实际轮次的确认区间及自身毛净。',
'- 2022/与2024_924/内每臂目录：原始DECISIONS/ACTIONS/ROUNDS/CLAIMS、账本QA、排序审计和输出哈希。',
'- FEATURE_SEAL.json、CONTRACT.json、PRE_ECONOMIC_AUDIT.json、EXECUTION_AUTHORIZATION.json、RUN_ONCE.json、COMPLETION.json：特征、实现、审核、授权及唯一运行证据。', '']
(O/'READOUT.md').write_text('\n'.join(lines),encoding='utf-8')
print('READOUT_WRITTEN',len('\n'.join(lines)))
