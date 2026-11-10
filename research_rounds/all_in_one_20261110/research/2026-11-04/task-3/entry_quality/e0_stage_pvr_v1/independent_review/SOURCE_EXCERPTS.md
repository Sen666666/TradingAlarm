# Source excerpts (read only; line numbers from current bound bytes)

## stock_signal: /Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/selection_qualification_closeout_v1/eligibility_source/stock_signal.py:8

```python
   8 sys.path[:0]=[str(RR/'pv-strength-b5-20261025/code'),str(RR/'b5-g1-20261025/code'),str(RR/'pv-participation-response-20261020/code')]
   9 from data_utils import eligible_prices
  10 from numeric import event_frame_numeric
  11 from participation import participation_frame
  12 from evidence import build_evidence
  13 from policy import e0_policy
  14 from grade import classify
  15 from policies_g1 import project
```

## stock_signal: /Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/selection_qualification_closeout_v1/eligibility_source/stock_signal.py:25

```python
  25     assert frame.index.is_unique and frame.index.is_monotonic_increasing
  26     f=eligible_prices(frame).copy()
  27     if f.empty:return pd.DataFrame(index=f.index)
  28     assert f.segment_id.nunique()==1
  29     events=event_frame_numeric(f.close,f.volume,joint=True,event_exit=False)
  30     state,_=participation_frame(f,events,mode='volume')
  31     e=f[['segment_id','open','high','low','close','volume']].copy()
  32     e['valid_price_observation']=True
  33     e['price_observation']=e.groupby('segment_id',sort=False).cumcount()
  34     e['event']=events.event;e['confirmed_pivot_price']=events.confirmed_pivot_price
  35     e['ready']=state.ready;e['previous_close']=e.groupby('segment_id',sort=False).close.shift()
  36     v=e.volume.where(np.isfinite(e.volume)&e.volume.gt(0))
  37     e['volume_baseline']=v.groupby(e.segment_id,sort=False).transform(lambda q:q.shift().rolling(21,min_periods=21).median())
  38     for field in ['volume_ratio','high_effort','declined']:e[field]=state[field]
  39     e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
  40     base,_=e0_policy(e);assert not base.pending.fillna(0).any()
```

## stock_signal: /Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/selection_qualification_closeout_v1/eligibility_source/stock_signal.py:46

```python
  46     projected=project(e,base,g,'G1_I')
  47     out=pd.DataFrame(index=f.index)
  48     for n in ['ready','target','floor','entered','exited']:out['e0_'+n]=base[n]
  49     for n in ['target','floor','entered','exited','buy_event','exit_reason']:out['i_'+n]=projected[n]
  50     out=out.rename(columns={'i_buy_event':'i_buy'})
  51     for n in ['grade','ready','fresh_up','acute_down','up_reasons']:out['g_'+n]=g[n]
  52     out['numeric_event']=events.event
  53     out['numeric_leg_direction']=events.leg_direction
  54     out['close']=f.close
  55     return out
```

## numeric: /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:23

```python
  23 def compare(a: float, b: float) -> int:
  24     """Order finite nonnegative magnitudes, treating the gamma4 band as a tie.
  25 
  26     Homogeneous in exact arithmetic. Independent rounded rescaling can move an
  27     input on the band's boundary across it; universal scale invariance is NOT
  28     promised. Comparisons outside this band remain strict.
  29     """
  30     a, b = float(a), float(b)
  31     if not (math.isfinite(a) and math.isfinite(b) and a >= 0 and b >= 0):
  32         raise ValueError("finite nonnegative magnitudes required")
  33     if abs(a - b) <= GAMMA4 * max(a, b):
  34         return 0
  35     return 1 if a > b else -1
```

## numeric: /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:53

```python
  53 def higher(old: float, new: float) -> float:
  54     """The existing ratchet retains its actual old point on a numerical tie."""
  55     return float(new) if compare(new, old) > 0 else float(old)
```

## numeric: /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:67

