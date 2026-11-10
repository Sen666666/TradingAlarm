"""Same-date, same-strength-band rise/fall contrasts; fixed lags, diagnostic only."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent

def changes(scores,lag):
    f=scores[['date','symbol','strength']].sort_values(['symbol','date']).copy()
    if f.duplicated(['symbol','date']).any():raise ValueError('Duplicate score dates')
    f['change']=f.groupby('symbol').strength.diff(lag)
    f['direction']=np.where(f.change>0,'rising',np.where(f.change<0,'falling','flat'))
    return f.loc[f.change.notna()]

def main():
    out=ROOT/'results/strength-transition-audit';out.mkdir(exist_ok=True)
    source=ROOT/'results/broad-exit-disagreement/all-observed-signals.parquet';labeled=ROOT/'results/strength-calibration-audit/labeled-scores.parquet'
    score=pd.read_parquet(source);score['date']=pd.to_datetime(score.date);labels=pd.read_parquet(labeled);dailyrows=[];checkrows=[]
    for lag in [1,5]:
        c=changes(score,lag)
        for symbol,g in score.groupby('symbol'):
            cutoff=g.date.sort_values().iloc[len(g)//2]
            past=changes(g.loc[g.date.le(cutoff)],lag);full=c.loc[c.symbol.eq(symbol)&c.date.le(cutoff)]
            pd.testing.assert_frame_equal(past.reset_index(drop=True),full.reset_index(drop=True))
        f=labels.merge(c[['date','symbol','change','direction']],on=['date','symbol'],how='inner',validate='many_to_one')
        d=f.groupby(['year','date','horizon','bin','direction']).agg(n=('symbol','size'),mean_return=('forward_return','mean'),tail30=('tail30','mean'),mean_strength=('strength','mean')).reset_index();d['lag']=lag;dailyrows.append(d)
        checkrows.append(dict(lag=lag,feature_rows=len(c),joined_rows=len(f),prefix_checks=score.symbol.nunique()))
    d=pd.concat(dailyrows,ignore_index=True);d.to_parquet(out/'daily-cells.parquet',index=False)
    valid=d.loc[d.n.ge(5)&d.direction.isin(['rising','falling'])]
    p=valid.pivot(index=['lag','year','date','horizon','bin'],columns='direction',values=['mean_return','tail30','mean_strength']).dropna()
    contrast=pd.DataFrame({name:p[(name,'rising')]-p[(name,'falling')] for name in ['mean_return','tail30','mean_strength']}).reset_index()
    contrast.to_parquet(out/'paired-contrasts.parquet',index=False)
    s=contrast.groupby(['lag','year','horizon','bin']).agg(paired_dates=('date','size'),rising_minus_falling_return=('mean_return','mean'),rising_minus_falling_tail30=('tail30','mean'),within_bin_strength_difference=('mean_strength','mean')).reset_index();s.to_csv(out/'summary.csv',index=False)
    (out/'validation.json').write_text(json.dumps(dict(checks=checkrows,input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,labeled]},limits=[
      'Fixed1/5 previous observed-score steps; firstlagrows absent, no backfill. Zerochanges excluded frompairedcontrast but saved.',
      'Identicaldate andsame2pointscoreband, at least5stocks ineachdirection; equaldateweight. Residualwithin-bandstrength differences reported, not fully matched.',
      'Observedbar lags can span differentcalendar lengths withhalts; directionalchange usespastonly.',
      'Forwardclose returns andtail30labels for evaluationonly; no executableentry, costs oraccountwealth result.',
      'Correlatedstocks/overlappinghorizons andpreviouslyinspected485stockdevelopment; no significance/causal orholdoutclaim.'
    ]),indent=2));print(s.loc[s.horizon.eq(21)&s.bin.isin(['6-8','8-10'])].to_string(index=False))
if __name__=='__main__':main()
