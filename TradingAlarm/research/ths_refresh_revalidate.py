"""Offline raw-to-raw revalidation; never mutates a live collector checkpoint."""
import json
from collections import Counter
import pandas as pd
import pyarrow.parquet as pq
from ths_refresh_batch import OUT,SOURCE
from ths_signal_adjustment import signal_frame


def main():
    checkpoint=json.loads((OUT/'batch-checkpoint.json').read_text());symbols=list(checkpoint['records'])
    old=pq.read_table(SOURCE,columns=['symbol','trade_date','open','high','low','close'],filters=[('symbol','in',symbols),('trade_date','>=',pd.Timestamp('2026-01-01'))]).to_pandas()
    groups={s:g.set_index('trade_date') for s,g in old.groupby('symbol')};records={}
    for s in symbols:
        ths=('USHA' if s.endswith('.SH') else 'USZA')+s.split('.')[0];stage='cached_inputs'
        try:
            h=json.loads((OUT/'ths-raw'/f'{ths}.json').read_text());a=json.loads((OUT/'rights'/f'{ths}.json').read_text())
            raw=pd.DataFrame(h['bars']);raw['date']=pd.to_datetime(raw.date);raw=raw.set_index('date');prior=groups[s];common=prior.index.intersection(raw.index)
            stage='overlap_count'
            if len(common)<20:raise ValueError('insufficient_overlap')
            stage='raw_price_match';diff=(prior.loc[common,['open','high','low','close']]-raw.loc[common,['open','high','low','close']]).abs();maximum=float(diff.to_numpy().max())
            if maximum>1e-6:raise ValueError('raw_mismatch')
            stage='structure'
            if raw.index.duplicated().any() or not((raw.low>0)&(raw.low<=raw[['open','close']].min(axis=1))&(raw.high>=raw[['open','close']].max(axis=1))).all():raise ValueError('invalid_OHLC')
            stage='signal_actions';frame=signal_frame(h,a,start='2023-01-01')
            records[s]=dict(status='raw_reference_and_signal_checked',previous_status=checkpoint['records'][s]['status'],overlap=len(common),max_raw_difference=maximum,last=str(raw.index.max().date()),rows=len(frame))
        except Exception as exc:
            records[s]=dict(status='quarantined',previous_status=checkpoint['records'][s]['status'],stage=stage,error_type=type(exc).__name__)
    report=dict(source=str(SOURCE),snapshot_symbols=len(symbols),records=records,counts=dict(Counter(v['status'] for v in records.values())),quarantine_stages=dict(Counter(v.get('stage') for v in records.values() if v['status']=='quarantined')),recovered=sum(v['status']=='raw_reference_and_signal_checked' and v['previous_status']=='quarantined' for v in records.values()),previously_accepted_now_fail=sum(v['status']=='quarantined' and v['previous_status']=='signal_window_checked' for v in records.values()),limitation='Offline checkpoint snapshot only. No collector checkpoint mutation; no corporate-action completeness or execution certification.20day overlap rule preserved; recent IPO insufficient overlap remains explicit.')
    (OUT/'raw-reference-revalidation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2))


if __name__=='__main__':main()
