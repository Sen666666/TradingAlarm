"""Single pre-frozen replay. Signal diagnostics only, no account engine imports."""
from pathlib import Path
import json,hashlib,datetime,sys
import numpy as np
import pandas as pd
from model import three_layer,PARAMS
HERE=Path(__file__).resolve().parent
VARIANTS={'new':{},'price':{'use_volume':False},'no_background':{'background_gate':False},'no_danger':{'danger_exit':False}}
MODELS=['original','temperature','new','price','no_background','no_danger']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x
def dump(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def describe(d,start,end):
    z=d.loc[start:end];out={'observations':len(z)}
    for m in MODELS:
        ent=z[m+'_entered'].astype(bool);ex=d[m+'_exited'].astype(bool)
        failures=censored=0
        for dt in z.index[ent]:
            k=d.index.get_loc(dt);tail=d.iloc[k+1:k+11]
            if tail[m+'_exited'].any():failures+=1
            elif len(tail)<10:censored+=1
        out.update({m+'_starts':int(ent.sum()),m+'_days':int(z[m+'_target'].sum()),
            m+'_carry':int(bool(len(z) and z[m+'_target'].iloc[0] and not ent.iloc[0])),
            m+'_ends10':failures,m+'_censored10':censored,
            m+'_down_starts':int((ent&z.background.eq('下降')).sum())})
    out['blocked_events']=int(z.blocked.sum());out['danger_exits']=int(z.exit_kind.eq('放量急跌').sum())
    out['cooling_exits']=int(z.exit_kind.eq('持续转弱').sum());out['floor_exits']=int(z.exit_kind.eq('结构破坏').sum())
    return out
def projected_intervals(d,m):
    rows=[]
    for dt in d.index[d[m+'_entered'].eq(1)]:
        k=d.index.get_loc(dt);ex=d.iloc[k+1:];ex=ex.index[ex[m+'_exited'].eq(1)]
        end=ex[0] if len(ex) else None
        rows.append(dict(model=m,start=str(dt.date()),end=str(end.date()) if end is not None else None,
            observed_bars_to_end=d.index.get_loc(end)-k if end is not None else None,
            entry_kind=d.loc[dt,'entry_kind'] if m=='new' else None,
            exit_kind=d.loc[end,'exit_kind'] if m=='new' and end is not None else None))
    return rows
def main():
    protocol=json.loads((HERE/'freeze.json').read_text())
    for p,h in protocol['files'].items():assert sha(HERE/p)==h,p
    fr=json.loads((HERE/'input-freeze.json').read_text());out=HERE/'results/v0';out.mkdir(parents=True,exist_ok=False)
    (out/'daily').mkdir();frames={};summaries=[];checks=[];intervals=[];prefix=[];constant=[];counter=[]
    for rec in fr['series']:
        sid=rec['symbol'];ip=HERE/'inputs'/(sid+'.parquet');assert sha(ip)==rec['input_sha256']
        bars=pd.read_parquet(ip)
        if sid=='AU0':
            controls={}
            for m,key in [('original','original'),('temperature','temperature_entry4')]:
                cr=rec['controls'][key];assert sha(cr['path'])==cr['sha256']
                ctrl=pd.read_parquet(cr['path']);pd.testing.assert_frame_equal(bars[['open','high','low','close','volume']],ctrl[['open','high','low','close','volume']],check_dtype=False)
                controls[m]=ctrl[['target','entered','exited','floor']].add_prefix(m+'_')
            d=bars.join(controls['original']).join(controls['temperature'])
        else:
            assert sha(rec['control_path'])==rec['control_sha256']
            ctrl=pd.read_parquet(rec['control_path']);pd.testing.assert_frame_equal(bars[['open','high','low','close','volume','segment_id']],ctrl[['open','high','low','close','volume','segment_id']],check_dtype=False)
            d=bars.join(ctrl[['baseline_target','baseline_entered','baseline_exited','baseline_floor','target','entered','exited','floor']].rename(columns={
                **{'baseline_'+k:'original_'+k for k in ['target','entered','exited','floor']},**{k:'temperature_'+k for k in ['target','entered','exited','floor']}}))
        checks.append(dict(symbol=sid,control_rows=len(d),hash_and_OHLCV_exact=True))
        mainparts=[]
        for name,kwargs in VARIANTS.items():
            parts=[]
            for seg,z in bars.groupby('segment_id',sort=False):
                s,ledger=three_layer(z,**kwargs);parts.append(s)
                assert (s.target.diff().fillna(s.target.iloc[0])==s.entered-s.exited).all()
                assert not (s.entered&s.exited).any()
                if name=='new':
                    for k in sorted(set([len(z)//3,len(z)//2,len(z)*3//4,len(z)-1])):
                        if k<84:continue
                        truncated,_=three_layer(z.iloc[:k])
                        pd.testing.assert_frame_equal(truncated,s.iloc[:k],check_exact=True)
                        prefix.append(dict(symbol=sid,segment=int(seg),cut=k,columns=len(s.columns),exact=True))
                    cv=z.copy();cv['volume']=1.;cs,_=three_layer(cv)
                    constant.append(dict(symbol=sid,segment=int(seg),target_differences=int(s.target.ne(cs.target).sum()),
                        entry_differences=int(s.entered.ne(cs.entered).sum()),exit_differences=int(s.exited.ne(cs.exited).sum())))
                    # Real active danger event: change only that day's volume; observe that same day, no future needed.
                    for dt in s.index[s.exit_kind.eq('放量急跌')][:1]:
                        k=z.index.get_loc(dt);cv=z.iloc[:k+1].copy();cv.loc[dt,'volume']=float(z.volume.iloc[k-21:k].median())
                        cf,_=three_layer(cv)
                        counter.append(dict(symbol=sid,date=str(dt.date()),close=float(z.loc[dt,'close']),daily_z=float(s.loc[dt,'daily_z']),
                            q=float(s.loc[dt,'q']),actual_exit=s.loc[dt,'exit_kind'],reduced_volume_exit=cf.iloc[-1].exit_kind,
                            actual_target=int(s.loc[dt,'target']),reduced_volume_target=int(cf.iloc[-1].target)))
                    mainparts.append(s)
            s=pd.concat(parts).reindex(d.index)
            d=d.join(s[['target','entered','exited','floor']].add_prefix(name+'_'))
        state=pd.concat(mainparts).reindex(d.index).drop(columns=['target','entered','exited','floor'])
        d=d.join(state);d.to_parquet(out/'daily'/(sid+'.parquet'));d.to_csv(out/'daily'/(sid+'.csv'),float_format='%.17g')
        frames[sid]=d
        summaries.append(dict(symbol=sid,name=rec['name'],primary=sid in fr['primary'],**describe(d,'2024-01-01','2026-10-16')))
        intervals.extend(dict(symbol=sid,**i) for m in MODELS for i in projected_intervals(d,m))
        print(sid,'done',len(d),flush=True)
    windows=[dict(**c,**describe(frames[c['symbol']],c['start'],c['end'])) for c in json.loads((HERE/'cases.json').read_text())]
    pd.DataFrame(summaries).to_csv(out/'series-summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(windows).to_csv(out/'window-summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(intervals).to_csv(out/'intervals.csv',index=False,encoding='utf-8-sig')
    joint=[]
    for sid,sector in fr['pairs'].items():
        a=frames[sid];b=frames[sector];idx=a.index.intersection(b.index);z=pd.DataFrame(index=idx)
        for m in ['original','temperature','new']:
            z[m+'_target']=(a[m+'_target'].reindex(idx).eq(1)&b[m+'_target'].reindex(idx).eq(1)).astype(int)
            z[m+'_entered']=(z[m+'_target'].eq(1)&z[m+'_target'].shift(fill_value=0).eq(0)).astype(int)
            z[m+'_exited']=(z[m+'_target'].eq(0)&z[m+'_target'].shift(fill_value=0).eq(1)).astype(int)
        z.to_csv(out/(sid+'-joint.csv'))
        w=z.loc['2024-01-01':'2026-10-16'];joint.append(dict(symbol=sid,sector=sector,**{m+'_starts':int(w[m+'_entered'].sum()) for m in ['original','temperature','new']},**{m+'_days':int(w[m+'_target'].sum()) for m in ['original','temperature','new']}))
    probes=[]
    for sid,a,b,kind in [('USHJ512480','2024-09-24','2024-10-18','fast'),('HK09618','2024-09-24','2024-10-18','fast'),('AU0','2025-09-01','2025-10-22','fast'),
        ('USHJ518880','2025-01-01','2026-01-31','long'),('AU0','2025-01-01','2026-01-31','long'),('600919.SH','2024-01-01','2025-06-30','long'),('HK00700','2025-01-01','2025-10-31','long'),('URFI881129','2025-12-01','2026-07-31','long')]:
        d=frames[sid].loc[a:b]
        for m in ['original','temperature','new']:
            active=d.index[d[m+'_target'].eq(1)]
            probes.append(dict(symbol=sid,kind=kind,start=a,end=b,model=m,first_active=str(active[0].date()) if len(active) else None,
                carry=int(bool(d[m+'_target'].iloc[0] and not d[m+'_entered'].iloc[0])),starts=int(d[m+'_entered'].sum()),
                exits=int(d[m+'_exited'].sum()),active_bars=len(active),bars=len(d)))
    dangers=[]
    for sid,d in frames.items():
        for dt in d.index[d.exit_kind.eq('放量急跌')]:
            k=d.index.get_loc(dt);a=float(d.close.iloc[k-1]);row=dict(symbol=sid,date=str(dt.date()),daily_z=float(d.loc[dt,'daily_z']),q=float(d.loc[dt,'q']))
            for h in [10,20]:
                tail=d.iloc[k+1:k+h+1];row['available_'+str(h)]=len(tail);row['reclaimed_'+str(h)]=bool(tail.close.gt(a).any()) if len(tail) else None
            dangers.append(row)
    dump(out/'checks.json',dict(controls=checks,prefixes=prefix,constant_volume=constant,single_day_volume=counter,
        model_sha256=sha(HERE/'model.py'),account_runs=0,downloads=0,mechanism_revisions=0))
    dump(out/'diagnostics.json',dict(joint=joint,probes=probes,dangers=dangers,AU0_extension=describe(frames['AU0'],'2025-01-01','2026-10-23')))
    dump(out/'complete.json',dict(series=19,windows=len(windows),primary=fr['primary'],model_sha256=sha(HERE/'model.py'),
        freeze_sha256=sha(HERE/'freeze.json'),accounts=0,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    print('COMPLETE',len(prefix),'exact prefixes',len(counter),'single-day volume counterfactuals',flush=True)
if __name__=='__main__':main()
