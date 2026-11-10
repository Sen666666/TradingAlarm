"""At most three pure-signal examples, only to measure bounded feasibility."""
from pathlib import Path
import hashlib
import json
import signal as os_signal
import time
import pandas as pd
import pyarrow.dataset as ds
import stock_signal as pure

HERE=Path(__file__).resolve().parent
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
DAY='2024-09-24'


def main():
    assert not(HERE/'PILOT.json').exists()
    started=time.monotonic();rows=[]
    def stopped(*_):raise TimeoutError('60 second pure-signal pilot budget reached; never start all-stock scan')
    os_signal.signal(os_signal.SIGALRM,stopped);os_signal.setitimer(os_signal.ITIMER_REAL,60)
    try:
        for sid in ['000620.SZ','000004.SZ','002583.SZ']:
            at=time.monotonic()
            frame=ds.dataset(SOURCE).to_table(columns=['trade_date','open','high','low','close','volume'],filter=(ds.field('symbol')==sid)&(ds.field('trade_date')<=pd.Timestamp(DAY))).to_pandas().sort_values('trade_date').set_index('trade_date')
            frame['segment_id']=0
            compute_start=time.monotonic();out=pure.calculate(frame)
            row=dict(sid=sid,input_rows=len(frame),output_rows=len(out),compute_seconds=time.monotonic()-compute_start,total_seconds=time.monotonic()-at,
                     has_exact_target=pd.Timestamp(DAY)in out.index,stock_only_not_S0=True)
            if row['has_exact_target']:
                selected=out.loc[pd.Timestamp(DAY)].replace({float('nan'):None}).to_dict()
                row['target']=selected
            rows.append(row)
            (HERE/'PILOT_PROGRESS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str)+'\n')
            print(json.dumps(row,ensure_ascii=False,default=str),flush=True)
        status='COMPLETE_THREE_PURE_SIGNAL_EXAMPLES'
    except BaseException as e:
        status='STOPPED_BOUNDED_PILOT';rows.append(dict(error=repr(e)))
    finally:
        os_signal.setitimer(os_signal.ITIMER_REAL,0)
        payload=dict(status=status,rows=rows,seconds=time.monotonic()-started,all_stock_scan_started=False,new_accounts=0,
                     code_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in [Path(__file__),Path(pure.__file__)]})
        (HERE/'PILOT.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+'\n')


if __name__=='__main__':main()
