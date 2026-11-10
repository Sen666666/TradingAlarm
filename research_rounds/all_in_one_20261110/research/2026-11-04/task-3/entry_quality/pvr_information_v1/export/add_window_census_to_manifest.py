"""Metadata-only incorporation of the independently saved empty-domain census."""
from pathlib import Path
import json,hashlib
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=O/'FEATURE_MANIFEST_PRE_LABEL.json';a=O/'COMPLETED_EXPORT_SEAL_AUDIT.json';c=O/'EMPTY_SOURCE_DOMAIN_CENSUS.json';m=json.loads(p.read_text());audit=json.loads(a.read_text());census=json.loads(c.read_text())
 assert census['no_stock_source_row_on_968_count']==22 and census['no_sector_source_row_on_968_count']==0
 assert set(census['no_stock_source_row_on_968_export_dates'])==set(census['empty_original_stock_facts_cache_ids'])
 assert census['full_history_empty_stock_signal_files']==census['full_history_empty_industry_signal_files']==0
 old=O/'seal_intermediate';old.mkdir(exist_ok=False)
 (old/p.name).write_bytes(p.read_bytes());(old/a.name).write_bytes(a.read_bytes())
 note='The failed assertion counted full-history sig.empty, which is0 for stocks and industries. The independently saved grid/footer census identifies22 stocks with no source row on any of968 exported dates, matching22 empty original facts caches. Their22*968=21296 UNKNOWN rows remain in both complete grids. This domain distinction only corrects the seal; no source/feature/Parquet is changed.'
 for z in [m,audit]:
  z['counts'].update(window_empty_stock_symbols=22,window_empty_stock_day_rows_retained=22*968,window_empty_industry_symbols=0)
  z['source_sha256'][str(c.resolve())]=sha(c);z['source_sha256'][str(Path(__file__).resolve())]=sha(__file__)
 m['completion_note']['empty_signal_domain']=note;m['completion_note']['all_window_empty_rows_retained']=True;m['empty_source_domain_census']=census;audit['empty_signal_domain']=note;audit['all_window_empty_rows_retained']=True
 p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');a.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
 first=O/'finalize_completed_export.py';failure={'status':'PRESERVED_FIRST_READONLY_FINALIZER_METADATA_FAILURE','script':str(first.resolve()),'script_sha256':sha(first),'error':'AssertionError at line68: incorrect len(empty_industries)==22 acceptance assumption after the full1709 validation loop','stdout':'','completed_checks_before_error':['all1709 rowgroups and full sid/window/day/sector grids','raw quote open/close, original validity mask/block/observed','all133713 saved ranklog score readiness and ready bits','all1799 original signal hashes against manifests'],'data_or_exporter_modified':False,'feature_reexport':False,'resolution':'Metadata-only seal removes unsupported full-file22 test and incorporates the independent output-window census.'}
 with(O/'FIRST_FINALIZER_FAILURE.json').open('x')as f:json.dump(failure,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({'status':m['status'],'manifest_sha256':sha(p),'window_empty_stocks':22,'retained_unknown_rows':21296,'new_feature_runs':0},ensure_ascii=False))
if __name__=='__main__':main()
