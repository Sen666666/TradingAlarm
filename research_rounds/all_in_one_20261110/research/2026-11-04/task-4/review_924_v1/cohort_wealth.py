"""Saved native layer-wealth differences only; no account or trading replay."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D
import gzip, hashlib, json, sys, time

sys.dont_write_bytecode = True
O = Path(__file__).resolve().parent
WORK = O.parent
sys.path.insert(0, str(WORK / 'new_price_trend_v1'))
import native_mark_reader as MARK

ROOT = WORK / 'new_price_trend_v1/funding/runs/long_OFF/pair'
EPS = D('.000001')
SOURCES = {}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p, lines=False):
    SOURCES[str(p)] = sha(p)
    with gzip.open(p, 'rt') as f:
        return list(map(json.loads, f)) if lines else json.load(f)
def save(name, x):
    (O/name).write_text(json.dumps(x, ensure_ascii=False, indent=2, default=str)+'\n')
def eq(a,b,label): assert abs(a-b)<EPS, (label,str(a),str(b),str(a-b))
def group(layer):
    day=str(layer['opened'])[:10]
    return 'pre_924' if day<='2024-09-23' else 'rally_924_to_Oct8' if day<='2024-10-08' else 'post_Oct8'

def main():
    begun=time.monotonic(); O.mkdir(exist_ok=True)
    b=load(ROOT/'B.json.gz'); ds=load(ROOT/'daily.jsonl.gz',True)
    anchors=['2023-12-29','2024-09-23','2024-10-08','2024-12-31']
    daily={str(r['at'])[:10]:r for r in ds if str(r['at'])[:10]in anchors}
    assert len(daily)==4
    all_layers={int(l['id']):l for l in b['layers']}
    snapshots={}; summaries={}
    for day in anchors:
        r=daily[day]; live={int(l['id']):l for l in r['layers']}
        values={}; totals=defaultdict(lambda:dict(wealth=D(0),inventory=D(0),live_layers=0,live_stocks=set()))
        for lid,final in all_layers.items():
            if str(final['opened'])[:10]>day:
                cash=div=inv=D(0);qty=0
            elif lid in live:
                l=live[lid];cash=D(l['cash']);div=D(l['dividend']);qty=l['qty']
                inv=D(qty)*MARK.price(l['sid'],day)
            else:
                assert final['closed'] and str(final['closed'])[:10]<=day,('Layer state unknown',lid,day)
                # Entitlement is original previous-CLOSE inventory. No live
                # quantity after closure => no later new dividend recognition;
                # later payment of already-recognized receivables is not wealth.
                cash=D(final['cash']);div=D(final['dividend']);qty=0;inv=D(0)
            wealth=cash+div+inv;g=group(final)
            values[lid]=dict(layer=lid,sid=final['sid'],opened=final['opened'],cohort=g,
                cash=cash,recognized_dividend=div,qty=qty,inventory=inv,wealth=wealth)
            t=totals[g];t['wealth']+=wealth;t['inventory']+=inv
            if qty:t['live_layers']+=1;t['live_stocks'].add(final['sid'])
        eq(sum((x['inventory']for x in values.values()),D(0)),D(r['inventory']),('inventory',day))
        eq(D(1000000)+sum((x['wealth']for x in values.values()),D(0)),D(r['nav']),('wealth_NAV',day))
        snapshots[day]=values
        summaries[day]=dict(NAV=r['nav'],available=r['available'],inventory=r['inventory'],
            dividend_receivable=r['dividend_receivable'],cohorts={k:dict(v,live_stocks=len(v['live_stocks']))for k,v in totals.items()})
    phases=[('pre_924','2023-12-29','2024-09-23'),('rally','2024-09-23','2024-10-08'),
            ('post_peak','2024-10-08','2024-12-31'),('full_2024','2023-12-29','2024-12-31')]
    phase_rows=[]; layer_rows=[]
    for name,start,end in phases:
        by=defaultdict(lambda:D(0))
        for lid,l in all_layers.items():
            a,z=snapshots[start][lid],snapshots[end][lid];delta=z['wealth']-a['wealth']
            by[group(l)]+=delta
            if delta or a['qty'] or z['qty']:
                layer_rows.append(dict(phase=name,layer=lid,sid=l['sid'],kind=l['kind'],opened=l['opened'],
                    closed=l['closed'],reason=l['reason'],cohort=group(l),
                    begin_wealth=a['wealth'],end_wealth=z['wealth'],wealth_change=delta,
                    begin_qty=a['qty'],end_qty=z['qty'],begin_inventory=a['inventory'],end_inventory=z['inventory']))
        target=D(daily[end]['nav'])-D(daily[start]['nav']);eq(sum(by.values(),D(0)),target,('cohort',name))
        phase_rows.append(dict(phase=name,start=start,end=end,begin_NAV=daily[start]['nav'],end_NAV=daily[end]['nav'],
            wealth_change=target,return_pct=target/D(daily[start]['nav'])*100,cohort_changes=dict(by)))
    # All new post-Oct8 layers are truly closed by year end. Their whole actual
    # lifecycle net equals their phase wealth contribution, not hypothetical PnL.
    post=[l for l in b['layers']if group(l)=='post_Oct8']
    assert len(post)==303 and all(l['qty']==0 and l['closed']for l in post)
    eq(sum((D(l['cash'])+D(l['dividend'])for l in post),D(0)),next(x for x in phase_rows if x['phase']=='post_peak')['cohort_changes']['post_Oct8'],'new closed cohort')
    save('ANCHOR_COHORT_WEALTH.json',summaries);save('PHASE_COHORT_CHANGES.json',phase_rows)
    save('LAYER_PHASE_CHANGES.json',layer_rows)
    with gzip.open(O/'ANCHOR_ALL_LAYER_WEALTH.json.gz','wt')as f:json.dump(snapshots,f,ensure_ascii=False,default=str)
    SOURCES.update(MARK.sources);SOURCES[str(Path(__file__))]=sha(__file__)
    save('COHORT_SOURCE_SHA256.json',SOURCES)
    save('COHORT_SCOPE.json',dict(passed=True,seconds=time.monotonic()-begun,anchors=4,layers=len(all_layers),
        new_Account=0,new_RiskBook=0,new_Market=0,new_routes=0,new_fills=0,
        method='Original saved layer cash/dividend, actual anchor quantity and unchanged native mark. Closed layer wealth is constant; unpaid recognized dividends not counted twice.',
        meaning='Actual path attribution only; no claim all post-peak new losses avoidable; no counterfactual portfolio profit.'))
    print(json.dumps(phase_rows,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__':main()
