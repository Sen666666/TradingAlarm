"""Local2024 availability, immutable old overlap and own parent state only."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import csv,gzip,hashlib,importlib.util,io,json,sys
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;P=O.parent;I=O/'inputs'
R=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research')
IX=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
CAL=P.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/daily.jsonl.gz'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def read(p):return json.loads(Path(p).read_text())
def main():
    assert not(O/'INPUT_AVAILABILITY.json').exists(),'extension already prepared'
    oldfreeze=read(P/'INPUT_FREEZE.json')
    for f,h in dict(oldfreeze['sources'],**oldfreeze['inputs']).items():assert sha(f)==h,('old source/input drift',f)
    for f,h in read(P/'RUN_FREEZE.json')['sources'].items():assert sha(f)==h
    audit=P.parent/'independent_review/BENCHMARK_2022_2023_INDEPENDENT_AUDIT.json'
    assert read(audit)['status'].startswith('PASS') and sha(audit)==read(P/'INDEPENDENT_REVIEW_STATUS.json')['audit_sha256']
    with gzip.open(CAL,'rt') as f:records=[json.loads(x) for x in f]
    days=sorted({str(x.get('day') or x.get('at'))[:10] for x in records});days=[d for d in days if '2024-01-02'<=d<='2024-12-31']
    assert len(days)==242 and days[0]=='2024-01-02' and days[-1]=='2024-12-31'
    calendar=pd.DatetimeIndex(days);calendar.name='date'
    sys.path.insert(0,str(R));import portfolio_data as C
    assets,_=C.load_assets({'USHJ510300':('broad','equity')});a=assets['USHJ510300']
    raw=a['raw'].loc[:'2024-12-31'].copy();signal=a['signal'].loc[:'2024-12-31'].copy()
    assert calendar.difference(raw.index).empty
    full=raw.copy();full['volume_shares']=raw.volume*100;full['signal_close']=signal.close
    full['ma63']=signal.close.rolling(63,min_periods=63).mean();full['on']=full.signal_close.gt(full.ma63)&full.ma63.notna()
    full['adv20_prior_shares']=full.volume_shares.shift().rolling(20,min_periods=20).mean()
    old=pd.read_csv(P/'inputs/510300_history.csv',index_col='date',parse_dates=True)
    errors={c:float((old[c]-full.loc[old.index,c]).abs().max()) for c in old.columns if c!='on'}
    assert all(e<1e-9 for e in errors.values()) and old['on'].equals(full.loc[old.index,'on'])
    oldbytes=(P/'inputs/510300_history.csv').read_bytes();assert oldbytes.endswith(b'\n')
    tail=full.loc[calendar].to_csv(header=False,float_format='%.15g').encode()
    (I/'510300_history.csv').write_bytes(oldbytes+tail)
    assert (I/'510300_history.csv').read_bytes()[:len(oldbytes)]==oldbytes
    full.loc[calendar].to_csv(I/'510300_2024_daily.csv',float_format='%.15g')
    pd.DataFrame({'date':days}).to_csv(I/'calendar2024.csv',index=False)
    oldactions=read(P/'inputs/510300_actions.json');newdiv=[dict(e,source='local EastmoneyF10',entitlement='previous-close inventory',known_for_signal='ex-date close only') for e in a['dividends'] if '2024-01-01'<=e['ex_date']<='2024-12-31']
    newsplits=[e for e in a['splits'] if e['date']<='2024-12-31'];assert not newsplits
    actions=dict(oldactions);actions['dividends']=oldactions['dividends']+newdiv
    assert actions['dividends'][:len(oldactions['dividends'])]==oldactions['dividends']
    save(I/'510300_actions.json',actions)
    index=pd.read_csv(IX/'canonical/USZI399300.csv',index_col='date',parse_dates=True)
    assert calendar.difference(index.index).empty
    index.loc[calendar,['open','high','low','close','volume','amount']].to_csv(I/'HS300_2024_daily.csv',float_format='%.12g')
    states={};parentfiles=[]
    for name in ('BUY_HOLD','MA63_90'):
        terminal=read(P/'logs'/f'{name}_terminal.json');daily=list(csv.DictReader((P/'daily'/f'{name}.csv').open()));last=daily[-1]
        signals=read(P/'logs'/f'{name}_signals.json');orders=read(P/'logs'/f'{name}_orders.json')
        assert last['date']=='2023-12-29' and D(terminal['cash'])==D(last['cash']) and terminal['shares']==int(last['shares'])
        assert sum(D(x['amount']) for x in terminal['receivables'])==D(last['dividend_receivable'])
        assert sum(x['quantity'] for x in terminal['lots'])==terminal['shares']
        assert D(last['NAV'])==D(terminal['cash'])+D(terminal['shares'])*D(last['raw_close'])+D(last['dividend_receivable'])
        value=dict(terminal,previous_on=signals[-1]['on'],orderid=max(int(x['id'].rsplit('-',1)[1]) for x in orders if 'id'in x),
            NAV=last['NAV'],global_peak=str(max([D(1000000)]+[D(x['NAV']) for x in daily])),cumulative_fee=last['cumulative_fee'],cursor=last['date'],origin='2022-01-04')
        states[name]=value
        parentfiles += [P/'daily'/f'{name}.csv']+[P/'logs'/f'{name}_{kind}.json' for kind in ('terminal','signals','orders','fills')]
    save(O/'PARENT_STATE.json',states)
    sources=[Path(__file__),O/'CONTINUATION_CARD.txt',P/'run_benchmarks.py',P/'RUN_FREEZE.json',P/'INPUT_FREEZE.json',P/'INDEPENDENT_REVIEW_STATUS.json',P/'PERIODS.csv',audit,CAL,R/'portfolio_data.py',R/'portfolio-protocol.json',R/'data/tencent-sh510300-raw.json',R/'data/eastmoney-fhsp-510300.html',IX/'canonical/USZI399300.csv',IX/'checkpoints/USZI399300.json']+parentfiles
    save(O/'INPUT_AVAILABILITY.json',dict(at_UTC=datetime.now(timezone.utc).isoformat(),before_new_account_events=True,available=True,calendar=['2024-01-02','2024-12-31'],days=242,
        raw_ETF_and_HS300_overlap_all_calendar=True,dividends2024=newdiv,splits2024=newsplits,old_serialized_history_prefix_bytes_exact=True,
        old_numeric_recompute_errors=errors,old_MA_on_all_exact=True,own_parent_states=str(O/'PARENT_STATE.json'),
        no_downloads=True,old484financial_days_not_recomputed=True,execution_verified=False,
        sources={str(p):sha(p) for p in sources},inputs={str(p):sha(p) for p in I.glob('*')},parent_state_sha256=sha(O/'PARENT_STATE.json')))
    print('2024_INPUT_AND_PARENT_READY',sha(O/'INPUT_AVAILABILITY.json'),'days',len(days),flush=True)
if __name__=='__main__':main()
