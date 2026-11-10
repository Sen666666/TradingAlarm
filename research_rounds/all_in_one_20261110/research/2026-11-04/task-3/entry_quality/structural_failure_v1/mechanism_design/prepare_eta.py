"""Pure source-PVR normalization and frozen-pending rank diagnostics, no account."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from datetime import datetime,timezone
import ast,gzip,hashlib,json,math,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;E=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
T=E/'trend_exit_controls_v1';SOURCES={}
FORMULA=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
NATIVE=W/'pvr-slot1-native-readiness-20261101/native_rank.py'
WINDOWS=['2022_2024','strong']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,h=None):
 p=Path(p);s=sha(p)
 if h is not None:assert s==h,(p,s,h)
 SOURCES[str(p)]=s;return p
def read(p):return json.loads(bind(p).read_text())
def gzrows(p):
 bind(p)
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def save(p,x):
 p=O/p
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str,allow_nan=False);f.write('\n')
def write_jsonl(p,rows):
 with gzip.open(O/p,'xt') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
def basepath(win):return T/'runs/BASELINE'/win/'pair'
def pure_priority():
 src=bind(NATIVE).read_text();tree=ast.parse(src);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='priority_plan')
 env={'math':math};exec(compile(ast.Module(body=[node],type_ignores=[]),str(NATIVE),'exec'),env);return env['priority_plan']
def statistic(rows):
 return dict(rows=len(rows),stocks=len({x['sid'] for x in rows}),cost=str(sum((D(x['cost']) for x in rows),D(0))),net=str(sum((D(x['net']) for x in rows),D(0))),negative=str(sum((min(D(0),D(x['net'])) for x in rows),D(0))),positive=str(sum((max(D(0),D(x['net'])) for x in rows),D(0))))

def main():
 start=time.monotonic();protocol=read(O/'PROTOCOL.json');assert protocol['ranking_value']=='raw_eta_round12'
 ms=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');assert len(ms)==1709
 bind(FORMULA,'9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2')
 env={'np':np,'pd':pd};exec(compile(FORMULA.read_text(),str(FORMULA),'exec'),env);original=env['score'];priority=pure_priority()
 logs={w:list(gzrows(basepath(w)/'rank-policy.jsonl.gz')) for w in WINDOWS}
 calendars={w:[x['at'][:10] for x in gzrows(basepath(w)/'daily.jsonl.gz')] for w in WINDOWS}
 assert [len(calendars[w]) for w in WINDOWS]==[726,242]
 days=pd.DatetimeIndex(sorted({x for q in calendars.values() for x in q}),name='day')
 needed=defaultdict(set)
 for rr in logs.values():
  for r in rr:needed[r['sid']].add(r['day'])
 scores={};features={};entries=[];stats=Counter();zero_examples=[]
 weights=.9**np.arange(20,-1,-1);weights/=weights.sum()
 out=O/'scores';out.mkdir(exist_ok=False)
 for ix,m in enumerate(ms):
  sid=m['symbol'];p,h=next((Path(p),h) for p,h in m['source_sha256'].items() if p.endswith('/signal.parquet'));bind(p,h)
  f=pd.read_parquet(p).loc[:'2026-06-30'];z=original(f)
  # Original e already carries every invalid/source-segment warmup boundary.
  # Full21 finite e is the same domain as original E; no new state or window.
  A=z.e.abs().rolling(21,min_periods=21).apply(lambda x:np.dot(weights,x),raw=True)
  ready=np.isfinite(z.E)&np.isfinite(A)&A.gt(0)
  eta=pd.Series(np.nan,index=z.index);eta.loc[ready]=z.E.loc[ready]/A.loc[ready]
  assert eta.dropna().abs().le(1+1e-12).all()
  zero=np.isfinite(z.E)&A.eq(0);stats['zero_denominator_full_history']+=int(zero.sum())
  if zero.any() and len(zero_examples)<20:zero_examples.append(dict(sid=sid,days=[str(t.date()) for t in z.index[zero][:5]]))
  q=pd.DataFrame({'score':eta,'original_E':z.E,'absolute_energy':A,'original_score':z.score,'source_segment':f.segment_id},index=z.index).reindex(days)
  dest=out/(sid+'.parquet');q.to_parquet(dest)
  entries.append(dict(symbol=sid,output_sha256=sha(dest),rows=len(q),ready=int(q.score.notna().sum()),NA=int(q.score.isna().sum()),source=str(p),source_sha256=h,source_rows=len(f)))
  scores[sid]={str(t.date()):float(v) for t,v in q.score.items() if pd.notna(v)}
  features[sid]={str(t.date()):(float(r.original_score),float(r.original_E),float(r.absolute_energy),float(r.score) if pd.notna(r.score) else None) for t,r in q.iterrows() if str(t.date()) in needed[sid]}
  stats['source_rows']+=len(f);stats['export_rows']+=len(q);stats['eta_ready']+=int(q.score.notna().sum());stats['symbols']+=1
  if (ix+1)%400==0:print('ETA_FEATURES',ix+1,round(time.monotonic()-start,2),flush=True)
 manifest=dict(at=datetime.now(timezone.utc).isoformat(),stocks=1709,fixed_stock_ids=[m['symbol'] for m in ms],entries=entries,
  windows=[['2022-01-01','2024-12-31'],['2025-07-01','2026-06-30']],columns=['score(raw eta)','original_E','absolute_energy','original_score','source_segment'],
  new_market_models=0,new_account_paths=0,formula='eta=original_E / weighted21abs(original_e), same .9 weights; nonpositive denominator UNKNOWN; no epsilon/clamp/extra tie',ranking='raw eta rounded12, original H1 slot and tie semantics',protocol_sha256=sha(O/'PROTOCOL.json'),script_sha256=sha(__file__),original_formula_sha256=sha(FORMULA),stats=dict(stats),zero_denominator_examples=zero_examples)
 save('SCORES_MANIFEST.json',manifest)
 save('FEATURE_SOURCE_BINDING.json',dict(sources=SOURCES,seconds=time.monotonic()-start,new_accounts=0))
 # Freeze all original pending reordering before joining any later trade P&L.
 moves={};movement_summary={}
 for win,rr in logs.items():
  groups=defaultdict(list)
  for r in rr:groups[r['day']].append(r)
  mm=[];cc=Counter()
  for day,rs in sorted(groups.items()):
   intents=[dict(sid=r['sid'],rank=r['original_H1_rank'],role=role) for r in rs for role in r['roles']]
   old={r['sid']:r for r in rs}
   def oldscore(s,d):return old[s]['PVR']
   bk,bl=priority(intents,oldscore,day)
   for r in rs:
    assert bk[r['sid']]==r['priority_rank']
    orig=features[r['sid']][day][0]
    if r['PVR_ready']:assert orig==r['PVR'],('old PVR not exact',win,r['sid'],day,orig,r['PVR'])
    else:assert not np.isfinite(orig)
   keys,nl=priority(intents,lambda s,d:scores[s].get(d),day)
   oldslots={r['sid']:r['final_slot'] for r in rs}
   for n in nl:
    r=old[n['sid']];o,E0,A0,et=features[n['sid']][day]
    delta=n['final_slot']-oldslots[n['sid']]
    q=dict(window=win,day=day,sid=n['sid'],roles=r['roles'],original_H1_rank=r['original_H1_rank'],old_PVR_rank=r['priority_rank'],new_eta_rank=keys[n['sid']],old_PVR_slot=oldslots[n['sid']],new_eta_slot=n['final_slot'],eta_minus_PVR_slot=delta,old_PVR_score=r['PVR'],eta=et,original_E=E0 if math.isfinite(E0) else None,absolute_energy=A0 if math.isfinite(A0) else None)
    mm.append(q);cc['stock_day_queries']+=1;cc['changed']+=delta!=0;cc['earlier']+=delta<0;cc['later']+=delta>0;cc['same']+=delta==0;cc['eta_unknown']+=et is None;cc['old_score_exact']+=bool(r['PVR_ready'])
  moves[win]=mm;movement_summary[win]=dict(cc);write_jsonl(win+'_PENDING_RANK_MOVES.jsonl.gz',mm)
 save('RANKING_PRE_LABEL_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),summary=movement_summary,files={w:sha(O/(w+'_PENDING_RANK_MOVES.jsonl.gz')) for w in WINDOWS},no_trade_labels_read_yet=True))
 # Every native opportunity remains in its original source; only aggregate
 # coverage is copied here, not a fresh filtered trading universe.
 coverage={};competition={};label_results={}
 for win in WINDOWS:
  counter=Counter();byday=defaultdict(Counter)
  for r in gzrows(basepath(win)/'opportunities.jsonl.gz'):
   day=r['day'];s=r['sid'];ready=day in scores.get(s,{})
   counter['all_original_opportunity_rows']+=1;counter['all_eta_ready']+=ready
   if r['roles']:
    counter['rows_with_native_roles']+=1;counter['roles_eta_ready']+=ready
    for role in r['roles']:counter['role_'+role]+=1;counter['role_'+role+'_eta_ready']+=ready
    if not r['barriers']:
     counter['native_barrier_free_rows']+=1;counter['native_barrier_free_eta_ready']+=ready
   byday[day]['all']+=1;byday[day]['ready']+=ready
  coverage[win]=dict(totals=dict(counter),by_day={k:dict(v) for k,v in byday.items()})
  mm={(r['day'],r['sid']):r for r in moves[win]};cal=calendars[win];prev={cal[i]:cal[i-1] for i in range(1,len(cal))}
  funded=defaultdict(set);rejected=[];unmatched=[];fundcounts=Counter()
  for r in gzrows(basepath(win)/'funding.jsonl.gz'):
   od=r['at'][:10];d=prev.get(od);k=(d,r['sid'])
   if k not in mm:
    fundcounts['unmatched_funding_rows']+=1
    if len(unmatched)<20:unmatched.append(r)
    continue
   result=r['result'];fundcounts['matched_funding_rows']+=1
   if result=='reserved':funded[d].add(r['sid']);fundcounts['reserved_rows']+=1
   elif set(result.split(','))&{'cash_or_original_reserve','pool_capital','probe_risk','sector_capital','sector_risk','stock_capital'}:
    rejected.append((d,r));fundcounts['resource_rejected_rows']+=1
  backgrounds=[]
  for d,r in rejected:
   c=mm[d,r['sid']];cross=[mm[d,s] for s in funded[d] if mm[d,s]['old_PVR_rank']<c['old_PVR_rank'] and mm[d,s]['new_eta_rank']>c['new_eta_rank']]
   if cross:backgrounds.append(dict(decision_day=d,original_rejected_funding=r,candidate_rank=c,original_earlier_reserved_now_later=cross))
  competition[win]=dict(counts=dict(fundcounts),resource_reject_rows_with_order_reversal=len(backgrounds),unique_rejected_stock_days_with_order_reversal=len({(x['decision_day'],x['candidate_rank']['sid']) for x in backgrounds}),dates=len({x['decision_day'] for x in backgrounds}),unmatched_examples=unmatched,meaning='Necessary order-crossing background only; no proof rejected order can replace a funded order, no resource release, no new fills or profits.')
  write_jsonl(win+'_RESOURCE_COMPETITION_BACKGROUNDS.jsonl.gz',backgrounds)
  # Subsequent labels describe old actual fills after the rank freeze only.
  actual=read(E/'structural_failure_v1/state_semantics'/(win+'_ROWS.json'));enriched=[]
  for x in actual:
   k=(x['decision_at'][:10],x['sid']);assert k in mm
   enriched.append(dict(x,eta_rank_diagnostic=mm[k]))
  groups={'all':enriched,'first':[x for x in enriched if x['action']=='first_actual_participation'],'mobile':[x for x in enriched if x['role']=='mobile']}
  if win=='2022_2024':groups['post303']=[x for x in enriched if x['opened'][:10]>'2024-10-08'];assert len(groups['post303'])==303
  else:groups['own_tail30']=[x for x in enriched if D(x['net'])/D(x['cost'])>=D('.3')]
  label_results[win]={name:{kind:statistic([x for x in xs if ('earlier' if x['eta_rank_diagnostic']['eta_minus_PVR_slot']<0 else 'later' if x['eta_rank_diagnostic']['eta_minus_PVR_slot']>0 else 'same')==kind]) for kind in ('earlier','same','later')} for name,xs in groups.items()}
  save(win+'_ACTUAL_ENTRY_RANK_DIAGNOSTIC.json',enriched)
 save('OPPORTUNITY_COVERAGE.json',coverage);save('RESOURCE_COMPETITION_SUMMARY.json',competition);save('ACTUAL_ENTRY_RANK_SUMMARY.json',label_results)
 save('SOURCE_BINDING.json',dict(sources=SOURCES,script_sha256=sha(__file__),seconds=time.monotonic()-start,new_accounts=0,new_market_models=0))
 save('COMPLETION.json',dict(status='PURE_FEATURE_AND_NECESSARY_RANK_COVERAGE_COMPLETE',symbols=1709,actual_layers=3436,new_accounts=0,new_models=0,no_static_portfolio_return=True))
 print('ETA_COMPLETE',round(time.monotonic()-start,2),json.dumps(movement_summary),flush=True)
if __name__=='__main__':main()
