"""Local raw/index/action export only, no benchmark account computation."""
from pathlib import Path
from datetime import datetime,timezone
import gzip,hashlib,json,sys
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;I=O/'inputs'
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
R=ROOT/'TradingAlarm/research'
IX=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
CAL=O.parent/'pvr_pool_feasibility/continuation2023/run-2023/pair/daily.jsonl.gz'
OLD=ROOT/'research_rounds/three-layer-prototype-20261024/inputs/USHJ510300.parquet'
START='2022-01-04';END='2023-12-29'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def main():
    assert not(O/'INPUT_FREEZE.json').exists(),'inputs already frozen'
    sys.path.insert(0,str(R));import portfolio_data as P
    with gzip.open(CAL,'rt') as f:rows=[json.loads(x) for x in f]
    days=sorted({str(x.get('day') or x.get('at'))[:10] for x in rows})
    days=[d for d in days if START<=d<=END];assert len(days)==484 and days[0]==START and days[-1]==END
    cal=pd.DatetimeIndex(days);cal.name='date'
    checkpoint=json.loads((IX/'checkpoints/USZI399300.json').read_text())
    assert checkpoint['symbol']=='USZI399300' and checkpoint['status']=='complete'
    assert sha(IX/'canonical/USZI399300.csv')==checkpoint['canonical_sha256']
    idx=pd.read_csv(IX/'canonical/USZI399300.csv',parse_dates=['date']).set_index('date')
    assert idx.index.is_unique and idx.index.is_monotonic_increasing and cal.difference(idx.index).empty
    index=idx.loc[cal,['open','high','low','close','volume','amount']].copy()
    index.to_csv(I/'HS300_daily.csv',float_format='%.12g')
    assets,audit=P.load_assets({'USHJ510300':('broad','equity')});a=assets['USHJ510300'];raw=a['raw'].loc[:END].copy();signal=a['signal'].loc[:END].copy()
    assert cal.difference(raw.index).empty and raw.index.is_unique and raw.index.is_monotonic_increasing
    old=pd.read_parquet(OLD).loc[raw.index]
    rawdiff=max(float((old['raw_'+c]-raw[c]).abs().max()) for c in ['open','high','low','close','volume'])
    signaldiff=max(float((old[c]-signal[c]).abs().max()) for c in ['open','high','low','close'])
    assert rawdiff<1e-10 and signaldiff<1e-10,(rawdiff,signaldiff)
    out=raw.copy();out['volume_shares']=raw.volume*a['volume_multiplier'];out['signal_close']=signal.close
    out['ma63']=signal.close.rolling(63,min_periods=63).mean()
    out['on']=out.signal_close.gt(out.ma63)&out.ma63.notna()
    out['adv20_prior_shares']=out.volume_shares.shift().rolling(20,min_periods=20).mean()
    divs=[dict(e,source='local EastmoneyF10',entitlement='previous-close inventory',known_for_signal='ex-date close only') for e in a['dividends'] if e['ex_date']<=END]
    splits=[e for e in a['splits'] if e['date']<=END]
    assert not splits,'unexpected ETF split needs explicit treatment'
    out.to_csv(I/'510300_history.csv',float_format='%.15g')
    out.loc[cal].to_csv(I/'510300_daily.csv',float_format='%.15g')
    pd.DataFrame({'date':days}).to_csv(I/'calendar.csv',index=False)
    save(I/'510300_actions.json',dict(dividends=divs,splits=splits,unit='CNY per original share',payment_dates_explicit=True))
    sources=[IX/'canonical/USZI399300.csv',IX/'checkpoints/USZI399300.json',IX/'protocol.json',R/'data/tencent-sh510300-raw.json',R/'data/eastmoney-fhsp-510300.html',R/'portfolio_data.py',R/'portfolio_engine.py',R/'portfolio-protocol.json',R/'stock_execution.py',OLD,CAL,Path(__file__),O/'PROTOCOL.txt']
    sources+=sorted((IX/'raw/USZI399300').glob('page-*.bin'))
    inputs=list(I.glob('*'))
    freeze=dict(at_UTC=datetime.now(timezone.utc).isoformat(),before_benchmark_account_computation=True,calendar=[START,END],rows=484,
        first_possible_execution='2022-01-05 OPEN',old_9_asset_raw_max_abs_difference=rawdiff,old_9_asset_signal_max_abs_difference=signaldiff,
        index=dict(symbol='USZI399300',kind='HS300 price index; non-tradable',source_rows=len(idx),unit='index points'),
        ETF=dict(symbol='USHJ510300',raw_unit='CNY/share',wire_volume_unit='hands',volume_to_shares=100,lot=100,
            history=[str(raw.index[0].date()),END],actions=[e for e in divs if START<=e['ex_date']<=END],splits=splits,
            signal='causal reinvested total return close; no event before ex clock',execution='raw open; daily proxy, historical dated limit/halt states absent'),
        sources={str(p):sha(p) for p in sources},inputs={str(p):sha(p) for p in inputs})
    save(O/'INPUT_FREEZE.json',freeze)
    print('INPUT_FROZEN',sha(O/'INPUT_FREEZE.json'),'calendar',len(cal),'raw_history',len(raw),'old_signal_error',signaldiff,flush=True)
if __name__=='__main__':main()
