"""Bounded read-only adjustment probe at the already authorized quote endpoint."""
import argparse,json,socket,sys,urllib.parse
from pathlib import Path
from datetime import datetime
APP=Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from market import decode,bars
from sessions import SessionManager,DEFAULT_PREFERENCES,validate_handshake_reply
from fetch_history import receive

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--end',default='20260515');parser.add_argument('--count',type=int,default=31);parser.add_argument('--suffix',default='');args=parser.parse_args()
 if not args.end.isdigit() or len(args.end)!=8 or not 1<=args.count<=750 or not args.suffix.replace('-','').isalnum() and args.suffix:raise ValueError('Invalid probe arguments')
 manager=SessionManager(APP.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin',preferences_path=DEFAULT_PREFERENCES)
 output=[]
 with socket.create_connection(('119.3.43.91',9602),timeout=8) as sock:
  sock.settimeout(20);sock.sendall(manager.prepare());server_time=validate_handshake_reply(receive(sock))
  for instance,mode in enumerate(['Q','B','omitted'],910001):
   query=dict(id=210,instance=instance,zipversion=3,code='688008',market='USHA',start=1-args.count,end=args.end,datatype='1,7,8,9,11,13,19,74',period=16384)
   if mode!='omitted':query['fuquan']=mode
   payload=urllib.parse.urlencode(query,safe=',').encode();sock.sendall(b'\xfd'*4+f'{len(payload):08x}'.encode()+b'\x09'+payload)
   for _ in range(16):
    decoded=decode(receive(sock))
    if decoded and decoded[:2]==(210,instance):break
   else:raise ValueError('No matching response')
   output.append(dict(mode=mode,query=query,bars=bars(decoded[2]),records=decoded[2]))
   print(mode,len(decoded[2]),flush=True)
  manager.success(server_time)
 out=dict(symbol='USHA688008',fetched_at=datetime.now().astimezone().isoformat(),source='119.3.43.91:9602',probes=output,limitation='B and Q literals observed in shipped client; semantics require price/event cross-check. Omission is a probe, not presumed raw price.')
 (APP/('research/results/stock-data-audit/ths-adjustment-probe'+('-'+args.suffix if args.suffix else '')+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
