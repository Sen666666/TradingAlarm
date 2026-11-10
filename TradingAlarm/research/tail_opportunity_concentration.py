"""Reconciled date/group concentration of tail contributions; no hindsight selection."""
import json,hashlib
from pathlib import Path
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parent
SOURCES=[('strength-calibrated-order-transfer485','pairwise_volume'),('strength-calibrated-order-transfer485','calibrated_pair_order_volume'),('strength-uniform-transfer485','uniform_pairwise_volume'),('strength-peer-gate-transfer485','peer_raw_volume'),('strength-peer-gate-transfer485','peer_relative_volume')]

def concentration(values):
    v=np.asarray(values,float);v=v[v>0]
    if not len(v):return dict(effective_buckets=None,largest_share=None,top3_share=None)
    shares=np.sort(v/v.sum())[::-1]
    return dict(effective_buckets=float(1/np.sum(shares**2)),largest_share=float(shares[0]),top3_share=float(shares[:3].sum()))

def main():
    out=ROOT/'results/tail-opportunity-concentration';out.mkdir(exist_ok=True)
    mp=ROOT/'results/sector-stock-daily-mapping/assignments.parquet';mapping=pd.read_parquet(mp)[['date','symbol','proxy','relative_proxy']];mapping['signal_date']=pd.to_datetime(mapping.date).dt.strftime('%Y-%m-%d');mapping=mapping.drop(columns='date')
    summaries=[];dates=[];months=[];groups=[];hashes={};checks=[]
    for directory,name in SOURCES:
        root=ROOT/'results'/directory;ledgerfile=root/'tail-economics-ledger.parquet';episodefile=root/'episodes.parquet';reportfile=root/'tail-economics.json'
        for path in [ledgerfile,episodefile,reportfile]:hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        f=pd.read_parquet(ledgerfile);f=f.loc[f.strategy.eq(name)&f.allocation.eq('equal_capital')].copy()
        ep=pd.read_parquet(episodefile);ep=ep.loc[ep.strategy.eq(name)&ep.delay.eq(0)&ep.cutoff.eq('2026-10-16'),['symbol','entry_date','signal_date']]
        f=f.merge(ep,on=['symbol','entry_date'],validate='one_to_one');f=f.merge(mapping,on=['symbol','signal_date'],how='left',validate='many_to_one')
        expected=next(x for x in json.loads(reportfile.read_text())['reports'] if x['strategy']==name and x['allocation']=='equal_capital')['total_synthetic_pnl_fraction']
        f['pnl']=f.pnl_initial_sleeve/485;f['tail_pnl']=f.pnl.where(f.return_fraction.ge(.3),0);f['ordinary_pnl']=f.pnl-f.tail_pnl;f['tail_count']=f.return_fraction.ge(.3).astype(int)
        error=abs(f.pnl.sum()-expected);assert error<1e-12
        for column,container in [('signal_date',dates),('signal_month',months),('proxy',groups),('relative_proxy',groups)]:
            if column=='signal_month':f[column]=f.signal_date.str[:7]
            elif column in ['proxy','relative_proxy']:f[column]=f[column].fillna('unmapped')
            g=f.groupby(column).agg(episodes=('symbol','size'),tail_count=('tail_count','sum'),tail_pnl=('tail_pnl','sum'),ordinary_pnl=('ordinary_pnl','sum'),net_pnl=('pnl','sum')).reset_index().rename(columns={column:'bucket'})
            assert abs(g.net_pnl.sum()-expected)<1e-12;g['model']=name;g['dimension']=column;container.append(g)
            summaries.append(dict(model=name,dimension=column,tail_count=int(f.tail_count.sum()),tail_symbols=int(f.loc[f.tail_count.gt(0),'symbol'].nunique()),buckets_with_tail=int(g.tail_pnl.gt(0).sum()),tail_pnl=float(f.tail_pnl.sum()),ordinary_pnl=float(f.ordinary_pnl.sum()),**concentration(g.tail_pnl),top_buckets=g.nlargest(5,'tail_pnl').to_dict('records')))
        checks.append(dict(model=name,episodes=len(f),reconciliation_error=error))
    pd.concat(dates).to_csv(out/'date-cohorts.csv',index=False);pd.concat(months).to_csv(out/'month-cohorts.csv',index=False);pd.concat(groups).to_csv(out/'group-cohorts.csv',index=False)
    (out/'summary.json').write_text(json.dumps(summaries,indent=2));(out/'validation.json').write_text(json.dumps(dict(checks=checks,source_hashes=hashes,mapping_sha256=hashlib.sha256(mp.read_bytes()).hexdigest(),limits=['Tail threshold fixed30%individualepisode netreturn; contributionusesoriginalwithin-symbolcompounding, not equaltradeweight.','ConcentrationinverseHHI is descriptive effectivebuckets, not countofstatisticallyindependentbets orfutureopportunities.','Signaldate/monthcohortslabelentrytiming, not dateswhenprofitaccrued; holdingscanoverlap.','Priceassociationgroup atsignalclose, nottruehistoricalindustry; unmappedretained.','Hindsightlargestdates and tailclassification never usedforentryselection; selected485Asharedevelopment,synthesissleevesnotwholeaccount.']),indent=2))
    print(pd.DataFrame(summaries).loc[lambda x:x.dimension.isin(['signal_date','signal_month']),['model','dimension','tail_count','tail_symbols','buckets_with_tail','largest_share','top3_share','effective_buckets']].to_string(index=False))
if __name__=='__main__':main()
