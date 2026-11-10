from pathlib import Path
import json,requests,time,hashlib
O=Path(__file__).resolve().parent;N=O/'notices';P=O/'notice_pdf';P.mkdir(exist_ok=True)
for fn in sorted(N.glob('*.json')):
 if fn.name=='stock_map.json':continue
 b=json.loads(fn.read_text())
 if 'api_response' not in b:continue
 c=[a for a in b['api_response']['announcements'] if '实施' in a['announcementTitle'] and any(x in a['announcementTitle'] for x in ['权益分派','利润分配','股息分派','分红派息'])]
 assert len(c)==1,(fn,c);a=c[0];sid=b['requested_sid'];dest=P/(sid+'.pdf')
 if dest.exists():continue
 assert a['secCode']==sid[:6] and a['adjunctUrl'].startswith('finalpage/2022-')
 url='https://static.cninfo.com.cn/'+a['adjunctUrl']
 try:
  r=requests.get(url,timeout=20);r.raise_for_status();assert r.content.startswith(b'%PDF') and len(r.content)<10_000_000
  dest.write_bytes(r.content);(P/(sid+'.json')).write_text(json.dumps({'url':url,'metadata':a,'sha256':hashlib.sha256(r.content).hexdigest()},ensure_ascii=False,indent=2)+'\n');print(sid,len(r.content),flush=True)
 except Exception as e:(P/'STOP.json').write_text(json.dumps({'sid':sid,'error':str(e),'no_retry':True}));raise
 time.sleep(.5)
