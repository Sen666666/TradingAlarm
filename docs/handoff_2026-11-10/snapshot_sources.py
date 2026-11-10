#!/usr/bin/env python3
"""Read-only source scan plus additive project-local handoff snapshots. Never runs strategies."""
import csv, hashlib, json, os, shutil, sys, time
from pathlib import Path
from datetime import datetime, timezone
OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[1]
EXT=Path('/Users/bytedance/Documents/Codex')
ROOTS={
 'project_docs': PROJECT/'docs',
 'project_research_rounds': PROJECT/'research_rounds',
 'project_legacy_research': PROJECT/'TradingAlarm/research',
 'project_application': PROJECT/'TradingAlarm',
 '20261101_task': EXT/'2026-11-01/task',
 '20261104_task': EXT/'2026-11-04/task',
 '20261104_task2': EXT/'2026-11-04/task-2',
 '20261104_task3': EXT/'2026-11-04/task-3',
 '20261104_task4': EXT/'2026-11-04/task-4',
 '20261106_entry': EXT/'2026-11-06/entry_state_selection_v1',
 '20261106_cp_full': EXT/'2026-11-06/cp_sequential_full1709_v1',
 '20261106_cp_audit': EXT/'2026-11-06/cp_sequential_candidate_audit_v1',
 '20261106_h1': EXT/'2026-11-06/h1_failure_mechanism_v1',
 '20261106_multiscale': EXT/'2026-11-06/multiscale_entry_R_coverage_v1',
 '20261109_sector51': EXT/'2026-11-09/sector51_924_entry_review_v1',
}
SKIP={'.git','.venv','__pycache__','.tools','node_modules','runtime','private'}
TEXT={'.md','.txt','.py','.js','.html','.sh','.swift','.diff','.patch','.command'}
SMALL={'.json','.csv','.jsonl','.log'}
MEDIA={'.png','.jpg','.jpeg','.pdf','.svg','.xlsx'}
fields=['root_id','relative_path','absolute_source','bytes','mtime_utc','preservation','project_snapshot','sha256','source_stable_during_copy']
started=datetime.now(timezone.utc).isoformat(); total=copied=copy_bytes=already=0; errors=[]; counts={}; round_rows=[]
SNAP=OUT/'snapshots'; SNAP.mkdir(exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def utc(t): return datetime.fromtimestamp(t,timezone.utc).isoformat()
with (OUT/'FILE_INDEX.csv').open('x',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for rid,root in ROOTS.items():
  counts[rid]={'files':0,'bytes':0,'snapshots':0,'snapshot_bytes':0,'source':str(root)}
  if not root.exists():errors.append({'source':str(root),'error':'missing root'});continue
  for d,dirs,files in os.walk(root):
   dirs[:]=[n for n in dirs if n not in SKIP and not (Path(d)/n).resolve().is_relative_to(OUT)]
   if rid=='project_application':dirs[:]=[n for n in dirs if n!='research']
   if Path(d).is_relative_to(OUT):continue
   rel_dir=Path(d).relative_to(root)
   if len(rel_dir.parts)<=1:
    overview=[n for n in files if n.lower().endswith(('.md','.txt')) and any(x in n.lower() for x in ['read','conclu','report','contract','rule','freeze','status','protocol'])]
    if overview:round_rows.append({'root_id':rid,'directory':str(Path(d)),'files':' | '.join(sorted(overview))})
   for name in sorted(files):
    p=Path(d)/name
    if p.is_symlink():continue
    try:
     st=p.stat(); rel=p.relative_to(root);suffix=p.suffix.lower();external=not rid.startswith('project_')
     rec=dict(root_id=rid,relative_path=str(rel),absolute_source=str(p),bytes=st.st_size,mtime_utc=utc(st.st_mtime),preservation='original_in_project' if not external else 'indexed_original_only',project_snapshot='',sha256='',source_stable_during_copy='')
     do_copy=external and (suffix in TEXT or suffix in MEDIA or (suffix in SMALL and st.st_size<=262144)) and not name.startswith('.')
     if do_copy:
      dst=SNAP/rid/rel;dst.parent.mkdir(parents=True,exist_ok=True)
      with p.open('rb') as src,dst.open('xb') as out:shutil.copyfileobj(src,out,1024*1024)
      sh=sha(dst);now=p.stat();stable=st.st_size==now.st_size and st.st_mtime_ns==now.st_mtime_ns
      if stable:stable=sh==sha(p)
      rec.update(preservation='copied_snapshot',project_snapshot=str(dst.relative_to(OUT)),sha256=sh,source_stable_during_copy=str(stable).lower())
      copied+=1;copy_bytes+=dst.stat().st_size;counts[rid]['snapshots']+=1;counts[rid]['snapshot_bytes']+=dst.stat().st_size
      if not stable:errors.append({'source':str(p),'error':'source changed during snapshot; live file is authoritative'})
     else:already+=int(not external)
     w.writerow(rec);total+=1;counts[rid]['files']+=1;counts[rid]['bytes']+=st.st_size
    except Exception as e:errors.append({'source':str(p),'error':repr(e)})
  print(rid,counts[rid],flush=True)
with (OUT/'RESEARCH_DIRECTORY_INDEX.csv').open('x',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=['root_id','directory','files']);w.writeheader();w.writerows(round_rows)
summary={'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),'files_indexed':total,'files_copied':copied,'bytes_copied':copy_bytes,'already_in_project_indexed':already,'roots':counts,'errors':errors,'copy_policy':'External human-readable reports/code, figures/PDF, and JSON/CSV/JSONL/log <=256 KiB are copied; large matrices/accounts/market data/checkpoints remain at indexed source paths. Project files already resident are indexed, not duplicated. Runtime/private/venv/git/node_modules excluded. This is not a complete source-tree migration or whole-account atomic snapshot.'}
(OUT/'SNAPSHOT_VERIFICATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='roots'},ensure_ascii=False,indent=2),flush=True)
