import sys,ast,json,hashlib,time
from pathlib import Path
import pandas as pd,numpy as np
sys.dont_write_bytecode=True
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/nested_consolidation_core_economic_v1')
script_source=(O/'run.py').read_text()
env={'__file__':str(O/'run.py'),'__name__':'frozen_reuse_not_main'}
exec(compile(script_source[:script_source.index('\ndef main():')],str(O/'run.py')+':functions_only','exec'),env)
for k in ['read','sha','features','cal']: pass
read,sha=env['read'],env['sha']
hashes=read(O/'SOURCE_HASHES.json')
extra=[O/'run.py',O/'DAILY_SIGNALS.csv',O/'ROUNDS.csv',O/'COVERAGE.csv',O/'PROTOCOL.json',O/'NUMERICAL_CORRECTION.json']
hashes.update({str(p):sha(p) for p in extra})
assert all(sha(p)==h for p,h in hashes.items()),'SOURCE_HASH_DRIFT'
tree=ast.parse(script_source)
n=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_stock')
rs=ast.get_source_segment(script_source,n)
pairs=[
("def run_stock(sid,window,start,finish,arm,p,f,featuremap):","def run_stock(sid,window,start,finish,arm,p,f,featuremap,phase_mode=False):"),
("old=root['S'];old_native=root['S_native'];failed=z.close<=old_native",
 "old=root['S'];old_native=root['S_native'];phase_before=root['phase'];structural_failed=bool(z.close<=old_native);probe_failed=bool(phase_mode and root['phase']=='PROBE' and z.close<=root['U1_native']);failed=structural_failed or probe_failed"),
("out.update(failure_close=d,failure_close_price=float(z.raw_close),failure_S=old,failure_S_native=old_native)",
 "out.update(failure_close=d,failure_close_price=float(z.raw_close),failure_S=old,failure_S_native=old_native,failure_reason='STRUCTURAL_S' if structural_failed else 'PROBE_LOCAL_U',failure_trigger_native=old_native if structural_failed else root['U1_native'],failure_phase=root['phase'])"),
("   else:\n    lift,err=e0_floor(f,p,d)",
 "   else:\n    if phase_mode and root['phase']=='PROBE' and z.close>root['U0_native']:\n     root['phase']='TREND';out.update(promotion_day=d,promotion_C=float(z.raw_close))\n    lift,err=e0_floor(f,p,d)"),
("quantity=out.get('quantity',0)))","quantity=out.get('quantity',0),phase_before=phase_before,phase_after=root['phase'] if root is not None else None,structural_failed=structural_failed,probe_failed=probe_failed))"),
("rounds.append(out);root=dict(out=out,S=floor,S_native=floor_native,identity=identity(z),factor=float(z.adjustment_factor),pending=True,exit_pending=False,q=0)",
 "out.update(phase_mode=phase_mode,U0_native=float(p.iloc[k-20:k-10].high.max()),U1_native=float(p.iloc[k-10:k].high.max()));rounds.append(out);root=dict(out=out,S=floor,S_native=floor_native,identity=identity(z),factor=float(z.adjustment_factor),pending=True,exit_pending=False,q=0,phase='PROBE' if phase_mode and origin=='LOCAL' else 'TREND',U0_native=out['U0_native'],U1_native=out['U1_native'])")
]
for before,after in pairs:
 assert rs.count(before)==1,(before,rs.count(before))
 rs=rs.replace(before,after)
exec(compile(rs,'frozen_two_stage_exact_patch','exec'),env)
cal=pd.DatetimeIndex(np.load(env['H'],allow_pickle=False)['dates'])
env['cal']=cal
sids=sorted({x['sid'] for x in read(env['P']/'FIXED_CASES.json')})
assert len(sids)==22
manifest={x['symbol']:x for x in read(env['M'])}
cached=pd.read_csv(O/'DAILY_SIGNALS.csv',float_precision='round_trip')
cached.day=pd.to_datetime(cached.day)
data={};prefix_count=0;started=time.monotonic()
for sid in sids:
 m=manifest[sid];sp=Path(next(x for x in m['source_sha256'] if x.endswith('/signal.parquet')));fp=Path(m['refs']['facts'])
 assert sha(sp)==m['source_sha256'][str(sp)]
 p=pd.read_parquet(sp).reindex(cal);f=pd.read_parquet(fp);data[sid]=(p,f)
 fmap={cal.get_loc(x['day']):x for x in cached[cached.sid.eq(sid)].to_dict('records')}
 for window,start,finish in read(O/'PROTOCOL.json')['windows']:
  for mode,label in [(False,'UNION'),(True,'TWO_STAGE')]:
   nr,npth,nc=len(env['rounds']),len(env['paths']),len(env['coverage'])
   env['run_stock'](sid,window,start,finish,'UNION',p,f,fmap,phase_mode=mode)
   for x in env['rounds'][nr:]:
    x['arm']=label
    if mode:
     k=cal.get_loc(x['birth_day']);fresh=env['features'](p.iloc[:k+1],k);cache=fmap[k]
     for col in ['price_known','local_known','control','local','control_floor_native','l1_native','control_floor','u0','u1','l1','factor']:
      assert fresh[col]==cache[col],(sid,x['birth_day'],col,fresh[col],cache[col])
     assert x['U0_native']==p.iloc[:k+1].iloc[-21:-11].high.max()
     assert x['U1_native']==p.iloc[:k+1].iloc[-11:-1].high.max()
     prefix_count+=1
   for x in env['paths'][npth:]:x['arm']=label
   for x in env['coverage'][nc:]:x['arm']=label