```python
  67     if not close.index.is_unique or not close.index.is_monotonic_increasing:
  68         raise ValueError("ordered unique index required")
  69     raw = pd.concat([close.rename("close"), volume.rename("volume")], axis=1)
  70     d = raw.loc[raw.gt(0).all(axis=1) & np.isfinite(raw).all(axis=1)]
  71     if d.empty:
  72         raise ValueError("no valid observations")
  73     prices, volumes = d.close.to_numpy(), d.volume.to_numpy()
  74     returns = [math.nan] + [log_ratio(prices[t], prices[t - 1])
  75                               for t in range(1, len(d))]
  76     sigma = np.full(len(d), np.nan)
  77     baseline = d.volume.shift().rolling(21).median().to_numpy()
  78     for t in range(64, len(d)):
  79         sigma[t] = max(math.sqrt(math.fsum(x * x for x in returns[t - 63:t]) / 63), 1e-8)
```

## numeric: /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:80

```python
  80     direction, ext, active, floor = -1, None, False, math.nan
  81     rows = []
  82     for t, date in enumerate(d.index):
  83         row = dict(confirmation=math.nan, leg_direction=math.nan,
  84                    developing_extreme=math.nan, confirmed_pivot=math.nan,
  85                    structure_floor=math.nan, event=0.0, target=0.0,
  86                    entered=0.0, exited=0.0, pivot_age=math.nan,
  87                    developing_extreme_price=math.nan, confirmed_pivot_price=math.nan,
  88                    structure_floor_price=math.nan, confirmed_pivot_date=None,
  89                    developing_extreme_date=None)
  90         if not math.isfinite(sigma[t] + baseline[t]):
  91             rows.append(row)
  92             continue
  93         if ext is None:
  94             ext = t
  95         if active and not event_exit and compare(prices[t], floor) <= 0:
  96             active, row["exited"] = False, 1.0
```

## numeric: /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:97

```python
  97         extreme_order = compare(prices[t], prices[ext])
  98         if (direction == -1 and extreme_order < 0) or (direction == 1 and extreme_order > 0):
  99             ext = t
 100         if t > ext:
 101             activity = math.sqrt(
 102                 (math.fsum(float(x) for x in volumes[ext + 1:t + 1]) / (t - ext))
 103                 / baseline[ext]
 104             ) if joint else 1.0
 105             activity = min(max(activity, 0.5), 2.0)
 106             confirmation = (-direction) * log_ratio(prices[t], prices[ext]) * activity / (math.sqrt(5) * sigma[ext])
 107             row["confirmation"] = confirmation
 108             # A numerically indistinguishable exact threshold is inclusive.
 109             if compare(max(confirmation, 0.0), 1.0) >= 0:
 110                 event = -direction
 111                 pivot = float(prices[ext])
 112                 row.update(event=float(event), confirmed_pivot=math.log(pivot),
 113                            confirmed_pivot_price=pivot, pivot_age=float(t - ext),
 114                            confirmed_pivot_date=str(d.index[ext].date()))
 115                 if event == 1:
 116                     if active:
 117                         floor = higher(floor, pivot)
 118                     elif not row["exited"]:
 119                         active, floor, row["entered"] = True, pivot, 1.0
 120                 elif event_exit and active:
 121                     active, row["exited"] = False, 1.0
 122                 direction, ext = event, t
 123         row.update(leg_direction=float(direction),
 124                    developing_extreme=math.log(float(prices[ext])),
 125                    developing_extreme_price=float(prices[ext]),
 126                    developing_extreme_date=str(d.index[ext].date()), target=float(active))
 127         if active or row["exited"]:
 128             row.update(structure_floor=math.log(floor), structure_floor_price=floor)
```

## numeric: /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:129

```python
 129         rows.append(row)
 130     result = pd.DataFrame(rows, index=d.index).reindex(close.index)
 131     for col in ("event", "entered", "exited"):
 132         result[col] = result[col].fillna(0.0)
 133     result["target"] = result.target.ffill().fillna(0.0)
 134     for col in ("confirmed_pivot_date", "developing_extreme_date"):
 135         result[col] = result[col].astype("string")
```

## policy: /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:14

```python
  14 from arithmetic import compare, higher
```

## policy: /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:86

