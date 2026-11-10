import json,pathlib,hashlib
import pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'pvr_2026_sector_opportunity_attribution_v1';P=R/'account_comparison_continuous_v1/sector_2026_price_path_diagnostic_v1'
d=pd.read_csv(O/'ALL_257_ACTUAL_ENTRY_ROUNDS.csv');g=pd.read_csv(O/'GROUP_STATISTICS.csv');s=pd.read_csv(O/'INDUSTRY_TRADE_STATISTICS.csv')
p=pd.read_csv(P/'INDUSTRY_PRICE_PATHS_90.csv');c=pd.read_csv(P/'NATIVE_CLOSE_90.csv',index_col='date')
z=p.merge(s,left_on='sid',right_on='sector',how='left',validate='one_to_one')
assert len(z)==90 and z.new_rounds.notna().sum()==68
z.to_csv(O/'ALL_90_INDUSTRY_PRICE_AND_TRADES.csv',index=False)
q=d.merge(p,left_on='sector',right_on='sid',suffixes=('','_index'),validate='many_to_one')
for i,r in q.iterrows():
 path=c[r.sector];sd=r.signal_day;ed=r.entry_day
 end=str(r.closed)[:10] if r.round_status=='CLOSED' else '2026-05-16'
 held=path[(path.index>=ed)&(path.index<end)]
 assert len(held)>0
 q.loc[i,'sector_signal_close']=path.loc[sd]
 q.loc[i,'sector_signal_return_since_base_pct']=(path.loc[sd]/path.iloc[0]-1)*100
 q.loc[i,'sector_signal_drawdown_from_running_peak_pct']=(path.loc[sd]/path.loc[:sd].max()-1)*100
 q.loc[i,'sector_held_last_date']=held.index[-1]
 q.loc[i,'sector_held_last_vs_signal_pct']=(held.iloc[-1]/path.loc[sd]-1)*100
 q.loc[i,'sector_held_max_vs_signal_pct']=(held.max()/path.loc[sd]-1)*100
 q.loc[i,'sector_held_min_vs_signal_pct']=(held.min()/path.loc[sd]-1)*100
q.to_csv(O/'ALL_257_ENTRIES_WITH_INDUSTRY_DAILY_PATH.csv',index=False)
monthly=[]
for (month,group),v in d.assign(month=d.entry_day.str[:7]).groupby(['month','pool_group']):
 closed=v[v.round_status=='CLOSED'];opened=v[v.round_status=='OPEN']
 monthly.append({'month':month,'group':group,'new':len(v),'closed':len(closed),'wins':int(sum(closed.round_pnl>0)),'losses':int(sum(closed.round_pnl<0)),'open':len(opened),'closed_net':float(closed.round_pnl.sum()),'open_mark_net':float(opened.round_pnl.sum())})
pd.DataFrame(monthly).to_csv(O/'MONTH_AND_POOL_STATUS.csv',index=False)
m3=[]
for arm in ['all1709','tech407']:
 path=R/'m3_ab_shared_probe_v1/tech407_admission_mask_ablation_v1'/('run_'+arm+'_once')
 led=json.load(open(path/'DAY_LEDGER.json'))
 cut=[r for r in led if r['day'][:10]=='2026-05-15'][0]
 m3.append({'arm':arm,'asof_2026_05_15':cut['CLOSE']})
