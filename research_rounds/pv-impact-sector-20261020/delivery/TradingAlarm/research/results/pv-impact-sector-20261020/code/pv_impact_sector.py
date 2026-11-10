"""Frozen mechanism diagnostic plus historical-subset implementation comparison."""
import argparse,hashlib,json,itertools,sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from run_pv_segment_round import volume
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
from monthly_ah_engine import run
from campaign_claims import CampaignClaims
from monthly_claim_ledger_audit import reconcile as reconcile_claims
from campaign_completion_ledger_audit import reconcile as reconcile_cash
from pv_episode_audit import audit_episodes


def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def period(day):return '2018-21' if day.year<2022 else '2022-23' if day.year<2024 else '2024-26'

def event_features(a):
    c=a['signal'].close;v=volume(a);f=pd.DataFrame({'close':c,'volume':v});f=f[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    y=np.log(f.close);r=y.diff();noise=r.shift(5).rolling(21).apply(lambda x:np.sqrt(np.mean(x*x)),raw=True)
    out=pd.DataFrame({'close':f.close,'severity':(y-y.shift(5))/(np.sqrt(5)*noise),'background':(y.shift(5)-y.shift(68))/(np.sqrt(63)*noise),'volatility_ratio':r.rolling(5).apply(lambda x:np.sqrt(np.mean(x*x)),raw=True)/noise,'relative_volume':f.volume.rolling(5).mean()/f.volume.shift(5).rolling(63).median()})
    out['qualifies']=out.background.gt(0)&out.severity.lt(0)&np.isfinite(out[['severity','background','volatility_ratio','relative_volume']]).all(axis=1)
    last=-100;accepted=[]
    for i in range(len(out)):
        ok=out.qualifies.iloc[i] and i-last>=21
        accepted.append(ok)
        if ok:last=i
    out['event']=accepted
    return out


def diagnostic(out):
    etf,_=load_extended();hk,_=load_assets();rows=[];prefix=0
    for group,assets in [('etf17',etf),('hk7',hk)]:
        for s,a in assets.items():
            f=event_features(a)
            cut=a['signal'].index[len(a['signal'])//2];sub=dict(a,signal=a['signal'].loc[:cut],raw=a['raw'].loc[:cut])
            # Split metadata outside prefix ignored by volume() when not indexed.
            pd.testing.assert_frame_equal(f.loc[:cut],event_features(sub));prefix+=1
            ids=np.flatnonzero(f.event.to_numpy())
            for i in ids:
                if i+21>=len(f):continue
                row=f.iloc[i];future=f.close.iloc[i+1:i+22];pastpeak=f.close.iloc[i-5:i+1].max()
                rows.append(dict(group=group,symbol=s,date=str(f.index[i].date()),label_end=str(f.index[i+21].date()),period=period(f.index[i]),severity=float(row.severity),background=float(row.background),volatility_ratio=float(row.volatility_ratio),relative_volume=float(row.relative_volume),volume_cell='high' if row.relative_volume>=1.5 else 'low' if row.relative_volume<=1 else 'middle',price_cell='mild' if row.severity>=-1.5 else 'severe',forward21=float(np.log(future.iloc[-1]/row.close)),adverse21=float(np.log(future.min()/row.close)),recovered=bool(future.max()>=pastpeak)))
    events=pd.DataFrame(rows);events.to_csv(out/'events.csv',index=False)
    cells=events.groupby(['group','period','price_cell','volume_cell']).agg(n=('forward21','size'),forward21=('forward21','mean'),adverse21=('adverse21','mean'),recovery=('recovered','mean')).reset_index();cells.to_csv(out/'cells.csv',index=False)
    pairs=[]
    for (group,s,p),f in events.groupby(['group','symbol','period']):
        low=f[f.volume_cell.eq('low')];used=set()
        for hi_id,hi in f[f.volume_cell.eq('high')].sort_values('date').iterrows():
            candidate=low.loc[~low.index.isin(used)].copy()
            if candidate.empty:continue
            ds=(candidate.severity-hi.severity).abs();db=(candidate.background-hi.background).abs();dv=(np.log(candidate.volatility_ratio)-np.log(hi.volatility_ratio)).abs()
            valid=(ds<=.5)&(db<=.75)&(dv<=.5)
            if not valid.any():continue
            distance=(ds/.5)**2+(db/.75)**2+(dv/.5)**2;lo_id=distance[valid].idxmin();lo=candidate.loc[lo_id];used.add(lo_id)
            pairs.append(dict(group=group,symbol=s,period=p,high_date=hi.date,low_date=lo.date,high_severity=hi.severity,low_severity=lo.severity,distance=float(distance.loc[lo_id]),forward_difference=float(hi.forward21-lo.forward21),recovery_difference=int(hi.recovered)-int(lo.recovered),adverse_difference=float(hi.adverse21-lo.adverse21)))
    matched=pd.DataFrame(pairs);matched.to_csv(out/'matched-pairs.csv',index=False)
    summaries=[]
    for g in ['etf17','hk7']:
        for p in ['2018-21','2022-23','2024-26']:
            part=matched[(matched.group==g)&(matched.period==p)] if len(matched) else matched
            summaries.append(dict(group=g,period=p,n=len(part),high_minus_low_forward=float(part.forward_difference.mean()) if len(part) else None,high_minus_low_recovery=float(part.recovery_difference.mean()) if len(part) else None,insufficient=len(part)<10))
    write(out/'event-summary.json',{'n_events':len(events),'prefix_checks':prefix,'matched':summaries,'new_rule_adopted':False})
    fig,ax=plt.subplots(figsize=(11,4))
    for g,offset in [('etf17',-.15),('hk7',.15)]:
        v=[s for s in summaries if s['group']==g];ax.bar(np.arange(3)+offset,[s['high_minus_low_forward'] or 0 for s in v],width=.3,label=g)
        for i,s in enumerate(v):ax.text(i+offset,(s['high_minus_low_forward'] or 0),f"n={s['n']}",ha='center',va='bottom',fontsize=8)
    ax.set_xticks(range(3),['2018-21','2022-23','2024-26']);ax.axhline(0,color='black',lw=.7);ax.set_title('Matched price conditions: high minus low volume, next21 log return');ax.legend();fig.tight_layout();fig.savefig(out/'matched-volume.png',dpi=130);plt.close(fig)
    print(json.dumps(summaries),flush=True)


def make_targets(etf,stocks,joint,kind,picks=None):
    base=pairwise_frame(etf['signal'].close,volume(etf),joint=joint);gate=strength_exposure(base.strength)
    scores={s:pairwise_frame(a['signal'].close,volume(a),joint=joint).strength for s,a in stocks.items()}
    selected=[];previous=0.;hist={s:[] for s in stocks};events=[]
    for day,level in gate.items():
        if level and not previous:
            ranking=sorted(stocks,key=lambda s:(-float(scores[s].loc[:day].iloc[-1]) if np.isfinite(scores[s].loc[:day].iloc[-1]) else float('inf'),s))
            selected=ranking[:2] if kind=='top2' else list(picks or stocks)
            events.append(dict(date=str(day.date()),selected=selected.copy(),ranking=ranking,scores={s:float(scores[s].loc[:day].iloc[-1]) for s in stocks}))
        if not level:selected=[]
        for s in stocks:hist[s].append(float(s in selected))
        previous=level
    targets={s:pd.Series(hist[s],index=gate.index).reindex(a['signal'].index,method='ffill').fillna(0.) for s,a in stocks.items()}
    return gate,targets,events,base


def accounts(out):
    etfs,_=load_extended();hk,_=load_assets();etf=etfs['HK03033'];names=['HK00700','HK03690','HK09618'];stocks={s:hk[s] for s in names};recipients={s:hk[s] for s in ['HK09618','HK03690']};results=[]
    combos=list(itertools.combinations(names,2));cases=[]
    for joint in [True,False]:
        for kind,picks in [('etf',None),('all3',None),('top2',None)]+[(f'pair{i}',list(v)) for i,v in enumerate(combos)]:
            for sc,cost,fx,delay in [('base',15,10,0)]+([('cost2',30,20,0),('delay1',15,10,1)] if joint and kind in ['etf','all3','top2'] else []):cases.append((joint,kind,picks,sc,cost,fx,delay))
    cases += [(True,'hold_etf',None,'base',15,10,0),(True,'hold_all3',None,'base',15,10,0)]
    for joint,kind,picks,sc,cost,fx,delay in cases:
        case=('volume' if joint else 'price')+'-'+kind+'-'+sc
        assert not (out/f'{case}-path.parquet').exists(),'Never overwrite account outputs'
        gate,targets,events,base=make_targets(etf,stocks,joint,'all3' if kind.startswith('hold') else kind,picks)
        if kind in ['etf','hold_etf']:
            chosen={'HK03033':etf};signals={'HK03033':gate if kind=='etf' else gate*0+1};claims=None;kwargs={}
        else:
            chosen=stocks;signals=targets if kind!='hold_all3' else {s:v*0+1 for s,v in targets.items()};claims=CampaignClaims(stocks,recipients);kwargs={}
            if kind=='top2' or kind.startswith('pair'):kwargs=dict(selection=lambda d,s,q,p:s,entry_fraction=.45)
        metrics,path,orders,decisions=run(chosen,'2022-01-01','2026-10-16','score_change',cost,fx,delay,signals=signals,cadence='daily',security_claims=claims,**kwargs)
        check=reconcile_claims(chosen,path,orders,cost,fx,recipients) if claims else reconcile_cash(chosen,path,orders,cost,fx)
        episodes,daily,shape=audit_episodes(chosen,path,orders,fx)
        assert all(o['signal_date']<o['date'] for o in orders)
        path.to_parquet(out/f'{case}-path.parquet');write(out/f'{case}-orders.json',orders);write(out/f'{case}-decisions.json',decisions);write(out/f'{case}-episodes.json',episodes);write(out/f'{case}-entry-selection.json',events);pd.DataFrame(daily).to_csv(out/f'{case}-daily-episodes.csv',index=False)
        row=dict(case=case,**metrics,ledger=check,episodes=shape,picks=picks,periods={})
        for label,start,end in [('2022-23','2022-01-01','2023-12-31'),('2024-25','2024-01-01','2025-12-31'),('2026','2026-01-01','2026-10-16')]:
            sub=path.loc[start:end];prior=path.loc[path.index<pd.Timestamp(start),'nav'];initial=prior.iloc[-1] if len(prior) else 1.;row['periods'][label]=float(sub.nav.iloc[-1]/initial-1)
        results.append(row);write(out/'accounts.json',results);print(case,round(metrics['total_return'],4),round(metrics['max_drawdown'],4),flush=True)
    gate,_,events,score=make_targets(etf,stocks,True,'all3');pd.DataFrame({'close':etf['signal'].close,'strength':score.strength,'target':gate,'volume':volume(etf)}).to_csv(out/'sector-signals.csv',index_label='date')
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
    for kind in ['etf','all3','top2','hold_etf','hold_all3']:
        p=pd.read_parquet(out/f'volume-{kind}-base-path.parquet');axes[0].plot(p.index,p.nav,label=kind);axes[1].plot(p.index,p.drawdown,label=kind)
    axes[0].legend();axes[0].set_title('Same sector gate: ETF vs fixed historical stock subset; development only');axes[1].set_ylabel('Drawdown');fig.tight_layout();fig.savefig(out/'account-comparison.png',dpi=130);plt.close(fig)
    write(out/'account-validation.json',{'cases':len(results),'expected':20,'max_ledger_error':max(max(r['ledger'].values()) for r in results),'max_episode_error':max(r['episodes']['max_daily_error'] for r in results),'historical_subset_not_full_sector':True})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['diagnostic','accounts'],required=True);a=p.parse_args();assert sha(a.output/'protocol.json')==json.loads((a.output/'freeze.json').read_text())['sha256']
    if a.phase=='diagnostic':diagnostic(a.output)
    else:accounts(a.output)
