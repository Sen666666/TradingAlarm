from pathlib import Path
import pandas as pd,numpy as np,json,gzip,hashlib
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=R/'major_trends_2025_2026_review_v1'
p=pd.read_csv(O/'ALL_FIXED_PERIOD_PRICE_PATHS.csv');a=pd.read_csv(O/'FIXED_QUARTER_ACTUAL_CONTRIBUTIONS.csv');s=pd.read_csv(O/'SEMICONDUCTOR_PRECIOUS_STOCK_CONTRIBUTIONS.csv');b=pd.read_csv(O/'90_INDUSTRY_OVERVIEW.csv')
v=pd.read_csv(O/'VALID_DAILY_CLOSES.csv',index_col=0);v.index=pd.to_datetime(v.index)
checks=[]
for _,r in p.iterrows():
 x=v.loc[r.base_date:r.end_date,r.sid].dropna().values
 mat=x[None,:]/x[:,None]-1
 vals=mat[np.triu_indices(len(x),k=1)]
 assert abs(max(0,float(vals.max()))*100-r.max_rise_pct)<1e-8
 assert abs(max(0,-float(vals.min()))*100-r.max_drawdown_pct)<1e-8
 checks.append((r.period,r.sid))
json.dump({'independent_all_pair_extrema_checks':len(checks),'all_passed':True,'method':'independent all strict chronological pairs versus prefix extrema'},open(O/'INDEPENDENT_EXTREMA_QA.json','w'),ensure_ascii=False,indent=2)
def one(r):return f"{r['name']}：期末{r.period_return_pct:+.2f}%，期间相对期初最高{r.peak_from_base_pct:+.2f}%（{r.peak_day}）；最大按时序上涨{r.max_rise_pct:.2f}%（{r.rise_low}至{r.rise_high}），最大回撤{r.max_drawdown_pct:.2f}%（{r.drawdown_peak}至{r.drawdown_trough}）。"
lines=['2025 至 2026 重大行情与原账户参与复核','行情截止2026年10月22日，原PVR账户截止2026年5月15日','',
'一 主要发现',
'用户所指确是跨阶段大行情，不应被缩成2026年初几个月或十余点局部涨幅。半导体行业从2024年底至2026/6/30峰值上涨180.23%；黄金Au99.99现货从2024年底到2026/1/29峰值上涨102.18%。两条主线都经历过回撤和再启动，并不是单向上涨。',
'原PVR120万元账户在2025/1/1至2026/5/15，净值从770,085.81升至1,254,596.96元，增加484,511.15元。半导体的同期净贡献仅183.81元，A股贵金属股票（包括白银股）贡献7,581.74元，其余股票贡献476,745.60元。这是按同一时间段守恒的贡献，不是把整个历史已闭回合净额拼在一起。',
'这段328个收盘中，半导体平均市值占净值1.5636%，151天空仓；贵金属股票平均1.2488%，179天空仓。原账对这两条大行情的参与很薄，这一事实值得继续查清。它不证明问题只是仓位小，也不证明扩大仓位就会盈利。',
'原1709股票账户没有黄金现货或期货，因此不能说它应直接捕获黄金现货翻倍。贵金属股票指数包括白银及不同业务公司，价格路径远不同于金价，必须单列。',
'',
'二 可比较的年度事实',
'覆盖固定现有90行业，不是历史时点成分齐全的全A。2025全年与2026截至10/22不能同称“全年”。行业等初始权价格篮子仅作描述：基期各行业归一后求均值，无日再平衡，不是可交易组合或沪深300。']
for _,r in b.iterrows():
 lines.append(f"{r.period}：90行业中{int(r.rising)}涨、{int(r.falling)}跌，期末涨幅中位数{r.median_return_pct:+.2f}%；期末≥50%的行业{int(r.over50_return)}个，期间相对期初最高≥50%的{int(r.over50_peak)}个、≥100%的{int(r.over100_peak)}个。价格篮子{r.period_return_pct:+.2f}%，最大回撤{r.max_drawdown_pct:.2f}%（{r.drawdown_peak}至{r.drawdown_trough}）。")
