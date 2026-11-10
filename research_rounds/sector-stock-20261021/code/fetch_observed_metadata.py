"""Single-attempt public observed query; no cookies/auth, no redirects or retries."""
import argparse
from pathlib import Path
from datetime import datetime
import hashlib
import json
import requests

def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();raw=args.plan.read_bytes();plan=json.loads(raw)
    urls=plan['initial_public_urls'];assert len(urls)<=plan['budget']['public_http_gets_max']
    assert plan['budget']['public_before']+len(urls)<=plan['budget']['public_parent_limit']
    assert set(plan.get('headers',{})) <= {'Referer'}
    args.out.mkdir(parents=True,exist_ok=False)
    record={'created_at':datetime.now().astimezone().isoformat(),'plan_sha256':hashlib.sha256(raw).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'credentials_used':False,'requests':[]}
    for n,url in enumerate(urls,1):
        row={'sequence':n,'url':url}
        try:
            headers={'User-Agent':'Mozilla/5.0 TradingAlarm-public-metadata-research',**plan.get('headers',{})}
            with requests.get(url,headers=headers,timeout=20,stream=True,allow_redirects=False) as response:
                b=bytearray()
                for chunk in response.iter_content(65536):
                    b.extend(chunk)
                    if len(b)>15_000_000: raise ValueError('response exceeds budget')
                name=f'{n:02d}.body'
                with (args.out/name).open('xb') as f:f.write(b)
                row.update(status=response.status_code,content_type=response.headers.get('Content-Type'),bytes=len(b),response=name,sha256=hashlib.sha256(b).hexdigest(),redirects=0)
        except Exception as e:row.update(error_type=type(e).__name__)
        record['requests'].append(row)
        (args.out/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(row,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
