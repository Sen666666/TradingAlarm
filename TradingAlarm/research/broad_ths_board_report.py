"""Board-stratified descriptive signal diagnostics; no sector selection."""
import json,math,argparse
import pandas as pd
from build_stock_features import ROOT
from ths_refresh_batch import board


def main(output):
    out=ROOT/'results'/output;table=pd.read_parquet(out/'episodes.parquet');table['board']=table.symbol.map(board);rows=[]
    for (name,delay,cutoff,b),g in table.groupby(['strategy','delay','cutoff','board']):
        for cost in (15,30):
            for cohort in ('all','entries2026'):
                h=g if cohort=='all' else g[g.entry_date.ge('2026-01-01')];closed=h[h.status.eq('closed')];v=closed[f'return{cost}'];marked=h[~h.status.eq('terminal_unknown')][f'return{cost}'].sort_values();n=math.ceil(len(marked)*.1);w=v[v>0];l=v[v<0]
                rows.append(dict(strategy=name,delay=int(delay),cutoff=cutoff,board=b,cost=cost,cohort=cohort,closed=len(v),open=int(h.status.eq('open_at_cutoff').sum()),terminal=int(h.status.eq('terminal_unknown').sum()),known=len(marked),closed_win_rate=float(v.gt(0).mean()) if len(v) else None,payoff=float(w.mean()/abs(l.mean())) if len(w) and len(l) else None,known_marked_mean=float(marked.mean()) if len(marked) else None,known_bottom90_mean=float(marked.iloc[:-n].mean()) if n and len(marked)>n else None))
    for whole in json.loads((out/'summary.json').read_text()):
        matched=[r for r in rows if all(r[k]==whole[k] for k in ('strategy','delay','cutoff','cost','cohort'))];n=sum(r['known'] for r in matched)
        if n:assert abs(sum(r['known']*r['known_marked_mean'] for r in matched if r['known'])/n-whole['known_marked_mean'])<1e-12
        assert sum(r['closed'] for r in matched)==whole['counts'].get('closed',0)
    (out/'board-report.json').write_text(json.dumps(dict(rows=rows,validation='Board counts and weighted known-episode means reconcile to pooled report.',limitations='Balancedcollectionpriority,not marketweights. Tradecountweighted averages,not portfolio returns. No boardselected by these results.'),indent=2)+'\n')
    for r in rows:
        if r['cutoff']=='2026-10-16' and r['delay']==0 and r['cost']==15 and r['cohort']=='all':print(r)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);main(parser.parse_args().output)
