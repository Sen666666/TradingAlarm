"""Freeze disjoint second balanced batch before any strength-model evaluation."""
import hashlib,json
from collections import Counter
import pandas as pd
import pyarrow.parquet as pq
from ths_refresh_batch import OUT,SOURCE,board
from ths_signal_adjustment import signal_frame

def main():
    checkpoint=json.loads((OUT/'batch-checkpoint.json').read_text())['records']
    original=set(json.loads((OUT/'batch-checkpoint-before-raw-correction.json').read_text())['records'])
    first=json.loads((OUT/'validated-input-balanced-all500.json').read_text())
    used={r['symbol'] for r in first['records']}|set(first['excluded'])|original
    selected=sorted(set(checkpoint)-used);assert len(selected)==500
    source=pq.read_table(SOURCE,columns=['symbol','trade_date','open','high','low','close'],filters=[('symbol','in',selected),('trade_date','>=',pd.Timestamp('2026-01-01'))]).to_pandas()
    groups={s:g.set_index('trade_date') for s,g in source.groupby('symbol')}
    accepted=[];excluded={}
    for symbol in selected:
        r=checkpoint[symbol]
        if r['status']!='signal_window_checked':excluded[symbol]=r;continue
        ths=r['ths_symbol'];hp=OUT/'ths-raw'/f'{ths}.json';ap=OUT/'rights'/f'{ths}.json';sp=OUT/f'{ths}-signal.parquet'
        history=json.loads(hp.read_text());actions=json.loads(ap.read_text());raw=pd.DataFrame(history['bars']);raw['date']=pd.to_datetime(raw.date);raw=raw.set_index('date')
        old=groups[symbol];common=old.index.intersection(raw.index);assert len(common)>=20
        maximum=float((old.loc[common,['open','high','low','close']]-raw.loc[common,['open','high','low','close']]).abs().to_numpy().max());assert maximum<=1e-6
        assert raw.index.is_unique and raw.index.is_monotonic_increasing
        assert ((raw.low>0)&(raw.low<=raw[['open','close']].min(axis=1))&(raw.high>=raw[['open','close']].max(axis=1))).all()
        saved=pd.read_parquet(sp);pd.testing.assert_frame_equal(saved,signal_frame(history,actions,start='2023-01-01'))
        assert raw.index.max()==pd.Timestamp('2026-10-16')
        accepted.append({'symbol':symbol,'ths_symbol':ths,'board':board(symbol),'signal_sha256':hashlib.sha256(sp.read_bytes()).hexdigest(),'history_sha256':hashlib.sha256(hp.read_bytes()).hexdigest(),'rights_sha256':hashlib.sha256(ap.read_bytes()).hexdigest(),'overlap':len(common),'max_raw_difference':maximum})
    result={'attempted':len(selected),'passed':len(accepted),'records':accepted,'excluded':excluded,'selection':'Second preordered balanced500 collected before adaptive model outcomes; exclude all original600 andfirstbalanced500 attempts, not just accepted names. No return filtering.','disjoint_from_prior_attempts':len(used),'boards':dict(Counter(r['board'] for r in accepted)),'limits':'Disjoint instruments, same market dates and common shocks; not temporal holdout. Collector selection depends on current local universe/data availability, so survivorship/PIT gaps remain.'}
    target=OUT/'validated-input-balanced-second500.json'
    if target.exists():assert json.loads(target.read_text())==result
    else:target.write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ('records','excluded')})
if __name__=='__main__':main()
