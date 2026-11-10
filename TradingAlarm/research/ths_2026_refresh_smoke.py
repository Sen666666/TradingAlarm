"""Bounded2026 source smoke;isolated snapshots,authorized quote/search nodes only."""
import json,time,sys
from pathlib import Path
import fetch_history as history
import fetch_ths_rights as rights
from fetch_history import APP
sys.path.insert(0,str(APP))
from search import SearchClient
from sessions import SessionManager,DEFAULT_PREFERENCES
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data/ths-refresh-20261018';OUT.mkdir(exist_ok=True)
history.OUT=OUT;rights.OUT=OUT/'rights';rights.OUT.mkdir(exist_ok=True)

def main():
    manager=SessionManager(APP.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin',preferences_path=DEFAULT_PREFERENCES)
    client=SearchClient(manager);reports=[]
    for code in ('688008','600519','000001'):
        started=time.monotonic()
        try:
            matches=[r for r in client.search(code) if r.get('code')==code and r.get('market') in ('USHA','USZA')]
            if len(matches)!=1:raise ValueError('Unique live A-share identifier not resolved')
            symbol=matches[0]['symbol'];bars=history.fetch(symbol,'20261016','2026-01-01',1,'raw')
            actions=rights.fetch_rights(symbol)
            daily=bars['bars'];dates=[r['date'] for r in daily]
            valid=all(r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high'] and r['low']>0 for r in daily)
            reports.append(dict(code=code,symbol=symbol,status='received',seconds=round(time.monotonic()-started,3),rows=len(daily),rows2026=sum(d>='2026-01-01' for d in dates),first=min(dates) if dates else None,last=max(dates) if dates else None,unique_dates=len(set(dates))==len(dates),ohlc_valid=valid,action_records=len(actions['records']),unparsed_actions=len(actions['unparsed']),corporate_actions_complete=False))
        except Exception as exc:reports.append(dict(code=code,status='error',error_type=type(exc).__name__,seconds=round(time.monotonic()-started,3)))
        (OUT/'smoke-report.json').write_text(json.dumps(reports,indent=2));print(json.dumps(reports[-1]),flush=True)
        time.sleep(.3)

if __name__=='__main__':main()
