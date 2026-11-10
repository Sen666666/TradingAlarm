import argparse,hashlib,json
from pathlib import Path
import numpy as np,pandas as pd

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def features(c):
    y=np.log(c.to_numpy());x=np.arange(len(y));b,a=np.polyfit(x,y,1);res=y-(a+b*x);den=((y-y.mean())**2).sum();r=y[-1]-y[0]
    z=pd.Series(y).rolling(5).mean().dropna();sign=np.sign(z-z.median()).replace(0,np.nan).ffill().dropna()
    return dict(n=len(y),log_return=r,max_drawdown=float((c/c.cummax()-1).min()),r2=1-float((res**2).sum()/den) if den>0 else 0.,displacement=b*(len(y)-1),range=y.max()-y.min(),max5ratio=max(0,float(pd.Series(y).diff(5).max()))/r if r>0 else None,crossings=int((sign.diff().abs()==2).sum()),lower_count=int((y<=y.min()+.25*(y.max()-y.min())).sum()),upper_count=int((y>=y.min()+.75*(y.max()-y.min())).sum()))
def main(root,out):
    assert not (out/'census.csv').exists();assert sha(out/'protocol.json')==json.loads((out/'freeze.json').read_text())['sha256'];inputs={};records=[];frames={}
    def track(p):inputs[str(p)]=sha(p)
    def add(s,market,c,v,path):
        for year in ['2024','2025']:
            d=c.loc[year+'-01-01':year+'-12-31'];vv=v.reindex(d.index);d=d.loc[d.gt(0)&vv.gt(0)&np.isfinite(d)&np.isfinite(vv)]
            if len(d)<200:continue
            m=features(d);slow=.15<=m['log_return']<=.50 and m['max_drawdown']>=-.15 and m['r2']>=.65 and m['max5ratio']<=.35
            rang=abs(m['log_return'])<=.05 and .10<=m['range']<=.35 and abs(m['displacement'])<=.06 and m['crossings']>=6 and min(m['lower_count'],m['upper_count'])>=10
            records.append(dict(symbol=s,market=market,year=year,source=str(path),slow=slow,range_case=rang,**m))
    old=root/'results/pv-competing-state-20261020'
    for p in sorted(old.glob('*-signals.csv')):
        track(p);z=pd.read_csv(p,index_col='date',parse_dates=True);s=p.name.replace('-signals.csv','');add(s,'HK' if s.startswith('HK') else 'ETF_A',z.close,z.volume,p)
    base=root/'data/ths-refresh-20261018';cohort=base/'validated-input-balanced-second500.json';track(cohort)
    for rec in json.loads(cohort.read_text())['records']:
        p=base/f"{rec['ths_symbol']}-signal.parquet";track(p);assert inputs[str(p)]==rec['signal_sha256'];z=pd.read_parquet(p);add(rec['symbol'],'A_stock',z.signal_close,z.volume,p)
    d=pd.DataFrame(records).sort_values(['year','symbol']);d.to_csv(out/'census.csv',index=False);chosen=[];used=set()
    for role,market,col in [('S3','A_stock','slow'),('C3','A_stock','range_case'),('C4','HK','range_case')]:
        eligible=d.loc[d.market.eq(market)&d[col]&~d.symbol.isin(used)]
        if len(eligible):
            r=eligible.iloc[0].to_dict();r['id']=role;chosen.append(r);used.add(r['symbol'])
        else:chosen.append(dict(id=role,missing=True))
    (out/'selection.json').write_text(json.dumps(chosen,ensure_ascii=False,indent=2)+'\n');(out/'selection-manifest.json').write_text(json.dumps({'code':{str(Path(__file__).resolve()):sha(Path(__file__))},'inputs':inputs,'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},ensure_ascii=False,indent=2)+'\n')
    print(d.groupby('market')[['slow','range_case']].sum().to_string());print(json.dumps(chosen,ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.root,a.out)
