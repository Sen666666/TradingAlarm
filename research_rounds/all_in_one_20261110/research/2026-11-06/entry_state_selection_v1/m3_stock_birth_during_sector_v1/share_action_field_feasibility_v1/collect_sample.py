"""Six fixed samples only: public issuer fact retrieval, no strategy execution."""
from pathlib import Path
from decimal import Decimal as D
import json,time,hashlib,datetime
import pandas as pd,requests
from akshare.stock.stock_dividend_cninfo import stock_dividend_cninfo
B=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1')
O=B/'share_action_field_feasibility_v1'
S=['603938.SH','603005.SH','000672.SZ','300655.SZ','688378.SH','688300.SH']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
d=pd.read_csv(B/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv')
t=d[(d.status=='FACTOR_PATH_UNKNOWN')&(d.split_ratio!=1)]
assert len(t)==50 and t.sid.nunique()==50
assert not O.exists(),'Do not overwrite'
O.mkdir();(O/'raw').mkdir()
files=[B/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv',B/'lifecycle_v1/ROUNDS.csv',B/'lifecycle_v1/ACTIONS.csv',B/'lifecycle_v1/simulate.py']
seal={'created_utc':now(),'scope':'Six fixed cross-market share-action samples only. No strategy, no factor/source edits, no full-50 acquisition.','targets':t[['sid','name','status_day','cash_per_old_share','split_ratio']].to_dict('records'),'sample':S,'source_hashes':{str(p):sha(p) for p in files},'limits':{'max_requests':6,'pause_seconds':0.5,'timeout_seconds':20,'retries':0,'stop_on':'any error, denial or unexpected schema'}}
write(O/'PRE_RUN_SEAL.json',seal)
orig=requests.sessions.Session.request
caps=[]
def bounded(self,method,url,**kw):
 assert url=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139'
 kw['timeout']=20
 start=time.monotonic();r=orig(self,method,url,**kw)
 caps.append({'http_status':r.status_code,'elapsed_s':time.monotonic()-start,'body':r.text})
 r.raise_for_status();return r
requests.sessions.Session.request=bounded
res=[];start=time.monotonic()
for sid in S:
 row=t[t.sid==sid].iloc[0];caps.clear()
 try:
  stock_dividend_cninfo(sid[:6])
  assert len(caps)==1
  c=caps[0];raw=json.loads(c.pop('body'))
  assert raw.get('resultcode')==200 and isinstance(raw.get('records'),list)
  write(O/'raw'/(sid+'.json'),{'sid':sid,'requested_code':sid[:6],'retrieved_at_utc':now(),'endpoint':'https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139','params':{'scode':sid[:6]},'transport':c,'raw':raw,'source_time_status':'Current historical response, not an archived PIT snapshot'})
  hits=[r for r in raw['records'] if r.get('F020D')==row.status_day]
  item={'sid':sid,'name':row['name'],'ex_date':row.status_day,'old_split_ratio':row.split_ratio,'old_cash_per_share':row.cash_per_old_share,'exact_matches':len(hits)}
  if len(hits)==1:
   r=hits[0]
   ratio=D(1)+(D(str(r.get('F010N') or 0))+D(str(r.get('F011N') or 0)))/D(10)
   cash=D(str(r.get('F012N') or 0))/D(10)
   item.update(r);item.update({'source_split_ratio':float(ratio),'source_gross_cash_per_share':float(cash),'split_delta':str(ratio-D(str(row.split_ratio))),'cash_delta':str(cash-D(str(row.cash_per_old_share))),'F025D_is_sellability_proof':False})
  res.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
 except Exception as e:
  write(O/'STOP.json',{'sid':sid,'error_type':type(e).__name__,'error':str(e)[:400],'at_utc':now(),'outcome':'Stopped, no retry/alternate route'});raise
 time.sleep(.5)
pd.DataFrame(res).to_csv(O/'SAMPLE_FIELD_COVERAGE.csv',index=False)
write(O/'RUN_SAMPLE.json',{'completed':len(res),'elapsed_seconds':time.monotonic()-start,'frozen_inputs_unchanged':all(sha(Path(p))==h for p,h in seal['source_hashes'].items()),'full_50_not_acquired':True,'strategy_runs':0})
