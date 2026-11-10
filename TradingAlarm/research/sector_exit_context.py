"""Fixed proxy-state context for broad stock exit disagreements; no new trading rule."""
import json,hashlib
from pathlib import Path
import pandas as pd
from sector_factors import expanded_assets
from pairwise_trend_strength import pairwise_frame
from volume_units import split_consistent_volume
OUT=Path('results/sector-exit-context')

def join_context(events,mapping,states,column):
    m=mapping[['date','symbol',column]].rename(columns={column:'proxy_symbol'})
    z=events.merge(m,on=['date','symbol'],how='left',validate='one_to_one')
    return z.merge(states,on=['date','proxy_symbol'],how='left',validate='many_to_one')

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 protocol=dict(events='All3234complete485Ashare pairwisevolumezero-vs-symmetricexitdisagreements',mapping=['proxy','relative_proxy'],sector_state='Existing pairwisevolume score of matchedETF >5 means positive slope; <=5nonpositive; score calculatedat eventclose, nofuture. No new threshold tuning.',comparison='Annual state contrasts and same-day contrasts with >=2events ineachstate; report coverage andbothmappingversions',limits='Selected surviving9ETF price-association proxies,not realindustrymembership. Reuseddevelopmenthistory and21observedbarforwardlabels,not accountPNL. Same-daycomparison changes sample andweighting,not causalcontrol.')
 p=OUT/'protocol.json'
 if p.exists():assert json.loads(p.read_text())==protocol
 p.write_text(json.dumps(protocol,indent=2));ep=Path('results/broad-exit-disagreement/events.parquet');mp=Path('results/sector-stock-daily-mapping/assignments.parquet');e=pd.read_parquet(ep);e['date']=pd.to_datetime(e.date);m=pd.read_parquet(mp);assets={s:a for s,a in expanded_assets().items() if a['kind']=='equity' and a['currency']=='CNY' and a['sector']!='broad_cn'};states=[]
 for symbol,a in assets.items():
  valid=a['raw'].index[a['raw'].volume.gt(0)].intersection(a['signal'].index);v=split_consistent_volume(a['raw'].volume,a.get('splits',[])).reindex(valid);score=pairwise_frame(a['signal'].close.reindex(valid),v).strength
  states.extend(dict(date=d,proxy_symbol=symbol,score=float(value)) for d,value in score.items() if pd.notna(value))
 state=pd.DataFrame(states);state.to_parquet(OUT/'proxy-states.parquet',index=False);rows=[];daily=[];joined=[];coverage=[]
 for column in protocol['mapping']:
  z=join_context(e,m,state,column);coverage.append(dict(mapping=column,total=len(z),covered=int(z.score.notna().sum())));z=z.loc[z.score.notna()].copy();z['positive']=z.score.gt(5);z['mapping']=column;joined.append(z)
  for year,g in z.groupby('year'):
   for positive,h in g.groupby('positive'):
    rows.append(dict(mapping=column,year=int(year),positive=bool(positive),events=len(h),mean_forward21=float(h.forward21.mean()),median_forward21=float(h.forward21.median()),mean_mfe21=float(h.mfe21.mean()),mean_mae21=float(h.mae21.mean()),positive_return_fraction=float(h.forward21.gt(0).mean())))
  for date,g in z.groupby('date'):
   high=g.loc[g.positive];low=g.loc[~g.positive]
   if min(len(high),len(low))<2:continue
   daily.append(dict(mapping=column,date=str(date.date()),year=date.year,positive_count=len(high),nonpositive_count=len(low),difference=float(high.forward21.mean()-low.forward21.mean())))
 pd.concat(joined).to_parquet(OUT/'joined-events.parquet',index=False);pd.DataFrame(rows).to_csv(OUT/'annual-context.csv',index=False);d=pd.DataFrame(daily);d.to_csv(OUT/'same-date-contrasts.csv',index=False);s=d.groupby(['mapping','year']).agg(dates=('date','size'),mean_positive_minus_nonpositive=('difference','mean'),positive_fraction=('difference',lambda x:float(x.gt(0).mean())));s.to_csv(OUT/'date-balanced-summary.csv')
 (OUT/'validation.json').write_text(json.dumps(dict(coverage=coverage,input_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ep,mp]},proxy_count=len(assets)),indent=2));print(pd.DataFrame(rows).to_string(index=False));print(s.to_string())
if __name__=='__main__':main()
