"""Post-output facts for reporting; never feeds a model or trade decision."""
import numpy as np,pandas as pd
from common import ROOT,OLD,NAMES,read,write,sha,now

def changes(s):
    z=s.dropna();return int(z.diff().ne(0).iloc[1:].sum())
def main():
    folder=ROOT/'analysis';folder.mkdir(exist_ok=False);viewer={};facts=[];windows=[]
    points={sid:set() for sid in NAMES}
    for x in read(OLD/'analysis/selected-facts.json'):points[x['asset']].add(x['date'])
    points['AU0'].update(['2025-05-21','2025-07-31','2026-03-02','2026-03-23','2026-04-01','2026-07-23'])
    points['512480'].update(['2022-05-23','2026-08-10'])
    fields=['close','volume','b1_strength','pace_5','pace_21','amplitude_5','amplitude_21',
        'direction','episode','retention','span_log_pct','episode_age','progress_age','support_advances',
        'support_price','origin_price','extreme_price','checkpoint_price','e0_target','e0_floor',
        'shock','opposition','adverse_pre_sigma','down_zone_log_pct','up_zone_log_pct',
        'oldest_down_age','oldest_up_age','down_events','up_events','activity',
        'structure_broken','old_retention_at_t','pre_direction']
    manifest=read(ROOT/'figures/real-manifest.json')['plots']
    for sid,name in NAMES.items():
        f=pd.read_parquet(ROOT/'results'/(sid+'.parquet'));old=pd.read_parquet(OLD/'results'/(sid+'.parquet'))
        f['b1_amplitude_21_log_pct']=100*21*old.drift
        f['day_return_pct']=100*f.close.pct_change(fill_method=None)
        f['return_5_pct']=100*f.close.pct_change(5,fill_method=None)
        f['return_21_pct']=100*f.close.pct_change(21,fill_method=None)
        for date in sorted(points[sid]):
            g=f.loc[:date];x=g.iloc[-1];row=dict(asset=sid,name=name,requested=date,date=str(g.index[-1].date()))
            for c in fields+['b1_amplitude_21_log_pct','day_return_pct','return_5_pct','return_21_pct']:
                row[c]=float(x[c]) if np.isfinite(x[c]) else None
            facts.append(row)
        for w in [x for x in manifest if x['asset']==sid]:
            g=f.loc[w['start']:w['end']];active=g.loc[g.direction.ne(0)&g.direction.notna()]
            windows.append(dict(asset=sid,id=w['id'],first=str(g.index[0].date()),last=str(g.index[-1].date()),observations=len(g),
                close_change_pct=float(100*(g.close.iloc[-1]/g.close.iloc[0]-1)),
                b1_min=float(g.b1_strength.min()),b1_max=float(g.b1_strength.max()),b1_sign_changes=changes(np.sign(g.b1_strength)),
                p5_sign_changes=changes(np.sign(g.pace_5)),p21_sign_changes=changes(np.sign(g.pace_21)),
                p21_mean=float(g.pace_21.mean()),p21_min=float(g.pace_21.min()),p21_max=float(g.pace_21.max()),
                direction_changes=changes(g.direction),retention_min=float(active.retention.min()),retention_max=float(active.retention.max()),
                structures_created=int(g.structure_created.fillna(0).sum()),structures_broken=int(g.structure_broken.fillna(0).sum()),
                all_statistics_descriptive_not_trades=True))
        g=f.loc['2021-01-01':,fields+['b1_amplitude_21_log_pct','day_return_pct','return_5_pct','return_21_pct']].copy()
        g.insert(0,'date',g.index.strftime('%Y-%m-%d'));viewer[sid]=__import__('json').loads(g.to_json(orient='records'))
    write(folder/'selected-facts.json',facts);pd.DataFrame(facts).to_csv(folder/'selected-facts.csv',index=False,encoding='utf-8-sig')
    write(folder/'window-statistics.json',windows);pd.DataFrame(windows).to_csv(folder/'window-statistics.csv',index=False,encoding='utf-8-sig')
    write(folder/'viewer-data.json',viewer)
    write(folder/'summary.json',dict(recorded_at=now(),point_rows=len(facts),windows=len(windows),
        output_selection_is_posthoc_descriptive=True,formula_changes_after_real_outputs=0,accounts=0,
        inputs={sid:sha(ROOT/'results'/(sid+'.parquet')) for sid in NAMES}))
    print({'facts':len(facts),'windows':len(windows),'accounts':0},flush=True)
if __name__=='__main__':main()
