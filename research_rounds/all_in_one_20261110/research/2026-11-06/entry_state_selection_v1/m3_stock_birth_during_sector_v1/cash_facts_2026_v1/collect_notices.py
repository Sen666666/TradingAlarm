from pathlib import Path
import csv,json,requests,time,hashlib,datetime,importlib.util
O=Path(__file__).resolve().parent;B=O.parent
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
mpath=B/'cash_dividend_precision_24_v1/notices/stock_map.json';mp={x['code']:x for x in json.loads(mpath.read_text())['stockList']}
rows=list(csv.DictReader((B/'source_bridge_2026_feasibility_v1/CASH_FACTOR_EVENTS.csv').open()))
for name in ['notices','notice_pdf']:(O/name).mkdir(exist_ok=True)
save(O/'NOTICE_MAP_SOURCE.json',{'path':str(mpath),'sha256':sha(mpath)})
def req(method,url,dest,**kw):
 ts=now();r=requests.request(method,url,timeout=20,**kw);dest.write_bytes(r.content);save(dest.with_suffix(dest.suffix+'.meta.json'),{'url':url,'method':method,'retrieved_at_utc':ts,'status':r.status_code,'sha256':sha(dest),'params':kw.get('data')});r.raise_for_status();return r
for row in rows:
 sid=row['sid']
 try:
  p=O/'notices'/(sid+'.json');facts=json.loads((O/'raw'/(sid+'.json')).read_text())['raw']['records'];hits=[x for x in facts if x.get('F020D')==row['day']];assert len(hits)==1
  day=datetime.date.fromisoformat(hits[0]['F006D']);m=mp[sid[:6]]
  payload={'pageNum':1,'pageSize':100,'column':'szse','tabName':'fulltext','plate':'','stock':sid[:6]+','+m['orgId'],'searchkey':'','secid':'','category':'','trade':'','seDate':(day-datetime.timedelta(days=1)).isoformat()+'~'+(day+datetime.timedelta(days=1)).isoformat(),'sortName':'','sortType':'','isHLtitle':'true'}
  raw=json.loads(p.read_text())['response'] if p.exists() else req('POST','https://www.cninfo.com.cn/new/hisAnnouncement/query',p.with_suffix('.response'),data=payload).json();assert isinstance(raw.get('announcements'),list) and raw['totalAnnouncement']<=100
  candidates=[a for a in raw['announcements'] if '实施' in a['announcementTitle'] and any(x in a['announcementTitle'] for x in ['权益分派','利润分配','股息分派','分红派息'])];assert candidates and all(a['secCode']==sid[:6] for a in candidates)
  save(p,{'sid':sid,'ex_date':row['day'],'payload':payload,'response':raw,'candidates':candidates});time.sleep(.5)
  for a in candidates:
   assert a['adjunctUrl'].startswith('finalpage/');dest=O/'notice_pdf'/(sid+'_'+a['announcementId']+'.pdf');
   if not dest.exists():req('GET','https://static.cninfo.com.cn/'+a['adjunctUrl'],dest)
   assert dest.read_bytes().startswith(b'%PDF') and dest.stat().st_size<10000000
   save(dest.with_suffix('.json'),{'sid':sid,'metadata':a,'url':'https://static.cninfo.com.cn/'+a['adjunctUrl'],'sha256':sha(dest)})
   time.sleep(.5)
  print(sid,[a['announcementTitle'] for a in candidates],flush=True)
 except Exception as e:
  save(O/'STOP_NOTICES.json',{'sid':sid,'error':repr(e),'at':now(),'no_retry':True});print('STOP',repr(e),flush=True);break
