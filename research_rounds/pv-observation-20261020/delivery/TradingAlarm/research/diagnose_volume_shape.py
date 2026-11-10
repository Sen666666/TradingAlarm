import argparse,json,hashlib
from pathlib import Path
import pandas as pd,numpy as np
from run_pv_segment_round import assets,volume,write,manifest

def features(a):
    r=a['raw'];c=a['signal'].close;v=volume(a);valid=r[['open','high','low','close']].gt(0).all(axis=1)&np.isfinite(r[['open','high','low','close']]).all(axis=1)&v.gt(0)&np.isfinite(v)&r.high.ge(r[['open','close']].max(axis=1)-1e-8)&r.low.le(r[['open','close']].min(axis=1)+1e-8)
    r=r.loc[valid];c=c.loc[valid];v=v.loc[valid];y=np.log(c);ret=y.diff();noise=np.sqrt(ret.shift(5).pow(2).rolling(21).mean());base=v.shift(5).rolling(63).median();high_count=pd.concat([v.shift(i)/base for i in range(5)],axis=1).ge(1.5).sum(axis=1);body=np.log(r.close/r.open);span=np.log(r.high/r.low);loc=((r.close-r.low)/(r.high-r.low)).where(r.high>r.low,.5)
    f=pd.DataFrame(dict(close=c,severity=y.diff(5)/(np.sqrt(5)*noise),background=(y.shift(5)-y.shift(68))/(np.sqrt(63)*noise),volatility=np.sqrt(ret.pow(2).rolling(5).mean())/noise,body_efficiency=body.rolling(5).sum()/span.rolling(5).sum(),close_location=loc.rolling(5).mean(),mean_volume=v.rolling(5).mean()/base,high_count=high_count),index=c.index);f['shape']=np.where(high_count>=3,'sustained',np.where(high_count==1,'isolated','other'));last=-100;accepted=[]
    for i,row in enumerate(f.itertuples()):
        ok=np.isfinite([row.severity,row.background,row.volatility,row.body_efficiency,row.close_location,row.mean_volume]).all() and row.volatility>0 and row.mean_volume>0 and row.severity>=1 and row.background>=0 and i-last>=5
        accepted.append(bool(ok))
        if ok:last=i
    f['event']=accepted;f['observation_index']=np.arange(len(f));return f

def period(day):return '2018-21' if day.year<2022 else '2022-23' if day.year<2024 else '2024-26'
def main(out):
    assert not (out/'events.csv').exists();groups,_=assets();rows=[];prefix=0
    for group,items in groups.items():
        for s,a in items.items():
            f=features(a);cut=a['raw'].index[len(a['raw'])//2];sub=dict(a,raw=a['raw'].loc[:cut],signal=a['signal'].loc[:cut]);pd.testing.assert_frame_equal(features(sub),f.loc[:cut]);prefix+=1
            for i in np.flatnonzero(f.event):
                if i+63>=len(f):continue
                x=f.iloc[i].to_dict();x.update(group=group,symbol=s,date=str(f.index[i].date()),period=period(f.index[i]),forward21=float(np.log(f.close.iloc[i+21]/f.close.iloc[i])),forward63=float(np.log(f.close.iloc[i+63]/f.close.iloc[i])),opportunity30=bool(f.close.iloc[i+1:i+64].max()/f.close.iloc[i]>=1.3));rows.append(x)
    events=pd.DataFrame(rows);events.to_csv(out/'events.csv',index=False);pairs=[];coverage=[];cols=['severity','background','volatility','body_efficiency','close_location','mean_volume'];limits=np.array([.5,1,.5,.25,.2,.35])
    for (group,s,p),f in events.groupby(['group','symbol','period']):
        lows=f[f['shape'].eq('isolated')];used=set();highs=f[f['shape'].eq('sustained')];matched=0;near_count=0;eligible_count=0
        for hi_id,h in highs.sort_values('date').iterrows():
            l=lows.loc[~lows.index.isin(used)].copy()
            if l.empty:continue
            gap=(pd.to_datetime(l.date)-pd.Timestamp(h.date)).abs().dt.days;obs=(l.observation_index-h.observation_index).abs();time=(gap<=63)&(obs>=21);near_count+=int(time.any())
            diff=np.abs(l[cols].to_numpy(float)-h[cols].to_numpy(float));diff[:,2]=np.abs(np.log(l.volatility)-np.log(h.volatility));diff[:,5]=np.abs(np.log(l.mean_volume)-np.log(h.mean_volume));good=(diff<=limits).all(axis=1)&time.to_numpy();eligible_count+=int(good.any())
            if not good.any():continue
            dist=(diff/limits)**2;distance=dist.sum(axis=1);positions=np.flatnonzero(good);j=positions[np.argmin(distance[good])];lo_id=l.index[j];lo=l.iloc[j];used.add(lo_id);matched+=1;pairs.append(dict(group=group,symbol=s,period=p,sustained_date=h.date,isolated_date=lo.date,calendar_gap=int(gap.iloc[j]),observed_gap=int(obs.iloc[j]),distance=float(distance[j]),forward21_difference=float(h.forward21-lo.forward21),forward63_difference=float(h.forward63-lo.forward63),opportunity30_difference=int(h.opportunity30)-int(lo.opportunity30)))
        coverage.append(dict(group=group,symbol=s,period=p,sustained=len(highs),isolated=len(lows),with_time_candidate=near_count,with_full_candidate=eligible_count,matched=matched))
    pd.DataFrame(coverage).to_csv(out/'coverage.csv',index=False);matched=pd.DataFrame(pairs,columns=['group','symbol','period','sustained_date','isolated_date','calendar_gap','observed_gap','distance','forward21_difference','forward63_difference','opportunity30_difference']);matched.to_csv(out/'pairs.csv',index=False)
    cells=events.groupby(['group','period','shape']).agg(n=('forward21','size'),mean21=('forward21','mean'),mean63=('forward63','mean'),opportunity30=('opportunity30','mean')).reset_index();cells.to_csv(out/'unmatched-descriptive-cells.csv',index=False)
    summaries=[]
    for group in groups:
        for p in ['2018-21','2022-23','2024-26']:
            z=matched[(matched.group==group)&(matched.period==p)];summaries.append(dict(group=group,period=p,n=len(z),mean21=float(z.forward21_difference.mean()) if len(z) else None,mean63=float(z.forward63_difference.mean()) if len(z) else None,insufficient=len(z)<30))
    write(out/'summary.json',dict(events=len(events),prefix_checks=prefix,matched_total=len(matched),groups=summaries,conclusion='Report match support before any economic inference; no new trading rule.'));manifest(out,'diagnostic');print(json.dumps(summaries,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert hashlib.sha256((a.output/'protocol.json').read_bytes()).hexdigest()==json.loads((a.output/'freeze.json').read_text())['sha256'];main(a.output)
