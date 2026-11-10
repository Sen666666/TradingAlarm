"""Offline frozen experiment; trajectories and accounts are separate invocations."""
import argparse, hashlib, json, os, sys, platform
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from trend_pv_segment import segment_frame,exposure

READS=set()
def record(event,args):
    if event=='open' and isinstance(args[0],str):
        p=Path(args[0])
        if '/research/data/' in str(p) and p.is_file():READS.add(p.resolve())
sys.addaudithook(record)
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from monthly_ah_engine import run
from campaign_claims import CampaignClaims
from campaign_completion_ledger_audit import reconcile as reconcile_cash
from monthly_claim_ledger_audit import reconcile as reconcile_claims
from trend_equal_weight import equal_scores
from trend_half_slow import quiet_half_slow
from trend_thrust_fail import thrust_state
from pv_episode_audit import audit_episodes


def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def assets():
    etf,ea=load_extended();hk,ha=load_assets()
    hk={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in hk.items()}
    return {'etf17':etf,'hk7':hk},ea+ha

def volume(a):
    ratio=pd.Series(1.,index=a['raw'].index)
    for e in a['splits']:
        if pd.Timestamp(e['date']) in ratio.index:ratio.loc[e['date']]*=e['ratio']
    return a['raw'].volume/ratio.cumprod()

def build(a,name):
    c=a['signal'].close;v=volume(a)
    if name in ['pv','price','lag_volume','penalty075','penalty125']:
        result=segment_frame(c,v,joint=name!='price',volume_lag=21 if name=='lag_volume' else 0,penalty=.75 if name=='penalty075' else 1.25 if name=='penalty125' else 1.)
        result['target']=exposure(result.strength)
    elif name=='sma63':
        result=pd.DataFrame({'strength':c/c.rolling(63).mean()-1});result['target']=(result.strength>0).astype(float)
    elif name=='half_slow':
        amount=c*v;plain=equal_scores(c,amount);op=quiet_half_slow(c,amount,plain)
        result=pd.DataFrame({'strength':op,'target':thrust_state(op.to_numpy(),plain.fast.to_numpy(),plain.slow.to_numpy(),c.to_numpy())},index=c.index)
    elif name=='buyhold':result=pd.DataFrame({'strength':1.,'target':1.},index=c.index)
    else:raise ValueError(name)
    return result


def manifest(out,phase):
    code={str(Path(m.__file__).resolve()):sha(Path(m.__file__)) for m in list(sys.modules.values()) if getattr(m,'__file__',None) and str(m.__file__).endswith('.py') and ('/research/' in str(m.__file__) or Path(m.__file__).parent==Path(__file__).parent)}
    inputs={str(p):sha(p) for p in sorted(READS)}
    write(out/f'{phase}-manifest.json',{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'platform':platform.platform(),'code':code,'inputs':inputs,'protocol_sha256':sha(out/'protocol.json')})


