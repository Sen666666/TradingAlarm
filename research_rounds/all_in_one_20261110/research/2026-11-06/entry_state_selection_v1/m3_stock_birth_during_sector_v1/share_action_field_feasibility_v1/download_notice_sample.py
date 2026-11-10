from pathlib import Path
import json,time,requests,hashlib,datetime
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1/share_action_field_feasibility_v1')
D=O/'notices';assert not D.exists();D.mkdir()
j=json.loads((O/'ANNOUNCEMENT_QUERY_SAMPLE.json').read_text())
out=[]
for q in j['samples']:
 a=q['response']['announcements']
 assert len(a)==1
 url='https://static.cninfo.com.cn/'+a[0]['adjunctUrl']
 r=requests.get(url,timeout=20);r.raise_for_status()
 assert r.content.startswith(b'%PDF-') and len(r.content)<5000000
 p=D/(q['code']+'.pdf');p.write_bytes(r.content)
 out.append({'code':q['code'],'url':url,'http_status':r.status_code,'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
 print(json.dumps(out[-1]),flush=True);time.sleep(.5)
(O/'PDF_SOURCE_MANIFEST.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
