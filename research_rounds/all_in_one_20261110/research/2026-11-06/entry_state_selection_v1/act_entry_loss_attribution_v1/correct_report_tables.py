from pathlib import Path
import pandas as pd,json,hashlib,datetime
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
slow=pd.read_csv(O/'STALLED20_LATE_WINNERS.csv');slow.entry_year=slow.entry_year.astype(str)
h=['账户','首买年','未推进总数','后来净盈利数/净额','后来≥30%数/净额','后来≥50%数/净额','≥30%首次5%确证晚于20日']
rows=[]
for arm in ['PVR','NOACT']:
 for year in ['ALL','2022','2024']:
  z=slow[(slow.account==arm)&(slow.entry_year==year)].set_index('threshold')
  row=[arm,year,str(int(z.iloc[0].stalled_total))]
  for threshold in [0.,.3,.5]:
   x=z.loc[threshold];row.append(f'{int(x.closed_winners_n)}/{x.round_net:,.2f}')
  row.append(str(int(z.loc[.3].first5_confirmed_after20)));rows.append(row)
table='\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']+['| '+' | '.join(x)+' |' for x in rows])
before={};after={}
for name in ['REPORT.md','REPORT_FINAL.md']:
 p=O/name;old=p.read_text();before[name]=sha(p)
 (O/(name[:-3]+'_BEFORE_TABLE_CORRECTION.md')).write_text(old)
 left=old.index('### 慢赢家不能删去');start=old.index('| 账户',left);end=old.index('\n\n门槛回报分母',start)
 new=old[:start]+table+old[end:];p.write_text(new);after[name]=sha(p)
 assert all('| '+' | '.join(row)+' |' in new for row in rows)
 got=[x for x in new[new.index('| 账户',left):new.index('\n\n门槛回报分母',left)].splitlines()[2:]]
 assert got==['| '+' | '.join(row)+' |' for row in rows]
p=O/'build_report.py';before['build_report.py']=sha(p);code=p.read_text()
code=code.replace("slow.query('account==@arm and entry_year==@year').iloc[0]","slow[(slow.account==arm)&(slow.entry_year==year)].iloc[0]")
code=code.replace('slow.query("account==@arm and entry_year==@year and threshold==@th").iloc[0]','slow[(slow.account==arm)&(slow.entry_year==year)&(slow.threshold==th)].iloc[0]')
code=code.replace("slow.query('account==@arm and entry_year==@year and threshold==.3').iloc[0]","slow[(slow.account==arm)&(slow.entry_year==year)&(slow.threshold==.3)].iloc[0]")
assert 'slow.query' not in code;p.write_text(code);after['build_report.py']=sha(p)
# All old data outputs, not report rendering, remain identical to their sealed bytes.
seal=json.loads((O/'OUTPUT_SHA256.json').read_text())
for n,h in seal.items():
 if n not in ['build_report.py','REPORT.md','REPORT_FINAL.md']:assert sha(O/n)==h,('primary numeric output changed',n)
F=json.loads((O/'FREEZE.json').read_text())
for path,h in F['source_hashes'].items():assert sha(path)==h,('source changed',path)
(O/'REPORT_TABLE_CORRECTION.json').write_text(json.dumps(dict(corrected_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),error='Pandas query in report list comprehension resolved outer arm/year/threshold, repeating final cohort in 3 monetary display cells. Underlying STALLED20_LATE_WINNERS.csv and all research tables were correct.',fix='Explicit boolean index in generator, rebuilt six report rows, independently compared all cells against indexed CSV values. Original reports archived before correction.',before=before,after=after,report_cells_checked=42,primary_numeric_tables_unchanged=True,source1534_unchanged=True,fast_extension_freeze_old_report_hash_retained_at='REPORT_BEFORE_TABLE_CORRECTION.md'),ensure_ascii=False,indent=2))
(O/'FINAL_MANIFEST.json').write_text(json.dumps(dict(status='PASS_COMPLETED_RESEARCH',account_runs=0,final_report='REPORT_FINAL.md',source_files_unchanged=1534,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={x.name:sha(x) for x in O.iterdir() if x.is_file() and x.name!='FINAL_MANIFEST.json'}),indent=2))
print(table);print('CORRECTED_AND_CHECKED')
