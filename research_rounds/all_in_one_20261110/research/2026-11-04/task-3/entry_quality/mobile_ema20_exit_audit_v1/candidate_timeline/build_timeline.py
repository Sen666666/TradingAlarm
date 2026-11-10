"""Fixed seven-symbol indicator/source join only. Never imports/runs an account."""
from pathlib import Path
import csv, gzip, hashlib, json, math
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SRC={}
SELECTION={'002583.SZ':[2017,2039], '601066.SH':[1916,1958],
 '002670.SZ':[2225], '601995.SH':[1915], '601601.SH':[1904,1914,1931],
 '601319.SH':[1884,1897,1911,1952], '601628.SH':[1893,1907,1930]}
NAMES={'002583.SZ':'海能达','601066.SH':'中信建投','002670.SZ':'国盛证券',
 '601995.SH':'中金公司','601601.SH':'中国太保','601319.SH':'中国人保','601628.SH':'中国人寿'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return json.load(f)
def frame(p,expected=None):
 p=Path(p);h=sha(p);assert expected is None or h==expected
 SRC[str(p.resolve())]=h;return pd.read_parquet(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,pd.Timestamp):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

protocol=read(O/'PROTOCOL.json')
ms={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
bp=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair/B.json.gz'
book=read(bp,True)
cal=pd.DatetimeIndex([pd.Timestamp(x['at'][:10]) for x in book['decisions']])
assert cal.is_unique and cal.is_monotonic_increasing
daily_p=bp.parent/'daily.jsonl.gz';SRC[str(daily_p.resolve())]=sha(daily_p)
daily={}
with gzip.open(daily_p,'rt') as f:
 for line in f:
  d=json.loads(line);day=d['at'][:10]
  daily[day]=dict(at=d['at'],layers=[h for h in d['layers'] if h['sid'] in SELECTION],
                  pending_sells=d['pending_sells'],on=d['on'])
requests={}
for ai,a in enumerate(book['audit']):
 if a['kind']=='pilot_layer_exit' and a.get('sid') in SELECTION:
  for lid in a['layers']:
   requests.setdefault(lid,[]).append(dict(book_audit_index=ai,raw=a))
buys={t['layer']:t for t in book['trades'] if t['side']=='buy' and t['security_id'] in SELECTION}
selected_layers={x['id']:x for x in book['layers'] if x['sid'] in SELECTION}
ca=[dict(book_audit_index=i,raw=a) for i,a in enumerate(book['audit']) if a['kind']=='split' and any(s in str(a) for s in SELECTION)]

allrows=[]; summaries=[]; layer_summary=[]; warm={}; keyrows=[]
for sid,ids in SELECTION.items():
 m=ms[sid];f=frame(m['refs']['facts'],m['output_sha256'][m['refs']['facts']])
 sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 raw=frame(sp,m['source_sha256'][sp]).reindex(f.index)
 cp=frame(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])
 assert f.index.is_unique and f.index.is_monotonic_increasing
 ok=(raw.price_eligible.eq(True)&raw.observed_bar.eq(True)&raw.source_invalid.eq(False)
     &raw.synthetic_event_bar.eq(False)&np.isfinite(f.close)&f.close.gt(0)
     &raw.segment_id.eq(f.segment_id)&np.isclose(raw.close,f.close,rtol=1e-10,atol=1e-10))
 e=pd.Series(np.nan,index=f.index);n=pd.Series(0,index=f.index,dtype=int)
 run=f.segment_id.ne(f.segment_id.shift()).cumsum()
 for _,g in f.groupby(run,sort=False):
  ix=g.index[ok.loc[g.index]]
  e.loc[ix]=f.loc[ix,'close'].astype(float).ewm(alpha=2/21,adjust=False,min_periods=20).mean()
  n.loc[ix]=np.arange(1,len(ix)+1)
 z=f.reindex(cal).copy();z['valid']=ok.reindex(cal).fillna(False);z['E']=e.reindex(cal);z['n']=n.reindex(cal)
 z['E5']=z.E.shift(5);z['slope']=(z.E-z.E5)/5
 valid6=z.valid.eq(True).rolling(6,min_periods=6).sum().eq(6)
 # All six days, not merely endpoints, must be in one original source run.
 run_cal=run.reindex(cal)
 same6=run_cal.rolling(6,min_periods=6).min().eq(run_cal.rolling(6,min_periods=6).max())
 z['ready']=valid6&same6&z.E.notna()&z.E5.notna()
 hit=z.ready&z.close.lt(z.E)&z.slope.lt(0)
 warm[sid]=dict(full_history_first=str(f.index[0].date()),source_rows=len(f),
   visible_start='2024-08-01',first_visible_valid_observations=int(z.loc['2024-08-01':,'n'].iloc[0]),
   full_history_seed=True,EMA_ready_observations=20,sixty_not_additional_gate=True)
 first_per_layer={}
 prior_by_layer={}
 for j,day in enumerate(cal):
  ds=str(day.date());d=daily[ds];s=z.loc[day]
  current=[h for h in d['layers'] if h['sid']==sid]
  fac=float(s.factor) if pd.notna(s.factor) else math.nan
  factor_ok=bool(np.isfinite(fac) and fac>0 and pd.notna(s.raw_close)
   and np.isclose(float(s.close),fac*float(s.raw_close),rtol=1e-10,atol=1e-10))
  hrows=[]
  for h in current:
   lid=h['id'];rq=requests.get(lid,[]);first=min((a['raw']['at'] for a in rq),default=None)
   before=bool(first and first<d['at']);after=bool(first and first<=d['at'])
   old=prior_by_layer.get(lid)
   oldfloor=(old['last_core_line'] if h['kind']=='core' else old['floor']) if old else buys[lid]['floor']
   original_floor_adj=h['last_core_line'] if h['kind']=='core' else h['floor']
   hrows.append(dict(layer=lid,kind=h['kind'],qty=h['qty'],target_loss_layer=lid in ids,
    original_first_request=first,pending_before_original_CLOSE=before,pending_after_original_CLOSE=after,
    original_request_same_CLOSE=bool(first==d['at']),
    old_floor_used_at_original_CLOSE_adj=oldfloor,
    floor_after_original_CLOSE_adj=original_floor_adj,
    floor_after_original_CLOSE_raw=float(original_floor_adj)/fac if factor_ok else None,
    note='Old floor from preceding original daily snapshot; first-held-day floor from original buy fill. Current snapshot is after original CLOSE checks/ratchet, not an alternate floor simulation.'))
   if h['kind']=='add' and bool(s.ready) and bool(hit.loc[day]) and not after:
    first_per_layer.setdefault(lid,ds)
   prior_by_layer[lid]=h
  if not '2024-08-01'<=ds<='2024-12-31':continue
  c=cp.loc[day] if day in cp.index else None
  cond=bool(hit.loc[day]) if bool(s.ready) else None
  prev_slope=z.slope.iloc[j-1] if j else math.nan
  cross=(bool(prev_slope>=0 and s.slope<0) if j and bool(z.ready.iloc[j-1]) and bool(s.ready) else None)
  mobile=[h for h in hrows if h['kind']=='add']
  row=dict(sid=sid,name=NAMES[sid],day=ds,signal_at=d['at'],source_segment=s.segment_id,
   raw_C=s.raw_close,adjusted_C=s.close,factor=fac,factor_valid=factor_ok,
   raw_display_status='READY' if factor_ok else 'UNKNOWN',
   raw_display_unknown_reason=[] if factor_ok else ['missing_or_invalid_original_factor'],
   EMA20_adj=s.E,EMA20_raw=s.E/fac if factor_ok else None,
   EMA_tminus5_adj=s.E5,EMA_tminus5_raw=s.E5/fac if factor_ok else None,
   tminus5_market_day=str(cal[j-5].date()) if j>=5 else None,
   slope5_adj=s.slope if bool(s.ready) else None,
   slope5_raw=s.slope/fac if factor_ok and bool(s.ready) else None,
   valid_current_quote=bool(s.valid),all_six_market_sessions_valid=bool(valid6.iloc[j]),
   same_six_source_run=bool(same6.iloc[j]),valid_observations_in_source=s.n,
   EMA20_ready=bool(s.E==s.E),slope5_ready=bool(s.ready),
   C_below_EMA20=bool(s.close<s.E) if bool(s.valid) and pd.notna(s.E) else None,
   slope5_negative=bool(s.slope<0) if bool(s.ready) else None,
   slope5_first_cross_nonnegative_to_negative=cross,joint_condition_state=cond,
   unknown_reason=[] if bool(s.ready) else ['invalid_quote_or_missing_required_session_or_source_boundary_or_EMA_warmup'],
   I_target=s.i_target,I_floor_adj=s.i_floor,I_floor_raw=s.i_floor/fac if factor_ok and pd.notna(s.i_floor) else None,
   CP_receipt=bool(c.receipt) if c is not None and pd.notna(c.receipt) else None,
   CP_candidate_adj=c.candidate if c is not None else None,
   CP_candidate_raw=c.candidate/fac if c is not None and factor_ok and pd.notna(c.candidate) else None,
   original_ACT_on=d['on'],original_stock_exit_pending_after_CLOSE=sid in d['pending_sells'],
   original_MOBILE_held_qty=sum(h['qty'] for h in mobile),
   original_MOBILE_held_layers=[h['layer'] for h in mobile],
   original_MOBILE_pending_before=[h['layer'] for h in mobile if h['pending_before_original_CLOSE']],
   original_MOBILE_pending_after=[h['layer'] for h in mobile if h['pending_after_original_CLOSE']],
   candidate_new_request_layers_after_original=[h['layer'] for h in mobile if cond is True and not h['pending_after_original_CLOSE']],
   first_additional_candidate_request_layers_on_original_prefix=[h['layer'] for h in mobile if first_per_layer.get(h['layer'])==ds],
   earliest_next_market_OPEN=f'{cal[j+1].date()} 09:30:00+08:00' if j+1<len(cal) else None,
   earliest_OPEN_is_not_fill_prediction=True,original_layer_state=hrows)
  allrows.append(row)
  if (sid=='002583.SZ' and ds in ['2024-10-31','2024-11-04','2024-11-05']) or (sid=='601601.SH' and ds in ['2024-10-08','2024-10-09']):keyrows.append(row)
 for lid in ids:
  h=selected_layers[lid]
  if h['kind']!='add':
   layer_summary.append(dict(sid=sid,layer=lid,kind=h['kind'],excluded='CORE_NOT_AFFECTED_BY_MOBILE_ONLY'));continue
  opened=pd.Timestamp(h['opened'][:10]);closed=pd.Timestamp(h['closed'][:10]) if h.get('closed') else pd.Timestamp.max
  hd=(cal>=opened)&(cal<closed)
  # Includes original request CLOSE and any pending-to-fill interval.
  hit_days=cal[hit&hd]
  first=str(hit_days[0].date()) if len(hit_days) else None
  rq=requests.get(lid,[]);req=min((a['raw']['at'] for a in rq),default=None)
  layer_summary.append(dict(sid=sid,name=NAMES[sid],layer=lid,kind=h['kind'],opened=h['opened'],
   original_first_request=req,original_request_source=rq,
   original_fill_closed=h.get('closed'),first_joint_state_while_original_held_including_pending=first,
   first_additional_request_before_original=first_per_layer.get(lid),
   earlier_than_original_request=bool(first and req and first<req[:10]),
   original_sells=[dict(book_trade_index=i,raw=t) for i,t in enumerate(book['trades'])
      if t['side']=='sell' and any(p['layer']==lid for p in t.get('parts',[]))]))
 chosen=[x for x in layer_summary if x['sid']==sid and 'excluded' not in x]
 summaries.append(dict(sid=sid,name=NAMES[sid],selected_mobile_layers=[x['layer'] for x in chosen],
  original_first_mobile_request=min((x['original_first_request'] for x in chosen if x['original_first_request']),default=None),
  first_joint_state_while_selected_original_mobile_held=min((x['first_joint_state_while_original_held_including_pending'] for x in chosen if x['first_joint_state_while_original_held_including_pending']),default=None),
  any_earlier_request=any(x['earlier_than_original_request'] for x in chosen),
  first_joint_state_visible_any_position_status=min((r['day'] for r in allrows if r['sid']==sid and r['joint_condition_state'] is True),default=None)))

save('DAILY_TIMELINE.json',allrows)
save('TARGET_LAYER_REQUEST_COMPARISON.json',layer_summary)
save('SEVEN_STOCK_SUMMARY.json',summaries)
save('KEY_DATES.json',keyrows)
flat=[{k:v for k,v in r.items() if k!='original_layer_state'} for r in allrows]
with (O/'DAILY_TIMELINE.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader()
 for r in flat:w.writerow({k:json.dumps(clean(v),ensure_ascii=False) if isinstance(v,(list,dict)) else clean(v) for k,v in r.items()})
save('SOURCE_AND_SCOPE.json',dict(status='INDICATOR_AND_ORIGINAL_STATE_JOIN_ONLY_NO_ACCOUNT',
 source_sha256=SRC,script_sha256=sha(__file__),warmup=warm,selected_symbols=list(SELECTION),
 original_selected_split_audit=ca,rows=len(allrows),new_accounts=0,new_backtests=0,new_strategy_paths=0,
 protection_source='Original saved daily post-CLOSE layer snapshots; no new floor state machine.',
 request_source='Original book pilot_layer_exit per-layer unions; single exit_request alone is stock-level only.',
 pending_included=True,ema_alpha=2/21,ema_adjust=False,EMA_ready_count=20,
 original_market_session_source=str(bp.resolve())+' decisions[].at',
 old_EMA20_plugin='trend_exit_controls_v1/prepare_indicators.py and PROTOCOL.txt: original C<EMA20 all-position arm, no negative-slope gate'))
print(json.dumps(clean(summaries),ensure_ascii=False,indent=2))
print('KEY_DATES',json.dumps(clean(keyrows),ensure_ascii=False))
