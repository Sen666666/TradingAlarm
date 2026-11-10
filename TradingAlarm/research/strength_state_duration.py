"""Same-period causal state diagnostics; no trading-rule changes."""
import hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from geometric_strength import geometric_frame,strength_exposure
from adaptive_geometric_strength import adaptive_frame
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from strategy_signals import period_metrics
ROOT=Path(__file__).resolve().parent

def state_episodes(exposure,start='2024-01-01',end='2026-10-16'):
    s=exposure.loc[:end];v=s.to_numpy();rows=[];active=None;left=False
    for i,(date,value) in enumerate(s.items()):
        if date<pd.Timestamp(start):continue
        previous=v[i-1] if i else 0
        if active is None and value and (not previous or not rows and left is False):
            active=i;left=bool(previous)
        if active is not None and not value:
            rows.append({'entry':str(s.index[active].date()),'exit':str(date.date()),'sessions':i-active,'left_censored':left,'right_censored':False,'exit_pos':i});active=None;left=False
    if active is not None:rows.append({'entry':str(s.index[active].date()),'exit':None,'sessions':len(s)-active,'left_censored':left,'right_censored':True,'exit_pos':None})
    for r in rows:
        i=r['exit_pos']
        r['reentry5']=bool(np.any(v[i+1:i+6]>0)) if i is not None and i+5<len(v) else None
    return rows

def inventory():
    data=ROOT/'data/ths-refresh-20261018';manifest=json.loads((data/'validated-input-balanced-second500.json').read_text())
    for r in manifest['records']:
        p=data/f"{r['ths_symbol']}-signal.parquet";assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256']
        f=pd.read_parquet(p);f=f[f.observed_bar&f.volume.gt(0)]
        yield 'a485',r['symbol'],f.signal_close,f.close,f.volume
    for group,assets in [('hk7',load_assets()[0]),('etf17',load_extended()[0])]:
        for name,a in assets.items():
            raw=a['raw'];ix=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(a['signal'].index)
            yield group,name,a['signal'].close.reindex(ix),raw.close.reindex(ix),raw.volume.reindex(ix)

def main():
    out=ROOT/'results/strength-state-duration';rows=[];episodes=[]
    for n,(group,name,close,raw,volume) in enumerate(inventory()):
        for model in ('linear','adaptive'):
            f=adaptive_frame(close,raw,volume) if model=='adaptive' else geometric_frame(close,raw,volume,degree=1)
            exposure=strength_exposure(f.strength);window=f.loc['2024-01-01':'2026-10-16'];e=state_episodes(exposure);episodes.extend(dict(group=group,symbol=name,model=model,**r) for r in e)
            rows.append({'group':group,'symbol':name,'model':model,'sessions':len(window),'occupied_fraction':float(exposure.reindex(window.index).mean()),'strength_jump2_fraction':float(window.strength.diff().abs().ge(2).mean()),'linear_weight_mean':float(window.linear_weight.mean()) if model=='adaptive' else 1.})
        if (n+1)%100==0:print('state symbols',n+1,flush=True)
    t=pd.DataFrame(rows);e=pd.DataFrame(episodes);t.to_parquet(out/'symbol-states.parquet',index=False);e.to_parquet(out/'episodes.parquet',index=False);reports=[]
    for (group,model),g in t.groupby(['group','model']):
        a=e[e.group.eq(group)&e.model.eq(model)];complete=a[~a.left_censored & ~a.right_censored];reentry=a[~a.right_censored].dropna(subset=['reentry5'])
        reports.append({'group':group,'model':model,'symbols':len(g),'complete_states':len(complete),'left_censored':int(a.left_censored.sum()),'right_censored':int(a.right_censored.sum()),'holding_sessions_median':float(complete.sessions.median()),'holding_sessions_p90':float(complete.sessions.quantile(.9)),'states_5_or_less_fraction':float(complete.sessions.le(5).mean()),'reentry5_fraction':float(reentry.reentry5.mean()),'reentry5_denominator':len(reentry),'mean_symbol_occupied_fraction':float(g.occupied_fraction.mean()),'mean_symbol_linear_weight':float(g.linear_weight_mean.mean())})
    accounts=[]
    path=ROOT/'results/trend-strength-ah-transfer'
    for r in json.loads((path/'results.json').read_text()):
        if r['scenario']=='base' and r['strategy'] in ('linear_geometry_price_volume','adaptive_geometry_price_volume'):
            p=pd.read_parquet(path/f"{r['case']}-path.parquet");accounts.append({'group':r['group'],'model':r['strategy'],'same_calendar_2024_carry_in':period_metrics(p,'2024-01-01','2026-10-16')})
    (out/'report.json').write_text(json.dumps({'reports':reports,'accounts':accounts,'limits':'Latent desired exposure, not executed holdings. Same2024-2026observed-session window with prior warmup; within-market holidays/suspensions differ. Complete durations exclude left/right censored states; reentry labels omit incomplete5barfuture. Pooled episode distributions andequal-name occupancy are descriptive, not independent samples. Account2024 starts with carried positions, unlike initialcashA runs.'},indent=2)+'\n')
    print(json.dumps(reports,indent=2));print(accounts)
if __name__=='__main__':main()
