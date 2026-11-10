"""Read frozen fixture clocks/cache identity only; no model/neutral/Account/Runner evaluation."""
from pathlib import Path
import json,hashlib,ast
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;T=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');M=Path('/Users/bytedance/Documents/ChatGPT/money');R=M/'research_rounds';U=W/'universe-cp1-inputs-20261031';END='2026-06-30'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2))
card=T/'risk_constraints/VOLUME_NEUTRAL_EXISTING_ALGORITHM_CARD.md';selection=T/'risk_constraints/volume_neutral_card_v1/SOURCE_AND_SELECTION_FREEZE.json';fixtures=read(selection)['fixtures'];sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')};im={r['series']:r for r in read(U/'INDUSTRY_MANIFEST.json')}
models=[M/'TradingAlarm/desk/refresh.py',R/'pv-strength-b5-20261025/code/api.py',R/'pv-strength-b5-20261025/code/evidence.py',R/'pv-strength-b5-20261025/code/arithmetic.py',R/'pv-strength-b5-20261025/code/policy.py',R/'pv-strength-b4-20261025/code/model.py',R/'pv-participation-response-20261020/code/numeric.py',R/'pv-participation-response-20261020/code/data_utils.py',R/'b5-g1-20261025/code/grade.py',R/'b5-g1-20261025/code/policies_g1.py',R/'ix-a-share-entry-20261025/code/prepare_ix.py',W/'native-I-cache-interface-20261031/cache.py',W/'universe-cp1-inputs-20261031/prepare.py',W/'case-stock-cp1-warmup-20261031/generate.py',R/'continuous-protection-lines-20261028/code/model.py',W/'pvr-current-v3-information-capital-20261101/original_score_function.py',W/'cp1-evidence-trace-20261031/trace.py']
paths=[Path(__file__),card,selection,U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',W/'native-I-cache-interface-20261031/PILOT_GATE.json',*models]
for x in fixtures:
 for r in [sm[x['sid']],im[x['sector']]]:paths.extend(Path(p)for p in {*r['source_sha256'],*r['output_sha256']})
paths=sorted(set(paths));freeze={str(p):sha(p)for p in paths};save('SOURCE_FREEZE.json',dict(before_inspection=True,scope='fixture metadata/source clock/cache identity only; no indicator/feature/neutral/cold computation or account',sources=freeze))
# Reuse exact original observation-mask functions only; no event/strength models.
p=R/'pv-participation-response-20261020/code/data_utils.py';nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in {'boolean_column','eligible_prices'}];env=dict(np=np,pd=pd);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p)+'::observation-mask-only','exec'),env);eligible=env['eligible_prices']
rows=[]
for x in fixtures:
 for industry,sid,r in [(False,x['sid'],sm[x['sid']]),(True,x['sector'],im[x['sector']])]:
  assert all(sha(p)==h for p,h in {**r['source_sha256'],**r['output_sha256']}.items())
  sp=next(p for p in r['source_sha256']if p.endswith('/signal.parquet'));ep=next(p for p in r['source_sha256']if p.endswith('/events.parquet'));signal=pd.read_parquet(sp).loc[:END];f=eligible(signal);q=pd.read_parquet(r['refs']['CP1_input']).loc[:END];cp=pd.read_parquet(r['refs']['CP1']).loc[:END];e=pd.read_parquet(ep).reindex(f.index)
  assert f.index.equals(q.index)and q.index.equals(cp.index);pd.testing.assert_series_equal(f.close,q.close,check_exact=True,check_dtype=False,check_names=False,check_freq=False);assert q.e0_down.equals(e.event.eq(-1))
  z=dict(fixture=x['id'],sid=sid,industry=industry,mode=r.get('mode','industry original source frame'),warm_from=str(q.index.min().date()),rows=len(q),raw_source_rows=len(signal),source_segments={str(k):len(g)for k,g in f.groupby('segment_id',sort=False)},positive_finite_volume_rows=int((np.isfinite(f.volume)&f.volume.gt(0)).sum()),nonpositive_or_unknown_volume_price_rows=int((~(np.isfinite(f.volume)&f.volume.gt(0))).sum()),CP1_ready_first=str(cp.index[cp.ready][0].date())if cp.ready.any()else None,CP1_receipts=int(cp.receipt.sum()),cutoff_counts={d:int((q.index<=d).sum())for d in ['2021-12-31','2024-09-23',END]},price_clock_equal_to_CP1=True,CP1_down_equal_original_event=True,cold_model_run=False)
  if not industry:
   fp=r['refs']['facts'];facts=pd.read_parquet(fp).loc[:END];ip=next(p for p in r['source_sha256']if '/ix-a-share-entry-'in p);ix=pd.read_parquet(ip).loc[:END];assert f.index.equals(facts.index)and f.index.equals(ix.index)
   cols={'g_grade':'grade','g_ready':'strength_ready','g_fresh_up':'fresh_up','g_acute_down':'acute_down'}
   for a,b in cols.items():pd.testing.assert_series_equal(facts[a],ix[b],check_exact=True,check_dtype=False,check_names=False,check_freq=False)
   z.update(cached_G1_fields_exact_to_IX=list(cols),G1_ready_first=str(ix.index[ix.strength_ready][0].date())if ix.strength_ready.any()else None,old_native_pilot_fixture=sid in {r['sid']for r in read(W/'native-I-cache-interface-20261031/PILOT_GATE.json')['receipts']})
  rows.append(z)
def body(p,name):
 n=next(n for n in ast.parse(Path(p).read_text()).body if isinstance(n,ast.FunctionDef)and n.name==name);b=n.body
 if isinstance(b[0],ast.Expr)and isinstance(b[0].value,ast.Constant)and isinstance(b[0].value.value,str):b=b[1:]
 return ast.dump(ast.Module(body=b,type_ignores=[]),include_attributes=False)
a=R/'pv-strength-b5-20261025/code/arithmetic.py';b=R/'pv-participation-response-20261020/code/numeric.py';matches={k:body(a,k)==body(b,k)for k in ['compare','log_ratio','higher']}
assert all(matches.values());assert all(sha(p)==h for p,h in freeze.items())
save('INSPECTION.json',dict(status='SOURCE_CLOCK_CACHE_IDENTITY_PASS_COLD_REPRODUCTION_PENDING_OWNER',fixtures=rows,B5_numeric_helper_bodies_exact=matches,original_B4_expected_sha256='0beb0b16f2f2cac4f1aff23258b7c45722dc12f16e495be27bf5635c03888cf1',actual_B4_sha256=sha(R/'pv-strength-b4-20261025/code/model.py'),sources_post_exact=True,new_model_feature_runs=0,new_account_objects=0))
print(json.dumps(rows,ensure_ascii=False,indent=2))
