"""Independent old-CP guard versus post-CLOSE ratchet check; read-only."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;S=O.parent;E=S.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 with(gzip.open(p,'rt')if gz else Path(p).open())as f:return[json.loads(x)for x in f]if lines else json.load(f)
def eq(a,b,tag):assert abs(D(str(a))-D(str(b)))<D('.000001'),(tag,a,b)
def main():
 out=O/'TEN_CHAIN_PROTECTION_ORDER_AUDIT.json';assert not out.exists();p=S/'chains/COMPLETE_ORIGINAL_CHAINS.json';chains=read(p);pair=E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair';book=read(pair/'B.json.gz',True);daily=read(pair/'daily.jsonl.gz',True,True);di={d['at'][:10]:i for i,d in enumerate(daily)};buy={t['layer']:t for t in book['trades']if t['side']=='buy'};dec={t['at']:t for t in book['decisions']};req=[a for a in book['audit']if a.get('kind')=='pilot_layer_exit'];sm={m['symbol']:m for m in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};C=Counter();samples=[];sources={str(p.resolve()):sha(p),str((pair/'B.json.gz').resolve()):sha(pair/'B.json.gz'),str((pair/'daily.jsonl.gz').resolve()):sha(pair/'daily.jsonl.gz')}
 for chain in chains:
  sid=chain['campaign']['sid'];m=sm[sid];facts=pd.read_parquet(m['refs']['facts']);cp=pd.read_parquet(m['refs']['CP1'])
  for pp in [m['refs']['facts'],m['refs']['CP1']]:sources[pp]=sha(pp)
  for o in chain['observations']:
   d=o['day'];i=di[d];now=daily[i];old={}if i==0 else{h['id']:h for h in daily[i-1]['layers']};q=facts.iloc[facts.index.searchsorted(pd.Timestamp(d),side='right')-1];c=cp.loc[d]if pd.Timestamp(d)in cp.index else None;hard=not now['on']or not bool(q.i_target)
   expectedcore=[h['id']for h in now['layers']if h['sid']==sid and h['kind']=='core'];assert o['core_actually_funded_and_held_before_new_CLOSE_decision']==expectedcore
   assert o['original_intents']==[x for x in dec[now['at']]['intents']if x['sid']==sid];C['CORE_and_current_intent_clock']+=1
   for h in o['actual_live_layers']:
    z=h['snapshot'];lid=z['id'];prior=old.get(lid);oldfloor=D(prior['floor']if prior else buy[lid]['floor'])
    locked=any(r['at']<now['at']and lid in r['layers']for r in req)
    if z['kind']=='core':
     known=prior.get('last_core_line')if prior else buy[lid]['floor'];expected=D(str(q.i_floor))if not hard and pd.notna(q.i_floor)else D(known)
     eq(z['last_core_line'],expected,'core known reference');C['CORE_reference_not_independent_stop']+=1;continue
    if hard or locked:expected=oldfloor;C['hard_or_preexisting_lock_keeps_old_floor']+=1
    elif D(str(q.close))<=oldfloor:
     expected=oldfloor;assert any(r['at']==now['at']and lid in r['layers']and r['reason']=='CP1_add_protection'for r in req);C['old_floor_checked_before_ratchet_exit']+=1
    else:
     expected=max(oldfloor,D(str(q.i_floor)))if pd.notna(q.i_floor)else oldfloor
     if c is not None and bool(c.receipt):expected=max(expected,D(str(c.candidate)))
     C['survivor_post_CLOSE_ratchet_checked']+=1
     if expected>oldfloor and len(samples)<5:samples.append(dict(sid=sid,layer=lid,day=d,prior_guard_floor=str(oldfloor),close=str(q.close),post_CLOSE_floor=str(expected),CP_receipt=False if c is None else bool(c.receipt)))
    eq(z['floor'],expected,'mobile old check then ratchet')
 sources[str(Path(__file__).resolve())]=sha(__file__)
 result=dict(status='PASS_OLD_PROTECTION_GUARD_AND_POST_CLOSE_RATCHET_ORDER',checks=dict(C),samples=samples,source_sha256=sources,new_financial_accounts=0,new_financial_events=0,semantic_limits=['CORE last_core_line is a risk-reference update, not an additional standalone stop.','The observed first down event is not itself I_target failure.','Trade.pvr is legacy H1 score; frozen_intent.PVR_score/rank-policy.PVR is actual priority source, eta for the new experiment.'])
 with out.open('x')as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({'status':result['status'],'checks':dict(C)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
