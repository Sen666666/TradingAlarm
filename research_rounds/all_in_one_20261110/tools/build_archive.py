#!/usr/bin/env python3
"""One-time non-destructive APFS snapshot builder. Refuses existing payload paths."""
import csv,ctypes,datetime,hashlib,json,os,pathlib,stat,time
import argparse, sys
from archive_paths import validate_map

def configure():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--source-map',required=True,help='JSON source roots and archive-relative destinations')
 ap.add_argument('--output',required=True,help='A NEW archive directory; existing targets refused')
 ap.add_argument('--dry-run',action='store_true',help='Validate and print plan without creating files')
 args=ap.parse_args()
 try:
  root=pathlib.Path(args.output).expanduser().resolve()
  rows=validate_map(json.loads(pathlib.Path(args.source_map).expanduser().read_text())['roots'])
  rows=[dict(x,source=str(pathlib.Path(x['source']).resolve())) for x in rows]
  validate_map(rows)
  projects=[pathlib.Path(x['source']) for x in rows if x['destination']=='project' and x['kind']=='directory']
  if len(projects)!=1:raise ValueError('Exactly one directory mapping to project is required')
  if root.exists():raise ValueError('Output already exists; choose a new directory')
  if not root.parent.is_dir():raise ValueError('Output parent directory must exist')
  for item in rows:
   source=pathlib.Path(item['source'])
   if not (source.is_file() if item['kind']=='file' else source.is_dir()):raise ValueError('Missing source: '+str(source))
   if source.resolve()==root or source.resolve().is_relative_to(root):raise ValueError('Source cannot be inside output')
  if args.dry_run:
   print(json.dumps({'dry_run':True,'output':str(root),'roots':rows,'files_created':0},indent=2));sys.exit(0)
  if sys.platform!='darwin':raise ValueError('APFS clone builder requires macOS; no full-copy fallback')
  root.mkdir(exist_ok=False);(root/'manifest').mkdir()
  return root,projects[0],rows
 except (OSError,ValueError,KeyError,TypeError) as e:ap.error(str(e))

ROOT,SOURCE,MAP=configure()
EXDIR={'.git','.venv','venv','__pycache__','.cache','.codex','.handoff','.tools','private'}
EXFILE={'.DS_Store','settings.json'}
lib=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
lib.clonefile.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
lib.clonefile.restype=ctypes.c_int

def write_new(p,obj):
 with p.open('x') as f: json.dump(obj,f,ensure_ascii=False,indent=2)

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()

def mapped(s):
 s=pathlib.Path(s)
 for x in MAP:
  p=pathlib.Path(x['source'])
  if s==p:return ROOT/x['destination']
  if x['kind']=='directory' and s.is_relative_to(p):return ROOT/x['destination']/s.relative_to(p)
 return None

def excluded(p):
 if p==ROOT or p.is_relative_to(ROOT):return 'avoid_self_recursion'
 if p.name in EXDIR:return 'environment_private_or_cache_directory'
 if p.name in EXFILE or p.name=='.env' or p.name.startswith('.env.') or p.suffix in {'.pyc','.pyo'}:return 'private_settings_or_cache_file'
 rt=SOURCE/'TradingAlarm/runtime'
 if p.is_relative_to(rt) and p!=rt and not p.is_relative_to(rt/'market'):return 'live_or_paper_account_runtime_not_research_market_data'
 return None

