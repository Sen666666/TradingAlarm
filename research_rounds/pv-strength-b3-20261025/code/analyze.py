"""Post-output descriptions only; no feedback into model."""
import numpy as np,pandas as pd
from common import ROOT,B2,NAMES,read,write,now

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,list):return [clean(v) for v in x]
    if isinstance(x,(np.integer,np.floating)):x=x.item()
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def main():
    target=ROOT/'analysis';target.mkdir(exist_ok=False)
    frames={sid:pd.read_parquet(ROOT/'results'/(sid+'.parquet')) for sid in NAMES}
    stats=[];viewer={}
    for w in read(B2/'figures/real-manifest.json')['plots']:
        g=frames[w['asset']].loc[w['start']:w['end']].dropna(subset=['grade'])
        stats.append(dict(id=w['id'],asset=w['asset'],name=w['name'],start=str(g.index[0].date()),end=str(g.index[-1].date()),rows=len(g),
            price_change_pct=100*(g.close.iloc[-1]/g.close.iloc[0]-1),
            counts={str(int(k)):int((g.grade==k).sum()) for k in [-2,-1,0,1,2]},
            changes=int(g.grade.ne(g.grade.shift()).iloc[1:].sum()),freeze_created=int(g.freeze_created.sum()),
            volume_changed_days=int(g.grade.ne(g.price_grade).sum()),
            b1_min=g.b1_strength.min(),b1_max=g.b1_strength.max(),
            b1_sign_changes=int(np.sign(g.b1_strength).ne(np.sign(g.b1_strength.shift())).iloc[1:].sum())))
    cols=['close','volume','e0_target','e0_floor','b1_strength','b2_pace_21','b2_signed_retention',
        'grade','phase','price_grade','normal_grade','local','background','z_21','z_63',
        'amplitude_21','amplitude_63','return_21','return_63','shock','effective_shock','activity',
        'freeze_count','freeze_created','freeze_age','freeze_anchor_price']
    selected=[]
    old=pd.read_csv(B2/'analysis/selected-facts.csv')
    sidcol='asset' if 'asset' in old else 'sid'
    for sid,name in NAMES.items():
        f=frames[sid].loc['2021-01-01':]
        dates=[str(d.date()) for d in f.index]
        viewer[sid]=dict(name=name,dates=dates,fields={k:clean(f[k].tolist()) for k in cols})
        for d in old.loc[old[sidcol].eq(sid),'date'].unique():
            if pd.Timestamp(d) in f.index:
                row=f.loc[d];selected.append(dict(asset=sid,name=name,date=d,**{k:row[k] for k in cols}))
    write(target/'window-statistics.json',clean(stats));pd.DataFrame([{**r,**r['counts']} for r in stats]).drop(columns='counts').to_csv(target/'window-statistics.csv',index=False,encoding='utf-8-sig')
    write(target/'selected-facts.json',clean(selected));pd.DataFrame(selected).to_csv(target/'selected-facts.csv',index=False,encoding='utf-8-sig')
    write(target/'viewer-data.json',viewer)
    write(target/'summary.json',dict(recorded_at=now(),windows=len(stats),selected_facts=len(selected),accounts=0))
    print({'windows':len(stats),'selected_facts':len(selected)},flush=True)
if __name__=='__main__':main()
