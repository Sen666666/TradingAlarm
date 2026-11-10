"""Coverage scale over existing actual holding maxima, not a new exit rule."""
from pathlib import Path
from decimal import Decimal as D
import hashlib,json
O=Path(__file__).resolve().parent;P=O.parent;SRC={}
def read(p):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
rows=read(P/'POST_PURCHASE_ALL25_PATHS.json')
layers=read('/Users/bytedance/Documents/Codex/2026-11-04/task/loss_correction/no60_behavior_v1/PVR_NO60-SEMICONDUCTOR_ACCEPTED_LIFECYCLES.json')
lm={r['layer']:r for r in layers};out=[]
for r in rows:
 q=lm[r['layer']]['actual_fill']['shares'];R=D(r['initial_nominal_price_to_floor_risk'])
 advance=D(q)*D(r['actual_price'])*D(r['maximum_close_gain_during_actual_holding_pct'])/100
 assert R>0
 out.append(dict(layer=r['layer'],sid=r['sid'],name=r['name'],role=r['role'],opened=r['opened'],closed=r['closed'],
  original_initial_shares=q,original_buy_cost=r['buy_cost'],original_lifecycle_net=r['net'],original_closed_negative=r['closed_net_negative'],
  original_open=bool(r['quantity']),initial_nominal_price_floor_R=R,maximum_quoted_close_advance_in_entry_share_units=advance,
  maximum_quoted_close_advance_R=advance/R,
  any_quoted_close_above_fill=advance>0,quoted_advance_at_least_1R=advance>=R,quoted_advance_at_least_2R=advance>=2*R))
groups={}
for k in ['any_quoted_close_above_fill','quoted_advance_at_least_1R','quoted_advance_at_least_2R']:
 a=[r for r in out if r[k]];neg=[r for r in a if r['original_closed_negative']]
 groups[k]=dict(layers=len(a),stocks=len({r['sid']for r in a}),mobile_layers=sum(r['role']=='mobile'for r in a),
  original_closed_negative_layers=len(neg),original_closed_negative_stocks=len({r['sid']for r in neg}),
  original_negative_contribution_of_contactable_layers=sum((D(r['original_lifecycle_net'])for r in neg),D(0)),
  original_net_of_all_contactable_layers=sum((D(r['original_lifecycle_net'])for r in a),D(0)),
  layer_ids=[r['layer']for r in a],negative_layer_ids=[r['layer']for r in neg])
save('ALL25_PROFIT_PROGRESS_SCALE.json',out)
save('PROFIT_PROGRESS_COVERAGE_BOUND_SUMMARY.json',dict(groups=groups,
 total_original_layers=25,total_original_stocks=18,total_original_negative_layers=15,
 total_original_negative_contribution=sum((D(r['net'])for r in rows if r['closed_net_negative']),D(0)),
 rule_selection='No rule or threshold selected; zero/1R/2R are fixed descriptive scales of original quoted CLOSE progress',
 bound='Only which original holdings a rule activated at that price-progress scale could contact before the actual exit. These are original contributions, not recoverable profit, a continuous account bound, or an estimated counterfactual PnL',
 units='R is original initial shares times raw fill-price minus frozen initial raw floor, no fees; adjusted CLOSE relative to entry normalized fill converted back to entry-share units. Original legal holding CLOSE maxima exclude the sell-OPEN date CLOSE',
 other_values='Corporate-action account cash/receivables and current shares are not reconstructed here. Daily trace is required for any executable net-profit handoff',
 new_accounts=0,new_financial_paths=0))
SRC[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('PROFIT_BOUND_SOURCE_SHA256.json',SRC)
print(json.dumps(groups,ensure_ascii=False,indent=2,default=str))
