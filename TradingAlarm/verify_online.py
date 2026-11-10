"""Explicit user-authorized, bounded read-only verification. No credential output."""
import json
from pathlib import Path
from market import SessionClient
from server import SESSION
from sessions import HandshakeRejected, SessionUnavailable

result={'symbol':'USHA688008','endpoint':'119.3.43.91:9602','sessionBefore':SESSION.status()}
try:
    client=SessionClient('119.3.43.91',9602,session_manager=SESSION)
    data=client.fetch('USHA688008')
    SESSION.success(client.server_time)
    result.update(success=True,quote=data['quote'],intradayRows=len(data['intraday']),dailyBars=len(data['bars']),
                  intradayFirst=data['intraday'][0] if data['intraday'] else None,
                  intradayLast=data['intraday'][-1] if data['intraday'] else None,
                  firstDaily=data['bars'][0]['date'] if data['bars'] else None,
                  lastDaily=data['bars'][-1] if data['bars'] else None)
    Path(__file__).with_name('data').joinpath('online-verification-market.json').write_text(json.dumps(data,ensure_ascii=False))
except HandshakeRejected:
    SESSION.failed(rejected=True);result.update(success=False,error='handshake_rejected')
except SessionUnavailable as exc:
    result.update(success=False,error=str(exc))
except Exception as exc:
    SESSION.failed();result.update(success=False,errorType=type(exc).__name__)
result['sessionAfter']=SESSION.status()
Path(__file__).with_name('online-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
