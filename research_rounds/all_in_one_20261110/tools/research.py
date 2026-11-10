#!/usr/bin/env python3
"""Portable, read-only research archive browser and verifier. Never imports engines."""
import argparse,ast,collections,csv,hashlib,json,pathlib,sys
from archive_paths import ArchivePaths
ROOT=None
PATHS=None

def resolve(old):
 return PATHS.resolve(old)

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()

def emit(o):print(json.dumps(o,ensure_ascii=False,indent=2))

def manifest_rows():
 for fn in ['FILES.csv','SUPPLEMENTAL_FILES.csv']:
  p=PATHS.inside(pathlib.Path('manifest')/fn)
  if p.exists():
   with p.open() as f:
    yield from csv.DictReader(f)

def main():
 global ROOT,PATHS
 ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--project-root',help='Archive root; default: RESEARCH_ARCHIVE_ROOT or script location'); ap.add_argument('--source-map',default='manifest/SOURCE_MAP.json',help='Mapping file inside archive'); ap.add_argument('--input-manifest',default='project/docs/handoff_2026-11-10/CURRENT_INPUT_DEPENDENCIES.csv',help='Input CSV inside archive'); sub=ap.add_subparsers(dest='command',required=True)
 sub.add_parser('status');r=sub.add_parser('resolve');r.add_argument('old_absolute_path')
 v=sub.add_parser('verify');v.add_argument('--current-inputs',action='store_true');v.add_argument('--archive',action='store_true')
 sub.add_parser('check-python');sub.add_parser('duplicates')
 args=ap.parse_args()
 try:PATHS=ArchivePaths(args.project_root,args.source_map);ROOT=PATHS.root
 except (OSError,ValueError,KeyError,TypeError) as e:ap.error(str(e))
 if args.command=='resolve':
  p=resolve(args.old_absolute_path);emit({'archive_path':str(p),'exists':p.exists(),'inside_archive':p.resolve().is_relative_to(ROOT)});return 0 if p.exists() else 1
 if args.command=='status':
  p=pathlib.Path('research/2026-11-09/sector51_924_entry_review_v1/mainline_candidate_v12_winner_funding_cash_688200_v2');s=json.loads(PATHS.inside(p/'RUN_STATUS.json').read_text());c=json.loads(PATHS.inside(p/'runtime_checkpoint/LATEST.json').read_text())
  emit({'snapshot_only':True,'result':s['result'],'usable_bounded_result':s['usable_bounded_result'],'prefix_22_certified':s['prefix_22_certified'],'raw_export_days':s['days'],'raw_last_day':s['last']['day'],'raw_orders':s['orders'],'certified_day':c['certified_day'],'finished_at':s['finished_at'],'new_backtest_started':False});return 0
 if args.command=='check-python':
  files=[];errors=[]
  for rel in ['research/2026-11-09/sector51_924_entry_review_v1','research/2026-11-06/entry_state_selection_v1','tools']:
   for p in (ROOT/rel).rglob('*.py'):
    files.append(str(p.relative_to(ROOT)))
    try:ast.parse(PATHS.inside(p).read_bytes(),filename=str(p))
    except Exception as e:errors.append({'file':str(p.relative_to(ROOT)),'error':str(e)})
  emit({'mode':'AST only; no import or execution','files_checked':len(files),'errors':errors});return bool(errors)
 if args.command=='duplicates':
  groups=collections.defaultdict(list)
  for r in manifest_rows():
    if r['sha256']:groups[(r['sha256'],int(r['bytes']))].append(r['destination'])
  dup=[{'sha256':k[0],'bytes_each':k[1],'count':len(v),'paths':v} for k,v in groups.items() if len(v)>1]
  dup.sort(key=lambda x:(x['count']-1)*x['bytes_each'],reverse=True)
  emit({'scope':'only files with recomputed SHA256 in FILES.csv','duplicate_groups':len(dup),'duplicate_copies_beyond_first':sum(x['count']-1 for x in dup),'duplicate_logical_bytes':sum((x['count']-1)*x['bytes_each'] for x in dup),'not_reclaimable_disk_bytes':'APFS clone sharing means logical duplicates do not equal reclaimable physical bytes','top_30_groups':dup[:30]});return 0
 if args.command=='verify':
  if not args.current_inputs and not args.archive:ap.error('Choose --current-inputs and/or --archive')
  out={};totalerrors=0
  if args.current_inputs:
   f=PATHS.inside(args.input_manifest);errors=[];records=[];total=0
   with f.open(encoding='utf-8-sig') as h:
    for r in csv.DictReader(h):
     try:
      p=resolve(r['absolute_path']);exists=p.is_file();inside=p.resolve().is_relative_to(ROOT);actual=digest(p) if exists else None;expected=r['expected_sha256_from_frozen_manifest'];ok=exists and inside and actual==expected;total+=p.stat().st_size if exists else 0
      row={'source':r['absolute_path'],'archive':str(p.relative_to(ROOT)),'exists':exists,'inside_archive':inside,'sha256':actual,'expected_sha256':expected,'matches':ok}
     except Exception as e:row={'source':r['absolute_path'],'matches':False,'error':str(e)};ok=False
     records.append(row)
     if not ok:errors.append(row)
   out['current_inputs']={'files_checked':len(records),'bytes_hashed':total,'errors':errors,'matches':len(records)-len(errors),'all_read_from_archive':not any(not r.get('inside_archive',False) for r in records),'records':records};totalerrors+=len(errors)
  if args.archive:
   checked=0;hashed=0;syms=0;logical=0;errors=[]
   for r in manifest_rows():
     checked+=1
     try:
      p=PATHS.inside(r['destination'])
      if not p.exists():raise ValueError('missing')
      if not p.resolve().is_relative_to(ROOT):raise ValueError('external symlink')
      if r['kind']=='symlink':syms+=1;continue
      logical+=p.stat().st_size
      if p.stat().st_size!=int(r['bytes']):raise ValueError('size differs')
      if r['sha256']:
       hashed+=1
       if digest(p)!=r['sha256']:raise ValueError('SHA256 differs')
     except Exception as e:errors.append({'file':r['destination'],'error':str(e)})
   out['archive']={'entries_checked':checked,'files_with_sha256_checked':hashed,'internal_links_checked':syms,'logical_bytes':logical,'errors':errors,'large_unhashed_files_verified_by_size_and_native_clone_receipt_only':True};totalerrors+=len(errors)
  out['passed']=totalerrors==0;emit(out);return bool(totalerrors)
 return 1
if __name__=='__main__':
 try:sys.exit(main())
 except (OSError,ValueError,KeyError,TypeError) as e:
  print('Error: '+str(e),file=sys.stderr);sys.exit(2)
