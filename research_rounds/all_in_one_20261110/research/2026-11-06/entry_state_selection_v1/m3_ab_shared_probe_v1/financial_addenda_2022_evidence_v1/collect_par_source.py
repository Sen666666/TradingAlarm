from pathlib import Path
import requests,json,hashlib,datetime,time,subprocess
O=Path(__file__).resolve().parent;O.joinpath('sources').mkdir();B=O.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
protected={str(p):sha(p) for name in ['compound_equity_2022_evidence_v1','future_cash4_2022_evidence_v1'] for p in (B/name).rglob('*') if p.is_file()};dump('PROTECTED_INPUT_HASHES.json',protected)
data={'pageNum':1,'pageSize':30,'column':'szse','tabName':'fulltext','plate':'','stock':'000987,gssz0000987','searchkey':'审计','secid':'','category':'','trade':'','seDate':'2022-03-24~2022-04-03','sortName':'','sortType':'','isHLtitle':'false'}
ledger=[]
def fetch(method,url,**kw):
 t=time.monotonic();r=requests.request(method,url,timeout=20,**kw);ledger.append({'method':method,'url':url,'http_status':r.status_code,'bytes':len(r.content),'seconds':time.monotonic()-t,'retrieved_utc':now()});dump('NETWORK_LEDGER.json',ledger);r.raise_for_status();return r
try:
 r=fetch('POST','https://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'});x=r.json();assert isinstance(x.get('announcements'),list) and x.get('totalAnnouncement',0)<=30
 cand=[a for a in x['announcements'] if a['secCode']=='000987' and '2021' in a['announcementTitle'] and '审计报告' in a['announcementTitle'] and '内部' not in a['announcementTitle']]
 dump('sources/000987_audit_index.json',{'params':data,'retrieved_utc':now(),'response':x,'candidates':cand,'not_archived_PIT':True});print('INDEX',json.dumps([{'title':a['announcementTitle'],'date':a['announcementTime'],'url':a['adjunctUrl']} for a in x['announcements']],ensure_ascii=False),flush=True);assert len(cand)==1
 a=cand[0];url='https://static.cninfo.com.cn/'+a['adjunctUrl'];assert url.startswith('https://static.cninfo.com.cn/finalpage/2022-');r=fetch('GET',url);assert r.content.startswith(b'%PDF') and len(r.content)<15000000;p=O/'sources/000987_2021_audit.pdf';p.write_bytes(r.content);h=sha(p);dump('sources/000987_2021_audit.json',{'url':url,'metadata':a,'sha256':h,'retrieved_utc':now()})
 script='ObjC.import("Foundation"); ObjC.import("PDFKit"); var d=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath('+json.dumps(str(p))+')); var a=[]; for(var i=0;i<d.pageCount;i++){a.push({page:i+1,text:ObjC.unwrap(d.pageAtIndex(i).string)})}; JSON.stringify({pages:a});';proc=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],capture_output=True,text=True,check=True,timeout=60);text=json.loads(proc.stdout);text.update(source_sha256=h,extraction_warning=proc.stderr.strip());dump('sources/000987_2021_audit.text.json',text)
 print('PDF',json.dumps({'url':url,'sha256':h,'pages':len(text['pages'])},ensure_ascii=False),flush=True)
 for p in text['pages']:
  if any(w in (p['text'] or '') for w in ['面值','批准报出','批准报出日']):print('MATCH PAGE',p['page'],'\n',p['text'],flush=True)
 assert len(ledger)==2 and all(sha(Path(p))==v for p,v in protected.items())
except Exception as e:dump('ACQUISITION_STOP.json',{'error_type':type(e).__name__,'error':str(e)[:700],'outcome':'Stopped without retry or alternative acquisition','requests':len(ledger)});raise