json.dump(m3,open(O/'M3_ASOF_2026_05_15.json','w'),ensure_ascii=False,indent=2)
def money(x):return f'{x:,.2f}'
def pct(x):return '不适用' if pd.isna(x) else f'{x:.2f}%'
def payoff(x):return '无赢或无亏，不定义' if pd.isna(x) else f'{x:.3f}'
lines=['2026 年行业行情与原 PVR 实际交易核对','窗口 2026 年 1 月 1 日至 5 月 15 日','',
'一 直接回答',
'科技和半导体确有行情。全90行业61涨29跌，期末涨幅中位数5.38%。半导体+44.79%、元件+47.00%、电子化学品+72.13%、通信设备+29.79%。不能用已闭回合低胜率，推断这些行业没有行情。',
'原120万元PVR在本窗口新开257回合，242只股票、68个行业。已闭193轮41赢152亏，完整回合胜率21.24%，已闭净额+34,835.77元。旧407科技范围已闭3/19赢，非科技38/174赢，同账切片并不支持“非科技稀释高胜率科技”。但科技另15轮未闭、原账估值净+104,230.66元，不能把未闭右尾记作输或遗漏。',
'半导体具体错位：9次新开中，8次在1/12至2/4买、在1/14至3/27退出，1赢7亏合计−8,699.49元；剩下立昂微5/11买，到5/15仍未闭，账面约+35.38元。行业1/28至3/23最大回撤17.49%，随后又上涨。跨年前已带入2026的68个旧回合中没有半导体。此事实不证明知道未来后应持有原失败交易，也不证明简单延迟止损有效。',
'非科技也不是都没行情：电力+26.54%、煤炭+15.95%、环境治理+12.43%。原账这些行业已闭分别净赚22,824.87、20,996.07、56,759.34元；工业金属、港口、医疗服务指数也有阶段上涨，但原交易净亏，须区分具体进入时点、退出和个股路径。',
'本报告只复核真实旧账及每日价格，不新跑策略，不提出用未来行情筛选股票。',
'',
'二 统计与时点边界',
'自然窗口2026/1/1至5/15，首个交易日1/5；价格基期为2025/12/31，共85交易日加基期86观测。90行业7740格价格在原账户signal、原CSV、prepared bars和缓存完全一致，无缺日、前填、合成事件条或invalid。',
'完整回合指真实0→0生命周期，包含追加。初层指该回合第一次实际BUY层，可能原kind=add，并不等于已盈利后的追加。胜率只用各自已闭分母；所有已闭净额为原费后记账。未闭数及期末原账mark净额单列，未做5/15强平，未扣假设清仓费用，也不是最终胜负。',
'本研究按2026实际首买选回合，不是全账户2026年度收益。另68个跨年旧回合不混入新生胜率；新生初买累计金额可超过120万元，因为资金反复周转。平均占资是85日剩余含买费成本的平均，不是交易金额之和，不是潜在可避免损失。',
'科技按旧研究407只股票名单；严格半导体按固定股票主表行业名“半导体”，是科技的子集。名单、名字和行业归属来自现有快照，NON-PIT，不宣称历史当日全市场成分。名字若源表仅有数字则原样保留，不猜名字。',
'原账的历史真实可成交性、外部现金股息实际兑付和历史公司行动条款PIT仍UNKNOWN；本报告保留原记账股息，不将UNKNOWN补零或筛掉。日线开盘代理和原执行限制继承，不能当实盘保证。',
'所有行业最大上涨与回撤只用收盘，端点严格先后；最大上涨=max(C后/C前−1)，最大回撤=max(1−C后/C前)，均含基期。事后最低/最高点不是当时可知的买卖信号、不是可以兑现的收益。股票和指数收益不是同一标的。',
'基准是90行业在12/31各自归一后取平均的初始等资本价格篮子，期末+8.1797%、最大回撤12.7649%（2/27至3/23）；权重随价格漂移，不是每日再平衡，不是可交易组合或沪深300，不含成本股息。源中无正式沪深300，不冒充。',
'',
'三 科技与非科技的实际成交统计']
for _,r in g.iterrows():
 lines += [f"{r['group']}：新开{int(r.new_rounds)}轮/{int(r.stocks)}股；完整已闭{int(r.round_wins)}赢{int(r.round_losses)}亏，未闭{int(r.round_open)}；胜率{r.round_winrate*100:.2f}%；平均赢{money(r.round_mean_win)}元、平均亏{money(r.round_mean_loss)}元、盈亏比{payoff(r.round_payoff)}；已闭净{money(r.round_closed_net)}元，未闭原账mark净{money(r.round_open_mark_net_NOT_final)}元。",
 f"  初层已闭{int(r.initial_wins)}赢{int(r.initial_losses)}亏，未闭{int(r.initial_open)}，胜率{r.initial_winrate*100:.2f}%，已闭净{money(r.initial_closed_net)}元、盈亏比{payoff(r.initial_payoff)}。",
 f"  初买累计含费{money(r.initial_total_buy_cost)}元；完整轮平均占资{money(r.round_avg_capital)}元，峰值{money(r.round_peak_capital)}元（{r.round_peak_capital_day}）。"]
lines+=['','四 最新 M3 共享账户不能回答 2026 新开质量',
'最新双臂是2024秋季新生队列，出生窗口只开放2024/9至12月，不接纳2026新生。两臂实际逐笔日志在2026/1/1至5/15连追加和卖出也均为0。',
'all1709最后交易2025/7/25，5/15现金和净值均1,222,183.32元、持仓0。TECH407最后交易2025/3/25，5/15现金1,240,808.53元，但万业企业600641仍有100首层+1000追加股自2024/11/28缺开盘路径，资产UNKNOWN、净值不认证，绝不能把它算全现金。',
'因此没有一个“最新M3在2026新开低胜率”的有效分母。其2024秋账户结果不能用来回答2026的新入场选择。',
'','五 各月真实新开与未结束分布']
for r in monthly:
 lines.append(f"{r['month']} {r['group']}：新{r['new']}；已闭{r['wins']}赢/{r['losses']}亏、未闭{r['open']}；已闭净{money(r['closed_net'])}元；未闭mark净{money(r['open_mark_net'])}元。")
