import pathlib,json,sys,subprocess,hashlib,datetime,time,urllib.parse
O=pathlib.Path(__file__).parent
kind,name,url,*extra=sys.argv[1:]
assert kind in ['search_index_api','document']
host=urllib.parse.urlsplit(url).hostname
assert host and (host.endswith('.szse.cn') or host.endswith('.sse.com.cn'))
ledger=[json.loads(s) for s in (O/'REQUEST_LEDGER.jsonl').read_text().splitlines() if s]
assert sum(r['category']==kind for r in ledger)<((json.loads((O/'PLAN_AMENDMENT.json').read_text())['amended_request_cap'] if (O/'PLAN_AMENDMENT.json').exists() else 20) if kind=='search_index_api' else 24)
assert len(ledger)<45
p=O/'raw'/name; assert not p.exists()
start=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic()
cmd=['/usr/bin/curl','--silent','--show-error','--max-time','35','--connect-timeout','12','--max-redirs','0','--dump-header',str(p)+'.headers','--output',str(p),'--write-out','%{http_code}']
if extra: cmd+=['--referer',extra[0]]
if len(extra)>1: cmd+=['--header','Content-Type: application/json','--data-raw',extra[1]]
cmd+=[url]
r=subprocess.run(cmd,capture_output=True,text=True)
record={'id':len(ledger)+1,'category':kind,'name':name,'url':url,'referer':extra[0] if extra else None,'requested_at':start,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':round(time.monotonic()-t,3),'http_status':r.stdout,'curl_exit_code':r.returncode,'stderr':r.stderr,'path':str(p),'bytes':p.stat().st_size if p.exists() else 0,'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,'tls_verification_disabled':False,'automatic_redirects':False,'automatic_retries':False,'credentials_used':False,'method':'POST' if len(extra)>1 else 'GET','body':json.loads(extra[1]) if len(extra)>1 else None}
with (O/'REQUEST_LEDGER.jsonl').open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
print(json.dumps(record,ensure_ascii=False))
