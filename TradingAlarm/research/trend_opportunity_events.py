"""Retrospective union of overlapping winning-label intervals, never signals."""
import json
from pathlib import Path
import pandas as pd
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from strategy_signals import build_signals
from trend_first_passage_audit import MODELS

OUT=Path('results/trend-opportunity-events')


def merge_intervals(intervals):
    result=[]
    for start,end in sorted(intervals):
        if end<start:raise ValueError('reversed interval')
        if not result or start>result[-1]['end']:
            result.append(dict(start=start,end=end,members=1))
        else:
            result[-1]['end']=max(result[-1]['end'],end);result[-1]['members']+=1
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(status='Frozen before outcomes',interval='Each up_first label: signal date through first+30% touch date; union overlapping intervals within symbol, including transitive overlap; no gap tolerance.',evaluation='Within each retrospective union, first registered long close with next observed open no later than last touch. Report open-price move from earliest member next-open reference; holding fraction within union.',limits='Union is not a uniquely identified economic campaign. Could merge sequential moves; inter-asset events correlated. Any participation is permissive and not profitable capture. Earliest anchor and end are future-informed. No strategy changes.'),indent=2))
    labels=pd.read_parquet('results/trend-first-passage-audit/labels-and-exposure.parquet')
    etf,_=load_extended();hk,_=load_assets();events=[];evaluations=[]
    for group,assets in [('etf17',etf),('hk7',hk)]:
        signals={m:build_signals(assets,m) for m in MODELS}
        for symbol,a in assets.items():
            raw=a['raw'];valid=raw.index[raw.volume.gt(0)].intersection(a['signal'].index);f=a['signal'].reindex(valid)
            wins=labels.loc[labels.group.eq(group)&labels.symbol.eq(symbol)&labels.label.eq('up_first')]
            intervals=[]
            for row in wins.itertuples():
                i=f.index.get_loc(pd.Timestamp(row.date));intervals.append((i,i+row.bars_to_event))
            for number,event in enumerate(merge_intervals(intervals)):
                start,end=event['start'],event['end'];key=f'{group}-{symbol}-{number}'
                entry=f.open.iloc[start+1]
                events.append(dict(event=key,group=group,symbol=symbol,start=str(f.index[start].date()),end=str(f.index[end].date()),year=f.index[start].year,observation_dates=event['members'],observed_span=end-start,earliest_reference_open=float(entry)))
                for model in MODELS:
                    s=signals[model][symbol].reindex(f.index)
                    positions=[i for i in range(start,end) if s.iloc[i]>0]
                    first=positions[0] if positions else None
                    evaluations.append(dict(event=key,group=group,symbol=symbol,year=f.index[start].year,model=model,any_participation=bool(positions),first_signal=str(f.index[first].date()) if first is not None else None,first_possible_open=str(f.index[first+1].date()) if first is not None else None,bars_from_anchor=first-start if first is not None else None,price_move_before_first=float(f.open.iloc[first+1]/entry-1) if first is not None else None,held_fraction=float(s.iloc[start:end].gt(0).mean())))
                    segment=s.iloc[start:end].gt(0)
                    evaluations[-1]['long_runs']=int((segment&~segment.shift(fill_value=False)).sum())
    e=pd.DataFrame(events);v=pd.DataFrame(evaluations);e.to_csv(OUT/'events.csv',index=False);v.to_csv(OUT/'model-review.csv',index=False)
    assert e.observation_dates.sum()==labels.label.eq('up_first').sum()
    summary=v.groupby(['group','model']).agg(events=('event','size'),participated=('any_participation','sum'),mean_held_fraction=('held_fraction','mean'),median_pre_entry_move=('price_move_before_first','median'),median_delay=('bars_from_anchor','median'))
    summary.to_csv(OUT/'summary.csv');print(summary.to_string())
    print(e.groupby(['group','year']).agg(events=('event','size'),observation_dates=('observation_dates','sum')).to_string())


if __name__=='__main__':main()
