"""Read-only loopback viewer; no endpoints can mutate research or accounts."""
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import argparse,mimetypes
WEB=Path(__file__).resolve().parent/'web'
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k):super().__init__(*a,directory=str(WEB),**k)
 def send_head(self):
  path=Path(self.translate_path(self.path.split('?',1)[0]));compressed=path.with_suffix(path.suffix+'.gz')
  if path.suffix=='.json' and compressed.is_file() and WEB.resolve() in compressed.resolve().parents:
   f=compressed.open('rb');self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Encoding','gzip');self.send_header('Content-Length',str(compressed.stat().st_size));self.send_header('Cache-Control','public,max-age=3600');self.end_headers();return f
  return super().send_head()
 def end_headers(self):
  self.send_header('X-Content-Type-Options','nosniff');super().end_headers()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8810);args=p.parse_args();server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);print(f'Trade atlas: http://127.0.0.1:{server.server_address[1]}/',flush=True);server.serve_forever()
