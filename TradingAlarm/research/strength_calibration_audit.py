"""Fixed score-bin forward calibration; paired daily controls, no strategy fitting."""
import json,hashlib
from pathlib import Path
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parent

def labels(close,h):return close.shift(-h)/close-1

def main():
    out=ROOT/'results/strength-calibration-audit';out.mkdir(exist_ok=True)
    source=ROOT/'results/broad-exit-disagreement/all-observed-signals.parquet';scores=pd.read_parquet(source);scores['date']=pd.to_datetime(scores.date)
    manifest=json.loads((ROOT/'data/ths-refresh-20261018/validated-input-balanced-second500.json').read_text());rows=[]
    for rec in manifest['records']:
        path=ROOT/'data/ths-refresh-20261018'/f"{rec['ths_symbol']}-signal.parquet";assert hashlib.sha256(path.read_bytes()).hexdigest()==rec['signal_sha256']
        f=pd.read_parquet(path);c=f.loc[f.observed_bar&f.volume.gt(0),'signal_close']
        s=scores.loc[scores.symbol.eq(rec['symbol']),['date','symbol','strength']].set_index('date')
        for h in [1,5,21]:
            a=s.copy();a['forward_return']=labels(c,h).reindex(a.index);a['horizon']=h;rows.append(a.reset_index())
    f=pd.concat(rows,ignore_index=True).dropna();f['year']=f.date.dt.year
    f['bin']=pd.cut(f.strength,[-1e-12,2,4,6,8,10],labels=['0-2','2-4','4-6','6-8','8-10']).astype(str)
    f['same_date_mean']=f.groupby(['date','horizon']).forward_return.transform('mean');f['excess']=f.forward_return-f.same_date_mean;f['tail30']=f.forward_return.ge(.3)
    f.to_parquet(out/'labeled-scores.parquet',index=False)
    daily=f.groupby(['year','date','horizon','bin']).agg(n=('symbol','size'),mean_return=('forward_return','mean'),excess=('excess','mean'),tail30=('tail30','mean')).reset_index()
    daily.to_parquet(out/'daily-bins.parquet',index=False)
    summary=daily.groupby(['year','horizon','bin']).agg(dates=('date','size'),observations=('n','sum'),date_equal_mean_return=('mean_return','mean'),date_equal_excess=('excess','mean'),date_equal_tail30=('tail30','mean')).reset_index();summary.to_csv(out/'annual-summary.csv',index=False)
    # Compare strong vs moderately strong bins on identical dates with >=5names each.
    chosen=daily.loc[daily.n.ge(5)&daily.bin.isin(['6-8','8-10'])]
    pivot=chosen.pivot(index=['year','date','horizon'],columns='bin',values='mean_return').dropna()
    pivot['high_minus_moderate']=pivot['8-10']-pivot['6-8'];pivot.to_csv(out/'paired-dates.csv')
    paired=pivot.groupby(['year','horizon']).agg(dates=('high_minus_moderate','size'),mean_high_minus_moderate=('high_minus_moderate','mean'));paired.to_csv(out/'paired-summary.csv')
    (out/'validation.json').write_text(json.dumps(dict(input_hashes=485,score_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),labeled_rows=len(f),unmatured_rows_dropped=len(scores)*3-len(f),fixed_bins=[0,2,4,6,8,10],limits=['Existing pairwisevolume score, not the papers trend definition; hypothesis check, not replication.','Forwardlabels use future only for evaluation; no strategy or threshold trained.','Equaldatebin means and matchedsame-date contrasts avoid weighting busy dates more; survivinguniverse and correlation remain.','Forwardclose returns ignore transactioncosts, executableentries andpositionmanagement; not accountperformance.','Overlapping horizons not independent; no significance orpvalue claims. 2024-2026inspecteddevelopment.']),indent=2))
    print(paired.to_string());print(summary.loc[summary.horizon.eq(21)].to_string(index=False))
if __name__=='__main__':main()