z=pd.DataFrame(env['rounds'])
cov=pd.DataFrame(env['coverage'])
pth=pd.DataFrame(env['paths'])
original=pd.read_csv(O/'ROUNDS.csv',float_precision='round_trip')
original=original[original.arm.eq('UNION')].copy()
base=z[z.arm.eq('UNION')].copy()
keys=['sid','window','arm','birth_day']
for c in ['birth_day','entry_day','exit_day','failure_close','unknown_day']:
 original[c]=pd.to_datetime(original[c]);base[c]=pd.to_datetime(base[c])
original=original.sort_values(keys).reset_index(drop=True);base=base.sort_values(keys).reset_index(drop=True)
assert len(base)==len(original)==86
for c in original.columns:
 a=original[c];b=base[c]
 if pd.api.types.is_numeric_dtype(a):
  assert np.array_equal(a.to_numpy(),b.to_numpy(),equal_nan=True),(c,a.compare(b).to_dict())
 elif pd.api.types.is_datetime64_any_dtype(a):
  assert (a.eq(b)|(a.isna()&b.isna())).all(),(c,a.compare(b).to_dict())
 else:
  assert (a.eq(b)|(a.isna()&b.isna())).all(),(c,a.compare(b).to_dict())
oldcov=pd.read_csv(O/'COVERAGE.csv');oldcov=oldcov[oldcov.arm.eq('UNION')].sort_values(['sid','window']).reset_index(drop=True)
newcov=cov[cov.arm.eq('UNION')].sort_values(['sid','window']).reset_index(drop=True)
pd.testing.assert_frame_equal(oldcov,newcov,check_dtype=False)
def stats(g):
 d=g[g.status.eq('COMPLETE')];w=d[d.net_pnl.gt(0)];l=d[d.net_pnl.lt(0)];a=g[g.accepted]
 return dict(roots=len(g),accepted=len(a),complete=len(d),W=len(w),L=len(l),B=int(d.net_pnl.eq(0).sum()),win_rate=len(w)/len(d) if len(d) else None,net=float(d.net_pnl.sum()),gross_win=float(w.net_pnl.sum()),gross_loss=float(-l.net_pnl.sum()),avg_win=float(w.net_pnl.mean()),avg_loss=float(-l.net_pnl.mean()),avg_win_loss=float(w.net_pnl.mean()/-l.net_pnl.mean()) if len(w) and len(l) else None,profit_factor=float(w.net_pnl.sum()/-l.net_pnl.sum()) if len(l) else None,fees_complete=float((d.entry_fee+d.exit_fee).sum()),unknown_accepted=int(a.status.str.startswith('UNKNOWN').sum()),unknown_unaccepted=int((~g.accepted&g.status.str.startswith('UNKNOWN')).sum()),unresolved_end=int(a.status.eq('UNRESOLVED_END').sum()),status_counts=g.status.value_counts().to_dict())
summary=[dict(window=win,arm=arm,**stats(g)) for (win,arm),g in z.groupby(['window','arm'])]
paired=[]
for win in ['2022','2024_924']:
 for sid in sids:
  r=dict(window=win,sid=sid)
  for arm in ['UNION','TWO_STAGE']:
   g=z[z.window.eq(win)&z.sid.eq(sid)&z.arm.eq(arm)];c=cov[cov.window.eq(win)&cov.sid.eq(sid)&cov.arm.eq(arm)].iloc[0]
   r[arm]=stats(g)
   r[arm]['stopped_unknown']=bool(c.stopped_unknown)
   r[arm]['flat_unknown_signal_days']=int(c.unknown_signal_days)
   r[arm]['unknown_roots']=int(g.status.str.startswith('UNKNOWN').sum())
   r[arm]['unresolved_any']=int((g.accepted&~g.status.eq('COMPLETE')).sum())
  r['strict_pair']=all(r[a]['unresolved_any']==0 and not r[a]['stopped_unknown'] and r[a]['unknown_roots']==0 for a in ['UNION','TWO_STAGE'])
  r['completed_net_difference']=r['TWO_STAGE']['net']-r['UNION']['net']
  r['paired_total_difference']=r['completed_net_difference'] if r['strict_pair'] else None
  paired.append(r)
