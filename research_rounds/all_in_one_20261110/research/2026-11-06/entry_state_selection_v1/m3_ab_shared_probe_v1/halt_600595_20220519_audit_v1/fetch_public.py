import pathlib,json,sys,subprocess,hashlib,datetime,time,urllib.parse
O=pathlib.Path(__file__).parent
kind,name,url,*extra=sys.argv[1:];assert kind in ['query','document']
host=urllib.parse.urlsplit(url).hostname;assert host and any(host==d or host.endswith('.'+d) for d in ['sse.com.cn','cninfo.com.cn','cls.cn','sohu.com','dfcfw.com','cs.com.cn','cnstock.com','sfccn.com'])
a=[json.loads(s) for s in (O/'REQUEST_LEDGER.jsonl').read_text().splitlines() if s];assert sum(r['category']==kind for r in a)<(4 if kind=='query' else 6)
p=O/'raw'/name;assert not p.exists();t=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
cmd=['/usr/bin/curl','--silent','--show-error','--max-time','30','--connect-timeout','12','--max-redirs','0','--dump-header',str(p)+'.headers','--output',str(p),'--write-out','%{http_code}']
if extra:cmd+=['--referer',extra[0]]
cmd+=[url];r=subprocess.run(cmd,capture_output=True,text=True)
row={'id':len(a)+1,'category':kind,'name':name,'url':url,'requested_at':started,'elapsed_seconds':round(time.monotonic()-t,3),'http_status':r.stdout,'curl_exit_code':r.returncode,'stderr':r.stderr,'path':str(p),'bytes':p.stat().st_size if p.exists() else 0,'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,'tls_default':True,'auto_redirect':False,'auto_retry':False}
with (O/'REQUEST_LEDGER.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
print(json.dumps(row,ensure_ascii=False))