lines+=['2025较多行业同时上涨；2026则少数重大右尾与广泛下跌并存。仅看10/22期末涨幅，会把半导体6月的大浪及后来的回落混成一个小涨幅。反过来，拿最高点收益当可实现收益也不成立。',
'','三 按实际先后分段的主观评价',
'以下“肥尾、可试错、可错过”是看过完整路径后的验收标签，不是实时信号、交易门槛或对未买股票的追溯授权。固定年度/半年表见后文；下面允许主观选择经济上连贯的阶段，但不拿选中的端点声称预测能力。',
'1. 2025年初至4月：允许小仓试错，必须接受失败和再入。半导体1/6至2/26曾上涨29.23%，随后2/26至4/7回撤22.63%；90行业价格篮子3/18至4/7回撤15.96%。不能因为后来有大行情，假定初次试仓当时已可放心加仓。',
'2. 2025年4月恢复至2026年6月科技主浪：核心肥尾，应作为参与能力的重要验收对象。半导体4/7至2025/10/9上涨71.32%，10/9至11/21回撤16.32%；2026年初先上涨、1/28至3/23再回撤17.49%，随后冲到6/30。跨2025/4/7低点至2026/6/30上涨205.40%，相对2024年底上涨180.23%。低点是事后挑出的，不能当算法买价。中间的失效、退出与正常重入不能被当成另一条无关小行情。',
'3. 2025至2026年1月黄金主浪：核心肥尾。Au99.99在2025上半年+24.34%、下半年+27.53%，全年+58.57%，续至2026/1/29达到相对2024年底+102.18%。A股贵金属指数2025+96.07%，再至2026/1/29达到相对2024年底+298.39%。二者不同，不能相互替代。',
'4. 2026年黄金主浪之后：可以不追每次反弹。Au99.99从1/29高点到7/1回撤30.11%，A股贵金属指数1/29至7/17回撤51.77%；后者7/17至8/24又反弹52.31%。这类大幅反弹可能值得新小仓试错，但不因为反弹幅度大就把早先失败持仓算成应永久拿住。',
'5. 2026年6月底之后科技回落：可选择错过多数反抽，而非把其与前期主浪等价。半导体6/30至10/22回撤40.74%，中间7/30至8/18反弹27.26%。是否有新的可靠右侧要用当日信息验证，本文不据回看结果设门。',
'6. 2026年其他行业：有局部机会，但不将十余点普遍反弹抬升为与翻倍主线同等的核心肥尾验收目标。这里不扩大为每个小行情都必须买到；90行业完整值保留，便于审查是否遗漏其他真正大主线。',
'','四 半导体与黄金三种标的分开列示']
for label in ['2025全年','2026年内截至1022','跨年2025至2026年内','原账覆盖跨年']:
 lines.append(label+'：')
 for _,r in p[(p.period==label)&p.sid.isin(['URFI881121','URFI881169','sge-Au9999','sina-AU0'])].iterrows():lines.append('  '+one(r))
lines+=['Au99.99为上金所现货日线。AU0为供应商沪金连续序列，换月和连续调整规则未知，不能直接当可交易合约回报。原始金价数据已存在本地，本次没有补抓外部行情。',
'','五 原PVR账户每阶段参与与净贡献',
'贡献公式为：期间实际买卖净现金流 + 原账已记股息应收变化 + 原账收盘持仓估值变化。手续费已在买卖现金流中；所有股票贡献合计与原净值变化守恒。平均市值/NAV按每日比例取平均；剩余买入成本另外列，不与名义仓位或风险额混同。',
'原账户缺价日采用其最近有效价作账簿估值，不代表该日有新行情或能成交；外部兑付、真实成交性和历史公司行动PIT仍UNKNOWN。此次重建没有修改原账。']
for period,t in a.groupby('period',sort=False):
 lines.append(period+'：')
 for _,r in t.iterrows():
  lines.append(f"  {r['group']}：净贡献{r.contribution:+,.2f}元；平均市值/NAV {r.mean_NAV_fraction*100:.4f}%，最高{r.peak_NAV_fraction*100:.2f}%（{r.peak_NAV_fraction_day}）；{int(r.sessions)}天中{int(r.held_days)}天有仓、{int(r.zero_days)}天空仓；平均剩余买入成本{r.mean_remaining_cost:,.2f}元。")
