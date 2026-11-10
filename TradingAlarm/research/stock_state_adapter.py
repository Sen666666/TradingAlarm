"""Dated provider state adapter. Never infers daily price limits from OHLC or ST alone."""
from stock_execution import OpenState

def provider_open_state(row,symbol,execution_date,source_crosschecked=False):
    expected=symbol[-2:].lower()+'.'+symbol[:6]
    if row.get('code')!=expected or row.get('date')!=execution_date or row.get('adjustflag')!='3':
        raise ValueError('instrument/date/raw-price mismatch')
    status=row.get('tradestatus')
    trading={'0':False,'1':True}.get(status)
    try:price=float(row.get('open','nan'))
    except (TypeError,ValueError):price=float('nan')
    return OpenState(date=execution_date,raw_open=price,trading=trading,state_verified=source_crosschecked)