```python
  86         active, floor, pending = False, math.nan, None
  87         next_id = 0
  88         for n, (date, fact) in enumerate(bars.iterrows()):
  89             if fact.price_observation != n:
  90                 raise ValueError("Price observation clock must restart at zero and advance on valid rows")
  91             price_event = int(fact.event) if pd.notna(fact.event) else 0
  92             ready = bool(fact.ready)
  93             c = float(fact.close)
  94             q = float(fact.volume_ratio)
  95             declined, high_effort = bool(fact.declined), bool(fact.high_effort)
  96             entered = exited = created = response = consumed = independent = 0
  97             ended_id = None
  98             entry_kind = ""
  99             if active and compare(c, floor) <= 0:
 100                 active, exited = False, 1
 101             if pending:
 102                 if compare(c, pending["lower"]) < 0:
 103                     response = -1
 104                 elif compare(c, pending["reclaim"]) > 0:
 105                     response = 1
 106             if price_event == 1:
 107                 pivot = float(fact.confirmed_pivot_price)
 108                 if not math.isfinite(pivot):
 109                     raise ValueError("up event lacks canonical pivot")
 110                 if active:
 111                     floor = higher(floor, pivot)
 112                 elif not exited:
 113                     active, entered, floor = True, 1, pivot
 114                     entry_kind = "original_event"
```

## G1_I: /Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:6

```python
   6 def project(e,base,g,kind):
   7     if kind not in ['G1_I','G1_X','G1_IX']:raise ValueError(kind)
   8     use_i=kind in ['G1_I','G1_IX'];use_x=kind in ['G1_X','G1_IX']
   9     active=False;floor=math.nan;segment=None;rows=[]
  10     for dt,r in e.iterrows():
  11         b=base.loc[dt];a=g.loc[dt]
  12         if r.segment_id!=segment:active=False;floor=math.nan;segment=r.segment_id
  13         valid=bool(r.valid_price_observation)
  14         if not valid:
  15             rows.append(dict(date=dt,target=np.nan,entered=0,exited=0,floor=np.nan,exit_line=np.nan,buy_event=False,entry_kind='',exit_reason='',grade=a.grade));continue
  16         shadow=bool(b.target);ready=bool(a.ready);entered=exited=0;reason='';entry_kind=''
  17         fresh=bool(a.fresh_up) if ready else False
  18         warm=ready and a.grade>=2
  19         cold=ready and (a.grade<=-2 or bool(a.acute_down))
  20         if active:
  21             if not shadow or float(r.close)<=floor:reason='E0_structure_boundary'
  22             elif use_x and cold:reason='G1_cold_or_acute'
  23             if reason:active=False;exited=1
  24             elif np.isfinite(b.floor):floor=max(floor,float(b.floor))
  25         # Entry-only is a new-evidence gate and restoration channel, while
  26         # exit-only preserves E0's new-cycle entry stream. An exit-only entry
  27         # is first checked by the extra exit rule on the next observation,
  28         # matching the original sensitive-policy ordering.
  29         opportunity=shadow and warm and (bool(b.entered) or fresh) if use_i else bool(b.entered)
  30         if not active and not exited and opportunity:
  31             active=True;entered=1;floor=float(b.floor)
  32             entry_kind='G1_fresh_warm_evidence' if use_i else str(b.entry_kind)
  33         buy=bool(active and opportunity) if use_i else bool(active)
  34         rows.append(dict(date=dt,target=int(active),entered=entered,exited=exited,floor=floor if active or exited else np.nan,exit_line=floor if active or exited else np.nan,buy_event=buy,entry_kind=entry_kind,exit_reason=reason,grade=a.grade))
```

## native_cache: /Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py:16

