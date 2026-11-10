"""Pure source/mark audit; no Market, Runner or Account construction/replay.

Call the unchanged native FrozenMarket.latest_mark function on read-only source
fields. FastMarket explicitly checks/delegates to this reference implementation.
"""
from pathlib import Path
from types import SimpleNamespace,MethodType
from decimal import Decimal as D
from datetime import datetime
import dataclasses,gzip,hashlib,json,sys,time
import pandas as pd
import entry_adapter as E

O=Path(__file__).resolve().parent
F=E.J.M.E.FastMarket.__mro__[1]
native=sys.modules[F.__module__]

def main():
    t=time.monotonic();day='2026-06-26'
    daily=O/'runs/strong_BB20/pair/daily.jsonl.gz'
    with gzip.open(daily,'rt')as f:
        saved=next(x for x in map(json.loads,f)if x['at'][:10]==day)
    at=datetime.fromisoformat(saved['at'])
    records={r['series_id']:r for r in json.loads((E.J.M.P/'manifest.json').read_text())['series']}
    sm={r['symbol']:r for r in json.loads((E.L.U/'STOCK_MANIFEST.json').read_text())}
    protocol=json.loads((E.J.BP.C.OLD/'inputs-v2/economic-protocol.json').read_text())
    rules=json.loads((E.J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json').read_text())
    sessions={k:tuple(datetime.fromisoformat(x)for x in v)for k,v in rules['calendars'].items()}
    result=[];rawtotal=D(0);facttotal=D(0)
    for sid,qty in saved['positions'].items():
        rec=records[sid]
        rawpath=native.checked_ref(rec['raw'],E.J.M.P)
        frame=native.read_raw(rawpath,rec)
        frame['valid_price']=frame.index.isin(native.eligible_prices(frame).index)
        frame['observed_bar']=native.boolean_column(frame,'observed_bar',True)
        events,_=native.read_actions(rec,E.J.M.P)
        # Data carrier only: neither a native Market nor a financial object.
        view=SimpleNamespace(raw={sid:frame},bundle=SimpleNamespace(series={sid:SimpleNamespace(record=rec)}),
            lines={sid:SimpleNamespace(market='A')},sessions=sessions,actions={sid:events},protocol=protocol)
        view.source_available=MethodType(F.source_available,view)
        view.rate=MethodType(F.rate,view)
        mark=F.latest_mark(view,sid,at)
        f=pd.read_parquet(sm[sid]['refs']['facts'],columns=['raw_close'])
        i=f.index.searchsorted(pd.Timestamp(day),side='right')-1
        factprice=D(str(f.iloc[i].raw_close));price=mark.cny_price(at)
        fv=D(qty)*factprice;mv=D(qty)*price;facttotal+=fv;rawtotal+=mv
        # The actual raw observation date remains known_at after a derived ex ref.
        known=mark.known_at
        actions=[e for e in events if known.date().isoformat()<e['effective_date']<=day]
        tail=frame.loc[:day].tail(3)
        result.append(dict(sid=sid,qty=qty,native_mark=str(price),facts_raw_close=str(factprice),
            facts_last_date=str(f.index[i].date()),native_known_at=str(known),
            native_source=mark.source_id,facts_minus_native_value=str(fv-mv),
            intervening_actions=actions,raw_path=str(rawpath),raw_sha256=rec['raw']['sha256'],
            actions_path=rec['adjustment']['actions']['path'],actions_sha256=rec['adjustment']['actions']['sha256'],
            raw_tail=tail.reset_index().to_dict('records')))
    expected=D(saved['inventory'])
    assert rawtotal==expected,('pure original mark function does not reproduce native inventory',rawtotal,expected)
    out=dict(passed=True,day=day,at=str(at),native_inventory=str(expected),pure_native_marks_inventory=str(rawtotal),
        facts_raw_close_inventory=str(facttotal),facts_minus_native_inventory=str(facttotal-rawtotal),
        changed=[r for r in result if D(r['facts_minus_native_value'])!=0],all_positions=result,
        native_function=F.__module__+'.FrozenMarket.latest_mark',native_function_file=str(Path(native.__file__)),
        no_native_market_initialization=True,new_accounts=0,new_fills=0,seconds=time.monotonic()-t)
    (O/'JUN26_NATIVE_MARK_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps({k:v for k,v in out.items()if k not in ['all_positions','changed']},ensure_ascii=False,indent=2))
    print('CHANGED',json.dumps(out['changed'],ensure_ascii=False,default=str,indent=2))

if __name__=='__main__':main()
