"""Read-only id211 probe from the shipped RequestItem.plist template."""
import json,socket,struct,sys,urllib.parse
from pathlib import Path
APP=Path(__file__).resolve().parents[1];sys.path.insert(0,str(APP))
from market import decode
from sessions import SessionManager,DEFAULT_PREFERENCES,validate_handshake_reply
from fetch_history import receive

def main():
 manager=SessionManager(APP.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin',preferences_path=DEFAULT_PREFERENCES)
 out=[];directory=APP/'research/results/stock-data-audit'
 with socket.create_connection(('119.3.43.91',9602),timeout=8) as sock:
  sock.settimeout(15);sock.sendall(manager.prepare());validate_handshake_reply(receive(sock))
  for instance,(market,code) in enumerate([('USHA','688008'),('USZA','300033')],920001):
   query=dict(id=211,instance=instance,zipversion=3,market=market,code=code,start=0,end=0,datatype='1,471',period=16384)
   payload=urllib.parse.urlencode(query,safe=',').encode();sock.sendall(b'\xfd'*4+f'{len(payload):08x}'.encode()+b'\x09'+payload)
   for _ in range(16):
    body=receive(sock)
    if len(body)>=17 and struct.unpack_from('<II',body,2)==(instance,211):break
   else:raise ValueError('No matching211response')
   (directory/f'ths-actions-{code}.bin').write_bytes(body)
   header=struct.unpack_from('<HIIHIB',body)
   try:decoded=decode(body,allowed_kinds=(211,));result=decoded[2] if decoded else None;error=None
   except Exception as exc:result=None;error=type(exc).__name__
   item=dict(symbol=market+code,query=query,response_header=header,bytes=len(body),records=result,decode_error=error);out.append(item)
   print(json.dumps(dict(symbol=item['symbol'],header=header,rows=len(result) if result is not None else None,first=result[:1] if result else [],error=error)),flush=True)
   (directory/'ths-actions-protocol-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