def trajectories(out):
    groups,audit=assets(); all_assets={**groups['etf17'],**groups['hk7']};rows=[];checks=[]
    for s,a in all_assets.items():
        v=volume(a);c=a['signal'].close
        result=build(a,'pv');price=build(a,'price');lag=build(a,'lag_volume')
        for end in [len(c)//2,len(c)-50]:
            prefix=segment_frame(c.iloc[:end],v.iloc[:end]);pd.testing.assert_frame_equal(result.drop(columns='target').iloc[:end],prefix)
        scaled=segment_frame(c*10,v*100)
        np.testing.assert_allclose(result.drop(columns='target'),scaled,atol=1e-7,rtol=1e-7,equal_nan=True)
        data=result.join(c.rename('close')).join(v.rename('volume'));data['price_strength']=price.strength;data['price_target']=price.target;data['lag_target']=lag.target
        data.to_csv(out/f'{s}-signals.csv',index_label='date')
        changes=data.target.diff().fillna(data.target).ne(0);events=data.loc[changes].copy();events['symbol']=s;rows.extend(events.reset_index().to_dict('records'))
        checks.append(dict(symbol=s,prefix_checks=2,rows=len(c),resets=int(result.reset.fillna(0).sum()),price_target_different=int(result.target.ne(price.target).sum()),lag_target_different=int(result.target.ne(lag.target).sum()),zero_volume=int(a['raw'].volume.le(0).sum()),duplicate_dates=int(c.index.duplicated().sum()),first=str(c.index.min().date()),last=str(c.index.max().date())))
    pd.DataFrame(rows).to_csv(out/'signal-events.csv',index=False)
    protocol=json.loads((out/'protocol.json').read_text())
    for s,start,end in protocol['cases']:
        d=pd.read_csv(out/f'{s}-signals.csv',index_col='date',parse_dates=True).loc[start:end]
        fig,axes=plt.subplots(4,1,figsize=(12,8),sharex=True,gridspec_kw={'height_ratios':[3,1,2,1]})
        axes[0].plot(d.index,d.close,color='black');axes[0].set_title(s+' causal trajectory (not account returns)')
        for val,color,marker in [(1,'green','^'),(-1,'red','v')]:
            event=d.target.diff().fillna(0).eq(val);axes[0].scatter(d.index[event],d.close[event],color=color,marker=marker,s=25)
        axes[1].bar(d.index,d.volume,width=1,color='grey');axes[1].set_ylabel('Volume')
        axes[2].plot(d.index,d.strength,label='PV');axes[2].plot(d.index,d.price_strength,label='Price',alpha=.6);axes[2].axhline(0,color='black',lw=.5);axes[2].axhline(1,color='green',lw=.5);axes[2].legend()
        axes[3].plot(d.index,d.segment_length,label='Segment length');axes[3].scatter(d.index[d.reset.eq(1)],d.segment_length[d.reset.eq(1)],s=8,color='red');axes[3].legend()
        fig.tight_layout();fig.savefig(out/f'{s}-trajectory.png',dpi=130);plt.close(fig)
    # Shared-prefix counterfactual is a market impossibility check, not predictive success.
    rng=np.random.default_rng(4);ix=pd.bdate_range('2020-01-01',periods=180)
    r=np.r_[rng.normal(.003,.004,100),rng.normal(-.006,.004,20),rng.normal(.003,.004,60)]
    c=pd.Series(np.exp(np.cumsum(r)),index=ix);v=pd.Series(100.,index=ix);v.iloc[100:120]=800.
    synthetic=segment_frame(c,v);plain=segment_frame(c,v*0+100)
    alternative=c.copy();alternative.iloc[120:]=c.iloc[119]*np.exp(np.cumsum(np.full(60,-.006)))
    alternate=segment_frame(alternative,v)
    pd.testing.assert_frame_equal(synthetic.iloc[:120],alternate.iloc[:120])
    synthetic.join(plain.strength.rename('constant_volume_strength')).join(c.rename('close')).join(v.rename('volume')).to_csv(out/'synthetic.csv')
    write(out/'trajectory-validation.json',{'assets':checks,'prefix_checks':48,'scale_invariance':True,'synthetic_common_prefix':True,'synthetic_volume_changes':int((synthetic.strength-plain.strength).abs().gt(1e-10).sum()),'data_audit':audit,'accounts_not_run_yet':True})
    manifest(out,'trajectory');print('Trajectories ready',flush=True)


def accounts(out):
    assert (out/'trajectory-review.md').exists(),'Review actual trajectories before accounts'
    groups,_=assets();results=[]
    for group,items in groups.items():
        for name in ['pv','price','lag_volume','sma63','half_slow','buyhold','penalty075','penalty125']:
            signals={s:build(a,name).target for s,a in items.items()}
            scenarios=[('base',15,10,0)]+([('cost2',30,20,0),('delay1',15,10,1)] if name in ['pv','price'] else [])
            for scenario,cost,fx,delay in scenarios:
                case=f'{group}-{name}-{scenario}';assert not (out/f'{case}-path.parquet').exists(),'Never overwrite a completed case'
                claims=CampaignClaims(items,{s:items[s] for s in ('HK09618','HK03690')}) if group=='hk7' else None
                metrics,path,orders,decisions=run(items,'2022-01-01','2026-10-16','score_change',cost,fx,delay,security_claims=claims,signals=signals,cadence='daily')
                check=reconcile_claims(items,path,orders,cost,fx,{s:items[s] for s in ('HK09618','HK03690')}) if claims else reconcile_cash(items,path,orders,cost,fx)
                ep,daily,summary=audit_episodes(items,path,orders,fx)
                # Execution must follow its recorded signal time; pending fills remain causal.
                assert all(pd.Timestamp(o['date'])>pd.Timestamp(o['signal_date']) for o in orders)
                path.to_parquet(out/f'{case}-path.parquet');write(out/f'{case}-orders.json',orders);write(out/f'{case}-decisions.json',decisions);write(out/f'{case}-episodes.json',ep)
                df=pd.DataFrame(daily);df.to_csv(out/f'{case}-daily-episodes.csv',index=False)
                periods={}
                for label,start,end in [('2022-23','2022-01-01','2023-12-31'),('2024-25','2024-01-01','2025-12-31'),('2026','2026-01-01','2026-10-16')]:
                    sub=path.loc[start:end];before=path.loc[path.index<pd.Timestamp(start),'nav'];base=float(before.iloc[-1]) if len(before) else 1.
                    nav=pd.concat([pd.Series([base]),sub.nav.reset_index(drop=True)],ignore_index=True)
                    contribution={k:float(df.loc[df.date.between(start,end)&df.label.eq(k),'pnl'].sum()) for k in ['tail','ordinary','open_or_claim']} if len(df) else {k:0. for k in ['tail','ordinary','open_or_claim']}
                    assert abs(sum(contribution.values())-(sub.nav.iloc[-1]-base)*1e6)<1e-6
                    periods[label]={'return':float(sub.nav.iloc[-1]/base-1),'max_drawdown':float((nav/nav.cummax()-1).min()),'pnl_bridge':contribution,'labels':'end-of-full-run hindsight labels, daily-window contribution, not whole-trade exit assignment'}
                result=dict(case=case,**metrics,ledger=check,episodes=summary,periods=periods);results.append(result);write(out/'accounts.json',results)
                print(case,round(metrics['total_return'],4),round(metrics['max_drawdown'],4),'ordinary',round(summary['ordinary']['net_pnl']),flush=True)
    manifest(out,'account')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--phase',choices=['trajectories','accounts'],required=True);args=parser.parse_args()
    freeze=json.loads((args.output/'protocol-freeze.json').read_text());assert freeze['sha256']==sha(args.output/'protocol.json')
    if args.phase=='trajectories':trajectories(args.output)
    else:accounts(args.output)
