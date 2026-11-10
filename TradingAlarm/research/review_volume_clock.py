"""Fixed-protocol volume clock review; no parameter selection."""
import json, hashlib
from pathlib import Path
import pandas as pd
from episode_capital_tail_audit import attach_cash
ROOT=Path(__file__).resolve().parent
out=ROOT/'results/strength-volume-clock'
results=json.loads((out/'results.json').read_text())
tails=[]
for strategy in ['pairwise_volume','volume_clock_pairwise']:
    case=f'hk7-{strategy}-daily-base'
    eps=attach_cash(json.loads((out/f'{case}-episodes.json').read_text()),json.loads((out/f'{case}-orders.json').read_text()))
    f=pd.DataFrame(eps); path=pd.read_parquet(out/f'{case}-path.parquet')
    error=abs(f.pnl.sum()-(path.nav.iloc[-1]-1)*1e6)
    assert error<1e-6
    for threshold in [.3,.8]:
        tail=f.return_on_buy_cash.ge(threshold)
        tails.append(dict(case=case,threshold=threshold,episodes=len(f),tail_count=int(tail.sum()),tail_contribution=float(f.loc[tail,'pnl'].sum()/1e6),ordinary_contribution=float(f.loc[~tail,'pnl'].sum()/1e6),reconciliation_error=float(error)))
summary=[{k:r[k] for k in ['case','total_return','max_drawdown','average_cash_weight','year2026']} for r in results]
review=dict(status='development_only_not_adopted',summary=summary,tail_accounting=tails,validation=json.loads((out/'validation.json').read_text()),unit_tests=3,
 decision='总收益略有改善；港股普通交易合计为正，但按累计买入现金口径没有单次收益达到30%的交易，未体现目标中的大赢家贡献。账户重大行情80%的目标仍无达标证据；港股2026表现恶化。不据此替换主算法或扩大至完整个股组合。',
 limits=['全部历史为反复使用的开发数据；不是独立样本外证据。','ETF17/HK7选定样本，不能证明跨市场普适性。','尾部按单次累计买入现金收益30%/80%分组，仅用于归因；不是账户收益，也不是可预知筛选器。','大量现金降低了资金暴露；低回撤不能单独证明有效。'],
 next='先检验2026趋势转弱阶段的识别延迟及强度曲线；成交量时钟只保留为对照，停止以全期收益小幅提高为理由扩展搜索。')
review['source_hashes']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['volume_clock_strength.py','test_volume_clock_strength.py','strategy_signals.py','review_volume_clock.py']}
(out/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
p=ROOT/'progress.json'; progress=json.loads(p.read_text());progress['latest_volume_clock_review']={'status':'completed_not_adopted','review':'results/strength-volume-clock/review.json','next':review['next']};p.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(tails,ensure_ascii=False,indent=2))
for r in results:
    if r['scenario']=='base':print(r['case'],r['total_return'],r['average_cash_weight'],r['max_drawdown'])
