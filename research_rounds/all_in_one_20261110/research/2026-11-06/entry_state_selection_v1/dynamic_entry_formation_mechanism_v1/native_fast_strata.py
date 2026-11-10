"""Additional native fast-state strata and date/industry descriptive contrasts; no filter test."""
from pathlib import Path
import json,hashlib,ast
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
src={str(p) for p in [Path(__file__),O/'analyze.py',O/'BASELINE_ENTRY_FEATURES.csv',U/'STOCK_MANIFEST.json']}
manifest={m['symbol']:m for m in read(U/'STOCK_MANIFEST.json')}
z=pd.read_csv(O/'BASELINE_ENTRY_FEATURES.csv',float_precision='round_trip');z['CP_known']=False;z['fresh_CP']=False
for sid,ix in z.groupby('sid').groups.items():
 p=manifest[sid]['refs']['CP1'];src.add(p);assert sha(p)==manifest[sid]['output_sha256'][p]
 cp=pd.read_parquet(p,columns=['receipt']).reindex(pd.DatetimeIndex(z.loc[ix,'signal_day']))
 z.loc[ix,'CP_known']=cp.receipt.notna().to_numpy();z.loc[ix,'fresh_CP']=cp.receipt.eq(True).fillna(False).to_numpy(dtype=bool)
z['native_fresh_state']=np.where(~z.CP_known,'CP_UNKNOWN',np.where(z.i_buy&z.fresh_CP,'I_BUY_AND_CP',np.where(z.i_buy,'I_BUY_ONLY',np.where(z.fresh_CP,'CP_ONLY','NO_I_BUY_NO_CP'))))
z.to_csv(O/'BASELINE_NATIVE_FAST_STATES.csv',index=False)
source=(O/'analyze.py').read_text()
for n in ast.parse(source).body:
 if isinstance(n,ast.FunctionDef) and n.name=='metric':exec(compile(ast.get_source_segment(source,n),'unchanged_metric','exec'),globals())
out=[]
for keys in [['native_fresh_state'],['quarter','native_fresh_state'],['event_type','native_fresh_state']]:
 for val,g in z.groupby(keys,dropna=False):out.append(dict(features='|'.join(keys),values='|'.join(map(str,val)),**metric(g)))
pd.DataFrame(out).to_csv(O/'NATIVE_FAST_STRATA.csv',index=False)
# Direct FIRST/LATER comparison excludes pre-2022/unknown roots and preserves daily grouping.
rows=[]
c=z[z.evidence_usable_closed&z.first_feasible_in_I.isin(['FIRST_FEASIBLE_AB','LATER_FEASIBLE_AB'])]
for keys in [['signal_day'],['signal_day','sector']]:
 sums=c.groupby(keys+['first_feasible_in_I']).agg(n=('sid','size'),win=('core_net',lambda a:(a>0).mean()),mean_net=('core_net','mean'),tail50=('tail50','sum')).unstack('first_feasible_in_I').dropna()
 for idx,r in sums.iterrows():
  vals=idx if isinstance(idx,tuple) else (idx,);row=dict(grouping='|'.join(keys),group='|'.join(map(str,vals)))
  for field in ['n','win','mean_net','tail50']:
   row['first_'+field]=r[(field,'FIRST_FEASIBLE_AB')];row['later_'+field]=r[(field,'LATER_FEASIBLE_AB')]
  row['win_diff']=row['first_win']-row['later_win'];row['mean_net_diff']=row['first_mean_net']-row['later_mean_net'];rows.append(row)
paired=pd.DataFrame(rows);paired.to_csv(O/'FIRST_LATER_MATCHED_GROUPS.csv',index=False)
summary={}
for key,g in paired.groupby('grouping'):
 summary[key]={'groups':len(g),'date_or_sector_date_equal_win_diff':float(g.win_diff.mean()),'equal_mean_net_diff_cny':float(g.mean_net_diff.mean()),'first_count':int(g.first_n.sum()),'later_count':int(g.later_n.sum()),'not_causal_or_predictive_test':True}
save(O/'FIRST_LATER_MATCHED_SUMMARY.json',summary);save(O/'NATIVE_FAST_SOURCE_HASHES.json',{p:sha(p) for p in sorted(src)})
save(O/'OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(pd.DataFrame(out).query("features=='native_fresh_state'").to_string(index=False));print(json.dumps(summary,indent=2))
