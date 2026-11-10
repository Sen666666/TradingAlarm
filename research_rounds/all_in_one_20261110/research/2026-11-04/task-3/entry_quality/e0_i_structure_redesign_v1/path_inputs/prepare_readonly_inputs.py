"""Clip/join saved E0/I input columns only. No indicator or strategy execution."""
from pathlib import Path
import gzip,hashlib,json,math
import pandas as pd

O=Path(__file__).resolve().parent;Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SRC={}
TARGETS={'000620.SZ':('2021-01-01','2022-02-08'),'601019.SH':('2022-01-01','2023-06-30'),'601601.SH':('2024-01-01','2024-10-10'),'002583.SZ':('2024-01-01','2024-11-27'),'603061.SH':('2025-01-01','2026-06-30'),'605111.SH':('2025-01-01','2026-06-30'),'300623.SZ':('2025-01-01','2026-06-30')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return json.load(f)
def frame(p,h):
 p=Path(p);assert sha(p)==h;SRC[str(p.resolve())]=h;return pd.read_parquet(p)
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,pd.Timestamp):return str(v)
 if hasattr(v,'item'):v=v.item()
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
hist=read(Q/'structural_failure_v1/accounting/results_v2/2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json')
strong=read(Q/'structural_failure_v1/accounting/results_v2/strong_CAMPAIGNS_FULL_ACCOUNTING.json')
books={w:read(Q/'trend_exit_controls_v1/runs/BASELINE'/w/'pair/B.json.gz',True) for w in ['2022_2024','strong']}
index=[];schema={};pivots=[];campaigns=[]
for sid,(start,end) in TARGETS.items():
 m=sm[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));ep=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'))
 fs={'price':frame(sp,m['source_sha256'][sp]),'events':frame(ep,m['source_sha256'][ep]),'native':frame(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]),'CP':frame(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])}
 schema[sid]={k:dict(path=sp if k=='price' else ep if k=='events' else m['refs']['facts'] if k=='native' else m['refs']['CP1'],source_first_day=str(f.index.min().date()),source_last_day=str(f.index.max().date()),columns={n:str(f[n].dtype) for n in f.columns}) for k,f in fs.items()}
 base=fs['price'].loc[start:end].copy();assert not base.empty
 joined=base.add_prefix('price__')
 for k in ['events','native','CP']:joined=joined.join(fs[k].reindex(base.index).add_prefix(k+'__'))
 out=O/(sid.replace('.','_')+'_DAILY_INPUTS.parquet');joined.to_parquet(out,index=True)
 pp=[]
 for day,r in fs['events'].loc[start:end].iterrows():
  if r['event'] not in [-1,1]:continue
  p=dict(sid=sid,known_at_CLOSE_day=str(day.date()),known_at_scope='First confirmation is this source event row, after that bar CLOSE/V; not actual feed receipt timestamp.',original_event=r.to_dict(),pivot_occurrence_day=r.get('confirmed_pivot_date'),pivot_date_is_not_known_at=True,E0_RMS_sigma_at_ext='NOT_PERSISTED_NO_RECOMPUTATION_AUTHORIZED_YET')
  pp.append(p);pivots.append(p)
 roots=[]
 window='strong' if sid in ['603061.SH','605111.SH','300623.SZ'] else '2022_2024';book=books[window]
 for t in book['trades']:
  if t['side']!='buy' or t['security_id']!=sid:continue
  if not start<=t['at'][:10]<=end:continue
  meta=book['metadata'][str(t['layer'])];roots.append(dict(layer=t['layer'],original_fill_at=t['at'],original_signal_at=t['signal_at'],original_stock_structure=meta.get('stock_structure'),original_watch_epoch=t.get('epoch'),scope='Existing funded-layer identity only; not a reconstructed full E0 root for every unfunded state.'))
 for c in (strong if window=='strong' else hist):
  if c['sid']==sid and c['opened'][:10]<=end and (c['closed'] is None or c['closed'][:10]>=start):campaigns.append(c)
 index.append(dict(sid=sid,target_start=start,target_end=end,requested_warmup_note='2025 is input context only for 2026 semiconductor examples; not another account run.' if window=='strong' else 'Requested slice only. Full earlier source history remains available for future approved initialization, not silently assumed reset.',output=str(out.resolve()),output_sha256=sha(out),rows=len(joined),first_observation=str(joined.index[0].date()),last_observation=str(joined.index[-1].date()),exact_source_missing={k:int(fs[k].reindex(base.index).isna().all(axis=1).sum()) for k in ['events','native','CP']},confirmed_event_rows=len(pp),funded_original_stock_structure_roots=roots,
 native_full_E0_fields=['native__e0_ready','native__e0_target','native__e0_floor'],native_I_fields=['native__i_target','native__i_floor','native__i_buy'],
 E0_RMS_sigma_status='NOT_PERSISTED_IN_EVENTS_NATIVE_OR_CP; current CP.s/z and receipt original_scale are different MAD-based quantities; do not substitute.',
 known_pivot_contract='Only events.event confirmation row supplies known_at_CLOSE_day; confirmed_pivot_date is historical occurrence and developing_extreme_date is a mutable candidate snapshot, not earlier knowledge.'))
save('INPUT_INDEX.json',index);save('SOURCE_SCHEMAS.json',schema);save('CONFIRMED_PIVOT_SOURCE_ROWS.json',pivots);save('ORIGINAL_CAMPAIGN_EXAMPLES.json',campaigns)
codes=[Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py'),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py'),W/'native-I-cache-interface-20261031/cache.py']
for p in codes:SRC[str(p)]=sha(p)
save('SOURCE_MANIFEST.json',dict(source_sha256=SRC,script_sha256=sha(__file__),export='Exact saved-column clipping/reindex joins only; no E0/I/scale calculation.',new_accounts=0,new_models=0,new_backtests=0,new_signal_calculations=0,new_outcome_calculations=0))
print(json.dumps(dict(status='PASS_SAVED_SOURCE_INPUTS_ONLY',stocks=len(index),rows=sum(r['rows'] for r in index),pivot_confirmation_rows=len(pivots),outputs=[dict(sid=r['sid'],rows=r['rows'],first=r['first_observation'],last=r['last_observation'],missing=r['exact_source_missing']) for r in index]),ensure_ascii=False))
