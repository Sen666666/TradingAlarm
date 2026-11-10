"""Read-only official facts. Writes new evidence only; never imports/runs a strategy."""
from pathlib import Path
import csv,json,time,hashlib,datetime,sys
import requests
from akshare.stock.stock_dividend_cninfo import stock_dividend_cninfo
O=Path(__file__).resolve().parent; B=O.parent
T=B/'relative_priority_equity_rebuild_v1/FIRST_ACTION_EVENTS_2024.csv'
OLD=B/'cash_dividend_source_feasibility_v1/raw'
SAMPLE=['300866.SZ','301310.SZ','688008.SH','600004.SH','002648.SZ','601916.SH','688005.SH','603986.SH']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
rows=list(csv.DictReader(T.open()));assert len(rows)==167 and len({r['sid'] for r in rows})==167
inputs=[T,B/'relative_priority_equity_rebuild_v1/COVERAGE_SUMMARY.json',B/'relative_priority_equity_run_2022_v1/engine.py']
seal=O/'SOURCE_SEAL.json'
if not seal.exists():save(seal,{'created_at':now(),'sources':{str(p):sha(p) for p in inputs},'targets':rows,'limits':{'sequential':True,'timeout':20,'retry':0,'pause_seconds':0.5,'stop_on':'any HTTP denial, exception, non-JSON or unexpected schema'},'backtest_runs':0})
assert all(sha(Path(p))==h for p,h in json.loads(seal.read_text())['sources'].items())
mode=sys.argv[1];assert mode in ('sample','remaining')
if mode=='remaining':assert json.loads((O/'SAMPLE_REVIEW.json').read_text())['batch_acquisition_permitted'] is True
out=O/'raw';out.mkdir(exist_ok=True)
missing=[r for r in rows if not (OLD/(r['sid']+'.json')).exists()]
if mode=='sample':
 # Fixed first six chronological missing rows plus late dates and the unsupported share event.
 selected=missing[:6]+[next(r for r in missing if r['sid']=='688005.SH')]+[missing[-1]]
else:selected=missing
orig=requests.sessions.Session.request;caps=[]
def bounded(self,method,url,**kw):
 if url!='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139':raise RuntimeError('unexpected destination')
 kw['timeout']=20;t=time.monotonic();r=orig(self,method,url,**kw);caps.append({'status_code':r.status_code,'elapsed_s':time.monotonic()-t,'body_text':r.text});r.raise_for_status();return r
requests.sessions.Session.request=bounded
n=0;started=time.monotonic()
for row in selected:
 sid=row['sid'];p=out/(sid+'.json')
 if p.exists():continue
 caps.clear()
 try:
  fetched=now();frame=stock_dividend_cninfo(sid[:6]);assert len(caps)==1
  cap=caps[0];raw=json.loads(cap.pop('body_text'));assert isinstance(raw,dict) and isinstance(raw.get('records'),list)
  assert raw.get('resultcode')==200 and raw.get('count')==len(raw['records']) and raw.get('total')==len(raw['records'])
  blob={'sid':sid,'requested_code':sid[:6],'retrieved_at_utc':fetched,'endpoint':'https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139','params':{'scode':sid[:6]},'transport':cap,'raw':raw,'source_time_status':'current retrieval of historical records; not archived PIT'}
  save(p,blob);n+=1;print(sid,len(frame),'saved',flush=True)
 except Exception as e:
  error={'sid':sid,'error_type':type(e).__name__,'error':str(e)[:500],'transport_status':caps[-1]['status_code'] if caps else None,'at':now(),'no_retry':True};save(O/'STOP_FACTS.json',error);print(error,flush=True);break
 time.sleep(.5)
save(O/('RUN_'+mode+'.json'),{'completed_new':n,'selected':len(selected),'all_missing':len(missing),'elapsed_s':time.monotonic()-started,'sources_unchanged':all(sha(Path(p))==h for p,h in json.loads(seal.read_text())['sources'].items()),'backtest_runs':0})
