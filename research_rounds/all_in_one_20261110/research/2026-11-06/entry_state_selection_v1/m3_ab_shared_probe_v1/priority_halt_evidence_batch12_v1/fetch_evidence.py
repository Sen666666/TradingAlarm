import json,pathlib,datetime,urllib.request,hashlib,sys,re,subprocess
O=pathlib.Path(__file__).parent
def fetch(label,url):
 c=json.loads((O/'BATCH_CONTROL.json').read_text()); assert c['document_reads']<48 and c['search_requests']<24, 'STOP: A bound reached'
 n=c['document_reads']+1;c['document_reads']=n;(O/'BATCH_CONTROL.json').write_text(json.dumps(c,ensure_ascii=False,indent=2))
 row={'kind':'document_read','number':n,'label':label,'url':url,'requested_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
  r=subprocess.run(["/usr/bin/curl","-fLsS","--max-time","35","-A","Mozilla/5.0",url],capture_output=True,check=True); data=r.stdout; row.update(status="curl_success",final_url=url,transport="system curl, TLS validation enabled")
  ext='pdf' if data.startswith(b'%PDF') else 'html'; p=O/'raw'/f'{n:02d}_{label}.{ext}';p.write_bytes(data)
  row.update(path=str(p),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
  if ext=='pdf':
   text=subprocess.run([str(O/'extract_pdf'),str(p)],capture_output=True,text=True,check=True).stdout
  else:
   from bs4 import BeautifulSoup
   html=data.decode('utf-8',errors='replace')
   if html.count('�')>10:
    html=data.decode('gb18030',errors='replace')
   soup=BeautifulSoup(html,'html.parser')
   for tag in soup(['script','style']): tag.decompose()
   text=soup.get_text('\n',strip=True)
  (O/'texts'/f'{n:02d}_{label}.txt').write_text(text);row['text_path']=str(O/'texts'/f'{n:02d}_{label}.txt')
  print(json.dumps({k:row.get(k) for k in ['number','label','status','bytes','sha256']},ensure_ascii=False),flush=True)
 except Exception as e: row['error']=repr(e);print(json.dumps(row,ensure_ascii=False),flush=True)
 row['completed_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (O/'REQUEST_LEDGER.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
if __name__=='__main__':
 for label,url in json.loads(sys.argv[1]): fetch(label,url)
