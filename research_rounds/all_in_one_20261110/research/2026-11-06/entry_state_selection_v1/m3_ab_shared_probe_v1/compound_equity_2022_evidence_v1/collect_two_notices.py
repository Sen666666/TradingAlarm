from pathlib import Path
import json,requests,datetime,hashlib,time,subprocess
O=Path(__file__).resolve().parent;S=O.parent.parent/'m3_stock_birth_during_sector_v1/share_action_facts_50_v1'
mp={r['code']:r for r in json.loads((S/'notices/stock_map.json').read_text())['stockList']}
ledger=[]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(n,o):(O/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def fetch(method,url,**kwargs):
 assert url=='https://www.cninfo.com.cn/new/hisAnnouncement/query' or url.startswith('https://static.cninfo.com.cn/finalpage/2022-06-')
 t=time.monotonic();r=requests.request(method,url,timeout=20,**kwargs);ledger.append({'url':url,'method':method,'retrieved_utc':now(),'status':r.status_code,'elapsed_s':time.monotonic()-t,'bytes':len(r.content)});dump('NETWORK_LEDGER.json',ledger);r.raise_for_status();time.sleep(.5);return r
for sid in ['600850.SH','600056.SH']:
 try:
  assert not (O/'sources'/(sid+'_index.json')).exists()
  data={'pageNum':1,'pageSize':30,'column':'szse','tabName':'fulltext','plate':'','stock':sid[:6]+','+mp[sid[:6]]['orgId'],'searchkey':'实施','secid':'','category':'','trade':'','seDate':'2022-06-01~2022-06-24','sortName':'','sortType':'','isHLtitle':'false'}
  r=fetch('POST','https://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
  raw=r.json();assert isinstance(raw.get('announcements'),list) and raw.get('totalAnnouncement',0)<=30
  candidates=[a for a in raw['announcements'] if a['secCode']==sid[:6] and '权益分派实施公告' in a['announcementTitle']]
  dump('sources/'+sid+'_index.json',{'requested_sid':sid,'params':data,'retrieved_utc':now(),'api_response':raw,'implementation_candidates':candidates,'current_retrieval_not_PIT':True});assert len(candidates)==1,(sid,len(candidates))
  a=candidates[0];url='https://static.cninfo.com.cn/'+a['adjunctUrl'];r=fetch('GET',url);assert r.content.startswith(b'%PDF') and len(r.content)<10000000;p=O/'sources'/(sid+'.pdf');p.write_bytes(r.content);h=hashlib.sha256(r.content).hexdigest();dump('sources/'+sid+'.json',{'url':url,'metadata':a,'sha256':h,'retrieved_utc':now()})
  script='ObjC.import("Foundation"); ObjC.import("PDFKit"); var d=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath('+json.dumps(str(p))+')); var a=[]; for(var i=0;i<d.pageCount;i++){a.push({page:i+1,text:ObjC.unwrap(d.pageAtIndex(i).string)})}; JSON.stringify({pages:a});'
  proc=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],capture_output=True,text=True,check=True,timeout=30);data=json.loads(proc.stdout);data.update(source_sha256=h,extraction_warning=proc.stderr.strip());dump('sources/'+sid+'.text.json',data);print(json.dumps({'sid':sid,'url':url,'sha256':h,'pages':len(data['pages'])},ensure_ascii=False),flush=True)
 except Exception as e:
  dump('ACQUISITION_STOP.json',{'sid':sid,'error_type':type(e).__name__,'error':str(e)[:700],'at':now(),'outcome':'Stopped this batch with no retry or alternate route','completed_requests':len(ledger)});raise
assert len(ledger)==4
dump('ACQUISITION_RESULT.json',{'requests':len(ledger),'new_events':2,'reused_events':3,'max5_respected':True,'account_run':False,'old_sources_written':False,'elapsed_http_seconds':sum(r['elapsed_s'] for r in ledger)})
