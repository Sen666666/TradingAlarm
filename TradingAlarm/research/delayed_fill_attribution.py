"""Match original entry signals across execution delays; do not assume identical exit decisions."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent

def decompose(m,cost=.0015):
    r=m.copy()
    r['entry_effect']=-np.log(r.entry_price_delay/r.entry_price_base)
    r['exit_mark_effect']=np.log(r.exit_price_delay/r.exit_price_base)
    r['fee_effect']=(r.status_delay.eq('closed').astype(float)-r.status_base.eq('closed').astype(float))*np.log1p(-cost)
    r['observed_log_difference']=np.log1p(r.return15_delay)-np.log1p(r.return15_base)
    r['identity_error']=(r.entry_effect+r.exit_mark_effect+r.fee_effect-r.observed_log_difference).abs()
    return r

def main():
    out=ROOT/'results/delayed-fill-attribution';out.mkdir(exist_ok=True)
    source=ROOT/'results/strength-calibrated-order-transfer485/episodes.parquet';f=pd.read_parquet(source);f=f[f.cutoff.eq('2026-10-16')]
    reports=[];allmatched=[];unmatched=[]
    for name,g in f.groupby('strategy'):
        assert not g.duplicated(['symbol','signal_date','delay']).any()
        base=g[g.delay.eq(0)];delay=g[g.delay.eq(1)]
        m=base.merge(delay,on=['symbol','signal_date'],how='outer',suffixes=('_base','_delay'),indicator=True,validate='one_to_one')
        extra=m[m._merge.ne('both')].copy();extra['model']=name;unmatched.append(extra)
        a=decompose(m[m._merge.eq('both')].copy());assert a.identity_error.max()<1e-12
        a['model']=name;a['year']=pd.to_datetime(a.signal_date).dt.year
        a['base_label']=np.where(a.return15_base.ge(.3),'tail30',np.where(a.return15_base.lt(0),'loss','ordinary_win'))
        allmatched.append(a)
        reports.append(dict(model=name,base_episodes=len(base),delay_episodes=len(delay),matched=len(a),base_only=int(m._merge.eq('left_only').sum()),delay_only=int(m._merge.eq('right_only').sum()),matched_mean_entry_effect=float(a.entry_effect.mean()),matched_mean_exit_mark_effect=float(a.exit_mark_effect.mean()),matched_mean_log_difference=float(a.observed_log_difference.mean()),matched_both_closed=int((a.status_base.eq('closed')&a.status_delay.eq('closed')).sum())))
    a=pd.concat(allmatched,ignore_index=True);a.to_parquet(out/'matched.parquet',index=False);pd.concat(unmatched,ignore_index=True).to_parquet(out/'unmatched.parquet',index=False)
    a.groupby(['model','year']).agg(count=('symbol','size'),entry_effect=('entry_effect','mean'),exit_mark_effect=('exit_mark_effect','mean'),fee_effect=('fee_effect','mean'),total_difference=('observed_log_difference','mean')).to_csv(out/'annual.csv')
    a.groupby(['model','base_label']).agg(count=('symbol','size'),entry_effect=('entry_effect','mean'),exit_mark_effect=('exit_mark_effect','mean'),total_difference=('observed_log_difference','mean')).to_csv(out/'base-outcomes.csv')
    (out/'summary.json').write_text(json.dumps(reports,indent=2))
    (out/'validation.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),matched_count=len(a),max_identity_error=float(a.identity_error.max()),limits=[
        'Match bysymbol/originalentrysignaldate, not actual entrydate; unmatchedsignals reported separately.',
        'Exit/mark effect includes altered exit dates and possible cancellation/path changes; not isolated impact of one exit-day delay.',
        'Additive logreturn decomposition per matched episode, not arithmetic portfolio wealth or an executable timing overlay.',
        'Unmatched episodes and within-symbol compounding prevent matched means from reconciling full syntheticwealthdifference.',
        'Future outcome labels descriptive only; selected485Ashare2024-2026development, not unseenvalidation.'
    ]),indent=2));print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
