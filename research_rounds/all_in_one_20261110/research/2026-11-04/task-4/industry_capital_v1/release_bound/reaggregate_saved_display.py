"""Correct display medians using completed scalar rows, never rerun marks."""
from pathlib import Path
from decimal import Decimal as D
import gzip,hashlib,json,shutil,time
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def med(v):
 v=sorted(v);n=len(v);return (v[(n-1)//2]+v[n//2])/2 if n else None
def main():
 t=time.monotonic();path=O/'RELEASE_BOUND_SUMMARY.json';old=O/'RELEASE_BOUND_SUMMARY.pre_conventional_median.json';assert not old.exists();shutil.copyfile(path,old)
 rows=[json.loads(x)for x in gzip.open(O/'RELEASE_BOUND_EVENTS.jsonl.gz','rt')]
 masks={'ALL_RAW':lambda x:True,'ALL_FIRST':lambda x:x['is_first'],'LONG_RAW':lambda x:x['window']=='long','STRONG_RAW':lambda x:x['window']=='strong','H1_2026_SEMICONDUCTOR_RAW':lambda x:x['window']=='strong'and x['OPEN']>='2026-01-01'and x['semiconductor126'],'H1_2026_SEMICONDUCTOR_FIRST':lambda x:x['window']=='strong'and x['OPEN']>='2026-01-01'and x['semiconductor126']and x['is_first']}
 m=json.loads(path.read_text())
 for k,test in masks.items():
  a=[x for x in rows if test(x)and x['release_amount_status']=='KNOWN_NECESSARY_BOUND']
  for field,column,positive in [('relief_amount','required_sector_relief_lower_bound_SAFE',False),('positive_relief_amount','required_sector_relief_lower_bound_SAFE',True),('relief_to_new_minimum_gross','relief_to_new_minimum_gross',False)]:
   vs=[D(x[column])for x in a if not positive or D(x[column])>0]
   if vs:m['groups'][k][field]['median']=str(med(vs))
 m['median_definition']='Conventional median, mean of the two central values for even N; saved scalar display corrected without new prices/accounts.'
 path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 q=O/'SECTOR_ONLY_FIRST_RELEASE_SUMMARY.json';qa=O/'SECTOR_ONLY_FIRST_RELEASE_SUMMARY.pre_conventional_median.json';shutil.copyfile(q,qa);s=json.loads(q.read_text())
 for k,c in [('FIRST_CAPITAL_ONLY',{'sector_capital_only'}),('FIRST_BOTH_SECTOR_ONLY',{'both_sector_only'}),('FIRST_SECTOR_ONLY',{'sector_capital_only','both_sector_only'})]:
  a=[x for x in rows if x['is_first']and x['classification']in c and x['release_amount_status']=='KNOWN_NECESSARY_BOUND']
  s['groups'][k]['median_relief']=str(med([D(x['required_sector_relief_lower_bound_SAFE'])for x in a]));s['groups'][k]['median_relief_to_new_minimum_gross']=str(med([D(x['relief_to_new_minimum_gross'])for x in a]))
 s['median_definition']=m['median_definition'];q.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
 note=dict(display_only=True,raw_event_file_unchanged_sha256=sha(O/'RELEASE_BOUND_EVENTS.jsonl.gz'),old_summary_sha256=sha(old),corrected_summary_sha256=sha(path),seconds=time.monotonic()-t,new_marks=0,new_accounts=0,source_unknown_marks_observed=0,broad_exception_note='Original mark reader caught Exception, but no SOURCE_UNKNOWN record occurred. Future reuse should narrow to native RuleUnavailable rather than swallow programming errors.')
 (O/'SAVED_DISPLAY_CORRECTION.json').write_text(json.dumps(note,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(seconds=note['seconds'],ALL_FIRST=m['groups']['ALL_FIRST'],SECTOR_ONLY=s['groups']['FIRST_SECTOR_ONLY']),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
