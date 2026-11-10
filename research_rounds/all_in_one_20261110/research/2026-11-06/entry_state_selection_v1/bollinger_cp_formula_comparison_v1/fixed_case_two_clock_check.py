
from pathlib import Path
import ast,json,math,hashlib
import pandas as pd,numpy as np
root=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
d=root/'selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/cp_band_structure_case_audit_v1'
source=d/'audit_fixed_cases.py'
tree=ast.parse(source.read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='calculate')
code=ast.get_source_segment(source.read_text(),node)
ns={'pd':pd,'np':np,'math':math}
exec(compile(code,str(source),'exec'),ns)
oldcalc=ns['calculate']
new=code.replace("last_expand=None;last_breach=None\n for day","last_expand=None;last_breach=None;marker=math.nan;marker_day=None\n for day")
new=new.replace("state_before=state;Sbefore=S;Sday_before=Sday","""if 'source_reset' in event or not bool(fr.i_target):marker=math.nan;marker_day=None
  state_before=state;Sbefore=S;Sday_before=Sday""")
new=new.replace("expanding_now=bool(receipt and math.isfinite(up)and fr.close>up)","""if state=='REPAIR':
   if math.isfinite(marker) and fr.close<=marker:marker=math.nan;marker_day=None
   if bool(fr.i_target) and not math.isfinite(marker) and math.isfinite(up) and fr.close>up:
    marker=up;marker_day=str(day.date())
  else:marker=math.nan;marker_day=None
  marker_at_assessment=marker;marker_day_at_assessment=marker_day
  price_armed=bool(state=='REPAIR' and bool(fr.i_target) and math.isfinite(marker) and fr.close>marker)
  expanding_now=bool(receipt and math.isfinite(up) and (fr.close>up or price_armed))""")
new=new.replace("q=q,state_before=","marker=marker_at_assessment,marker_day=marker_day_at_assessment,price_armed=price_armed,q=q,state_before=")
exec(compile(new,'two_clock_candidate_in_memory','exec'),ns)
newcalc=ns['calculate']
manifest_path=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
manifest={r['symbol']:r for r in json.loads(manifest_path.read_text())}
oldcases=json.loads((d/'FORMULA_FREEZE.json').read_text())['case_set']
cases=oldcases+[('002317.SZ','2022-10-14'),('300085.SZ','2024-09-19'),('300085.SZ','2024-09-24'),('002583.SZ','2024-09-19'),('002583.SZ','2024-09-24'),('300666.SZ','2026-01-15'),('603061.SH','2026-01-15'),('000681.SZ','2026-01-15'),('603000.SH','2026-01-15'),('002153.SZ','2026-01-15'),('002716.SZ','2026-01-15'),('002865.SZ','2026-01-15')]
summary=[];diffs=[];checks=0;hashes={}
prior=pd.read_csv(d/'SIGNAL_SUMMARY.csv')
for sid in sorted(set(s for s,dt in cases)):
 if sid not in manifest:print('MISSING',sid);continue
 refs=manifest[sid]['refs'];f=pd.read_parquet(refs['facts']);cp=pd.read_parquet(refs['CP1'])
 assert f.index.equals(cp.index)
 cutoff=max(pd.Timestamp(dt) for s,dt in cases if s==sid)
 f=f.loc[:cutoff];cp=cp.reindex(f.index)
 z=oldcalc(f,cp);w=newcalc(f,cp)
 for p in [refs['facts'],refs['CP1']]:hashes[p]=hashlib.sha256(Path(p).read_bytes()).hexdigest()
 for s,dt in cases:
  if s!=sid:continue
  t=f.index.get_loc(pd.Timestamp(dt));a=z.iloc[t];b=w.iloc[t]
  for n in [t,t+1]:
   pd.testing.assert_frame_equal(newcalc(f.iloc[:n],cp.iloc[:n]),w.iloc[:n],check_exact=True);checks+=1
  prior_row=prior[prior.sid.eq(sid)&prior.signal_day.eq(dt)]
  if len(prior_row):
   p=prior_row.iloc[0]
   assert abs(float(p.multiplier)-a.multiplier)<1e-12
   assert p.state_after==a.state_after
  c=f.loc[:dt];g=c[c.segment_id.eq(c.segment_id.iloc[-1])].close
  mean=g.rolling(20,min_periods=20).mean();sig=g.rolling(20,min_periods=20).std(ddof=0);u=mean+2*sig;lo=mean-2*sig;fac=float(f.iloc[t].factor)
  summary.append(dict(sid=sid,day=dt,raw_close=round(float(b.raw_close),5),cp=bool(b.cp_receipt),I=bool(b.i_target),i_buy=bool(b.i_buy),old_state=a.state_after,new_state=b.state_after,old_mult=a.multiplier,new_mult=b.multiplier,marker_day=b.marker_day,raw_marker=b.marker/fac,BB20_M=mean.iloc[-1]/fac,BB20_U=u.iloc[-1]/fac,BB20_L=lo.iloc[-1]/fac,BB20_BW=(u.iloc[-1]-lo.iloc[-1])/mean.iloc[-1],BB20_pctB=(g.iloc[-1]-lo.iloc[-1])/(u.iloc[-1]-lo.iloc[-1]),BB20_priorU=u.iloc[-2]/fac))
 dif=w.cp_receipt & w.multiplier.ne(z.multiplier)
 for day,r in w[dif].iterrows():
  if day<pd.Timestamp('2022-01-01'):continue
  old=z.loc[day];diffs.append(dict(sid=sid,day=str(day.date()),old=old.multiplier,new=r.multiplier,marker_day=r.marker_day,close=r.raw_close))
print('FROZEN_MODIFICATION_CODE_SHA256',hashlib.sha256(new.encode()).hexdigest())
print('SOURCE_CALC_SHA256',hashlib.sha256(source.read_bytes()).hexdigest())
print('SUMMARY',pd.DataFrame(summary).to_json(orient='records'))
print('ALL_CHANGED_CP_2022_THROUGH_FIXED_CASE_CUTOFF',json.dumps(diffs))
print('CHECKS',json.dumps(dict(prefix_exact=checks,case_rows=len(summary),original_fixed_reproduced=True,source_files_unchanged=True,no_accounts=True,no_full_universe=True,source_hashes=hashes)))

out=Path(__file__).resolve().parent
pd.DataFrame(summary).to_csv(out/'FIXED20_BB20_AND_CLOCK_COMPARISON.csv',index=False)
(out/'CHANGED_CP_IN_FIXED_STOCK_PREFIXES.json').write_text(json.dumps(diffs,ensure_ascii=False,indent=2))
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(out/'CHECKS.json').write_text(json.dumps(dict(status='STOP_NO_INCREMENT_IN_FIXED_CASE_DOMAIN',prefix_exact=checks,case_rows=len(summary),stocks=len(set(r['sid'] for r in summary)),original_fixed_reproduced=True,changed_cp_since2022=len(diffs),no_accounts=True,no_full_universe=True,predeclared_in_parent_message_before_computation=True,artifact_saved_after_computation=True,source_calculation_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),new_calculation_sha256=hashlib.sha256(new.encode()).hexdigest(),source_hashes=hashes),ensure_ascii=False,indent=2))
