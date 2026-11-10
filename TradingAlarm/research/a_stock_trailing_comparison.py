import json,math
from pathlib import Path
import pandas as pd
root=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research')
base=root/'results/a-stock-zero-range-stress'; out=root/'results/a-stock-trailing-risk'
b=json.loads((base/'cutoffs/summary.json').read_text());t=json.loads((out/'cutoffs/summary.json').read_text()); lookup={(x['cutoff'],x['cost_bps']):x for x in b}
comparison=[]
for x in t:
 y=lookup[x['cutoff'],x['cost_bps']];comparison.append(dict(cutoff=x['cutoff'],cost_bps=x['cost_bps'],baseline_mean_R=y['marked_mean_R'],trailing_mean_R=x['marked_mean_R'],difference=x['marked_mean_R']-y['marked_mean_R'],ordinary_R=x['ordinary_R'],tail_R=x['top10_R']))
summary=[]
for name,directory in [('fixed',base),('trailing',out)]:
 d=pd.read_parquet(directory/'campaigns.parquet');known=d[d.status.ne('terminal_unknown')]; closed=d[d.status.eq('closed')];wins=closed[closed.R_cost15.gt(0)];loss=closed[closed.R_cost15.lt(0)]
 summary.append(dict(variant=name,campaigns=len(d),closed=len(closed),open=int(d.status.eq('open_at_cutoff').sum()),unknown=int(d.status.eq('terminal_unknown').sum()),closed_win_rate=len(wins)/len(closed),closed_payoff_R=wins.R_cost15.mean()/-loss.R_cost15.mean(),closed_mean_R=closed.R_cost15.mean(),known_mean_R=known.R_cost15.mean(),marked_price_moves_ge80=int(known.price_move.ge(.8).sum())))
(out/'comparison.json').write_text(json.dumps(dict(cutoffs=comparison,summary=summary),indent=2))
print(json.dumps(dict(cutoffs=comparison,summary=summary),indent=2))
p=root/'progress.json'; d=json.loads(p.read_text());d['a_stock_excursion_and_trailing']={'status':'full_excursion_diagnostic_and_single_prespecified_trailing_variant_complete','diagnostic':'29137closedlosses;only5324reached1Rcloseprofit;medianlossheld12observedcloses vs126forwinners. Doesnotjustifyforcedtwo-weekexit.','variant':'Monotonic highestheldclose minusoriginal4ATR distance;sameentry,costs,zero-range nofill;nexteligibleopen;no thresholdsearch.','comparison':comparison,'summary':summary,'validation':'9tests pass includingtrailinglag,blockedexitandfuturecloseinvariance;all5426histories rerun and5cutoffs independentlyrecomputed.','limits':'SyntheticpriceRnotaccountreturns;reusedexploration,universe/execution/terminalgaps remain.','next':'Assessordinarylossoffsetandtailretention beforeadoption;transferonlyifrobust,noautomaticdefaultchange.'};p.write_text(json.dumps(d,indent=2,ensure_ascii=False))
