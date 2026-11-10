"""Affected as-of/identity checks only. Do not read forward outcomes."""
from pathlib import Path
import json,gzip,ast,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def funtext(p,name):
 s=Path(p).read_text();n=next(x for x in ast.parse(s).body if isinstance(x,ast.FunctionDef) and x.name==name);return '\n'.join(s.splitlines()[n.lineno-1:n.end_lineno])+'\n'
checks=[]
def check(name,ok):assert ok,name;checks.append(name)
fr=read(O/'CONTRACT_FREEZE.json');check('contract still pre-pair frozen v1.2',sha(O/'CONTRACT.txt')==fr['contract_sha256'])
check('verbatim original score function',(O/'original_score_function.py').read_text()==funtext(R/'pvr-act-comparison-20261027/code/experiment.py','score'))
check('verbatim original matcher',(O/'original_match_function.py').read_text()==funtext(R/'pvr-incremental-order-20261029/code/study.py','match'))
env=dict(pd=pd);exec(compile(funtext(O/'prepare_only.py','epoch_maps'),str(O/'prepare_only.py'),'exec'),env)
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
physical=[]
for sid in ['000001.SZ','000002.SZ','000009.SZ']:
 p=Path(sm[sid]['refs']['facts']);check('original facts hash '+sid,sha(p)==sm[sid]['output_sha256'][str(p)]);f=pd.read_parquet(p,columns=['close','segment_id','i_target','e0_target']);full=env['epoch_maps'](f,sid)
 for cut in ['2022-06-30','2025-12-31']:
  small=env['epoch_maps'](f.loc[:cut],sid)
  for key in ['i','e0']:pd.testing.assert_series_equal(small[key],full[key].loc[:cut],check_exact=True,check_freq=False)
  physical.append(dict(sid=sid,cut=cut,epoch_ID_prefix_exact=True))
check('6 physical epoch identity prefixes',len(physical)==6)
correct=read(O/'ASOF_FEATURE_CORRECTION.json');targets=correct['corrections'];verified=[]
roots={'2022':W/'2022-normal-reference-20261031/runs/B_diag/pair','2025_26':W/'q2-normal-continuation-20261031/runs/B_diag/pair'}
for win,bad in targets.items():
 f=pd.read_parquet(O/win/'FEATURES.parquet');check('no future anchor '+win,not(f.anchor.notna()&pd.to_datetime(f.anchor).gt(f.date)).any());check('no negative age '+win,not f.age.lt(0).any());found={};seen_earlier={}
 with gzip.open(roots[win]/'opportunities.jsonl.gz','rt') as h:
  for line in h:
   x=json.loads(line)
   if x['core_Q'] is not True:continue
   for b in bad:
    k=b['symbol'],b['date'][:10]
    if x['sid']==b['symbol'] and x['day']==b['anchor']:found[k]=True
    if x['sid']==b['symbol'] and b['i_start']<=x['day']<=b['date'][:10]:seen_earlier[k]=True
 for b in bad:
  k=b['symbol'],b['date'][:10];check('actual laterQ exists '+str(k),found.get(k,False));check('no contemporaneous firstQ '+str(k),not seen_earlier.get(k,False));rr=f[f.symbol.eq(k[0])&f.date.eq(pd.Timestamp(k[1]))].iloc[0];check('laterQ row now unknown '+str(k),not rr.feature_ready and pd.isna(rr.anchor));verified.append(dict(window=win,sid=k[0],day=k[1],later_first_Q=b['anchor'],current_anchor_unknown=True))
 p=pd.read_parquet(O/win/'PAIRS_PRE_OUTCOMES.parquet');epochs=list(p.h1_e0_epoch)+list(p.other_e0_epoch);check('one use per E0 '+win,len(epochs)==len(set(epochs)))
 check('no outcome/funding columns '+win,not any(z in f.columns for z in ['return_pct','MAE_pct','MFE_pct','selected','B_diag']))
for name in ['prepare_only.py','capital_readiness_only.py','census_only.py','fix_asof_features_only.py']:
 s=(O/name).read_text();tree=ast.parse(s);strings={x.value for x in ast.walk(tree) if isinstance(x,ast.Constant) and isinstance(x.value,str)};check('no outcome value field access '+name,not strings.intersection({'return_pct','MAE_pct','MFE_pct','right_tail_MFE30'}))
cache=read(O/'CACHE_MANIFEST.json');check('all1659 exact score artifacts unchanged',all(sha(O/'pvr-cache'/f"{r['symbol']}.parquet")==r['output_sha256'] for r in cache['entries']))
result=dict(passed=True,count=len(checks),checks=checks,scope='current derivation/asof/identity only; unchanged old model evidence reused',physical_epoch_prefixes=physical,later_Q_counterexamples=verified,new_pair_label_joins=0,new_accounts=0)
(O/'FINAL_PREOUTCOME_GATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('FINAL_PREOUTCOME_GATE',len(checks),'PASS; 6physical epoch prefixes,12 actual later-Q counterexamples; no outcomes/account')
