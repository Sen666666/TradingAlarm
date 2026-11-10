"""Bounded checkpointed rights collection using an observed shipped-client query."""
import argparse,json,signal,socket,struct,sys,time
from pathlib import Path
from datetime import datetime
from fetch_history import APP,receive
sys.path.insert(0,str(APP))
from market import decode
from sessions import SessionManager,DEFAULT_PREFERENCES,validate_handshake_reply
from stock_actions import parse_ths_rights
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data/ths-rights';OUT.mkdir(exist_ok=True)

def fetch_rights(symbol):
 if not symbol.isalnum() or len(symbol)<5:raise ValueError('invalidsymbol')
 manager=SessionManager(APP.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin',preferences_path=DEFAULT_PREFERENCES)
 query=dict(id=211,instance=930001,zipversion=3,market=symbol[:4],code=symbol[4:],start=0,end=0,datatype='1,471',period=16384)
 with socket.create_connection(('119.3.43.91',9602),timeout=8) as sock:
  sock.settimeout(15);sock.sendall(manager.prepare());validate_handshake_reply(receive(sock))
  payload=urllib.parse.urlencode(query,safe=',').encode();sock.sendall(b'\xfd'*4+f'{len(payload):08x}'.encode()+b'\x09'+payload)
  for _ in range(16):
   body=receive(sock)
   if len(body)>=17 and struct.unpack_from('<II',body,2)==(930001,211):break
  else:raise ValueError('no matchingresponse')
 decoded=decode(body,allowed_kinds=(211,))
 if decoded is None:raise ValueError('unsupportedresponse')
 records=decoded[2];events=[];unparsed=[]
 for row in records:
  try:events.append(parse_ths_rights(symbol,row))
  except (ValueError,KeyError,TypeError) as exc:unparsed.append(dict(row=row,error_type=type(exc).__name__))
 out=dict(symbol=symbol,query=query,fetched_at=datetime.now().astimezone().isoformat(),records=records,events=events,unparsed=unparsed,
          complete_actions_certified=False,empty_does_not_prove_no_events=True)
 (OUT/(symbol+'.bin')).write_bytes(body)
 target=OUT/(symbol+'.json');temp=target.with_suffix('.tmp');temp.write_text(json.dumps(out,ensure_ascii=False,indent=2));temp.replace(target)
 return out

import urllib.parse

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=242);parser.add_argument('--budget-seconds',type=int,default=1200);args=parser.parse_args()
 signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('batchbudget')));signal.alarm(args.budget_seconds)
 paths=sorted((ROOT/'data/ths-raw').glob('*.json'))[:args.limit];summary=[];start=time.monotonic()
 try:
  for path in paths:
   symbol=path.stem;target=OUT/(symbol+'.json')
   try:
    if target.exists():
     data=json.loads(target.read_text())
     if data.get('symbol')!=symbol or 'records' not in data:raise ValueError('invalidcheckpoint')
    else:data=fetch_rights(symbol)
    summary.append(dict(symbol=symbol,status='received',records=len(data['records']),parsed=len(data['events']),unparsed=len(data['unparsed'])))
    print(symbol,len(data['records']),'unparsed',len(data['unparsed']),flush=True)
   except Exception as exc:
    summary.append(dict(symbol=symbol,status='error',error_type=type(exc).__name__))
    print(symbol,type(exc).__name__,flush=True)
    if time.monotonic()-start>=args.budget_seconds-1:break
   time.sleep(.2)
 finally:
  signal.alarm(0)
  (ROOT/'results/stock-data-audit/ths-rights-collection.json').write_text(json.dumps(dict(selected=len(paths),records=summary),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
