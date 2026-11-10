"""Bounded four official cash notices only. No account imports or registration."""
from pathlib import Path
import requests,json,datetime,hashlib,time,subprocess
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent;E=R/'m3_stock_birth_during_sector_v1';A=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')
stockmap=E/'share_action_facts_50_v1/notices/stock_map.json';mp={r['code']:r for r in json.loads(stockmap.read_text())['stockList']};ledger=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(n,o):(O/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
subjects=[('600348.SH','2022-07-13'),('601319.SH','2022-07-29'),('002270.SZ','2022-09-22'),('600050.SH','2022-11-09')]
protected={str(p):sha(p) for p in (B/'compound_equity_2022_evidence_v1').rglob('*') if p.is_file()};protected[str(stockmap)]=sha(stockmap)
for sid,d in subjects:protected[str(A/(sid+'.json'))]=sha(A/(sid+'.json'))
dump('PROTECTED_INPUT_HASHES.json',protected);dump('ACQUISITION_CONTRACT.json',{'created_utc':now(),'subjects':subjects,'max_queries_per_subject':1,'max_pdf_get_per_subject':1,'max_http_requests':8,'timeout_seconds':20,'retry':0,'scope':'Official implementation dates, gross cash and reference-cash differences; candidates only, no registration or account changes','old_compound47_package_unchanged':True});(O/'sources').mkdir()
def fetch(method,url,**kwargs):
 assert url=='https://www.cninfo.com.cn/new/hisAnnouncement/query' or url.startswith('https://static.cninfo.com.cn/finalpage/2022-')
 assert len(ledger)<8
 t=time.monotonic();r=requests.request(method,url,timeout=20,**kwargs);ledger.append({'url':url,'method':method,'retrieved_utc':now(),'status':r.status_code,'elapsed_s':time.monotonic()-t,'bytes':len(r.content)});dump('NETWORK_LEDGER.json',ledger);r.raise_for_status();time.sleep(.5);return r
for sid,d in subjects:
 try:
  end=datetime.date.fromisoformat(d);start=end-datetime.timedelta(days=30)
  data={'pageNum':1,'pageSize':30,'column':'szse','tabName':'fulltext','plate':'','stock':sid[:6]+','+mp[sid[:6]]['orgId'],'searchkey':'实施','secid':'','category':'','trade':'','seDate':str(start)+'~'+d,'sortName':'','sortType':'','isHLtitle':'false'}
  r=fetch('POST','https://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'});raw=r.json();assert isinstance(raw.get('announcements'),list) and raw.get('totalAnnouncement',0)<=30
  cand=[a for a in raw['announcements'] if a['secCode']==sid[:6] and '实施公告' in a['announcementTitle'] and any(w in a['announcementTitle'] for w in ['权益分派','利润分配','分红派息'])]
  dump('sources/'+sid+'_index.json',{'requested_sid':sid,'target_ex_date':d,'params':data,'retrieved_utc':now(),'api_response':raw,'implementation_candidates':cand,'current_retrieval_not_PIT':True});assert len(cand)==1,(sid,len(cand))
  a=cand[0];url='https://static.cninfo.com.cn/'+a['adjunctUrl'];r=fetch('GET',url);assert r.content.startswith(b'%PDF') and len(r.content)<10000000;p=O/'sources'/(sid+'.pdf');p.write_bytes(r.content);h=sha(p);dump('sources/'+sid+'.json',{'url':url,'metadata':a,'sha256':h,'retrieved_utc':now()})
  script='ObjC.import("Foundation"); ObjC.import("PDFKit"); var d=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath('+json.dumps(str(p))+')); var a=[]; for(var i=0;i<d.pageCount;i++){a.push({page:i+1,text:ObjC.unwrap(d.pageAtIndex(i).string)})}; JSON.stringify({pages:a});'
  proc=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],capture_output=True,text=True,check=True,timeout=30);text=json.loads(proc.stdout);text.update(source_sha256=h,extraction_warning=proc.stderr.strip());dump('sources/'+sid+'.text.json',text);print(json.dumps({'sid':sid,'url':url,'sha256':h,'pages':len(text['pages'])},ensure_ascii=False),flush=True)
 except Exception as e:
  dump('ACQUISITION_STOP.json',{'sid':sid,'error_type':type(e).__name__,'error':str(e)[:700],'at':now(),'outcome':'Stopped entire batch without retry or alternate route','completed_requests':len(ledger)});raise
assert len(ledger)==8 and all(sha(Path(p))==h for p,h in protected.items())
dump('ACQUISITION_RESULT.json',{'new_requests':8,'new_pdf_events':4,'old_compound47_unchanged':True,'account_runs':0,'registered_events':0,'old_sources_written':False,'elapsed_http_seconds':sum(r['elapsed_s'] for r in ledger)})
