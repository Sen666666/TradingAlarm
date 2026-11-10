import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from stock_actions import parse_ths_rights
from run_pv_segment_round import volume,write

def main(out,root):
    p=out/'a485';pairs=pd.read_csv(p/'pairs.csv');rng=np.random.default_rng(20261020);names=sorted(pairs.symbol.unique());draws=[]
    for _ in range(2000):
        sample=pd.concat([pairs[pairs.symbol.eq(s)] for s in rng.choice(names,len(names),replace=True)]);draws.append(float(sample.forward21_difference.mean()))
    dated=pairs.assign(year=pd.to_datetime(pairs.sustained_date).dt.year);yearstats=dated.groupby('year').agg(n=('symbol','size'),mean21=('forward21_difference','mean'),mean63=('forward63_difference','mean')).reset_index();yearstats.to_csv(p/'year-stability.csv',index=False)
    write(p/'uncertainty.json',dict(status='post-result descriptive sensitivity; asset bootstrap does not remove market/date dependence',pairs=len(pairs),assets=len(names),mean21=float(pairs.forward21_difference.mean()),median21=float(pairs.forward21_difference.median()),positive_fraction=float(pairs.forward21_difference.gt(0).mean()),asset_bootstrap95=[float(x) for x in np.quantile(draws,[.025,.975])],without_largest_negative=float(pairs.drop(pairs.forward21_difference.idxmin()).forward21_difference.mean()),without_largest_positive=float(pairs.drop(pairs.forward21_difference.idxmax()).forward21_difference.mean()),opportunity30_difference=float(pairs.opportunity30_difference.mean())))
    selected=[('largest_negative',pairs.loc[pairs.forward21_difference.idxmin()]),('largest_positive',pairs.loc[pairs.forward21_difference.idxmax()]),('closest_to_zero',pairs.loc[pairs.forward21_difference.abs().idxmin()])];cohort=json.loads((root/'data/ths-refresh-20261018/validated-input-balanced-second500.json').read_text());records={x['symbol']:x for x in cohort['records']};review=[]
    for label,pair in selected:
        rec=records[pair.symbol];base=root/'data/ths-refresh-20261018';z=pd.read_parquet(base/f"{rec['ths_symbol']}-signal.parquet");raw=z[['open','high','low','close','volume']].copy();splits=[]
        for row in json.loads((base/f"rights/{rec['ths_symbol']}.json").read_text())['records']:
            dt=pd.to_datetime(str(row['1']),format='%Y%m%d')
            if dt<=z.index.min() or dt>z.index.max():continue
            e=parse_ths_rights(rec['ths_symbol'],row);ratio=1+e['bonus_shares_per_old_share']+e['capitalization_shares_per_old_share']
            if ratio!=1:splits.append(dict(date=e['effective_date'],ratio=ratio))
        v=volume(dict(raw=raw,splits=splits));valid=raw.volume.gt(0)&raw[['open','high','low','close']].gt(0).all(axis=1);c=z.signal_close.loc[valid];v=v.loc[valid];fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True)
        for name in ['sustained','isolated']:
            day=pd.Timestamp(pair[name+'_date']);i=c.index.get_loc(day);start=max(0,i-20);end=min(len(c),i+64);x=np.arange(start-i,end-i);baseline=v.iloc[i-67:i-4].median();ax[0].plot(x,c.iloc[start:end].to_numpy()/c.iloc[i],label=name+' '+str(day.date()));ax[1].plot(x,v.iloc[start:end].to_numpy()/baseline,label=name)
        ax[0].set_title(pair.symbol+' '+label+' (post-result selected for review)');ax[0].set_ylabel('Price / event close');ax[1].set_ylabel('Volume / pre-event baseline');ax[1].set_xlabel('Observed sessions from event')
        for a in ax:a.axvline(0,color='black',ls=':');a.axvline(21,color='gray',ls=':');a.legend()
        fig.tight_layout();fig.savefig(p/f'{label}-review.png',dpi=120);plt.close(fig);review.append(dict(selection=label,**pair.to_dict()))
    write(p/'reviewed-pairs.json',review);print((p/'uncertainty.json').read_text());print(yearstats.to_string(index=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--research-root',type=Path,required=True);a=p.parse_args();main(a.output,a.research_root)
