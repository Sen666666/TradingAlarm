"""Compare executed holding intervals, with future outcomes used only as audit labels."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent

def held_mask(days,episode):
    start=pd.Timestamp(episode['entry_date'])
    if episode['status']=='closed':return (days>=start)&(days<pd.Timestamp(episode['exit_date']))
    return (days>=start)&(days<=pd.Timestamp(episode['mark_date']))

def interval_overlap(days,episode,others):
    active=held_mask(days,episode);held=np.zeros(len(days),dtype=bool)
    for other in others:held|=held_mask(days,other)
    sample=held[active];n=len(sample)
    if not n:raise ValueError('No observed holding bars')
    count=int(sample.sum());first=int(np.flatnonzero(sample)[0]) if count else None
    last=int(np.flatnonzero(sample)[-1]) if count else None
    return dict(bars=n,covered_bars=count,coverage=count/n,first_coverage_delay=first,trailing_uncovered=n-1-last if count else None,kind='none' if count==0 else 'full' if count==n else 'partial')

def main():
    out=ROOT/'results/trend-overlap-audit';out.mkdir(exist_ok=True)
    source=ROOT/'results/strength-uniform-transfer485/episodes.parquet';f=pd.read_parquet(source)
    f=f.loc[f.cutoff.eq('2026-10-16')&f.delay.eq(0)]
    assert not f.status.eq('terminal_unknown').any()
    manifest=json.loads((ROOT/'data/ths-refresh-20261018/validated-input-balanced-second500.json').read_text())
    rows=[];hashes=0
    for rec in manifest['records']:
        path=ROOT/'data/ths-refresh-20261018'/f"{rec['ths_symbol']}-signal.parquet"
        assert hashlib.sha256(path.read_bytes()).hexdigest()==rec['signal_sha256'];hashes+=1
        raw=pd.read_parquet(path);days=raw.index[raw.observed_bar&raw.volume.gt(0)]
        both=f.loc[f.symbol.eq(rec['symbol'])]
        for target,comparison in [('pairwise_volume','uniform_pairwise_volume'),('uniform_pairwise_volume','pairwise_volume')]:
            others=both.loc[both.strategy.eq(comparison)].to_dict('records')
            for ep in both.loc[both.strategy.eq(target)].to_dict('records'):
                result=interval_overlap(days,ep,others)
                label='tail30' if ep['return15']>=.3 else 'loss' if ep['return15']<0 else 'ordinary_win'
                rows.append(dict(target=target,comparison=comparison,symbol=ep['symbol'],entry_date=ep['entry_date'],exit_date=ep['exit_date'],status=ep['status'],return15=ep['return15'],label=label,**result))
    r=pd.DataFrame(rows);r.to_parquet(out/'overlap.parquet',index=False)
    result=r.groupby(['target','label','kind']).agg(episodes=('symbol','size'),mean_coverage=('coverage','mean'),median_delay=('first_coverage_delay','median'),median_trailing_uncovered=('trailing_uncovered','median'),mean_label_return=('return15','mean')).reset_index()
    result.to_csv(out/'summary.csv',index=False)
    assert len(r)==len(f)
    (out/'validation.json').write_text(json.dumps(dict(input_hashes=hashes,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),episode_count=len(r),matched_source_count=len(f),limits=[
       'Exposure overlap uses observed positive-volume bars, entry open inclusive and closed exit open exclusive; same-date handoff has no overlap.',
       'Each comparison is union of holding intervals; a slow episode may overlap multiple fast episodes. Do not add their returns as independent opportunity gains.',
       'Forward episode return determines diagnostic label only. These labels must never become entry features.',
       'Coverage measures time, not captured price return, and ignores intraday movement. No causal attribution of PNL improvement.',
       'This is existing selected485A-share development simulation, not new independent evaluation.'
    ]),indent=2))
    print(result.to_string(index=False))
if __name__=='__main__':main()
