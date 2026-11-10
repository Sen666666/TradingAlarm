"""Post-result arithmetic and graphics only; never changes any trading decision."""
from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
NAMES={'F100':'固定100万','F10':'固定10万','F30':'固定30万','A':'阶梯只加','B':'温度只加','C':'温度双向','D':'强冷削层'}
ORDER=list(NAMES)
def table(h,rs):return '| '+' | '.join(h)+' |\n| '+' | '.join(['---']*len(h))+' |\n'+''.join('| '+' | '.join(map(str,r))+' |\n' for r in rs)
def amount(x):return f'{x/1e8:.2f}亿'
def signed(x):return f'{x/1e8:+.2f}亿'
def pct(x):return f'{x:.2%}'
def main():
 out=HERE/'analysis-v1';d=pd.read_csv(out/'summary.csv');baseline=d[d.policy.eq('F100')].set_index('scenario');d['profit_retention']=[r.net_profit/baseline.loc[r.scenario].net_profit for r in d.itertuples()];d['funding_saved']=[1-r.peak_funding/baseline.loc[r.scenario].peak_funding for r in d.itertuples()];d['market_value_saved']=[1-r.peak_market_value/baseline.loc[r.scenario].peak_market_value for r in d.itertuples()];d['mean_market_value_ratio']=[r.mean_market_value/baseline.loc[r.scenario].mean_market_value for r in d.itertuples()];d['top20_profit_retention']=[r.top20_reference_profit/baseline.loc[r.scenario].top20_reference_profit for r in d.itertuples()];curves=pd.read_csv(out/'curves.csv');adequate=d.groupby('scenario').peak_funding.max();d['common_adequate_capital']=[adequate[r.scenario] for r in d.itertuples()];add=[]
 for r in d.itertuples():
  pp=curves[curves.account.eq(r.account)].pnl.to_numpy();capital=float(adequate[r.scenario]);ee=capital+pp;peak=np.maximum.accumulate(np.r_[capital,ee])[1:];add.append(float((1-ee/peak).max()))
 d['common_adequate_drawdown']=add;d.to_csv(out/'comparison.csv',index=False);base=d[d.scenario.eq('base')].set_index('policy').loc[ORDER].reset_index()
 text='# 温度指导仓位：七方案结果\n\n2015年初—2026-10-22、1709当前合格A股及2未知记录，原E0开仓资格/结构退出和行业准入不变，无限总资金/无名额限制。本轮只研究仓位，不研究换仓。3条F100控制与上一轮完整日账/成交一致并复用，18条新增经济一次完成，无结果后调档位。全部为当前存续/市值/行业快照开发资料，非样本外。\n\n'
 text+='金额档位为持仓买入成本，费用另计；浮盈不压回档位。F10/F30/F100固定首仓；A阶梯只加，B温度只加，C温度双向，D强冷削层，四动态方案初仓10万、上限100万。所有加仓须新量价事实、原资格及持仓价格盈利；C/D保留底仓到E0退出。具体见[冻结协议](PROTOCOL.md)。\n\n'
 text+=table(['方案','累计净利润','峰值现金需求K','资金节省','利润保留','利润/K','自身K口径最大回撤','共同资本尺度回撤'],[[NAMES[r.policy],signed(r.net_profit),amount(r.peak_funding),pct(r.funding_saved),pct(r.profit_retention),pct(r.profit_over_funding),pct(r.max_drawdown),pct(r.common_capital_drawdown)] for r in base.itertuples()])
 text+='\nK按全程现金预约、成交、释放及结算反推，盈利可循环；自身K回撤按K+累计损益重建。共同尺度固定为原F100基础K（约11.58亿元），仅用于暴露解释，若某方案需求超过该值不代表它能用该本金实际执行。两种回撤均为事后资金口径，不能只报较好者。收益是全区间累计，非年化。\n\n'
 text+='## 补充：共同足额本金与静态现金对照\n\n'
 text+=f"部分方案所需资金超过事前的F100参考K，因此补充采用该情景全部方案最高K作为统一足额本金。基础情景为{amount(float(adequate['base']))}。这是结果后的固定现金会计算术，不是新增回测或策略参数：每股预算和所有交易不变，多余资金保持无息现金。事前共同F100尺度结果仍保留在上表。\n\n"
 text+=table(['方案','共同足额本金','净利润','此本金累计收益','此本金最大回撤'],[[NAMES[r.policy],amount(r.common_adequate_capital),signed(r.net_profit),pct(r.net_profit/r.common_adequate_capital),pct(r.common_adequate_drawdown)] for r in base.itertuples()])
 text+='\n这项对照不表示小额方案原本需要这么多本金；它检验动态方案的低回撤能否超过静态低投入加闲置现金所达到的取舍。\n\n'
 text+='## 实际投入与成本\n\n'
 text+=table(['方案','最高收盘市值','平均收盘市值','最大回撤金额','显式费用','最高股数','实际追加成交','减仓请求','最小单位拒绝'],[[NAMES[r.policy],amount(r.peak_market_value),amount(r.mean_market_value),amount(r.max_drawdown_amount),amount(r.fees),int(r.max_holdings),int(r.add_fills),int(r.reduction_orders),int(r.minimum_quantity_rejections)] for r in base.itertuples()])
 text+='\n拒绝次数为订单尝试，重复日期不等于独立机会；其中也包含已接近目标成本、追加余额不足一手的重复请求，不能把总次数全算为初仓漏选。初仓与追加拒绝分解见analysis-v1/rejections-by-kind.json。10万元不能买最小数量时真实跳过或后续再竞争，不能假定与F100实际入场日完全相同。温度双向的实际减仓成本按整手可能略高于目标，未使用分数股。\n\n'
 text+='## 大赢家、全部试错和初仓\n\n'
 text+=table(['方案','尾部净利润','普通闭合净损益','开放权益净损益','所有闭合亏损','尾部/全部亏损','只首仓失败损失','加过仓周期净损益','原F100前20股利润保留'],[[NAMES[r.policy],signed(r.tail_profit),signed(r.ordinary_profit),signed(r.open_profit),amount(r.all_closed_losses),f'{r.tail_to_all_losses:.2f}',amount(r.failed_initial_loss),signed(r.added_cycle_profit),pct(r.top20_profit_retention)] for r in base.itertuples()])
 text+='\n30%仅是已闭合净回报分类，分母为周期累计买入款含费用。加减仓会改变该分母，尾部笔数变化不等于固定同一批赢家的覆盖；原F100前20贡献股名单固定用于诊断，不参与选股。只首仓失败=未发生任何追加成交的已闭合亏损周期；加过仓周期净损益包含其初仓，不能解释为单独追加层的因果利润。费用与滑点已计入，不重复扣费。\n\n'
 text+='## 全部压力情景\n\n'
 text+=table(['方案','情景','净利润','资金K','利润/K','回撤','利润保留'],[[NAMES[r.policy],r.scenario,signed(r.net_profit),amount(r.peak_funding),pct(r.profit_over_funding),pct(r.max_drawdown),pct(r.profit_retention)] for r in d.itertuples()])
 text+='\n双成本沿原指定可变费率/滑点加倍，不将所有税费都乘2；延迟为多一次可执行事件等待，含日有效资格与追加等待信用，不是同一批成交机械晚一天。\n\n'
 text+='\n本轮A/B/C/D仅是仓位方案代号，与旧selection-rotation-abcd轮的选股/换仓A/B/C/D不同。C/D底仓是10万元平均成本余额，不固定初始股数；局部回升未超过旧加仓锚仍不追加。边界见[结果前说明](INTERPRETATION.md)。\n'
 (HERE/'RESULTS.md').write_text(text)
 plt.rcParams['font.family']=['Arial Unicode MS','DejaVu Sans'];colors=dict(zip(ORDER,plt.cm.tab10.colors[:7]));fig,axes=plt.subplots(3,1,figsize=(14,11),sharex=True)
 for mode in ORDER:
  g=curves[(curves.policy==mode)&curves.scenario.eq('base')];dt=pd.to_datetime(g.date);axes[0].plot(dt,g.pnl/1e8,label=NAMES[mode],color=colors[mode]);axes[1].plot(dt,g.funding_to_date/1e8,label=NAMES[mode],color=colors[mode]);axes[2].plot(dt,g.drawdown*100,label=NAMES[mode],color=colors[mode])
 axes[0].set_ylabel('累计净利润（亿元）');axes[1].set_ylabel('截至当日峰值资金（亿元）');axes[2].set_ylabel('各自K重建回撤（%）');axes[2].invert_yaxis()
 for ax in axes:ax.grid(alpha=.2);ax.legend(ncol=4,fontsize=9)
 fig.suptitle('同开仓/E0退出：固定金额与温度仓位的资金—回撤取舍');fig.tight_layout();fig.savefig(HERE/'comparison.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,7))
 for r in base.itertuples():ax.scatter(r.peak_funding/1e8,r.net_profit/1e8,s=80+700*r.max_drawdown,color=colors[r.policy]);ax.annotate(NAMES[r.policy],(r.peak_funding/1e8,r.net_profit/1e8),xytext=(6,6),textcoords='offset points')
 ax.set_xlabel('峰值资金需求K（亿元，越低越省资金）');ax.set_ylabel('累计净利润（亿元）');ax.set_title('资金效率比较；点大小表示自身K口径最大回撤');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(HERE/'capital-profit.png',dpi=150);plt.close(fig)
 print(base[['policy','net_profit','peak_funding','funding_saved','profit_retention','profit_over_funding','max_drawdown','common_capital_drawdown','mean_market_value','fees']].to_string(index=False),flush=True)
if __name__=='__main__':main()
