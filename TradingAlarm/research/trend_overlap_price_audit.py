"""Exact log-price path partition by comparison holding intervals; hindsight attribution."""
import json,math,hashlib
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent

def key(date,close=False):return pd.Timestamp(date).toordinal()*2+int(close)
def endpoints(ep):
    return key(ep['entry_date']), key(ep['exit_date']) if ep['status']=='closed' else key(ep['mark_date'],True)

def partition(ep,others,cost=.0015):
    start,end=endpoints(ep)
    points={start:ep['entry_price'],end:ep['exit_price']};spans=[]
    for other in others:
        a,b=endpoints(other)
        if b<=start or a>=end:continue
        spans.append((a,b))
        for t,p in [(a,other['entry_price']),(b,other['exit_price'])]:
            if start<t<end:
                if t in points:assert math.isclose(points[t],p,rel_tol=1e-10)
                points[t]=p
    ordered=sorted(points);segments=[]
    for a,b in zip(ordered[:-1],ordered[1:]):
        covered=any(x<=a<y for x,y in spans)
        segments.append((covered,math.log(points[b]/points[a])))
    covered_indices=[i for i,(covered,_) in enumerate(segments) if covered]
    parts=dict(covered=0.,before=0.,after=0.,gap=0.,none=0.)
    for i,(covered,value) in enumerate(segments):
        label='covered' if covered else 'none' if not covered_indices else 'before' if i<covered_indices[0] else 'after' if i>covered_indices[-1] else 'gap'
        parts[label]+=value
    fees=(math.log1p(-cost) if ep['status']=='closed' else 0)-math.log1p(cost)
    net=sum(parts.values())+fees
    expected=math.log1p(ep['return15'])
    assert abs(net-expected)<1e-10
    return dict(**parts,fee_log=fees,net_log=net,segments=len(segments),has_overlap=bool(covered_indices),identity_error=abs(net-expected))

def main():
    out=ROOT/'results/trend-overlap-price-audit';out.mkdir(exist_ok=True)
    source=ROOT/'results/strength-uniform-transfer485/episodes.parquet';f=pd.read_parquet(source);f=f.loc[f.cutoff.eq('2026-10-16')&f.delay.eq(0)]
    assert not f.status.eq('terminal_unknown').any();rows=[]
    for symbol,g in f.groupby('symbol'):
        for target,comparison in [('pairwise_volume','uniform_pairwise_volume'),('uniform_pairwise_volume','pairwise_volume')]:
            others=g.loc[g.strategy.eq(comparison)].to_dict('records')
            for ep in g.loc[g.strategy.eq(target)].to_dict('records'):
                label='tail30' if ep['return15']>=.3 else 'loss' if ep['return15']<0 else 'ordinary_win'
                rows.append(dict(target=target,symbol=symbol,entry_date=ep['entry_date'],label=label,status=ep['status'],return15=ep['return15'],**partition(ep,others)))
    r=pd.DataFrame(rows);assert len(r)==len(f);r.to_parquet(out/'partition.parquet',index=False)
    r['entry_year']=pd.to_datetime(r.entry_date).dt.year
    metrics={x:(x,'mean') for x in ['covered','before','after','gap','none','fee_log','net_log']}
    summary=r.groupby(['target','label']).agg(count=('symbol','size'),overlap_count=('has_overlap','sum'),**metrics).reset_index()
    summary.to_csv(out/'summary.csv',index=False)
    r.groupby(['target','entry_year','label']).agg(count=('symbol','size'),**metrics).to_csv(out/'entry-years.csv')
    (out/'validation.json').write_text(json.dumps(dict(episodes=len(r),max_log_identity_error=float(r.identity_error.max()),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),limits=[
        'Exact additive logprice attribution on each target episode, not allocation-weighted account PNL. Means are episode-weighted.',
        'Comparison entry/exit boundaries partition paths at actual simulated open prices; open terminal marks use close prices.',
        'Net identity includes target episode15bps entry and closed exit cost. Segment returns do not include counterfactual comparison trading costs.',
        'Before/after means refer to comparison exposure within target interval. Beforefast exposure inside slow interval can represent earlier slow entry.',
        'Future outcomes label episodes only for audit; no causal claim or executable hindsight strategy.',
        'Many-to-many interval matching creates dependent observations. Inspected485stock development data, not new independent validation.'
    ]),indent=2));print(summary.to_string(index=False))
if __name__=='__main__':main()
