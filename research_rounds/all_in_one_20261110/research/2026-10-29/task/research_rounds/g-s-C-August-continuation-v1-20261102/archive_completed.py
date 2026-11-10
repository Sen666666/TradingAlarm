"""Lossless storage of OWN completed output bytes; never source/current state.
Every original SHA is retained and verified by gzip readback before replacing
the uncompressed copy. Original July archives, Aug1 gates, current day, imports,
BEFORE_EVENT and progress/provenance/flow files are never touched.
"""
from pathlib import Path
import argparse,hashlib,gzip,json,os,tempfile,time
P=Path(__file__).resolve().parent;MAN=P/'LOSSLESS_OUTPUT_ARCHIVE.json'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(x):
 fd,p=tempfile.mkstemp(dir=P,prefix='.archive-',suffix='.json');os.close(fd)
 Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(p,MAN)
def once():
 m=json.loads(MAN.read_text()) if MAN.exists() else dict(scope='own completed output bytes only; no financial events',entries={})
 for cell in ['C10','C20','C10_R0','C20_R0']:
  root=P/'runs'/cell;q=root/'PROGRESS.json'
  if not q.exists():continue
  day=json.loads(q.read_text())['cursor'][:10]
  for f in sorted(root.glob('2025-08-*')):
   if f.suffix not in ('.pkl','.json') or f.stem.split('-')[-1] not in ('ACTION','OPEN','CLOSE'):continue
   if f.name[:10]=='2025-08-01' or f.name[:10]>=day:continue
   key=str(f.relative_to(P));out=f.with_suffix(f.suffix+'.gz')
   assert key not in m['entries'] and not out.exists(),'unexpected prior archive without raw replacement'
   before=sha(f)
   if f.suffix=='.pkl':assert before==json.loads(f.with_suffix('.provenance.json').read_text())['checkpoint_sha256']
   tmp=out.with_suffix(out.suffix+'.tmp')
   with f.open('rb') as src,gzip.open(tmp,'wb',compresslevel=1) as dst:
    for b in iter(lambda:src.read(4*1024*1024),b''):dst.write(b)
   h=hashlib.sha256()
   with gzip.open(tmp,'rb') as chk:
    for b in iter(lambda:chk.read(4*1024*1024),b''):h.update(b)
   assert h.hexdigest()==before and sha(f)==before,'archive roundtrip mismatch'
   os.replace(tmp,out)
   m['entries'][key]=dict(archive=str(out.relative_to(P)),original_sha256=before,original_bytes=f.stat().st_size,gzip_sha256=sha(out),gzip_bytes=out.stat().st_size,exact_roundtrip_verified=True,restore='gzip -dc archive > original-path; verify original_sha256 before native restore')
   write(m);f.unlink()
   print('LOSSLESS_ARCHIVED',key,'saved_MB',round((m['entries'][key]['original_bytes']-out.stat().st_size)/1e6,1),flush=True)
 return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--watch',action='store_true');a=ap.parse_args()
 while True:
  m=once()
  if not a.watch or all((P/'runs'/c/'COMPLETED.json').exists() for c in ['C10','C20','C10_R0','C20_R0']):break
  time.sleep(20)
 print('ARCHIVE_SAFE',len(m['entries']),flush=True)
if __name__=='__main__':main()
