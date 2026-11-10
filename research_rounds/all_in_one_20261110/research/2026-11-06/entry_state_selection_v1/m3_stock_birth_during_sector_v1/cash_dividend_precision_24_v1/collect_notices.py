"""Bounded official public announcement read. No simulations or source edits."""
from pathlib import Path
import requests,json,time,sys,datetime
import pandas as pd
O=Path(__file__).resolve().parent;F=O.parent/'cash_dividend_source_feasibility_v1/PRECISION_DIFFERENCES.csv'
mode=sys.argv[1];assert mode in ['sample','remaining'];target=pd.read_csv(F);assert len(target)==24
out=O/'notices';out.mkdir(exist_ok=True)
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def req(method,url,**kw):
 r=requests.request(method,url,timeout=20,**kw);r.raise_for_status();return r
if not (out/'stock_map.json').exists():
 try:save(out/'stock_map.json',req('GET','https://www.cninfo.com.cn/new/data/szse_stock.json').json())
 except Exception as e:save(out/'STOP.json',{'phase':'stock_map','error':str(e),'no_retry':True});raise
mp={x['code']:x for x in json.loads((out/'stock_map.json').read_text())['stockList']}
rows=target[target.sid.isin(['002056.SZ','000060.SZ','300002.SZ'])] if mode=='sample' else target
for _,r in rows.iterrows():
 fn=out/(r.sid+'.json')
 if fn.exists():continue
 day=pd.Timestamp(r.implementation_announcement_date);start=(day-pd.Timedelta(days=1)).strftime('%Y-%m-%d');end=(day+pd.Timedelta(days=1)).strftime('%Y-%m-%d');m=mp[r.sid[:6]]
 payload={'pageNum':1,'pageSize':30,'column':'szse','tabName':'fulltext','plate':'','stock':r.sid[:6]+','+m['orgId'],'searchkey':'','secid':'','category':'','trade':'','seDate':start+'~'+end,'sortName':'','sortType':'','isHLtitle':'true'}
 try:
  raw=req('POST','https://www.cninfo.com.cn/new/hisAnnouncement/query',data=payload).json();assert isinstance(raw.get('announcements'),list) and int(raw['totalAnnouncement'])<=30,'unexpected schema or pagination'
  candidates=[a for a in raw['announcements'] if '实施' in a['announcementTitle'] and any(x in a['announcementTitle'] for x in ['权益分派','利润分配','股息分派'])]
  assert all(x['secCode']==r.sid[:6] for x in candidates)
  save(fn,{'retrieved_at_utc':str(pd.Timestamp.now(tz='UTC')),'requested_sid':r.sid,'original_target_ex_date':r.status_day,'params':payload,'api_response':raw,'implementation_candidates':candidates,'current_retrieval_not_PIT':True});print(r.sid,len(raw['announcements']),'candidates',len(candidates),flush=True)
 except Exception as e:save(out/'STOP.json',{'phase':mode,'sid':r.sid,'error':str(e),'no_retry':True});raise
 time.sleep(.5)
