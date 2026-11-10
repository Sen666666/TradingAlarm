import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
from trend_drift_break import drift_frame,exposure
from run_competing_state import draw,assets,volume,manifest,write,run,CampaignClaims,cash_check,claims_check,audit_episodes

def trajectories(out):
    assert not (out/'validation.json').exists();ix=pd.bdate_range('2020-01-01',periods=230);warm=.001*np.sin(np.arange(100)*2*np.pi/10);common=np.r_[warm,np.arange(40)*.002,np.linspace(.078,.048,10)]
    paths={'drift':np.r_[warm,np.arange(130)*.002],'range':np.r_[warm,.03*np.sin(np.arange(130)*2*np.pi/10)],'jump':np.r_[warm,np.full(130,.08)],'recover':np.r_[common,np.linspace(.051,.20,80)],'reverse':np.r_[common,np.linspace(.045,-.15,80)],'one_bar_shock':np.r_[warm,.08,np.zeros(129)],'steep_start':np.r_[warm,np.arange(20)*.01,.20+np.arange(110)*.001]};summaries=[];stored={}
    for name,y in paths.items():
        c=pd.Series(np.exp(y),index=ix);v=pd.Series(100.,index=ix);v.iloc[100:105]=800.;f=drift_frame(c,v);stored[name]=f.copy();pd.testing.assert_frame_equal(drift_frame(c[:150],v[:150]),f.iloc[:150]);np.testing.assert_allclose(drift_frame(c*10,v*100).strength,f.strength,rtol=1e-7,atol=1e-7,equal_nan=True);np.testing.assert_allclose(drift_frame(1/c,v).strength,-f.strength,rtol=1e-7,atol=1e-7,equal_nan=True)
        f['close']=c;f['volume']=v;f['target']=exposure(f.strength);f['price_strength']=drift_frame(c,v,joint=False).strength;f['duplicate_strength']=drift_frame(c,v,duplicate_level=True).strength;f['duplicate_target']=exposure(f.duplicate_strength);f.to_csv(out/f'synthetic-{name}.csv',index_label='date');draw(f,out/f'synthetic-{name}.png',name+' drift break');summaries.append(dict(case=name,entries=int(f.target.diff().iloc[100:].eq(1).sum()),held=int(f.target.iloc[100:].sum()),duplicate_held=int(f.duplicate_target.iloc[100:].sum()),first_target_offset=int(np.flatnonzero(f.target.iloc[100:].to_numpy())[0]) if f.target.iloc[100:].any() else None,max_score=float(f.strength.iloc[100:].max())))
    pd.testing.assert_frame_equal(stored['recover'].iloc[:150],stored['reverse'].iloc[:150]);groups,_=assets();checks=[];cases=json.loads((out/'protocol.json').read_text())['cases']
    for group,items in groups.items():
        for s,a in items.items():
            c=a['signal'].close;v=volume(a);f=drift_frame(c,v);cut=len(c)//2;pd.testing.assert_frame_equal(drift_frame(c.iloc[:cut],v.iloc[:cut]),f.iloc[:cut]);f['close']=c;f['volume']=v;f['target']=exposure(f.strength);f['price_strength']=drift_frame(c,v,joint=False).strength;f['price_target']=exposure(f.price_strength);f['duplicate_strength']=drift_frame(c,v,duplicate_level=True).strength;f['duplicate_target']=exposure(f.duplicate_strength);f.to_csv(out/f'{s}-signals.csv',index_label='date')
            for sym,start,end in cases:
                if sym==s:draw(f.loc[start:end],out/f'{s}-trajectory.png',s+' drift-break')
            checks.append(dict(symbol=s,group=group,entries=int(f.target.diff().eq(1).sum()),volume_days=int(f.target.ne(f.price_target).sum())));print('trajectory',s,flush=True)
    write(out/'validation.json',dict(synthetic=summaries,assets=checks,synthetic_prefix_checks=7,real_prefix_checks=24,scale_sign=True,common_prefix=True));manifest(out,'trajectory');print(summaries,flush=True)

def accounts(out):
    assert (out/'pre-account-review.md').exists();assert not (out/'accounts.json').exists();groups,_=assets();rows=[]
    for group,items in groups.items():
        for variant,col in [('pv','target'),('price','price_target'),('duplicate','duplicate_target')]:
            signals={s:pd.read_csv(out/f'{s}-signals.csv',index_col='date',parse_dates=True)[col] for s in items}
            for sc,cost,fx,delay in [('base',15,10,0)]+([('cost2',30,20,0),('delay1',15,10,1)] if variant=='pv' else []):
                case=f'{group}-{variant}-{sc}';recipients={s:groups['hk7'][s] for s in ['HK09618','HK03690']};claims=CampaignClaims(items,recipients) if group=='hk7' else None;m,path,orders,decisions=run(items,'2022-01-01','2026-10-16','score_change',cost,fx,delay,signals=signals,cadence='daily',security_claims=claims);check=claims_check(items,path,orders,cost,fx,recipients) if claims else cash_check(items,path,orders,cost,fx);ep,daily,shape=audit_episodes(items,path,orders,fx);assert max(check.values())<1e-6 and shape['max_daily_error']<1e-6;assert all(o['signal_date']<o['date'] for o in orders)
                path.to_parquet(out/f'{case}-path.parquet');write(out/f'{case}-orders.json',orders);write(out/f'{case}-decisions.json',decisions);write(out/f'{case}-episodes.json',ep);pd.DataFrame(daily).to_csv(out/f'{case}-daily-episodes.csv',index=False);rows.append(dict(case=case,**m,ledger=check,episodes=shape));write(out/'accounts.json',rows);print(case,m['total_return'],flush=True)
    manifest(out,'account')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['trajectories','accounts'],required=True);a=p.parse_args();assert hashlib.sha256((a.output/'protocol.json').read_bytes()).hexdigest()==json.loads((a.output/'freeze.json').read_text())['sha256'];assert hashlib.sha256(Path(__file__).with_name('trend_drift_break.py').read_bytes()).hexdigest()==json.loads((a.output/'protocol.json').read_text())['source_sha256'];globals()[a.phase](a.output)
