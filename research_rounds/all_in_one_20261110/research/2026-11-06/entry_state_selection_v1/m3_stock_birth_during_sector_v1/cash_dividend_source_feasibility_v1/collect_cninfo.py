"""Bounded read-only CNINFO acquisition. No strategy simulation, tax estimate or historical edits."""
from pathlib import Path
import sys,json,time,hashlib,datetime,csv
import pandas as pd
import requests
from akshare.stock.stock_dividend_cninfo import stock_dividend_cninfo
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
INPUT=BASE/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv'
SAMPLE=['300390.SZ','000708.SZ','000895.SZ','600298.SH','603303.SH','600276.SH','688303.SH','688206.SH','000651.SZ','003006.SZ','301286.SZ','603515.SH','002315.SZ']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def iso(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def main():
 mode=sys.argv[1]
 assert mode in ('sample','remaining')
 d=pd.read_csv(INPUT)
 target=d[(d.status=='FACTOR_PATH_UNKNOWN')&(d.split_ratio==1)&(d.cash_per_old_share>0)].copy()
 assert len(target)==426 and target.sid.nunique()==426
 target=target.sort_values(['status_day','sid'])
 seal=ROOT/'PRE_RUN_SEAL.json'
 if not seal.exists():
  files=[INPUT,BASE/'lifecycle_v1/ROUNDS.csv',BASE/'lifecycle_v1/ACTIONS.csv',BASE/'lifecycle_v1/simulate.py',Path(__file__)]
  dump(seal,{'created_utc':iso(),'purpose':'Company public-fact collection only, never promote tax assumptions or rerun strategy.','source_hashes':{str(p):sha(p) for p in files},'targets':target[['round_id','sid','name','status_day','cash_per_old_share','split_ratio']].to_dict('records'),'sample_symbols':SAMPLE,'limits':{'requests':'sequential','minimum_pause_s':0.5,'timeout_s':20,'retry':0,'stop_on':'any request error, HTTP denial/rate limit, non-JSON response or unexpected API schema'}})
 else:
  old=json.loads(seal.read_text())
  assert all(sha(Path(p))==h for p,h in old['source_hashes'].items()),'frozen input/code changed'
 if mode=='remaining':
  a=ROOT/'SAMPLE_INDEPENDENT_AUDIT.json'
  assert a.exists() and json.loads(a.read_text()).get('batch_acquisition_permitted') is True,'sample independent gate absent'
 root=ROOT/'raw'; root.mkdir(exist_ok=True)
 wanted=target[target.sid.isin(SAMPLE)] if mode=='sample' else target
 existing={p.stem for p in root.glob('*.json')}
 original=requests.sessions.Session.request
 captures=[]
 def bounded(self,method,url,**kw):
  if url!='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139': raise RuntimeError('unexpected destination')
  kw.setdefault('timeout',20)
  t=time.monotonic(); response=original(self,method,url,**kw)
  captures.append({'status_code':response.status_code,'elapsed_s':time.monotonic()-t,'body_text':response.text})
  response.raise_for_status()
  return response
 requests.sessions.Session.request=bounded
 begin=time.monotonic(); n=0
 for _,row in wanted.iterrows():
  sid=row.sid
  if sid in existing: continue
  captures.clear(); started=iso()
  try:
   frame=stock_dividend_cninfo(sid[:6])
   assert len(captures)==1,'unexpected request count'
   cap=captures[0]; raw=json.loads(cap.pop('body_text'))
   assert isinstance(raw,dict) and isinstance(raw.get('records'),list),'unexpected schema'
   blob={'sid':sid,'requested_code':sid[:6],'retrieved_at_utc':started,'endpoint':'https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139','params':{'scode':sid[:6]},'transport':cap,'raw':raw,'source_time_status':'current retrieval of historical records; not an archived point-in-time snapshot'}
   dump(root/(sid+'.json'),blob)
   n+=1
   print(json.dumps({'sid':sid,'status':'saved','rows':len(frame),'elapsed_s':cap['elapsed_s'],'completed_this_run':n},ensure_ascii=False),flush=True)
  except Exception as e:
   # Public data query only; never dump headers, request secrets or local environment.
   error={'sid':sid,'mode':mode,'at_utc':started,'error_type':type(e).__name__,'error':str(e)[:600],'transport_status':captures[-1]['status_code'] if captures else None,'outcome':'stopped, no retry and no alternate access route'}
   dump(ROOT/('STOP_'+sid+'.json'),error);print(json.dumps(error,ensure_ascii=False),flush=True);break
  time.sleep(.5)
 dump(ROOT/('RUN_'+mode+'.json'),{'finished_utc':iso(),'requested_symbols':len(wanted),'completed_new':n,'existing_at_start':len(existing),'elapsed_s':time.monotonic()-begin,'frozen_inputs_unchanged':all(sha(Path(p))==h for p,h in json.loads(seal.read_text())['source_hashes'].items())})

if __name__=='__main__':main()
