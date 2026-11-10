"""Frozen ex-ante CORE rejection diagnostics. Never reads outcome/label files."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal as D
import gzip, hashlib, importlib.util, json, math, time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parent;WORK=ROOT.parent
LIMIT=90.0;SOURCES={}
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
RAW=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
MODEL=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/portfolio-correction-20261027/code/model.py')
SCORE={
 'long':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json'),
 'strong':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json')}

def bind(p):
 p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def number(v):return float(v)if pd.notna(v)and math.isfinite(float(v))else None
def truth(v):return None if pd.isna(v)else bool(v)
def dump_lines(path,rows):
 with gzip.open(path,'wt')as h:
  for r in rows:h.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')

def known_masks(f,g,out):
 valid=f.close.gt(0)&f.amount.gt(0)&np.isfinite(f.close)&np.isfinite(f.amount)
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in f:valid &= f[k].fillna(False).astype(bool)
 valid=valid.fillna(False).astype(bool)
 block=(~valid|~valid.shift(fill_value=False)|g.segment_id.ne(g.segment_id.shift())).cumsum()
 counts=valid.groupby(block,sort=False).cumsum()
 state_known=g[['e0_target','g_ready','g_grade']].notna().all(axis=1)
 warm5=state_known.groupby(block,sort=False).transform(lambda s:s.rolling(5,min_periods=5).sum()).eq(5)
 metrics=out[['ema21','return10','up_amount10']].notna().all(axis=1)
 return (valid&counts.ge(26)&warm5&metrics,valid&counts.ge(23)&metrics)

def main():
 started=time.monotonic();O.mkdir(parents=True,exist_ok=True);bind(__file__)
 for name in ['EXANTE_DIAGNOSTIC_STRATA.txt','MATCHED_PROTOCOL.txt']:bind(ROOT/name)
 sm={r['symbol']:r for r in read(SM)};raw={r['series_id']:r for r in read(RAW)['series']}
 manifests={w:read(p)for w,p in SCORE.items()};score_entries={w:{r['symbol']:r for r in m['entries']}for w,m in manifests.items()}
 spec=importlib.util.spec_from_file_location('frozen_COR_evidence_exante_only',bind(MODEL));model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
 events=[]
 with gzip.open(bind(ROOT/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz'),'rt')as h:
  for line in h:
   r=json.loads(line)
   if r['is_first_sector_reject_in_original_source_I_epoch']:events.append(r)
 assert len(events)==8335
 snaps=read(ROOT/'events/ORIGINAL_EXISTING_LAYER_SNAPSHOTS.json')
 needed=defaultdict(set);opens=defaultdict(set)
 for e in events:
  needed[e['sid']].add((e['window'],e['signal_day']))
  for x in snaps[e['snapshot_key']]['surviving_existing_layers_at_S0']:
   needed[x['sid']].add((e['window'],e['signal_day']));opens[x['sid']].add(e['OPEN'])
 stocks=sorted(needed);samples={stocks[i]for i in [0,len(stocks)//4,len(stocks)//2,3*len(stocks)//4,len(stocks)-1]}
 points={};open_values={};prefixes=[]
 for pos,sid in enumerate(stocks):
  if time.monotonic()-started>=LIMIT:
   dump_lines(O/'POINT_FEATURES.partial.jsonl.gz',list(points.values()))
   save('PARTIAL_STATUS.json',dict(complete=False,stocks_completed=pos,stocks_required=len(stocks),points=len(points),seconds=time.monotonic()-started,limit_seconds=LIMIT,no_future_labels_read=True))
   save('SOURCE_SHA256.partial.json',SOURCES);raise TimeoutError('Frozen ex-ante feature limit reached; partial preserved')
  fp=bind(sm[sid]['refs']['facts']);assert SOURCES[str(fp.resolve())]==sm[sid]['output_sha256'][str(fp)]
  g=pd.read_parquet(fp,columns=['close','segment_id','e0_target','i_target','g_ready','g_grade','g_fresh_up'])
  rp=bind(raw[sid]['raw']['path']);assert SOURCES[str(rp.resolve())]==raw[sid]['raw']['sha256']
  r=pd.read_parquet(rp,columns=['trade_date','open','amount','price_eligible','observed_bar','is_observed_bar']).set_index('trade_date')
  assert r.index.is_unique and g.index.is_unique
  f=pd.DataFrame(dict(close=pd.to_numeric(g.close,errors='coerce').astype(float),amount=r.amount.reindex(g.index),
                      price_eligible=r.price_eligible.reindex(g.index),observed_bar=r.observed_bar.reindex(g.index),is_observed_bar=r.is_observed_bar.reindex(g.index)),index=g.index)
  out=model.evidence(f,g);new_known,weak_known=known_masks(f,g,out)
  if sid in samples:
   for cut in ['2023-12-29','2024-09-30','2026-03-31']:
    small=model.evidence(f.loc[:cut],g.loc[:cut]);pd.testing.assert_frame_equal(small,out.loc[small.index],check_exact=True)
    nk,wk=known_masks(f.loc[:cut],g.loc[:cut],small)
    pd.testing.assert_series_equal(nk,new_known.loc[nk.index],check_exact=True)
    pd.testing.assert_series_equal(wk,weak_known.loc[wk.index],check_exact=True)
    prefixes.append(dict(sid=sid,cut=cut,observations=len(small),exact=True))
  scores={}
  for w in {x[0]for x in needed[sid]}:
   sp=bind(SCORE[w].parent/'scores'/f'{sid}.parquet');assert SOURCES[str(sp.resolve())]==score_entries[w][sid]['output_sha256']
   scores[w]=pd.read_parquet(sp,columns=['score']).score
  for w,day in needed[sid]:
   d=pd.Timestamp(day);z=g.loc[d]if d in g.index else None;t=out.loc[d]if d in out.index else None
   pvr=number(scores[w].get(d,np.nan));nk=bool(new_known.loc[d])if t is not None else False;wk=bool(weak_known.loc[d])if t is not None else False
   x=dict(window=w,sid=sid,signal_day=day,PVR_score=pvr,
    original_e0_target=truth(z.e0_target)if z is not None else None,original_i_target=truth(z.i_target)if z is not None else None,
    original_G1_ready=truth(z.g_ready)if z is not None else None,original_G1_grade=number(z.g_grade)if z is not None else None,
    original_G1_fresh_up=truth(z.g_fresh_up)if z is not None else None,
    COR_new_known=nk,COR_new_ok=bool(t.new_ok)if nk else None,COR_weak_known=wk,COR_weak=bool(t.weak)if wk else None,
    COR_ema21=number(t.ema21)if t is not None else None,COR_return10=number(t.return10)if t is not None else None,
    COR_up_amount10=number(t.up_amount10)if t is not None else None,
    COR_scope='Original pure evidence formula projection, not full COR strategy/RS rule')
   points[w,sid,day]=x
  for day in opens[sid]:
   d=pd.Timestamp(day);v=None
   if d in r.index and bool(r.loc[d,'observed_bar']):v=number(r.loc[d,'open'])
   open_values[sid,day]=v if v is not None and v>0 else None
  if(pos+1)%100==0:save('PROGRESS.json',dict(stocks_completed=pos+1,stocks_required=len(stocks),seconds=time.monotonic()-started,points=len(points)))
 rows=[];counts=Counter()
 for e in events:
  w,day=e['window'],e['signal_day'];c=dict(points[w,e['sid'],day]);orig=e['original_intent'].get('PVR_score')
  if orig is None:assert c['PVR_score']is None
  else:assert c['PVR_score']is not None and abs(c['PVR_score']-float(orig))<1e-10,(e['key'],'candidate PVR source mismatch')
  snap=snaps[e['snapshot_key']];group=defaultdict(list)
  for x in snap['surviving_existing_layers_at_S0']:group[x['sid']].append(x)
  olds=[];locked=set(snap['CLOSE_account']['pending_sells'])
  for sid,ls in sorted(group.items()):
   x=dict(points[w,sid,day]);qty=sum(D(str(z['qty_after_original_actions_and_protection_exits']))for z in ls);op=open_values.get((sid,e['OPEN']))
   weight=qty*D(str(op))if op is not None else None
   x.update(layers=[z['layer']for z in ls],S0_shares=str(qty),raw_OPEN=op,OPEN_capital_weight=str(weight)if weight is not None else None,
     prior_CLOSE_exit_lock=sid in locked,prior_layer_exit_reason=any(z['previous_CLOSE_raw_layer'].get('reason')or z['previous_CLOSE_raw_layer'].get('pending_I_exit_reference')for z in ls))
   olds.append(x)
  all_weights=bool(olds)and all(x['OPEN_capital_weight']is not None for x in olds)
  all_pvr=bool(olds)and all(x['PVR_score']is not None for x in olds)
  total=sum((D(x['OPEN_capital_weight'])for x in olds),D(0))if all_weights else None
  mean=sum((D(x['OPEN_capital_weight'])*D(str(x['PVR_score']))for x in olds),D(0))/total if all_weights and all_pvr and total>0 else None
  gap=D(str(c['PVR_score']))-mean if c['PVR_score']is not None and mean is not None else None
  gapbin='no_old_inventory'if not olds else'unknown'if gap is None else'gap_ge15'if gap>=15 else'gap_0_to15'if gap>=0 else'gap_negative'
  weakknown=bool(olds)and all(x['COR_weak']is not None for x in olds)
  weakcount=sum(x['COR_weak']is True for x in olds)
  weakgroup='no_old_inventory'if not olds else'unknown'if not weakknown else'none_weak'if weakcount==0 else'all_weak'if weakcount==len(olds)else'mixed_weak'
  weakfrac=sum((D(x['OPEN_capital_weight'])for x in olds if x['COR_weak']),D(0))/total if weakknown and all_weights and total>0 else None
  row=dict(key=e['key'],window=w,sid=e['sid'],signal_day=day,OPEN=e['OPEN'],industry=e['industry'],
    candidate=c,old_stocks=olds,old_stock_count=len(olds),old_OPEN_weights_known=all_weights,
    old_total_OPEN_capital=str(total)if total is not None else None,old_PVR_all_known=all_pvr,
    old_PVR_mean_OPEN_weighted=str(mean)if mean is not None else None,
    old_PVR_mean_unweighted=sum(x['PVR_score']for x in olds)/len(olds)if all_pvr else None,
    old_PVR_min=min(x['PVR_score']for x in olds)if all_pvr else None,old_PVR_max=max(x['PVR_score']for x in olds)if all_pvr else None,
    candidate_minus_old_PVR_mean=str(gap)if gap is not None else None,PVR_gap_stratum=gapbin,
    old_COR_weak_count=weakcount,old_COR_weak_stratum=weakgroup,old_COR_weak_fraction_OPEN_weighted=str(weakfrac)if weakfrac is not None else None,
    old_prior_CLOSE_exit_lock_stock_count=sum(x['prior_CLOSE_exit_lock']for x in olds),old_prior_layer_exit_reason_stock_count=sum(bool(x['prior_layer_exit_reason'])for x in olds),
    exante_only=True,future_labels_read=False)
  rows.append(row);counts[w+'|PVR|'+gapbin]+=1;counts[w+'|COR|'+weakgroup]+=1
 dump_lines(O/'EXANTE_EVENT_FEATURES.jsonl.gz',rows)
 dump_lines(O/'POINT_FEATURES.jsonl.gz',list(points.values()))
 save('SUMMARY.json',dict(complete=True,events=len(rows),needed_stocks=len(stocks),point_features=len(points),counts=dict(counts),
  prefix_checks=prefixes,seconds=time.monotonic()-started,limit_seconds=LIMIT,
  no_future_labels_read=True,new_accounts=0,new_ledger_paths=0,parameters_fitted=False,
  state_boundary='Unknown indicator/warmup values are None rather than known False; current OPEN only provides capital weights, not H/L/C signal evidence.',
  old_basket_boundary='Prior CLOSE locks are observed, but these features grant no FIFO/bonus-share/limit/partial-order sellability.'))
 save('SOURCE_SHA256.json',SOURCES)
 print(json.dumps(dict(events=len(rows),stocks=len(stocks),points=len(points),prefix_checks=len(prefixes),seconds=time.monotonic()-started),ensure_ascii=False))

if __name__=='__main__':main()
