from pathlib import Path
import json,time,datetime,requests
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1/share_action_field_feasibility_v1')
assert not (O/'ANNOUNCEMENT_QUERY_SAMPLE.json').exists()
samples=[('603005','2022-05-16'),('000672','2022-05-24'),('300655','2022-06-02'),('688300','2022-11-02')]
def fetch(method,url,**kw):
 r=requests.request(method,url,timeout=20,**kw);r.raise_for_status();o=r.json()
 time.sleep(.5);return o
obj=fetch('GET','https://www.cninfo.com.cn/new/data/szse_stock.json')
mp={r['code']:r['orgId'] for r in obj['stockList']}
out=[]
for code,date in samples:
 assert code in mp
 data={'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'','stock':code+','+mp[code],'searchkey':'实施','secid':'','category':'category_qyfpxzcs_szsh','trade':'','seDate':date+'~'+date,'sortName':'','sortType':'','isHLtitle':'false'}
 try:
  raw=fetch('POST','https://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
  assert isinstance(raw,dict) and isinstance(raw.get('announcements'),list)
  assert raw.get('totalpages',1)<=1 and len(raw['announcements'])<=30
  item={'code':code,'date':date,'endpoint':'https://www.cninfo.com.cn/new/hisAnnouncement/query','params':data,'response':raw}
  out.append(item)
  print(json.dumps({'code':code,'total':raw.get('totalAnnouncement'),'items':[{k:a.get(k) for k in ('secCode','secName','announcementTitle','announcementId','adjunctUrl','announcementTime')} for a in raw['announcements']]},ensure_ascii=False),flush=True)
 except Exception as e:
  (O/'ANNOUNCEMENT_QUERY_STOP.json').write_text(json.dumps({'code':code,'error_type':type(e).__name__,'error':str(e)[:400],'outcome':'stopped, no retry or alternate route'},ensure_ascii=False),encoding='utf-8')
  raise
(O/'ANNOUNCEMENT_QUERY_SAMPLE.json').write_text(json.dumps({'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'samples':out,'request_count':1+len(out),'scope':'Four notice index samples, no full-50 query'},ensure_ascii=False,indent=2),encoding='utf-8')
