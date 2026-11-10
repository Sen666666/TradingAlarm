"""Read-only actual loader audit; prohibit account creation or old-tree writes."""
from pathlib import Path
from collections import Counter
import sys,os,json,hashlib,importlib.util,gc
import numpy as np
import pandas as pd
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');C=Counter();S={};writes=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);S[str(p)]=sha(p);return json.loads(p.read_text())
def guard(event,args):
 path=None;write=False
 if event=='open':
  path=args[0];mode=args[1];flags=args[2];write=(isinstance(mode,str) and any(k in mode for k in ['w','a','x','+'])) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
 elif event in ['os.mkdir','os.remove','os.rmdir','os.rename','os.replace','os.chmod']:path=args[0];write=True
 if write and isinstance(path,(str,bytes,os.PathLike)):
  pp=Path(os.fsdecode(path)).resolve();writes.append(dict(event=event,path=str(pp)));assert pp.is_relative_to(P.resolve()),('write outside current experiment',event,pp)
sys.addaudithook(guard)
spec=importlib.util.spec_from_file_location('audited_new_loader',P/'load_inputs.py');X=importlib.util.module_from_spec(spec);spec.loader.exec_module(X)
S[str(P/'load_inputs.py')]=sha(P/'load_inputs.py');S[str(P/'STATE_MACHINE_FREEZE.json')]=sha(P/'STATE_MACHINE_FREEZE.json')
account_original=X.J.Account.__init__
def forbid(*args,**kwargs):raise AssertionError('No Account construction allowed in input audit')
X.J.Account.__init__=forbid
summ={}
try:
 for window in ['2022_2024','strong']:
  before=len(writes);shared,receipts,cp,states,ir,identity=X.inputs(window);bundle,market,facts=shared;assert len(market.lines)==len(cp)==len(receipts)==1709 and len(states)==90
  start,end=('2022-01-01','2024-12-31') if window=='2022_2024' else ('2025-07-01','2026-06-30');assert (X.J.START,X.J.END)==(start,end)
  assert not [r for r in writes[before:] if not Path(r['path']).is_relative_to(P.resolve())]
  calendar=[str(x.date()) for x in market.cutoffs if start<=str(x.date())<=end];assert len(calendar)==len(set(calendar))==(726 if window=='2022_2024' else 242)
  assert all(f.index.max()<=pd.Timestamp(end) for f in facts.f.values() if len(f));assert all(df.index.max()<=pd.Timestamp(end) for df in cp.values() if len(df));assert all(r['day']<=end for rr in states.values() for r in rr)
  if window=='2022_2024':
   expected={sid:{} for sid in receipts};industry={};annual_counts={}
   for mp in [W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',X.D.O/'inputs/MANIFEST.json']:
    count=Counter()
    for rec in read(mp):
     rr=read(rec['output_path']);assert sha(rec['output_path'])==rec['output_sha256'];assert len(rr)==rec['receipt_count'];count['files']+=1
     for r in rr:
      sid=rec['sid'];day=r['confirmed_day'];assert r['canonical_series']==sid and start<=day<=end and r['formation_start_exclusive']<r['formation_end_inclusive']==day
      assert not r['trace_unknown']
      if sid in expected:assert day not in expected[sid];expected[sid][day]=r;count['stock_receipts']+=1
      else:assert sid+'|'+day not in industry;industry[sid+'|'+day]=r;count['industry_receipts']+=1
    annual_counts[str(mp)]=dict(count)
   assert receipts==expected and ir==industry
   for sid,z in cp.items():
    dates={str(t.date()) for t in z.loc[start:end].index[z.loc[start:end].receipt.eq(True)]};assert dates==set(receipts[sid]);C['exact_receipt_date_sets']+=1
   for p,h in identity['receipt_union_sources'].items():assert sha(p)==h;C['receipt_binding_SHA']+=1
   # Original earlier annual frozen PVR values must be identical at every overlapping date.
   scorepath=X.D.O/'SCORES_MANIFEST.json';score=read(scorepath);curr={x['symbol']:x for x in score['entries']};score_days=set();scorechecks=0
   older=[W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json',W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/SCORES_MANIFEST.json']
   for mp in older:
    m=read(mp)
    for r in m['entries']:
     sid=r['symbol'];q=mp.parent/'scores'/(sid+'.parquet');assert sha(q)==r['output_sha256'];new=scorepath.parent/'scores'/(sid+'.parquet');assert sha(new)==curr[sid]['output_sha256'];a=pd.read_parquet(q);b=pd.read_parquet(new);a=a.loc['2022-01-01':'2023-12-31'];common=a.index.intersection(b.index);assert len(common)==len(a);np.testing.assert_allclose(a.loc[common,'score'],b.loc[common,'score'],rtol=0,atol=0,equal_nan=True);scorechecks+=len(common);C['earlier_score_symbol_prefixes']+=1
   for sid,r in curr.items():
    q=scorepath.parent/'scores'/(sid+'.parquet');assert sha(q)==r['output_sha256'];ff=pd.read_parquet(q);score_days.update(str(t.date()) for t in ff.loc[start:end].index);assert X.N.SCORES.at(sid,'2099-01-01') is None;C['score_no_future_substitute']+=1
   assert score_days==set(calendar)
   C['all_equal_earlier_PVR_score_rows']+=scorechecks
   summ[window]=dict(calendar_days=len(calendar),stock_receipts=sum(map(len,receipts.values())),industry_receipts=len(ir),annual_sources=annual_counts,original_score_days=len(score_days),old_score_rows_exact=scorechecks)
  else:
   assert identity['ACT_external_sha256']==sha(X.J.M.O/'recovery.csv')
   summ[window]=dict(calendar_days=len(calendar),stock_receipts=sum(map(len,receipts.values())),industry_receipts=len(ir),original_execution_support_inputs=True)
  # At representative native clocks, original date lookup cannot access future row.
  for day in [calendar[0],calendar[len(calendar)//2],calendar[-1]]:
   at=X.J.M.N.iso(day+'T15:10:00+08:00')
   for sid in list(market.lines)[::97]:
    row=facts.row(sid,at)
    if row is not None:assert pd.Timestamp(row.name)<=pd.Timestamp(day);C['facts_causal_row_lookup']+=1
  summ[window]['writes_during_inputs']=writes[before:];summ[window]['identity']=identity
  del shared,receipts,cp,states,ir,bundle,market,facts;gc.collect()
finally:X.J.Account.__init__=account_original
out=dict(status='PASS_LOADER_ONLY',checks=dict(C),windows=summ,write_audit_events=writes,source_sha256=S,scope='Actual input loaders invoked without any Account allowed; annual canonical receipts independently joined and source/date sets checked; original earlier annual PVR values compared exactly.',limits=['No annual account state/checkpoint imported by loader. Fresh1000000 initialization and full726/242 baseline identity remain account-run audit duties.','Full immutable facts/CP/states may reside in memory; original dated row/receipt/score consumers preserve visibility. No claim of prefix account equivalence from memory loading alone.','Six grace arms require independent all-held no-first-deviation witness, not this loader test.'],new_accounts=0)
(O/'LOADER_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['source_sha256','windows']},ensure_ascii=False,indent=2))
