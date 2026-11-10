"""Read-only official CNINFO public historical facts for 14 fixed existing events only."""
from pathlib import Path
import requests,json,datetime,time,hashlib
from akshare.stock.stock_dividend_cninfo import stock_dividend_cninfo
O=Path(__file__).resolve().parent;P=O/'RAW_ADDITIONAL';P.mkdir(exist_ok=True)
p=json.loads((O/'Q1_UNIVERSE_INVENTORY.json').read_text());targets=[t for t in p['additional_purecash'] if not t['cached_response_paths']];targets.sort(key=lambda t:(t['sid']!='000728.SZ',t['ex_date'],t['sid']));assert len({t['sid'] for t in targets})==46
original=requests.sessions.Session.request;captures=[]
def bounded(self,method,url,**kw):
 assert url=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139'
 kw['timeout']=45;t=time.monotonic();r=original(self,method,url,**kw);captures.append(dict(status_code=r.status_code,elapsed_s=time.monotonic()-t,body=r.text));r.raise_for_status();return r
requests.sessions.Session.request=bounded
results=[]
for t in targets:
 sid=t['sid'];dest=P/(sid+'.json')
 if dest.exists():results.append(dict(sid=sid,status='EXISTING_SKIPPED'));continue
 captures.clear();at=datetime.datetime.now(datetime.timezone.utc).isoformat()
 try:
  stock_dividend_cninfo(sid[:6]);assert len(captures)==1;cap=captures[0];raw=json.loads(cap.pop('body'));assert isinstance(raw.get('records'),list)
  blob=dict(sid=sid,requested_code=sid[:6],target_ex_date=t['ex_date'],retrieved_at_utc=at,endpoint='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139',params={'scode':sid[:6]},transport=cap,raw=raw,scope='Current retrieval of historical facts, not historical known-at or admission')
  dest.write_text(json.dumps(blob,ensure_ascii=False,indent=2)+'\n');hits=[r for r in raw['records'] if r.get('F020D')==t['ex_date']];res=dict(sid=sid,status='SAVED',path=str(dest),sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),hits=hits);results.append(res);print(json.dumps(res,ensure_ascii=False),flush=True)
 except Exception as e:
  res=dict(sid=sid,status='FAILED_ONE_BOUNDED_ATTEMPT',error_type=type(e).__name__,error=str(e)[:500],transport_status=captures[-1]['status_code'] if captures else None);results.append(res);print(json.dumps(res),flush=True)
  (P/('FAILURE_'+sid+'.json')).write_text(json.dumps(res,indent=2)+'\n')
  if not isinstance(e,(requests.exceptions.ReadTimeout,requests.exceptions.ConnectTimeout)):break
 time.sleep(.5)
(P/'COLLECTION_STATUS_BOUNDED_RETRY.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
