"""Generate a self-contained Chinese research evidence report from saved results."""
import html
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
NAMES={'HK02800':'盈富基金 02800','USHJ512480':'半导体 ETF 512480','USHJ510300':'沪深300 ETF',
       'USHJ511010':'国债 ETF','USHJ512010':'医药 ETF','USHJ512660':'军工 ETF',
       'USHJ512800':'银行 ETF','USHJ513050':'中概互联网 ETF','USHJ513100':'纳指 ETF',
       'USHJ515030':'新能源车 ETF','USHJ518880':'黄金 ETF'}
STRATEGIES={'buy_hold':'持有','sma200':'200 日均线','momentum252':'252 日动量',
            'donchian55_20':'55/20 日突破','trend_v1':'自研 v1','structure_change_v2':'自研 v2',
            'annual_selected':'逐年选择模型'}

def table(df,cols):
    df=df[cols].copy()
    for c in ['cagr','max_drawdown','realized_vol','return_total']:
        if c in df: df[c]=df[c].map(lambda n:f'{n:.2%}')
    if 'sharpe' in df: df['sharpe']=df.sharpe.map(lambda n:f'{n:.2f}')
    if 'symbol' in df: df['symbol']=df.symbol.map(NAMES)
    if 'strategy' in df: df['strategy']=df.strategy.map(STRATEGIES)
    df=df.rename(columns={'symbol':'资产','strategy':'方法','cagr':'年化收益','max_drawdown':'最大回撤',
                          'realized_vol':'实际年化波动','sharpe':'夏普（现金利率按零）','year':'年份','return_total':'区间收益'})
    return df.to_html(index=False,escape=True,border=0)