```python
  16 def derive(sid,cut=END):
  17  start=time.monotonic();rec=RECORDS[sid];paths={k:OLD/rec['files'][k]['path'] for k in ['signal','events','states']}
  18  for k,p in paths.items():assert sha(p)==rec['files'][k]['sha256'],(sid,k)
  19  ip=IX/'signals'/f'{sid}.parquet';assert sha(ip)==IXRECORDS[sid]['output_sha256']
  20  signal=pd.read_parquet(paths['signal']).loc[:cut];x=pd.read_parquet(ip).loc[:cut];event=pd.read_parquet(paths['events']).reindex(x.index);state=pd.read_parquet(paths['states']).reindex(x.index);valid=eligible_prices(signal);assert valid.index.equals(x.index),(sid,'same price-observation clock')
  21  if x.empty:return pd.DataFrame(columns=COLS,index=pd.DatetimeIndex([],name=signal.index.name)),dict(sid=sid,status='no_observation_before_cut',rows=0,seconds=time.monotonic()-start)
  22  for c in ['open','high','low','close','volume','segment_id']:np.testing.assert_equal(x[c].to_numpy(),valid[c].to_numpy(),err_msg=sid+'/'+c)
  23  e=x[['segment_id','open','high','low','close','volume']].copy();e['valid_price_observation']=True;e['price_observation']=e.groupby('segment_id',sort=False).cumcount();e['event']=event.event;e['confirmed_pivot_price']=event.confirmed_pivot_price;e['ready']=state.ready;e['previous_close']=e.groupby('segment_id',sort=False).close.shift()
  24  v=e.volume.where(np.isfinite(e.volume)&e.volume.gt(0));e['volume_baseline']=v.groupby(e.segment_id,sort=False).transform(lambda q:q.shift().rolling(21,min_periods=21).median())
  25  for c in ['volume_ratio','high_effort','declined']:e[c]=state[c]
  26  e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
  27  base,_=e0_policy(e);assert not base.pending.fillna(0).any()
  28  g=x[['grade','strength_ready','fresh_up','acute_down']].rename(columns={'strength_ready':'ready'});out=project(e,base,g,'G1_I')
  29  keep=x[['close','segment_id']].copy()
  30  for mode,frame in [('e0',base),('i',out)]:
  31   for c in ['target','floor']:keep[mode+'_'+c]=frame[c]
  32  keep['i_buy']=out.buy_event
  33  for c in ['grade','fresh_up','acute_down','ready']:keep['g_'+c]=g[c]
  34  keep['e0_ready']=base.ready;keep['factor']=signal.adjustment_factor.reindex(keep.index);keep['raw_close']=signal.raw_close.reindex(keep.index);keep=keep[COLS]
```

## producer: /Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/full_local_signal_20240924_v1/signals/run_signals.py:163

```python
 163    begin=time.monotonic();g=groups.get(sid,pd.DataFrame(columns=COLS));current=g.loc[g.trade_date.eq(pd.Timestamp(DAY))]
 164    r=dict(sid=sid,day=DAY,signal_status='MISSING_TARGET_BAR',target_source_row_present=not current.empty,
 165        prefix_end_day=None if g.empty else str(g.trade_date.iloc[-1].date()),input_prefix_rows=len(g),
 166        input_prefix_first=None if g.empty else str(g.trade_date.iloc[0].date()),
 167        source_sha256=freeze['source_sha256'],algorithm_binding=str(HERE/'FREEZE.json'),
 168        full_S0_eligibility_q=None,stock_hold_signal=None,stock_fresh_core_signal=None,
 169        stock_signal_readiness='UNKNOWN_NO_EXACT_TARGET',model_invoked=False)
 170    try:
 171     assert g.trade_date.is_unique and(g.trade_date<=pd.Timestamp(DAY)).all()
 172     if not current.empty:
 173      assert len(current)==1 and g.source.nunique(dropna=False)==1 and g.source.notna().all()
 174      cur=current.iloc[0]
 175      for k in COLS:r['source_'+k]=cur[k]
 176      frame=g.set_index('trade_date')[['open','high','low','close','volume']].copy();frame['segment_id']=0
 177      before=time.monotonic();cpu0=resource.getrusage(resource.RUSAGE_SELF)
 178      out=pure.calculate(frame)
 179      cpu1=resource.getrusage(resource.RUSAGE_SELF)
 180      r.update(model_invoked=True,model_seconds=time.monotonic()-before,
 181         model_cpu_seconds=cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime,
 182         eligible_price_observations=len(out))
 183      if pd.Timestamp(DAY)in out.index:
 184       r.update(out.loc[pd.Timestamp(DAY)].to_dict());r=normalized(r);r['signal_status']='EXACT_TARGET_STOCK_SIGNAL'
 185      else:r['signal_status']='TARGET_REJECTED_BY_ORIGINAL_ELIGIBLE_PRICE_MASK'
```
