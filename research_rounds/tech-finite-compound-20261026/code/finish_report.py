"""Finish report serialization after an unavailable BH win-rate produced NaN.
All existing financial outputs, tables, figures and failed JSON are preserved.
"""
from common import *
import html,collections
def main():
 s=pd.read_csv(HERE/'analysis/summary.csv');base=s[s.scenario.eq('base')];rot=pd.read_csv(HERE/'analysis/rotation-funnel.csv');reason=pd.read_csv(HERE/'analysis/rotation-invalid-reasons.csv');bg=pd.read_csv(HERE/'analysis/pool-price-background.csv');clean=lambda d:d.astype(object).where(pd.notna(d),None).to_dict('records')
 write(HERE/'post-result-summary-v2.json',dict(base=clean(base),rotation_funnel=clean(rot),invalid_reason_counts=reason.groupby(['scenario','reason']).size().reset_index(name='count').to_dict('records'),pool_price_background_final=float(bg.normalized_price.iloc[-1])))
 page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>科技有限复利与成交额换仓</title><style>body{font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;max-width:1250px;margin:30px auto;padding:0 20px;color:#203047;background:#f7f9fc}table{border-collapse:collapse;background:white;width:100%;font-size:14px}th,td{padding:9px;border-bottom:1px solid #ddd;text-align:right}th:first-child,td:first-child{text-align:left}img{max-width:100%;height:auto}.scroll{overflow:auto}a{color:#2264a7}.note{background:#fff5dc;padding:15px;border-radius:8px}</style><h1>科技股有限复利与成交额换仓</h1><p>2024—2026-10-26 · 407股 · 每户100万元 · 21条有效路径</p><p class="note">I基础收益139.14%/回撤41.05%；风险定仓62.20%/34.01%优于固定半仓37.89%/39.26%。成交额换仓109.47%/50.19%，基础更差、延迟情景改善，尚不稳定。所有基础组回撤均超过20%。</p><p><a href="CONCLUSION.md">研究结论</a> · <a href="RESULTS.md">完整结果与归因</a> · <a href="PROTOCOL.md">规则</a> · <a href="analysis/summary.csv">21情景CSV</a> · <a href="analysis/rotations.csv">逐对换仓</a></p><img src="comparison.png" alt="净值回撤暴露"><h2>基础情景</h2><div class="scroll">'''
 page+=base[['policy','final_nav','net_return','max_drawdown','mean_exposure','fees']].to_html(index=False,float_format=lambda v:f'{v:.4f}')
 page+='</div><h2>全部三情景</h2><div class="scroll">'+s[['policy','scenario','net_return','max_drawdown','mean_exposure','fees']].to_html(index=False,float_format=lambda v:f'{v:.4f}')+'</div><img src="return-risk.png" alt="收益与回撤"><p>表内小数收益/回撤/暴露乘100为百分比；金额为元。当前存续/分类/市值快照历史开发研究，非样本外；日线成交为声明代理。首次费用边界失败已保留，同参修复重跑一次，全部独立核账及前缀通过，无实盘。</p></html>'
 with (HERE/'index.html').open('x') as f:f.write(page)
 print('Report completion and strict JSON serialization pass',flush=True)
if __name__=='__main__':main()
