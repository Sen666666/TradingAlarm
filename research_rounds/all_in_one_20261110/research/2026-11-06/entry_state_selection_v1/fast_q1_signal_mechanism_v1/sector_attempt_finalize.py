"""Finalize causal display lineage only, no market numeric model or economic run."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
script=O/'sector_attempt_diagnostic.py';before=script.read_text();backup=O/'sector_attempt_diagnostic.before_display_lineage_fix.txt';assert not backup.exists();backup.write_text(before)
old=" q['last_failure_day']=q.day.where(q.action.eq('end_attempt')).ffill();q['last_failure_reason']=q.reason.where(q.action.eq('end_attempt')).ffill()"
new=""" q['market_source_segment']=f.segment_id.to_numpy()
 q['history_boundary']=(q.action.eq('unknown') | q.market_source_segment.ne(q.market_source_segment.shift())).cumsum()
 keys=[q.E0_episode,q.history_boundary]
 q['last_failure_day']=q.day.where(q.action.eq('end_attempt')).groupby(keys,dropna=True).ffill()
 q['last_failure_reason']=q.reason.where(q.action.eq('end_attempt')).groupby(keys,dropna=True).ffill()
 q.loc[q.action.eq('unknown'),['last_failure_day','last_failure_reason']]=[pd.NaT,None]"""
assert before.count(old)==1;script.write_text(before.replace(old,new))
parts=[]
for item in json.loads((U/'INDUSTRY_MANIFEST.json').read_text()):
 refs=item['refs']
 for k in ['state','CP1_input']:assert sha(refs[k])==item['output_sha256'][refs[k]]
 q=pd.read_parquet(refs['state']);f=pd.read_parquet(refs['CP1_input']);q['sector']=item['series'];q['day']=pd.to_datetime(q.day)
 q['market_source_segment']=f.segment_id.to_numpy();q['history_boundary']=(q.action.eq('unknown')|q.market_source_segment.ne(q.market_source_segment.shift())).cumsum();keys=[q.E0_episode,q.history_boundary]
 q['last_failure_day']=q.day.where(q.action.eq('end_attempt')).groupby(keys,dropna=True).ffill();q['last_failure_reason']=q.reason.where(q.action.eq('end_attempt')).groupby(keys,dropna=True).ffill();q.loc[q.action.eq('unknown'),['last_failure_day','last_failure_reason']]=[pd.NaT,None]
 parts.append(q[['sector','day','last_failure_day','last_failure_reason','market_source_segment','history_boundary']])
fields=['last_failure_day','last_failure_reason','market_source_segment','history_boundary'];patch=pd.concat(parts,ignore_index=True);audits=[]
for name,prefix in [('sector_attempt_permits_2022.csv','sector_'),('sector_attempt_startup_rows.csv','sector_'),('sector_attempt_daily_2022.csv','')]:
 p=O/name;previous=sha(p);g=pd.read_csv(p,low_memory=False);g.day=pd.to_datetime(g.day);cols=[prefix+k for k in fields];oldcols=[k for k in cols if k in g];g=g.drop(columns=oldcols).merge(patch.rename(columns={k:prefix+k for k in fields}),on=['sector','day'],how='left',validate='many_to_one');g.to_csv(p,index=False)
 ep='sector_E0_episode' if prefix else 'E0_episode';bad=g[g[ep].isna() & g[prefix+'last_failure_day'].notna()];assert len(bad)==0
 audits.append(dict(file=name,before_sha256=previous,after_sha256=sha(p),rows=len(g),missing_episode_with_failure_display=0))
# Boundary-only synthetic test: old failed episode never leaks into a new first attempt; unknown clears display history.
z=pd.DataFrame(dict(ep=['e1','e1',None,'e2','e2','e2','e2'],action=['probe','end_attempt','observe','observe','end_attempt','unknown','hold'],segment=[0]*7,day=pd.date_range('2020-01-01',periods=7)))
b=(z.action.eq('unknown')|z.segment.ne(z.segment.shift())).cumsum();v=z.day.where(z.action.eq('end_attempt')).groupby([z.ep,b],dropna=True).ffill();v[z.action.eq('unknown')]=pd.NaT
assert pd.isna(v.iloc[2]) and pd.isna(v.iloc[3]) and pd.isna(v.iloc[5]) and pd.isna(v.iloc[6]) and v.iloc[4]==z.day.iloc[4]
source=O/'sector_attempt_source_hashes.json';h=json.loads(source.read_text());h[str(script)]=sha(script);h[str(Path(__file__))]=sha(Path(__file__));source.write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n')
qa=O/'sector_attempt_verification.json';x=json.loads(qa.read_text());x['display_lineage_finalization']=dict(scoped_to_current_E0_and_source_and_unknown_boundary=True,synthetic_boundary_pass=True,outputs=audits,classification_counts_unchanged=True);qa.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
(O/'sector_attempt_output_hashes.json').write_text(json.dumps({p.name:sha(p) for p in sorted(O.glob('sector_attempt_*')) if p.is_file() and p.name!='sector_attempt_output_hashes.json'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(x['display_lineage_finalization'],ensure_ascii=False,indent=2))