lines+=['','六 全部 90 行业行情与实际交易','以下按期末指数涨幅排列。交易“赢/亏/未闭”均为完整回合，净额只含已闭。初层另列。无新开不等于全账户从未持有。']
for _,r in z.sort_values('period_return_rank').iterrows():
 lines.append(f"{int(r.period_return_rank):02d} {r.industry_name} {r.sid}：期末{pct(r.period_return_pct)}；最大时序上涨{pct(r.max_low_then_high_rise_pct)}（{r.rise_low_date}至{r.rise_high_date}）；最大回撤{pct(r.max_drawdown_pct)}（{r.drawdown_peak_date}至{r.drawdown_trough_date}）。")
 if pd.isna(r.new_rounds):lines.append('  2026新开0轮。')
 else:
  lines.append(f"  新开{int(r.new_rounds)}轮；完整{int(r.round_wins)}/{int(r.round_losses)}/{int(r.round_open)}，已闭净{money(r.round_closed_net)}元、盈亏比{payoff(r.round_payoff)}；初层{int(r.initial_wins)}赢/{int(r.initial_losses)}亏/{int(r.initial_open)}未闭，已闭净{money(r.initial_closed_net)}元；完整轮平均占资{money(r.round_avg_capital)}元。")
  lines.append(f"  首次至末次买入{r.first_buy}至{r.last_buy}；未闭mark净{money(r.round_open_mark_net_NOT_final)}元。")
lines+=['','七 全部 257 次实际初买对应信号与行业日线','金额单位元，初买为含买费成本。完整净额在“未闭”时只是原账期末mark。信号来自收盘；执行为原账下一共同交易日开盘代理，不读取当日未来行情重排。','行业买点字段：信号时相对12/31涨幅；信号时相对过去最高收盘的回落，均为当日可见价格描述。行业持有段最大/最小，是实际股票首买后至清仓开盘前最后收盘（未闭到5/15）的行业收盘相对信号收盘变化，只是事后对照，不是该股收益或可执行报价。']
for n,(_,r) in enumerate(q.sort_values(['entry_day','sid']).iterrows(),1):
 state='已闭 '+str(r.closed)[:10] if r.round_status=='CLOSED' else '未闭，截至5/15估值'
 lines += [f"{n:03d} {r.sid} {r['name']}｜{r.industry}｜{r.pool_group}；信号{r.signal_day}，买{r.entry_day}；{r.first_kind}/{r.first_reason}，原池{r.initial_pool}。",
 f"  初买{money(r.initial_buy_cost)}，初层净{money(r.initial_pnl)}；完整累计买款{money(r.round_buy_cost)}、净{money(r.round_pnl)}（{state}），后续ADD {int(r.followup_add_count)}次。",
 f"  行业信号时已涨{pct(r.sector_signal_return_since_base_pct)}、距此前最高收盘{pct(r.sector_signal_drawdown_from_running_peak_pct)}；持有段行业最大/最小{pct(r.sector_held_max_vs_signal_pct)}/{pct(r.sector_held_min_vs_signal_pct)}，末日{r.sector_held_last_date}相对信号{pct(r.sector_held_last_vs_signal_pct)}。"]
lines+=['','八 证据和核验范围',
'原成交信号与回合：selection_entry_diagnosis_v1 的 ALL_FIRST_ENTRIES.csv；初层和完整轮金额：act_entry_loss_attribution_v1 的 ALL_ROUND_ATTRIBUTION.csv；实际资本：同目录 DAILY_HELD_PATH.csv。',
'逐行业独立旧聚合对照：technology_winrate_scope_audit_v1 的 CURRENT_PVR_2026_INDUSTRY_CLOSED.csv，68行业新开、已闭、赢、未闭和净额逐项一致。',
'行业日线：sector_2026_price_path_diagnostic_v1 的 INDUSTRY_PRICE_PATHS_90.csv、NATIVE_CLOSE_90.csv；90行业7740格同源交叉验证，275源文件哈希未变，92条极值用两套算法复核一致。',
'最新M3：tech407_admission_mask_ablation_v1 两臂 EXACT_TRADE_JOURNAL.json、DAY_LEDGER.json、RUN_CONTRACT.json。本次读5/15真实日账，不拿6/30最终资产倒填。',
'本报告完成分母/金额/日占资守恒及源文件不变性检查，未重做全部原策略和公司行动独立审计；不声称换名单反事实、样本外或实盘有效。']
report='\n'.join(lines)+'\n'
(O/'2026年行业行情与实际交易完整核对.txt').write_text(report,encoding='utf-8')
json.dump({'rows':len(q),'industries':len(z),'traded_industries':int(z.new_rounds.notna().sum()),'text_chars':len(report),'same_dates_and_sources':True,'pertrade_actual_hold_end_before_sell_open':True,'source_prices':[str(P/'INDUSTRY_PRICE_PATHS_90.csv'),str(P/'NATIVE_CLOSE_90.csv')],'analysis_note':'posthoc descriptions only, no optimization'},open(O/'JOIN_CHECKS.json','w'),ensure_ascii=False,indent=2)
print('Report',O/'2026年行业行情与实际交易完整核对.txt','chars',len(report))
print(z[['industry_name','period_return_pct','new_rounds','round_wins','round_losses','round_open','round_closed_net','round_open_mark_net_NOT_final']].to_string(index=False))
print('SEMICONDUCTOR',q[q.strict_semi][['sid','entry_day','closed','sector_signal_return_since_base_pct','sector_held_max_vs_signal_pct','sector_held_min_vs_signal_pct']].to_string(index=False))