def main():
    cross=pd.read_csv(ROOT/'results/cross-market.csv')
    walk=json.loads((ROOT/'results/walk-forward.json').read_text())
    overview=pd.DataFrame(walk['overall']); yearly=pd.DataFrame(walk['yearly'])
    primary=cross[(cross.symbol.isin(['HK02800','USHJ512480']))&(cross.period=='2024_plus')&
                  (cross.sizing=='vol15_cap1')&(cross.cost_bps_per_side==15)]
    primary_table=table(primary,['symbol','strategy','cagr','max_drawdown','realized_vol','sharpe'])
    yearly_table=table(yearly[yearly.symbol.isin(['HK02800','USHJ512480']) & yearly.strategy.isin(['sma200','structure_change_v2','annual_selected'])],['symbol','strategy','year','return_total'])
    transfer_table=table(overview[overview.strategy.isin(['sma200','structure_change_v2','annual_selected'])],['symbol','strategy','cagr','max_drawdown','sharpe'])
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>TradingAlarm 趋势指标研究</title><style>body{font:16px/1.75 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;color:#1c2935;background:#fafbfc}h1,h2{line-height:1.3}section{background:white;border:1px solid #dde3e8;padding:24px;margin:24px 0;border-radius:12px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px;white-space:nowrap}td,th{padding:8px 12px;border-bottom:1px solid #e5e9ed;text-align:right}td:first-child,th:first-child{text-align:left}th{background:#eef3f7}.note{color:#526372}code{overflow-wrap:anywhere}a{color:#155fa0}</style>
<h1>趋势指标研究：证据与当前结论</h1><p class="note">研究日期：2026-10-17 · 数据截至 2026-10-16 · 状态：独立策略研究中；用户已移除趋势动物对照要求</p>
<section><h2>当前结论</h2><p>自研 v1 和 v2 尚未证明优于简单基准。应保留 200 日均线与波动率仓位作为后续检验基准；不将本轮优胜者直接认定为最优策略或实盘推荐。</p><p>在本次选取的 11 个资产上，2024 年以来相同仓位规则和成本条件下，v2 的夏普比率没有一项严格高于 200 日均线。逐年选取过去三年最佳模型也没有稳定改善结果。历史模型选择和研究设计已受到已知行情影响，不能称为新的样本外业绩。</p></section>
<section><h2>算法与大师方法的关系</h2><p>以海龟突破、长期均线、时间序列动量作可复现基准。自研 v1 将 20/60 日对数均线差与 60 日动量按波动率标准化，等权组合；连续两日评分≥0.75入场，评分≤0或跌破持有期最高收盘价减3倍ATR20离场。它容易在震荡中反复交易，也可能过早离场。</p><p>v2 把慢趋势与快变化分开：结构分数取价格偏离63、126、252日对数EMA、各自除以60日波动率与周期平方根后的中位数；20日标准化动量只作变化提示。结构分数连续两天高于0.1入场，低于−0.1退出。该修订改善部分结果，但没有显示稳定优势。</p><p>所有买卖在信号次日开盘执行，做多或持币、不加杠杆。共同仓位规则为 min(1, 15% / 过去60日年化波动率)，因此各策略实际风险仍不同。均线、动量、突破均是本文定义的具体实现，不等同于大师的完整交易系统。</p></section>
<section><h2>半导体与港股主对照</h2><p>2024 年初至 2026-10-16；单边成本 0.15%；统一波动率仓位。半导体使用可交易 ETF 512480 代理，不是趋势动物自建行业指数。</p><div class="scroll">PRIMARY</div></section>
<section><h2>逐年稳定性</h2><p>2026 年为截至 10 月 16 日的年内收益，未年化。账户跨年连续持仓。逐年选择使用前3个完整日历年、至少600个观测日的扣费夏普；年末选择、下年首日开盘执行，保持换仓成本。</p><div class="scroll">YEARLY</div></section>
<section><h2>跨资产迁移</h2><p>2024 年以来，固定参数；11个现存ETF样本并不代表完整市场。境内上市的跨境ETF不能替代对应海外市场直接交易的验证。</p><div class="scroll">TRANSFER</div></section>
<section><h2>更新后的研究目标与风险约束</h2><p>用户已取消趋势动物对照要求，目标为独立建立可持续用于A股和港股的趋势与仓位策略。组合最大回撤的研究目标为20%，不作保证，也不等同于20%的年化波动率。</p><p>当前单资产回测尚不等于组合验证。全部已看过的数据均视作探索样本；不根据本轮结果挑选收益最高的参数。下一阶段需要投资范围、组合集中度与相关性、真实费用和公司行动验证，并在规则冻结后开展前向模拟。</p><p>新增121组单因素压力测试，从2022年起检验均线周期、波动率周期、风险预算、交易成本和执行延迟。基准在半导体与盈富基金上的最大回撤约17.6%；提高资产波动率目标至20%后，回撤均超过22%，不满足20%组合回撤目标所需的风险余量。</p><p><a href="robustness.csv">全部压力测试CSV</a> · <a href="../independent-strategy-protocol.json">独立策略研究约束</a></p></section>
<section><h2>数据与执行边界</h2><ul><li>同花顺半导体ETF取得1781根日线；与腾讯重合640个交易日的OHLC一致，但不能据此证明全部复权或公司行动正确。</li><li>港股盈富基金使用原始价格与16次供应商现金分红记录；除息日形成应收款，到账日后才可使用；100万港元起始资金，500股整手。官方完整分红核验仍未完成。</li><li>境内ETF使用复权价和可分割份额近似；实际最低佣金、盘口价差、停牌及价格限制未完整建模。现金利息设为零；没有汇率换算，也没有强制期末平仓。</li><li>11资产×6策略×2仓位规则×2期间×3成本场景，共792组主比较；成本场景不能代替券商真实费用表。</li><li>已通过19项测试，覆盖未来数据隔离、次日执行、分红权利与到账、整手现金约束和年度选模。测试不证明未来收益。</li></ul></section>
<section><h2>可复现资料</h2><p><a href="cross-market.csv">主比较CSV</a> · <a href="yearly-stability.csv">逐年CSV</a> · <a href="walk-forward.json">逐年选模详情</a> · <a href="cross-market-protocol.json">研究条件</a></p><p>在项目根目录运行：<code>python3 TradingAlarm/research/cross_market.py</code>，随后 <code>python3 TradingAlarm/research/walk_forward.py</code>。</p><p>研究依据：<a href="https://www.tradingblox.com/originalturtles/originalturtlerules.pdf">原始海龟规则</a> · <a href="https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf">时间序列动量论文</a> · <a href="https://www.xiaoyuzhoufm.com/episode/6577e4cf991e2ee608b39c56">趋势动物相关原始节目</a> · <a href="https://www.xiaoyuzhoufm.com/episode/6890c2138e06fe8de74c266b">作者访谈</a> · <a href="https://www.trahk.com.hk/en-hk/trahk-fund/resources/">盈富基金官方资料</a></p></section></html>'''
    document=document.replace('PRIMARY',primary_table).replace('YEARLY',yearly_table).replace('TRANSFER',transfer_table)
    (ROOT/'results/research-report.html').write_text(document)
    print(ROOT/'results/research-report.html')

if __name__=='__main__': main()
