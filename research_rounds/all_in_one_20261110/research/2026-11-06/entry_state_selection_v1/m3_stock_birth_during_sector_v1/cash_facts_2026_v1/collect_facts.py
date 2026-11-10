from pathlib import Path
import csv,json,time,hashlib,datetime,requests
from akshare.stock.stock_dividend_cninfo import stock_dividend_cninfo
O=Path(__file__).resolve().parent;B=O.parent
T=B/'source_bridge_2026_feasibility_v1/CASH_FACTOR_EVENTS.csv'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
rows=list(csv.DictReader(T.open()));assert len(rows)==10
sources={str(T):sha(T)}
for r in rows:
 for k in ['rights_path','rights_source_path']:sources[r[k]]=sha(Path(r[k]))
save(O/'SOURCE_SEAL.json',{'created_at':now(),'sources':sources,'targets':rows,'timeout':20,'retries':0,'backtest_runs':0})
(O/'raw').mkdir();orig=requests.sessions.Session.request;caps=[]
def bounded(self,method,url,**kw):
 assert url=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139'
 kw['timeout']=20;t=time.monotonic();response=orig(self,method,url,**kw)
 caps.append({'url':url,'method':method,'status_code':response.status_code,'elapsed_s':time.monotonic()-t,'response_bytes':response.content,'body_text':response.text});response.raise_for_status();return response
requests.sessions.Session.request=bounded
for row in rows:
 sid=row['sid'];caps.clear();p=O/'raw'/(sid+'.json')
 try:
  fetched=now();frame=stock_dividend_cninfo(sid[:6]);assert len(caps)==1
  cap=caps[0];raw=json.loads(cap.pop('body_text'));body=cap.pop('response_bytes');bp=p.with_suffix('.response');bp.write_bytes(body)
  assert raw.get('resultcode')==200 and raw['count']==raw['total']==len(raw['records'])
  save(p,{'sid':sid,'requested_code':sid[:6],'retrieved_at_utc':fetched,'endpoint':cap['url'],'params':{'scode':sid[:6]},'transport':cap,'raw_response_path':str(bp),'raw_response_sha256':sha(bp),'raw':raw,'archived_PIT':False})
  print(sid,[(r.get('F007V'),r.get('F006D'),r.get('F018D'),r.get('F020D'),r.get('F023D')) for r in raw['records'] if r.get('F020D')==row['day']],flush=True)
 except Exception as e:
  if caps:
   c=dict(caps[-1]);body=c.pop('response_bytes');c.pop('body_text',None);(O/'raw'/(sid+'.failed.response')).write_bytes(body)
  save(O/'STOP_FACTS.json',{'sid':sid,'error':repr(e),'at':now(),'no_retry':True});print('STOP',repr(e),flush=True);break
 time.sleep(.5)
assert all(sha(Path(p))==h for p,h in sources.items())
