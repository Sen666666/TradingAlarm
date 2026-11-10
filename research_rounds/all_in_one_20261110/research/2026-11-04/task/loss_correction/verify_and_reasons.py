"""Independent Fraction arithmetic, source table and reported-aggregate checks.
No account imports, signal reconstruction or events.
"""
import json,hashlib
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
P=Path(__file__).resolve().parent
hashes=json.loads((P/'SOURCE_SHA256.json').read_text())
summ=json.loads((P/'SUMMARY.json').read_text())
datasets={}
for filename,sha in hashes.items():
    p=Path(filename);assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
    x=json.loads(p.read_text())
    if isinstance(x,dict):
        suffix='_R0' if p.parent.name=='analysis' else ''
        for cell,ll in x.items():datasets[('2022Jan',cell+suffix)]=ll
    else:datasets[('2025JulAug',p.name.split('-LAYERS')[0])]=x
checks=[];reasons=[];membership=[]
for record in summ:
    key=(record['period'],record['cell']);ll=datasets[key]
    closed=[x for x in ll if int(x['remaining_qty'])==0]
    neg=[x for x in closed if F(x['total_contribution'])<0]
    assert len(ll)==record['layers'] and len(closed)==record['closed'] and len(neg)==record['negative_closed']
    exact={
       'buy_gross':sum((F(x['buy_gross']) for x in ll),F()),
       'negative_closed_amount':-sum((F(x['total_contribution']) for x in neg),F()),
       'positive_closed_amount':sum((max(F(),F(x['total_contribution'])) for x in closed),F()),
       'open_layer_contribution':sum((F(x['total_contribution']) for x in ll if x['remaining_qty']),F()),
       'all_contribution':sum((F(x['total_contribution']) for x in ll),F())}
    assert all(F(record[k])==v for k,v in exact.items())
    for n in [10,20,30]:
        aa=[x for x in closed if F(x['total_contribution'])/F(x['buy_cost'])<=-F(n,100)]
        assert len(aa)==record[f'loss_ge_{n}_pct_count']
        assert -sum((F(x['total_contribution']) for x in aa),F())==F(record[f'loss_ge_{n}_pct_amount'])
    max_local_residual=F()
    for x in ll:
        realized=sum((F(y['net_cash'])-F(y['buy_cost_allocated']) for y in x['actual_sell_parts']),F())
        residual=abs(realized-F(x['realized_trade_PNL']))
        max_local_residual=max(max_local_residual,residual)
        assert residual<F(1,10**18)
        total=F(x['realized_trade_PNL'])+F(x['unrealized_net_buy_cost'])+F(x['booked_dividend_income'])
        assert abs(total-F(x['total_contribution']))<F(1,10**18)
    gg=defaultdict(list)
    for x in closed:
        kind=' | '.join(sorted({z['reason'] for z in x['actual_sell_parts']})) or 'NO_PART'
        gg[kind].append(x)
        membership.append(dict(period=key[0],cell=key[1],layer=x['layer'],sid=x['sid'],closed=x['closed'],buy_cost=x['buy_cost'],total_contribution=x['total_contribution'],actual_exit_reason_set=kind,negative=F(x['total_contribution'])<0))
    for kind,xx in sorted(gg.items()):
        reasons.append(dict(period=key[0],cell=key[1],actual_exit_reason_set=kind,closed_layers=len(xx),negative_layers=sum(F(x['total_contribution'])<0 for x in xx),negative_amount=float(-sum((min(F(),F(x['total_contribution'])) for x in xx),F())),positive_amount=float(sum((max(F(),F(x['total_contribution'])) for x in xx),F())),net_amount=float(sum((F(x['total_contribution']) for x in xx),F()))))
    checks.append(dict(period=key[0],cell=key[1],source_layers=len(ll),all_aggregates_exact=True,all_thresholds_exact=True,layer_sale_and_contribution_max_residual=float(max_local_residual)))
for filename,sha in hashes.items():assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==sha
for name,x in [('VERIFICATION.json',dict(passed=True,checks=checks,all_6_source_hashes_unchanged=True,financial_events=0,notes=['Fraction recomputation independent of Decimal aggregation; this is arithmetic verification, not an independent economic agent review.','Source layer exports contain prior Decimal allocation rounding at below 1e-18 yuan; full aggregate uses exact exported contribution.','Loss layers are correlated and are not independent trial/campaign observations.'])),('DETAILED_EXIT_REASON_SETS.json',reasons),('CLOSED_LAYER_REASON_MEMBERSHIP.json',membership)]:
    with (P/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2)
print(json.dumps([r for r in reasons if r['cell']=='C10'],ensure_ascii=False,indent=2))
