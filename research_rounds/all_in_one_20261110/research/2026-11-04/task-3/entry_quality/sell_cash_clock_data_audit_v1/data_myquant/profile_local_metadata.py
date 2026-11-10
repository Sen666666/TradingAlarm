"""Local filenames, Parquet footers and read-only SQLite control metadata. No API imports."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,sqlite3,struct,os
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent;R=Path('/Users/bytedance/repos/my-quant')
files=json.loads((O/'FILE_INVENTORY.json').read_text())['files'];records=[]
processed=[R/r['relative_path']for r in files if r['relative_path'].startswith('data/processed/')and r['relative_path'].endswith('.parquet')and'/features/'not in r['relative_path']]
feature=next((R/r['relative_path']for r in files if'/features/'in r['relative_path']and r['relative_path'].endswith('.parquet')),None)
raw=[]
for family in ['suspend_status','limit_prices','daily_bars','adjustment_factors','moneyflow','daily_basic','margin_detail','top_list','hk_hold','index_daily_basic']:
 candidates=[R/r['relative_path']for r in files if r['relative_path'].startswith('data/raw/tushare/a_share/'+family+'/')and r['relative_path'].endswith('.parquet')]
 if candidates:raw.append(sorted(candidates)[0])
if feature:processed.append(feature)
for p in processed+raw:
 st=p.stat();pf=pq.ParquetFile(p);meta=pf.metadata;names=pf.schema_arrow.names;stats={}
 for ci,name in enumerate(pf.schema.names):
  if not re.search(r'date|time|symbol|source|publish|known|ann_|ex_date|pay_date|suspend|limit|is_st|st_status',name,re.I):continue
  ss=[meta.row_group(i).column(ci).statistics for i in range(meta.num_row_groups)];available=[s for s in ss if s is not None]
  mins=[s.min for s in available if s.has_min_max];maxs=[s.max for s in available if s.has_min_max]
  try:lo,hi=min(mins),max(maxs)
  except (TypeError,ValueError):lo=hi=None
  stats[name]={'footer_min':str(lo)if lo is not None else None,'footer_max':str(hi)if hi is not None else None,'row_groups_with_stats':len(available),'row_groups_with_minmax':len(mins),'null_count_from_available_footer_stats':sum(s.null_count for s in available if s.null_count is not None),'all_row_groups_have_stats':len(available)==meta.num_row_groups}
 with p.open('rb')as h:
  h.seek(-8,2);trailer=h.read(8);footer_length=struct.unpack('<I',trailer[:4])[0]
  if trailer[4:]==b'PAR1'and footer_length<64*1024*1024:h.seek(-(footer_length+8),2);fh=hashlib.sha256(h.read(footer_length+8)).hexdigest()
  else:fh=None
 records.append({'path':str(p),'relative_path':str(p.relative_to(R)),'file_bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'footer_sha256':fh,'num_rows':meta.num_rows,'num_row_groups':meta.num_row_groups,'schema':[{'name':f.name,'type':str(f.type),'nullable':f.nullable}for f in pf.schema_arrow],'column_footer_stats':stats,'row_data_read':False,'file_stat_unchanged_during_read':p.stat().st_size==st.st_size and p.stat().st_mtime_ns==st.st_mtime_ns})
dbs=[]
for p in sorted((R/'data/meta/checkpoints').glob('*.sqlite')):
 conn=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True);conn.execute('PRAGMA query_only=ON')
 tables=[]
 for name,sql in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
  if re.search(r'credential|secret|token|api.?key',name,re.I):continue
  assert re.fullmatch(r'[A-Za-z0-9_]+',name)
  cols=[{'name':v[1],'type':v[2],'notnull':bool(v[3]),'primary_key_order':v[5]}for v in conn.execute('PRAGMA table_info("'+name+'")')]
  row={'table':name,'create_sql':sql,'columns':cols}
  names={c['name']for c in cols}
  if 'status'in names:
   row['status_counts']=[{'status':a,'rows':n}for a,n in conn.execute('SELECT status,COUNT(*) FROM "'+name+'" GROUP BY status')]
  # Control tables only: bounded date/timestamp/row-count aggregates, no request JSON or auth values.
  aggs={}
  for c in cols:
   n=c['name']
   if re.fullmatch(r'[A-Za-z0-9_]+',n)and re.search(r'(^|_)(date|start|end|created_at|updated_at|finished_at|row_count|rows)(_|$)',n,re.I)and not re.search(r'error|payload|request|auth|secret|token',n,re.I):
    vals=conn.execute('SELECT MIN("'+n+'"),MAX("'+n+'") FROM "'+name+'"').fetchone();aggs[n]=[str(v)if v is not None else None for v in vals]
  row['selected_metadata_minmax']=aggs;tables.append(row)
 conn.close();dbs.append({'path':str(p),'read_uri_mode':'ro&immutable=1','wal_present':p.with_name(p.name+'-wal').exists(),'shm_present':p.with_name(p.name+'-shm').exists(),'tables':tables,'read_scope':'schema and control status/date aggregates only; no credential/request/payload fields read'})
(O/'PARQUET_FOOTER_EVIDENCE.json').write_text(json.dumps({'repo':str(R),'method':'Canonical processed tables and one raw file per present family; footer/schema only, not all raw files','records':records},ensure_ascii=False,indent=2)+'\n')
(O/'SQLITE_READONLY_EVIDENCE.json').write_text(json.dumps({'method':'SQLite mode=ro&immutable=1 and query_only; no write. If WAL exists, latest WAL changes not asserted.','databases':dbs},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'parquets':[{'path':r['relative_path'],'rows':r['num_rows'],'date_stats':{k:v for k,v in r['column_footer_stats'].items()if'date'in k.lower()}}for r in records if '/features/'not in r['relative_path']and r['relative_path'].startswith('data/processed')],'checkpoint_statuses':{Path(d['path']).name:{t['table']:t.get('status_counts')for t in d['tables']}for d in dbs},'MY_QUANT_DATA_ROOT':os.environ.get('MY_QUANT_DATA_ROOT')},ensure_ascii=False))
