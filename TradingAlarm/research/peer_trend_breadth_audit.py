"""Leave-one-out trend breadth in causal price association groups, not industry backtest."""
import json,hashlib
from pathlib import Path
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parent

def peer_breadth(frame):
    f=frame.copy();f['positive']=f.strength.gt(5).astype(int)
    grouped=f.groupby(['date','group'])
    count=grouped.strength.transform('size')-1
    positive=grouped.positive.transform('sum')-f.positive
    f['peers']=count;f['breadth']=positive/count.replace(0,np.nan)
    return f

def main():
    out=ROOT/'results/peer-trend-breadth-audit';out.mkdir(exist_ok=True)
    source=ROOT/'results/broad-exit-disagreement/all-observed-signals.parquet';mapping=ROOT/'results/sector-stock-daily-mapping/assignments.parquet';labeled=ROOT/'results/strength-calibration-audit/labeled-scores.parquet'
    scores=pd.read_parquet(source)[['date','symbol','strength']];scores['date']=pd.to_datetime(scores.date);maps=pd.read_parquet(mapping);maps['date']=pd.to_datetime(maps.date);labels=pd.read_parquet(labeled)
    reports=[];diagnostics=[];allfeatures=[]
    for name in ['proxy','relative_proxy']:
        f=scores.merge(maps[['date','symbol',name]],on=['date','symbol'],validate='one_to_one').rename(columns={name:'group'}).dropna()
        f=peer_breadth(f);f['mapping']=name
        diagnostics.append(dict(mapping=name,mapped_rows=len(f),eligible_rows=int(f.peers.ge(10).sum()),eligible_symbols=int(f.loc[f.peers.ge(10),'symbol'].nunique())))
        allfeatures.append(f)
        f=f.loc[f.peers.ge(10)].copy();f['breadth_state']=np.where(f.breadth>.5,'majority_up',np.where(f.breadth<.5,'minority_up','tie'))
        joined=labels.merge(f[['date','symbol','breadth','breadth_state','peers']],on=['date','symbol'],validate='many_to_one')
        daily=joined.groupby(['year','date','horizon','bin','breadth_state']).agg(n=('symbol','size'),mean_return=('forward_return','mean'),tail30=('tail30','mean')).reset_index()
        daily.to_parquet(out/f'{name}-daily.parquet',index=False)
        valid=daily.loc[daily.n.ge(5)&daily.breadth_state.ne('tie')]
        pivot=valid.pivot(index=['year','date','horizon','bin'],columns='breadth_state',values=['mean_return','tail30']).dropna()
        diff=pd.DataFrame({k:pivot[(k,'majority_up')]-pivot[(k,'minority_up')] for k in ['mean_return','tail30']}).reset_index()
        diff['mapping']=name;diff.to_parquet(out/f'{name}-paired.parquet',index=False)
        s=diff.groupby(['mapping','year','horizon','bin']).agg(dates=('date','size'),majority_minus_minority_return=('mean_return','mean'),majority_minus_minority_tail30=('tail30','mean')).reset_index();reports.append(s)
    pd.concat(allfeatures,ignore_index=True).to_parquet(out/'features.parquet',index=False)
    result=pd.concat(reports,ignore_index=True);result.to_csv(out/'summary.csv',index=False)
    (out/'validation.json').write_text(json.dumps(dict(coverage=diagnostics,input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,mapping,labeled]},definition='Peerscurrentstrength>5; excludetarget; at least10peers; majority>50%vsminority<50%,tiesseparate; same-date2pointtargetstrengthbins at least5stocksperstate.',limits=['Associationgroupsfrompast126-daycorrelationwith9sectorETFs are not point-in-time industrymembership. Raw/marketrelativeassignmentbothreported.','Peerbreadthusesallavailablecurrent observations before joiningforwardlabels; no outcome-conditionedpeer pool.','Differentgroupscomprisecomparisonarms; datedmatchingdoesnotremoveindustry/universe compositionconfounding.','Forwardcloseoutcomesnottradingreturns; overlappinghorizons/correlatednames/no significance claims.','Selected485A-share2024-2026development; no HKsectorvalidation oraccountperformance.']),indent=2))
    print(result.loc[result.horizon.eq(21)&result.bin.isin(['6-8','8-10'])].to_string(index=False))
if __name__=='__main__':main()
