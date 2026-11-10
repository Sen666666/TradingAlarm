import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from trend_competing_state import competing_frame,exposure
from run_pv_segment_round import assets,volume,manifest,write
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
from monthly_ah_engine import run
from campaign_claims import CampaignClaims
from campaign_completion_ledger_audit import reconcile as cash_check
from monthly_claim_ledger_audit import reconcile as claims_check
from pv_episode_audit import audit_episodes

def draw(f,path,title):
    fig,ax=plt.subplots(4,1,figsize=(12,9),sharex=True);ax[0].plot(f.index,f.close,color='black');ax[0].plot(f.index,np.exp(f.log_level),label='filtered level',alpha=.7);ax[0].set_title(title);ax[0].legend();ax[1].bar(f.index,f.volume,color='gray');ax[2].plot(f.index,f.strength,label='PV');ax[2].plot(f.index,f.price_strength,label='Price');ax[2].axhline(1,ls=':',color='black');ax[2].axhline(0,color='black',lw=.5);ax[2].legend();ax[3].plot(f.index,f.jump_weight,label='jump');ax[3].plot(f.index,f.shock_weight,label='shock');ax[3].step(f.index,f.target,where='post',label='target',alpha=.5);ax[3].legend();fig.tight_layout();fig.savefig(path,dpi=120);plt.close(fig)

def trajectories(out):
    assert not (out/'validation.json').exists();protocol=json.loads((out/'protocol.json').read_text());ix=pd.bdate_range('2020-01-01',periods=230);warm=.001*np.sin(np.arange(100)*2*np.pi/10);common=np.r_[warm,np.arange(40)*.002,np.linspace(.078,.048,10)]
    paths={'drift':np.r_[warm,np.arange(130)*.002],'range':np.r_[warm,.03*np.sin(np.arange(130)*2*np.pi/10)],'jump':np.r_[warm,np.full(130,.08)],'recover':np.r_[common,np.linspace(.051,.20,80)],'reverse':np.r_[common,np.linspace(.045,-.15,80)]};synthetic={};rows=[]
    for name,y in paths.items():
        c=pd.Series(np.exp(y),index=ix);v=pd.Series(100.,index=ix);v.iloc[100:105]=800.;f=competing_frame(c,v);synthetic[name]=f.copy()
        pd.testing.assert_frame_equal(competing_frame(c[:150],v[:150]),f.iloc[:150]);np.testing.assert_allclose(competing_frame(c*10,v*100).strength,f.strength,atol=1e-7,rtol=1e-7,equal_nan=True);np.testing.assert_allclose(competing_frame(1/c,v).strength,-f.strength,atol=1e-7,rtol=1e-7,equal_nan=True)
        f['close']=c;f['volume']=v;f['target']=exposure(f.strength);f['price_strength']=competing_frame(c,v,joint=False).strength;f.to_csv(out/f'synthetic-{name}.csv',index_label='date');draw(f,out/f'synthetic-{name}.png',name)
        rows.append(dict(case=name,entries=int(f.target.diff().iloc[100:].eq(1).sum()),held=int(f.target.iloc[100:].sum()),final_score=float(f.strength.iloc[-1]),max_score=float(f.strength.iloc[100:].max())))
    pd.testing.assert_frame_equal(synthetic['recover'].iloc[:150],synthetic['reverse'].iloc[:150])
    groups,audit=assets();checks=[]
    for group,items in groups.items():
        for s,a in items.items():
            c=a['signal'].close;v=volume(a);f=competing_frame(c,v);cut=len(c)//2;pd.testing.assert_frame_equal(competing_frame(c.iloc[:cut],v.iloc[:cut]),f.iloc[:cut]);f['target']=exposure(f.strength);f['price_strength']=competing_frame(c,v,joint=False).strength;f['price_target']=exposure(f.price_strength);f['lag_strength']=competing_frame(c,v.shift(21)).strength;f['lag_target']=exposure(f.lag_strength);f['close']=c;f['volume']=v;f.to_csv(out/f'{s}-signals.csv',index_label='date')
            for name,start,end in protocol['cases']:
                if name==s:draw(f.loc[start:end],out/f'{s}-trajectory.png',s)
            checks.append(dict(group=group,symbol=s,entries=int(f.target.diff().eq(1).sum()),volume_price_different=int(f.target.ne(f.price_target).sum())));print('trajectory',s,flush=True)
    write(out/'validation.json',dict(real_prefix=24,synthetic_prefix=5,shared_prefix=True,scale_and_sign_checks=True,synthetic=rows,assets=checks));manifest(out,'trajectory');print(rows,flush=True)

def accounts(out):
    assert (out/'pre-account-review.md').exists();assert not (out/'accounts.json').exists();groups,_=assets();rows=[]
    for group,items in groups.items():
        for name in ['pv','price','lag','pairwise','sma63','buyhold']:
            signals={}
            for s,a in items.items():
                if name in ['pv','price','lag']:
                    f=pd.read_csv(out/f'{s}-signals.csv',index_col='date',parse_dates=True);signals[s]=f[{'pv':'target','price':'price_target','lag':'lag_target'}[name]]
                elif name=='pairwise':signals[s]=strength_exposure(pairwise_frame(a['signal'].close,volume(a),joint=True).strength)
                elif name=='sma63':c=a['signal'].close;signals[s]=(c>c.rolling(63).mean()).astype(float)
                else:signals[s]=pd.Series(1.,index=a['signal'].index)
            for sc,cost,fx,delay in [('base',15,10,0)]+([('cost2',30,20,0),('delay1',15,10,1)] if name=='pv' else []):
                case=f'{group}-{name}-{sc}';recipients={s:groups['hk7'][s] for s in ['HK09618','HK03690']};claims=CampaignClaims(items,recipients) if group=='hk7' else None
                m,path,orders,decisions=run(items,'2022-01-01','2026-10-16','score_change',cost,fx,delay,security_claims=claims,signals=signals,cadence='daily');check=claims_check(items,path,orders,cost,fx,recipients) if claims else cash_check(items,path,orders,cost,fx);ep,daily,shape=audit_episodes(items,path,orders,fx);assert max(check.values())<1e-6 and shape['max_daily_error']<1e-6;assert all(o['signal_date']<o['date'] for o in orders)
                path.to_parquet(out/f'{case}-path.parquet');write(out/f'{case}-orders.json',orders);write(out/f'{case}-decisions.json',decisions);write(out/f'{case}-episodes.json',ep);pd.DataFrame(daily).to_csv(out/f'{case}-daily-episodes.csv',index=False);rows.append(dict(case=case,**m,ledger=check,episodes=shape));write(out/'accounts.json',rows);print(case,m['total_return'],flush=True)
    manifest(out,'account')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['trajectories','accounts'],required=True);a=p.parse_args();assert hashlib.sha256((a.output/'protocol.json').read_bytes()).hexdigest()==json.loads((a.output/'freeze.json').read_text())['sha256'];assert hashlib.sha256(Path(__file__).with_name('trend_competing_state.py').read_bytes()).hexdigest()==json.loads((a.output/'protocol.json').read_text())['source_sha256'];globals()[a.phase](a.output)
