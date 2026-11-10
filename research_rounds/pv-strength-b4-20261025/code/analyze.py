"""Descriptive post-output audit. No fitting, ranking, strategy or accounts."""
import pandas as pd
import numpy as np
from common import ROOT,B3,NAMES,read,write,now

def runs(f,mask):
    groups=mask.ne(mask.shift()).cumsum();out=[]
    for _,g in f.loc[mask].groupby(groups.loc[mask]):
        out.append(dict(start=str(g.index[0].date()),end=str(g.index[-1].date()),observations=len(g),
            first_close=float(g.close.iloc[0]),last_close=float(g.close.iloc[-1]),
            close_to_close_pct=100*(float(g.close.iloc[-1]/g.close.iloc[0])-1),
            mu21_bp_min=float(g.mu21_bp.min()),mu21_bp_max=float(g.mu21_bp.max())))
    return out

def main():
    out=ROOT/'analysis';out.mkdir(exist_ok=False);windows=[];contradictions=[];receipts=[];selected=[]
    frames={sid:pd.read_parquet(ROOT/'results'/(sid+'.parquet')) for sid in NAMES}
    for w in read(B3/'figures/real-manifest.json')['plots']:
        f=frames[w['asset']].loc[w['start']:w['end']];both=f.S21.eq(1)&f.S63.eq(1)
        negative=runs(f,both&f.mu21.lt(0));near=runs(f,both&f.mu21_bp.abs().lt(1))
        contradictions.append(dict(window=w['id'],aligned_up_but_mu21_negative=negative,
            aligned_up_but_mu5_negative=runs(f,both&f.mu5.lt(0)),
            aligned_up_but_near_zero_mu21=near))
        row=dict(window=w['id'],asset=w['asset'],name=w['name'],start=str(f.index[0].date()),end=str(f.index[-1].date()),n=len(f),
            close_return_pct=100*(float(f.close.iloc[-1]/f.close.iloc[0])-1),
            mu21_negative=int(f.mu21.lt(0).sum()),mu5_negative=int(f.mu5.lt(0).sum()),
            mu21_bp_min=float(f.mu21_bp.min()),mu21_bp_max=float(f.mu21_bp.max()),
            mu21_bp_median=float(f.mu21_bp.median()),mu21_abs_bp_median=float(f.mu21_bp.abs().median()),
            mu21_sign_changes=int(f.mu21_direction.diff().abs().eq(2).sum()),
            S21_changes=int(f.confirmed_21.sum()),S63_changes=int(f.confirmed_63.sum()),
            acute_down_days=int(f.acute_down.sum()),b3_cold=int(f.b3_grade.eq(-1).sum()),b3_hot=int(f.b3_grade.eq(2).sum()),
            e0_valid=int(f.e0_target.eq(1).sum()),
            both_up=int(both.sum()),both_up_mu21_negative=int((both&f.mu21.lt(0)).sum()),
            both_up_mu21_negative_longest=max([x['observations'] for x in negative],default=0),
            both_up_near_zero=int((both&f.mu21_bp.abs().lt(1)).sum()),
            phases=f.phase.value_counts().to_dict())
        windows.append(row)
    selections={'AU0':['2025-05-15','2025-06-30','2025-07-31','2025-08-29','2025-09-04','2025-09-16','2026-01-29','2026-01-30','2026-02-02','2026-03-10','2026-03-20','2026-03-23','2026-04-13','2026-05-15','2026-06-05','2026-06-11'],
        '512480':['2026-04-01','2026-04-10','2026-07-02','2026-08-10','2026-08-13','2026-09-10'],
        '001309.SZ':['2025-12-18','2025-12-19','2026-03-25','2026-07-15'],
        '688981.SH':['2024-09-24','2024-09-27','2024-09-30','2024-10-08','2024-10-23','2026-08-20','2026-09-30']}
    fields=['close','r_bp','mu5_bp','mu21_bp','S21','S63','phase','confirmed_21','confirmed_63','acute_down','q','qeff','b3_grade','e0_target']
    for sid,dates in selections.items():
        f=frames[sid]
        for date in dates:
            if date in f.index:selected.append(dict(asset=sid,date=date,**f.loc[date,fields].to_dict()))
    for sid,f in frames.items():
        j=read(ROOT/'results'/(sid+'-events.json'));up=[e for e in j if e['kind']=='structure_confirmed' and e['direction']==1]
        wrong=[e for e in up if not(e['r']>0 and e['receipt']['new_frontier']==1 and e['receipt']['frontier_increment']>0)]
        receipts.append(dict(asset=sid,all_up_confirmations=len(up),nonpositive_or_no_frontier=len(wrong)))
    write(out/'window-statistics.json',windows);pd.DataFrame(windows).drop(columns='phases').to_csv(out/'window-statistics.csv',index=False,encoding='utf-8-sig')
    write(out/'structure-pace-conflicts.json',contradictions);write(out/'selected-facts.json',selected)
    pd.DataFrame(selected).to_csv(out/'selected-facts.csv',index=False,encoding='utf-8-sig')
    write(out/'up-confirmation-audit.json',receipts)
    # These are prior identified diagnostic spans, not new fitting windows.
    spans=[]
    for sid,a,b in [('AU0','2026-04-13','2026-06-05'),('AU0','2026-03-10','2026-03-20'),('512480','2026-08-13','2026-09-10')]:
        f=frames[sid].loc[a:b];spans.append(dict(asset=sid,start=a,end=b,observations=len(f),
            return_pct=100*(float(f.close.iloc[-1]/f.close.iloc[0])-1),mu21_negative=int(f.mu21.lt(0).sum()),
            mu5_negative=int(f.mu5.lt(0).sum()),phases=f.phase.value_counts().to_dict(),
            mu21_min_bp=float(f.mu21_bp.min()),mu21_max_bp=float(f.mu21_bp.max()),
            both_up_negative=int((f.S21.eq(1)&f.S63.eq(1)&f.mu21.lt(0)).sum())))
    write(out/'prior-failure-spans.json',spans)
    print({'windows':len(windows),'selected':len(selected),'up_confirmations':sum(r['all_up_confirmations'] for r in receipts),'violations':sum(r['nonpositive_or_no_frontier'] for r in receipts),'prior_failure_spans':spans})

if __name__=='__main__':main()