started=datetime.datetime.now(datetime.timezone.utc).isoformat(); free0=os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize
write_new(ROOT/'manifest/SOURCE_MAP.json',{'project_root_is_parent_of_manifest':True,'created_utc':started,'roots':MAP})
(ROOT/'.gitignore').write_text('*\n!.gitignore\n')
fields=['source','destination','kind','bytes','mtime_ns','method','sha256','source_stable','same_inode','original_link','resolved_target']
counts={}; errors=[]; syms=[]; excluded_rows=[]; n=0; bytecount=0; hashcount=0
with (ROOT/'manifest/FILES.csv').open('x',newline='') as mf:
 w=csv.DictWriter(mf,fieldnames=fields);w.writeheader()
 for group in MAP:
  srcroot=pathlib.Path(group['source']); dstroot=ROOT/group['destination']; counts[group['destination']]={'files':0,'bytes':0,'sha256_checked':0}
  if group['kind']=='file': walks=[(srcroot.parent,[],[srcroot.name])]
  else:
   dstroot.mkdir(parents=True,exist_ok=False);walks=os.walk(srcroot,followlinks=False)
  print('BEGIN',srcroot,flush=True)
  for folder,dirs,files in walks:
   folder=pathlib.Path(folder)
   keep=[]
   for d in dirs:
    p=folder/d;r=excluded(p)
    if r:excluded_rows.append([str(p),r]);continue
    if p.is_symlink():syms.append(p);continue
    target=mapped(p);target.mkdir(parents=True,exist_ok=False);keep.append(d)
   dirs[:]=keep
   for f in files:
    p=folder/f;r=excluded(p)
    if r:excluded_rows.append([str(p),r]);continue
    if p.is_symlink():syms.append(p);continue
    a=p.stat()
    if not stat.S_ISREG(a.st_mode):excluded_rows.append([str(p),'non_regular_file']);continue
    q=mapped(p);q.parent.mkdir(parents=True,exist_ok=True)
    if q.exists() or q.is_symlink():raise RuntimeError('Refuse overwrite '+str(q))
    if os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize<8*1024**3:raise RuntimeError('Free disk below 8GiB safety floor')
    rc=lib.clonefile(os.fsencode(p),os.fsencode(q),0)
    if rc:raise OSError(ctypes.get_errno(),'clonefile failed; no full-copy fallback',str(p))
    b=p.stat();c=q.stat();stable=(a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(b.st_size,b.st_mtime_ns,b.st_ctime_ns)
    digest=''
    if p.suffix.lower() in {'.py','.md','.txt','.toml','.yaml','.yml','.sh','.command'} and a.st_size<=2*1024**2:
     digest=sha(q)
     if digest!=sha(p):raise RuntimeError('SHA mismatch '+str(p))
     hashcount+=1;counts[group['destination']]['sha256_checked']+=1
    if c.st_size!=a.st_size or c.st_ino==a.st_ino or not stable:errors.append({'source':str(p),'reason':'metadata_or_stability_failure'})
    w.writerow(dict(source=str(p),destination=str(q.relative_to(ROOT)),kind='file',bytes=c.st_size,mtime_ns=c.st_mtime_ns,method='APFS_clonefile_independent_inode',sha256=digest,source_stable=stable,same_inode=c.st_ino==a.st_ino))
    n+=1;bytecount+=c.st_size;counts[group['destination']]['files']+=1;counts[group['destination']]['bytes']+=c.st_size
    if n%10000==0:mf.flush();print('PROGRESS',n,round(bytecount/1024**3,2),'GiB',flush=True)
  print('END',group['destination'],counts[group['destination']],flush=True)
 for p in syms:
  q=mapped(p);q.parent.mkdir(parents=True,exist_ok=True);target=p.resolve();mt=mapped(target);old=os.readlink(p)
  if not target.exists() or mt is None or not mt.exists():
   errors.append({'source':str(p),'reason':'unresolved_symlink','target':str(target)});continue
  new=os.path.relpath(mt,q.parent);os.symlink(new,q)
  if q.resolve()!=mt.resolve():raise RuntimeError('symlink verification failed')
  w.writerow(dict(source=str(p),destination=str(q.relative_to(ROOT)),kind='symlink',bytes=target.stat().st_size,method='internal_relative_symlink',original_link=old,resolved_target=str(mt.relative_to(ROOT)),source_stable=True,same_inode=False))
with (ROOT/'manifest/EXCLUDED.csv').open('x',newline='') as f:
 w=csv.writer(f);w.writerow(['source','reason']);w.writerows(excluded_rows)
free1=os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize
result={'started_utc':started,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':n,'logical_bytes':bytecount,'logical_GiB':bytecount/1024**3,'source_and_destination_sha256_checked_files':hashcount,'internal_symlinks':len(syms),'excluded_entries':len(excluded_rows),'free_bytes_before':free0,'free_bytes_after':free1,'observed_free_bytes_change':free0-free1,'groups':counts,'errors':errors,'full_content_sha256_of_all_large_files':False,'all_files_native_clone_return_and_size_and_distinct_inode_checked':True,'source_files_modified':0,'backtests_started':0}
write_new(ROOT/'manifest/ARCHIVE_RECEIPT.json',result); print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
if errors:raise SystemExit(1)