lines+=['半导体关键阶段：2025Q1仅2天有仓；Q2贡献+1381.97元，Q3+7610.01元，Q4+939.33元。2026Q1亏8699.49元，4/1至5/15只有5天有仓、贡献+35.38元。行业6/30的后续峰值已经超过原账户5/15终点，不能声称旧账在6月仍然没买。',
'贵金属股票关键阶段：2025Q1有仓11/57天、Q2有仓14/60天；Q3有仓19/66天。2025Q4及2026Q1有持仓延续，但该类别整个覆盖窗口只贡献7581.74元；2026/4/1至5/15完全空仓。',
'上面未证明漏买是行业门、个股资格、排序、旧状态还是资金限制导致，也未证明买得更多就能改善收益；需要按原合法候选和实际拒绝原因另外核，不能以行情之后很强倒推当时必须买。',
'','六 固定代表股及实际参与',
'代表股在本次计算前固定为源杰科技、江丰电子、珂玛科技、寒武纪、中芯国际、北方华创，以及山东黄金、中金黄金、紫金矿业、赤峰黄金、湖南黄金、湖南白银。只作机制病例，不能替代行业全部成员胜率。股价为原冻结复权收盘描述，不是费用后账户收益或已兑付总回报。']
full='2024-12-31 → 2026-05-15'
for _,r in p[(p.kind=='stock')&(p.period=='跨年2025至2026年内')].iterrows():
 lines.append(one(r));actual=s[(s.period==full)&(s.sid==r.sid)]
 if len(actual):
  t=actual.iloc[0];lines.append(f"  原账2025至5/15：{int(t.buy_fills)}次实际买单，{int(t.held_days)}天有仓，同期净贡献{t.contribution:+,.2f}元，平均市值/NAV {t.mean_nav_fraction*100:.4f}%。")
 else:lines.append('  原账2025至5/15：未持有，无买单；不能据此判断资格、排序、资金或行业门的具体责任。')
lines+=['','七 全部90行业的年度与跨年表现','每行列2025全年、2026截至10/22、跨年自2024年底至10/22。格式为期末涨幅 / 相对期初最高涨幅 / 最大回撤。端点与详细时序表一并保存。']
for sid,t in p[p.kind=='industry'].groupby('sid'):
 name=t['name'].iloc[0];parts=[]
 for per in ['2025全年','2026年内截至1022','跨年2025至2026年内']:
  r=t[t.period==per].iloc[0];parts.append(f'{r.period_return_pct:+.2f}% / {r.peak_from_base_pct:+.2f}% / {r.max_drawdown_pct:.2f}%')
 lines.append(f"{name} {sid}："+'；'.join(parts))
lines+=['','八 范围与证据',
'行情：固定90行业和12代表股的原H1_MANIFEST signal，每日observed且eligible、非synthetic、非invalid；2024/12/31至2026/10/22行业436共同观测，无前填。所有价格极值只用严格先后的日收盘，832组固定窗口以全日对法独立复核前缀算法。',
'账户：原120万元PVR连续账，使用实际买卖、每日快照、层股息和成本重建。逐日库存、实际现金变化、7个边界股息应收、各阶段净值差均核对通过。全局缺价日143条原衍生mark空值仅按原账旧估值恢复，不伪造新鲜价格；之前单纯把缺价mark相加的试算未通过，未用于贡献结论。',
'最新M3仍是2024秋新生队列，不能替代2025至2026连续新开账户；其2026没有实际交易，不能据此评价2026新开胜率。',
'数据均为现有固定池与映射，NON-PIT；行情大部分已被历史研究看过。未新跑策略、未调参数、未把事后阶段标记塞回信号。这里的主观肥尾评价用于检查研究目标是否正确，而不是宣称未来已可识别。',
'原始明细：ALL_FIXED_PERIOD_PRICE_PATHS.csv、90_INDUSTRY_OVERVIEW.csv、FIXED_QUARTER_ACTUAL_CONTRIBUTIONS.csv、SEMICONDUCTOR_PRECIOUS_STOCK_CONTRIBUTIONS.csv、DAILY_THEME_EXPOSURE.csv；核对结果PRICE_QA.json、INDEPENDENT_EXTREMA_QA.json、CONTRIBUTION_RECONCILIATION.json。']
(O/'2025至2026重大行情与原账户参与复核.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
source=[R/'act_only_ablation_continuous_v1/run/pair/PVR.json.gz',R/'act_only_ablation_continuous_v1/run/pair/daily.jsonl.gz',R/'act_entry_loss_attribution_v1/DAILY_HELD_PATH.csv',R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv']
json.dump({str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in source},open(O/'ACCOUNT_SOURCE_SHA256.json','w'),ensure_ascii=False,indent=2)
print('report_chars',len('\n'.join(lines)),'independent_extrema',len(checks));print(O/'2025至2026重大行情与原账户参与复核.txt')
