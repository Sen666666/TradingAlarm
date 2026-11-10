"""Bounded current retrieval of official issuer notices, never PIT assertion."""
from pathlib import Path
import csv,json,requests,time,hashlib,datetime,sys
O=Path(__file__).resolve().parent;B=O.parent
rows=list(csv.DictReader((O/'EVENT_FACT_COVERAGE.csv').open()))
map_path=B/'cash_dividend_precision_24_v1/notices/stock_map.json';mp={x['code']:x for x in json.loads(map_path.read_text())['stockList']}
out=O/'notices';pdf=O/'notice_pdf';out.mkdir(exist_ok=True);pdf.mkdir(exist_ok=True)
selected=[r for r in rows if r['fact_status'] in ['CASH_PRECISION_NOTICE_REQUIRED','MULTIPLE_ROWS_REQUIRES_NOTICE'] or r['sid'] in ['300866.SZ','688208.SH','300638.SZ']]
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def req(method,url,**kw):
 r=requests.request(method,url,timeout=20,**kw);r.raise_for_status();return r
for row in selected:
 sid=row['sid'];p=out/(sid+'.json')
 try:
  if not p.exists():
   rawp=Path(row['source_path']);hs=[x for x in json.loads(rawp.read_text())['raw']['records'] if x.get('F020D')==row['ex_day']];days={x['F006D'] for x in hs};assert len(days)==1
   day=datetime.date.fromisoformat(next(iter(days)));start=(day-datetime.timedelta(days=1)).isoformat();end=(day+datetime.timedelta(days=1)).isoformat();m=mp[sid[:6]]
   payload={'pageNum':1,'pageSize':100,'column':'szse','tabName':'fulltext','plate':'','stock':sid[:6]+','+m['orgId'],'searchkey':'','secid':'','category':'','trade':'','seDate':start+'~'+end,'sortName':'','sortType':'','isHLtitle':'true'}
   result=req('POST','https://www.cninfo.com.cn/new/hisAnnouncement/query',data=payload).json();assert isinstance(result.get('announcements'),list) and result['totalAnnouncement']<=100
   candidates=[a for a in result['announcements'] if '实施' in a['announcementTitle'] and any(x in a['announcementTitle'] for x in ['权益分派','利润分配','股息分派','分红派息'])];assert candidates and all(a['secCode']==sid[:6] for a in candidates)
   save(p,{'sid':sid,'target_ex_day':row['ex_day'],'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'payload':payload,'response':result,'candidates':candidates,'archived_PIT':False});time.sleep(.5)
  else:candidates=json.loads(p.read_text())['candidates']
  for a in candidates:
   dest=pdf/(sid+'_'+a['announcementId']+'.pdf')
   if dest.exists():continue
   assert a['adjunctUrl'].startswith('finalpage/')
   url='https://static.cninfo.com.cn/'+a['adjunctUrl'];r=req('GET',url);assert r.content.startswith(b'%PDF') and len(r.content)<10000000
   dest.write_bytes(r.content);save(dest.with_suffix('.json'),{'sid':sid,'target_ex_day':row['ex_day'],'url':url,'metadata':a,'sha256':hashlib.sha256(r.content).hexdigest(),'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});time.sleep(.5)
  print(sid,len(candidates),'notice PDFs',flush=True)
 except Exception as e:
  error={'sid':sid,'error_type':type(e).__name__,'error':str(e)[:500],'no_retry':True};save(O/'STOP_NOTICES.json',error);print(error,flush=True);break