pair_summaries=[]
for win in ['2022','2024_924']:
 keep=[x['sid'] for x in paired if x['window']==win and x['strict_pair']]
 ds=[x['paired_total_difference'] for x in paired if x['window']==win and x['strict_pair']]
 for arm in ['UNION','TWO_STAGE']:
  q=z[z.window.eq(win)&z.arm.eq(arm)&z.sid.isin(keep)]
  pair_summaries.append(dict(window=win,arm=arm,pairs=len(keep),excluded=22-len(keep),**stats(q)))
 pair_summaries.append(dict(window=win,net_difference=sum(ds),positive=sum(x>1e-8 for x in ds),negative=sum(x<-1e-8 for x in ds),equal=sum(abs(x)<=1e-8 for x in ds)))
# Round identity and winners are descriptive lineage, not substitutes for full-path paired totals.
base=z[z.arm.eq('UNION')];new=z[z.arm.eq('TWO_STAGE')]
winner_ledger=[]
for x in base[base.status.eq('COMPLETE')&base.net_pnl.gt(0)].to_dict('records'):
 same=new[new.sid.eq(x['sid'])&new.window.eq(x['window'])&new.birth_day.eq(x['birth_day'])]
 g=new[new.sid.eq(x['sid'])&new.window.eq(x['window'])&new.accepted&new.birth_day.gt(x['birth_day'])&new.entry_day.le(x['exit_day'])]
 winner_ledger.append(dict(sid=x['sid'],window=x['window'],original_birth=x['birth_day'],original_exit=x['exit_day'],original_net=x['net_pnl'],same_birth=same.to_dict('records'),later_reentries_before_original_exit=g.to_dict('records')))
# QA: no overlap; next-open/T+1; own current-date protection and frozen phase order.
completed=z[z.status.eq('COMPLETE')]
for x in completed.to_dict('records'):
 assert cal.get_loc(x['exit_day'])==cal.get_loc(x['failure_close'])+1
 assert x['exit_day']>x['entry_day']
 assert x['net_pnl']==float(env['D'](int(x['quantity']))*env['D'](str(data[x['sid']][0].loc[x['exit_day'],'raw_open']))*(1-env['SLIP'])-env['D'](str(x['exit_fee']))-env['D'](str(x['buy_cash']))) or abs(x['net_pnl']-(x['quantity']*x['exit_price']-x['exit_fee']-x['buy_cash']))<1e-8
for key,g in z[z.accepted].groupby(['sid','window','arm']):
 g=g.sort_values('entry_day')
 for a,b in zip(g.to_dict('records'),g.to_dict('records')[1:]):
  assert a['status']=='COMPLETE' and b['entry_day']>a['exit_day']
for x in pth.to_dict('records'):
 assert x['failed']==(x['structural_failed'] or x['probe_failed'])
 assert x['structural_failed']==(x['native_close']<=x['old_S_native'])
 if x['arm']=='UNION':assert not x['probe_failed']
 if x['phase_before']=='TREND':assert not x['probe_failed']
 if not x['failed'] and pd.notna(x['new_S_native']):assert x['new_S_native']>=x['old_S_native']
assert all(sha(p)==h for p,h in hashes.items()),'INPUT_CHANGED_DURING_RUN'
# Retain complete round and coverage ledgers, but only relevant path events to keep the read-only transcript bounded.
events=pth[(pth.arm.eq('TWO_STAGE'))&(pth.probe_failed|pth.phase_before.ne(pth.phase_after))]
out=dict(protocol=dict(stocks=sids,windows=read(O/'PROTOCOL.json')['windows'],END=str(env['END']),formula='Only LOCAL is PROBE; source/open and structural oldS first; close<=frozen nativeU1 exits nextOPEN; otherwise close>frozen nativeU0 promotes TREND; original E0 lift and CONTROL unchanged; after actual exit original fresh signals can reenter; no new births beyond original windows',native_coordinate=True,shared_account=False,threshold_sweeps=0,case_windows_excluded=True,script_patch_sha256=hashlib.sha256(rs.encode()).hexdigest()),summary=summary,strict_summary=pair_summaries,paired=paired,rounds=z.to_dict('records'),coverage=cov.to_dict('records'),phase_events=events.to_dict('records'),winner_ledger=winner_ledger,qa=dict(baseline_86_rounds_all_original_columns_exact=True,baseline_44_coverage_rows_exact=True,physical_prefix_checks=prefix_count,rounds=len(z),path_rows=len(pth),source_hashes_unchanged=True,T1_next_open_no_overlap_monotonic_assertions=True,seconds=time.monotonic()-started),source_hashes=hashes,exact_engine_patch=rs)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(pd.Timestamp,np.datetime64)):return str(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 if isinstance(x,(np.bool_,)):return bool(x)
 if x is pd.NaT:return None
 return x
print('RESULT_JSON:'+json.dumps(clean(out),ensure_ascii=False,separators=(',',':'),allow_nan=False),flush=True)
