"""Single observed shipped-client historical-limit-analysis request, authorized quote node only."""
import json,socket,struct,sys,urllib.parse,hashlib
from pathlib import Path
from fetch_history import APP,receive
sys.path.insert(0,str(APP))
from market import decode
from sessions import SessionManager,DEFAULT_PREFERENCES,validate_handshake_reply
OUT=APP/'research/results/stock-data-audit'
def main():
 query=dict(id=210,instance=950002,market='USHA',code='688008',start=-19,end='20231229',datatype='1,7,8,9,11,13,19,74',period=16384,zipversion=3)
 report=dict(endpoint='119.3.43.91:9602',query=query,template_source='Existing observed id210 query, retain field74 previously omitted by bars adapter',status='not_started',limitation='Unknown field semantics; empty response is not evidence of missing trading days')
 try:
  manager=SessionManager(APP.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin',preferences_path=DEFAULT_PREFERENCES)
  with socket.create_connection(('119.3.43.91',9602),timeout=8) as sock:
   sock.settimeout(12);sock.sendall(manager.prepare());validate_handshake_reply(receive(sock))
   payload=urllib.parse.urlencode(query,safe=',').encode();sock.sendall(b'\xfd'*4+f'{len(payload):08x}'.encode()+b'\x09'+payload)
   seen=[]
   for _ in range(8):
    body=receive(sock)
    if len(body)<10:continue
    instance,kind=struct.unpack_from('<II',body,2);seen.append(dict(instance=instance,kind=kind,size=len(body)))
    if instance==950002 and kind==210:
     (OUT/'ths-history-extra-field.bin').write_bytes(body)
     report.update(status='matching_response',bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),records=decode(body)[2]);break
   else:report['status']='no_matching_response'
   report['observed_response_types']=seen
 except Exception as exc:report.update(status='request_failed',error_type=type(exc).__name__)
 (OUT/'ths-history-extra-field.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False))
if __name__=='__main__':main()
