"""Bounded 50 fixed 2022 share-action facts. No simulation, source editing, credentials, or subsequent-event scan."""
from pathlib import Path
import json,time,datetime,hashlib,sys,shutil,subprocess
import pandas as pd, requests
from akshare.stock.stock_dividend_cninfo import stock_dividend_cninfo
O=Path(__file__).resolve().parent;B=O.parent;OLD=B/'share_action_field_feasibility_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def unchanged():
 s=json.loads((O/'PRE_RUN_SEAL.json').read_text());assert all(sha(Path(p))==h for p,h in s['source_hashes'].items())
def stop(phase,sid,e):
 save(O/'STOP.json',{'phase':phase,'sid':sid,'error_type':type(e).__name__,'error':str(e)[:600],'time':now(),'outcome':'Stopped without retry or alternate access route'});raise e
assert not (O/'STOP.json').exists(),'Previous stop requires outcome assessment'
d=pd.read_csv(B/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv')
t=d[(d.status=='FACTOR_PATH_UNKNOWN')&(d.split_ratio!=1)].sort_values(['status_day','sid'])
assert len(t)==t.sid.nunique()==50
for name in ['raw','notices','notice_pdf']:(O/name).mkdir(exist_ok=True)
if not (O/'PRE_RUN_SEAL.json').exists():
 paths=[B/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv',B/'lifecycle_v1/ROUNDS.csv',B/'lifecycle_v1/ACTIONS.csv',B/'lifecycle_v1/simulate.py',Path(__file__)]
 save(O/'PRE_RUN_SEAL.json',{'time':now(),'scope':'Only these 50 fixed first share-action interruptions. Official facts, not strategy.','targets':t[['sid','name','status_day','cash_per_old_share','split_ratio','core_qty','add_qty']].to_dict('records'),'source_hashes':{str(p):sha(p) for p in paths},'request_limits':{'new_api_max':44,'new_notice_query_max':46,'new_pdf_max':46,'timeout_s':20,'pause_s':0.5,'retry':0,'pagination_max':1},'coordinate_contract':'Keep old source cash/split and factor separate from actual shareholder entitlements and official exchange reference parameters.'})
 for p in (OLD/'raw').glob('*.json'):shutil.copy2(p,O/'raw'/p.name)
 oldq=json.loads((OLD/'ANNOUNCEMENT_QUERY_SAMPLE.json').read_text())
 olds={q['code']:q for q in oldq['samples']}
 for sid in t.sid:
  if sid[:6] not in olds:continue
  q=olds[sid[:6]];rows=q['response']['announcements'];assert len(rows)==1 and rows[0]['secCode']==sid[:6]
  save(O/'notices'/(sid+'.json'),{'requested_sid':sid,'reused_from':str(OLD/'ANNOUNCEMENT_QUERY_SAMPLE.json'),'params':q['params'],'api_response':q['response'],'implementation_candidates':rows,'current_retrieval_not_PIT':True})
  shutil.copy2(OLD/'notices'/(sid[:6]+'.pdf'),O/'notice_pdf'/(sid+'.pdf'))
  save(O/'notice_pdf'/(sid+'.json'),{'url':'https://static.cninfo.com.cn/'+rows[0]['adjunctUrl'],'metadata':rows[0],'sha256':sha(O/'notice_pdf'/(sid+'.pdf')),'reused_from':str(OLD/'notices'/(sid[:6]+'.pdf'))})
 shutil.copy2(B/'cash_dividend_precision_24_v1/notices/stock_map.json',O/'notices/stock_map.json')
unchanged();counts={'api_new':0,'notice_query_new':0,'pdf_new':0};start=time.monotonic()
orig=requests.sessions.Session.request;captures=[]
def bounded(self,method,url,**kw):
 allowed=['https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139','https://www.cninfo.com.cn/new/hisAnnouncement/query']
 assert url in allowed or url.startswith('https://static.cninfo.com.cn/finalpage/2022-')
 kw['timeout']=20;ts=time.monotonic();r=orig(self,method,url,**kw)
 captures.append({'url':url,'http_status':r.status_code,'elapsed_s':time.monotonic()-ts,'body':r.text if 'static.cninfo' not in url else None})
 r.raise_for_status();return r
requests.sessions.Session.request=bounded
for row in t.itertuples():
 p=O/'raw'/(row.sid+'.json')
 if p.exists():continue
 try:
  assert counts['api_new']<44
  captures.clear();stock_dividend_cninfo(row.sid[:6]);assert len(captures)==1
  cap=captures[0];raw=json.loads(cap.pop('body'));assert raw.get('resultcode')==200 and isinstance(raw.get('records'),list)
  save(p,{'sid':row.sid,'requested_code':row.sid[:6],'retrieved_at_utc':now(),'endpoint':'https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139','params':{'scode':row.sid[:6]},'transport':cap,'raw':raw,'source_time_status':'Current response, target only fixed 2022 event, not archived PIT'})
  counts['api_new']+=1;print('api',row.sid,len(raw['records']),flush=True)
 except Exception as e:stop('api',row.sid,e)
 time.sleep(.5)
mp={x['code']:x for x in json.loads((O/'notices/stock_map.json').read_text())['stockList']}
coverage=[]
for row in t.itertuples():
 raw=json.loads((O/'raw'/(row.sid+'.json')).read_text())['raw'];hits=[r for r in raw['records'] if r.get('F020D')==row.status_day]
 coverage.append({'sid':row.sid,'target_ex_date':row.status_day,'exact_api_hits':len(hits)})
 if len(hits)!=1:continue
 hit=hits[0];day=hit.get('F006D')
 if not day:continue
 p=O/'notices'/(row.sid+'.json')
 if p.exists():continue
 try:
  assert counts['notice_query_new']<46
  day=pd.Timestamp(day);se=(day-pd.Timedelta(days=1)).strftime('%Y-%m-%d')+'~'+(day+pd.Timedelta(days=1)).strftime('%Y-%m-%d')
  payload={'pageNum':1,'pageSize':30,'column':'szse','tabName':'fulltext','plate':'','stock':row.sid[:6]+','+mp[row.sid[:6]]['orgId'],'searchkey':'','secid':'','category':'','trade':'','seDate':se,'sortName':'','sortType':'','isHLtitle':'false'}
  r=requests.post('https://www.cninfo.com.cn/new/hisAnnouncement/query',data=payload);raw=r.json()
  assert isinstance(raw.get('announcements'),list) and int(raw['totalAnnouncement'])<=30,'unexpected schema or pagination'
  candidates=[a for a in raw['announcements'] if '实施公告' in a['announcementTitle'] and any(x in a['announcementTitle'] for x in ['权益分派','利润分配','股息分派','分红派息','转增股本'])]
  assert all(a['secCode']==row.sid[:6] for a in raw['announcements'])
  save(p,{'retrieved_at_utc':now(),'requested_sid':row.sid,'original_target_ex_date':row.status_day,'params':payload,'api_response':raw,'implementation_candidates':candidates,'current_retrieval_not_PIT':True})
  counts['notice_query_new']+=1;print('notice',row.sid,'candidates',len(candidates),flush=True)
 except Exception as e:stop('notices',row.sid,e)
 time.sleep(.5)
for row in t.itertuples():
 p=O/'notice_pdf'/(row.sid+'.pdf');q=O/'notices'/(row.sid+'.json')
 if p.exists() or not q.exists():continue
 b=json.loads(q.read_text());cand=b['implementation_candidates']
 if len(cand)!=1:continue
 a=cand[0]
 try:
  assert counts['pdf_new']<46 and a['secCode']==row.sid[:6] and a['adjunctUrl'].startswith('finalpage/2022-')
  url='https://static.cninfo.com.cn/'+a['adjunctUrl']
  r=requests.get(url);assert r.content.startswith(b'%PDF') and len(r.content)<10_000_000
  p.write_bytes(r.content);save(O/'notice_pdf'/(row.sid+'.json'),{'url':url,'metadata':a,'sha256':sha(p),'retrieved_at_utc':now()})
  counts['pdf_new']+=1;print('pdf',row.sid,len(r.content),flush=True)
 except Exception as e:stop('pdf',row.sid,e)
 time.sleep(.5)
for p in sorted((O/'notice_pdf').glob('*.pdf')):
 dest=p.with_suffix('.text.json')
 if dest.exists():continue
 script='ObjC.import("Foundation"); ObjC.import("PDFKit"); var d=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath('+json.dumps(str(p))+')); var a=[]; for(var i=0;i<d.pageCount;i++){a.push({page:i+1,text:ObjC.unwrap(d.pageAtIndex(i).string)})}; JSON.stringify({pages:a});'
 try:
  proc=subprocess.run(['/usr/bin/osascript','-l','JavaScript','-e',script],capture_output=True,text=True,check=True,timeout=30);data=json.loads(proc.stdout)
  data['source_sha256']=sha(p);data['extraction_warning']=proc.stderr.strip()
  data['text_extraction_ok']=sum(len(x.get('text') or '') for x in data['pages'])>100
  save(dest,data);print('text',p.stem,len(data['pages']),data['text_extraction_ok'],flush=True)
 except Exception as e:stop('extract',p.stem,e)
unchanged();save(O/'ACQUISITION_SUMMARY.json',{'finished':now(),'elapsed_s':time.monotonic()-start,'new_requests':counts,'raw_files':len(list((O/'raw').glob('*.json'))),'notice_queries':len(list((O/'notices').glob('*.json')))-1,'pdf_files':len(list((O/'notice_pdf').glob('*.pdf'))),'target_exact_hits':coverage,'source_inputs_unchanged':True,'strategy_runs':0})
print(json.dumps(counts),flush=True)
