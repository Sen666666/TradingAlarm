# Static source excerpts; no imports/execution

## adapter /Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/selection_qualification_closeout_v1/eligibility_source/stock_signal.py:25

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
  41     inputs=f[['open','high','low','close','volume','segment_id']].copy()
  42     inputs['valid_price_observation']=True
  43     inputs['valid_strength_observation']=np.isfinite(inputs.volume)&inputs.volume.gt(0)
  44     evidence,_=build_evidence(inputs)
  45     g,_=classify(evidence)
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

## B4 /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:85

```python
  85 def _log_prices(close):
  86     # Ratios remove the arbitrary price unit before log. Use differences of
  87     # logs only where extreme but finite positive inputs overflow/underflow.
  88     with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
  89         p = np.log(close / close[0])
  90     exceptional = ~np.isfinite(p)
  91     if exceptional.any():
  92         p[exceptional] = np.log(close[exceptional]) - math.log(float(close[0]))
  93     return p
```

## B4 /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:163

```python
 163     for t in range(len(f)):
 164         if t >= 1:
 165             for h in PACE_SPANS:
 166                 alpha = 2. / (h + 1.)
 167                 mu[h] = float(r[t]) if mu[h] is None else float(alpha * r[t] + (1. - alpha) * mu[h])
 168         row = _blank_row()
 169         if t < 64:
 170             rows.append(row)
 171             continue
 172 
 173         # Exactly the preceding 63 returns and 21 volumes; never today's data.
 174         scale = max(1.4826 * float(np.median(np.abs(r[t - 63:t]))), 1e-8)
 175         vref = float(np.median(v[t - 21:t]))
 176         activity = float(v[t] / vref)
 177         q = float(r[t] / scale)
 178         qeff = float(q * math.sqrt(float(np.clip(activity, 1., 4.)) if joint else 1.))
```

## B4 /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:195

```python
 195         for h in SCALES:
 196             row[f'delta_{h}'] = float(math.sqrt(h) * scale)
 197             row[f'confirmed_{h}'] = 0.
 198             row[f'confirmed_direction_{h}'] = 0.
 199             if h not in states:
 200                 states[h] = dict(
 201                     direction=0, high=float(p[t - 1]), low=float(p[t - 1]),
 202                     high_observation=t - 1, low_observation=t - 1,
 203                     candidates={
 204                         1: fresh_candidate(t, t - 1, h, 1, scale, vref, 'initialization'),
 205                         -1: fresh_candidate(t, t - 1, h, -1, scale, vref, 'initialization'),
 206                     },
 207                 )
 208             state = states[h]
 209             before = state['direction']
 210             candidates = state['candidates']
 211 
 212             # Only extrema belonging to the active structure are maintained.
 213             # Before first confirmation both initial candidates are available.
 214             if before >= 0 and gt(float(p[t]), state['high']):
 215                 state['high'], state['high_observation'] = float(p[t]), t
 216                 candidates[-1] = fresh_candidate(
 217                     t, t, h, -1, scale, vref, 'new_high', candidates.get(-1))
 218             if before <= 0 and lt(float(p[t]), state['low']):
 219                 state['low'], state['low_observation'] = float(p[t]), t
 220                 candidates[1] = fresh_candidate(
 221                     t, t, h, 1, scale, vref, 'new_low', candidates.get(1))
```

## B4 /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:223

```python
 223             # A single return cannot provide same-day directional extension in
 224             # both directions. The assertion also prevents an accidental double
 225             # confirmation if the implementation changes later.
 226             confirmations = []
 227             for direction, candidate in candidates.items():
 228                 if advance_candidate(t, h, candidate):
 229                     confirmations.append(direction)
 230             if len(confirmations) > 1:
 231                 raise AssertionError('At most one structure confirmation per scale and observation')
 232             if confirmations:
 233                 direction = confirmations[0]
 234                 receipt = copy.deepcopy(candidates[direction])
 235                 emit(t, 'structure_confirmed', horizon=h, previous_direction=before,
 236                      direction=direction, r=float(r[t]), volume=float(v[t]),
 237                      s=scale, lag_volume_reference=vref,
 238                      close=float(close[t]), log_close=float(p[t]), joint=bool(joint),
 239                      receipt=receipt)
 240                 state['direction'] = direction
 241                 row[f'confirmed_{h}'] = 1.
 242                 row[f'confirmed_direction_{h}'] = float(direction)
 243                 state['candidates'] = {
 244                     -direction: fresh_candidate(
 245                         t, t, h, -direction, scale, vref, 'direction_confirmed',
 246                         candidates.get(-direction))
 247                 }
 248                 # On confirmation discard the old structure's extreme. The
 249                 # new direction starts its running high/low at today's close.
 250                 if direction == 1:
 251                     state.update(high=float(p[t]), high_observation=t,
 252                                  low=None, low_observation=None)
 253                 else:
 254                     state.update(low=float(p[t]), low_observation=t,
 255                                  high=None, high_observation=None)
```

## B4 /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:277

```python
 277         rows.append(row)
 278 
 279     out = pd.DataFrame(rows, index=f.index, columns=FIELDS + DATE_FIELDS + ['phase'])
 280     out.attrs['terminal'] = copy.deepcopy(states) if states else None
 281     return out, journal
 282 
 283 
 284 def strength_frame(f, joint=True):
 285     """Return a causal indicator frame and journal, restarting per source segment.
 286 
 287     Invalid observations remain entirely unknown, and do not advance the valid
 288     clock. A later valid close bridges their price gap. Missing/invalid source
 289     identities are rejected; a new explicit segment restarts all warm-up and
 290     structure state and archives the old state as a source discontinuity.
```

## B4 /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:310

```python
 310     out = pd.DataFrame(np.nan, index=f.index, columns=FIELDS)
 311     for column in DATE_FIELDS:
 312         out[column] = pd.Series(None, index=f.index, dtype=object)
 313     out['phase'] = 'unknown'
 314     journal, terminal, previous = [], None, None
 315     for segment, group in f.groupby('segment_id', sort=False):
 316         if terminal:
 317             journal.append(dict(
 318                 segment=str(segment), date=str(group.index[0].date()), observation=None,
 319                 kind='source_discontinuity', previous_segment=previous,
 320                 unresolved=terminal,
 321             ))
 322         good = group.loc[group.valid_strength_observation]
 323         if len(good):
 324             a = good[['close', 'volume']].to_numpy(float)
 325             if not np.isfinite(a).all() or not (a > 0).all():
 326                 raise ValueError('Finite positive valid price/volume required')
 327             frame, events = run_valid(good, joint)
 328             out.loc[good.index, frame.columns] = frame
 329             journal.extend(dict(segment=str(segment), **event) for event in events)
 330             terminal = frame.attrs['terminal']
 331         else:
 332             terminal = None
 333         previous = str(segment)
 334     out.attrs['terminal'] = terminal
 335     out.attrs['model'] = 'PVS-B4'
 336     out.attrs['pace_units'] = 'mu5/mu21: log return per valid observation; *_bp: log bp per valid observation'
```

## evidence /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:160

```python
 160 def build_evidence(f):
 161     """Return (market_frame, {'events': list, 'strength': original_B4_list}).
 162 
 163     All rows are retained.  Price-invalid rows have unknown E0 facts; missing
 164     volume on a price-valid row still permits price facts and ready to persist.
 165     Extra input columns are intentionally not forwarded.  B4's 101 output
 166     columns receive only a `strength_` prefix; its journal stays unchanged.
```

## evidence /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:184

```python
 184         bars = group.loc[group.valid_price_observation, ["open", "high", "low", "close", "volume"]].astype(float)
 185         if bars.empty:
 186             continue
 187         events, event_clock = _event_facts(bars)
 188         facts.loc[bars.index, EVENT_COLUMNS] = events
 189         facts.loc[bars.index, "event_observation"] = event_clock
 190         facts.loc[bars.index, "price_observation"] = np.arange(len(bars), dtype=float)
 191         strength_dates = group.index[group.valid_strength_observation]
 192         facts.loc[strength_dates, "strength_observation"] = np.arange(len(strength_dates), dtype=float)
 193         v = bars.volume.where(np.isfinite(bars.volume) & bars.volume.gt(0))
 194         volume_base = v.shift().rolling(21, min_periods=21).median()
 195         ratios = v / volume_base
 196         ready, previous_close = False, math.nan
 197         for n, (date, bar) in enumerate(bars.iterrows()):
 198             ev = events.loc[date]
 199             ready = ready or bool(pd.notna(ev.leg_direction))
 200             c, low = float(bar.close), float(bar.low)
```

## evidence /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:227

```python
 227     b4 = _load_frozen_b4()
 228     strength, strength_journal = b4.strength_frame(f, joint=True)
 229     out = pd.concat([out, facts[FACT_COLUMNS + EVENT_COLUMNS], strength.add_prefix("strength_")], axis=1)
 230     out.attrs.update(
 231         model="PVS-B5", strength_source=str(B4_SOURCE.relative_to(ROOT)),
 232         strength_sha256=B4_SHA256, strength_attrs=strength.attrs.copy(),
 233         clocks="price: explicit mask; event: price plus positive finite C/V; strength: explicit subset mask",
 234         journal_contract="events: pure event/candidate receipts; strength: unchanged frozen B4 journal",
 235     )
 236     return out, {"events": event_journal, "strength": strength_journal}
```

## G1 /Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:13

```python
  13     rows=[];events=[];previous_segment=None;previous_grade=None;prior_extreme=math.nan;prior_s21=0
  14     for dt,r in e.iterrows():
  15         segment=str(r.segment_id)
  16         if segment!=previous_segment:
  17             previous_grade=None;prior_extreme=math.nan;prior_s21=0;previous_segment=segment
  18         out=dict(date=dt,segment_id=segment,ready=False,proposal=np.nan,grade=np.nan,score=np.nan,label='未知',phase='unknown',z5=np.nan,z21=np.nan,fresh_up=False,up_reasons='',transition='unknown',promotion_blocked=False,acute_down=False,acute_up=False,display='未知')
  19         if not bool(r.valid_strength_observation) or not np.isfinite(r.strength_mu21):rows.append(out);continue
  20         a,b=int(r.strength_S21),int(r.strength_S63);m5=float(r.strength_mu5);m21=float(r.strength_mu21);scale=float(r.strength_s)
  21         z5=math.sqrt(5)*m5/scale;z21=math.sqrt(21)*m21/scale
  22         down=bool(r.strength_acute_down);up=bool(r.strength_acute_up)
  23         reasons=[]
  24         if int(r.event)==1:reasons.append('new_E0_price_volume_up_event')
  25         for h in [21,63]:
  26             if float(r[f'strength_confirmed_direction_{h}'])==1:reasons.append(f'new_S{h}_up_confirmation')
  27         ext=float(r.strength_running_extreme_price_21)
  28         if a==1 and prior_s21==1 and np.isfinite(prior_extreme) and ext>prior_extreme+32*np.finfo(float).eps*max(abs(ext),abs(prior_extreme),1):reasons.append('new_price_frontier_in_confirmed_up_structure')
  29         fresh=bool(reasons)
```

## G1 /Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:44

```python
  44         proposal=g;old=previous_grade
  45         blocked=old is not None and proposal>old and not fresh
  46         if blocked:g=old
  47         transition='initialize' if old is None else 'upgrade' if g>old else 'downgrade' if g<old else 'blocked_upgrade' if blocked else 'unchanged'
  48         if down:phase='acute_down'
  49         elif launch:phase='fast_launch'
  50         elif up:phase='acute_up'
  51         elif a==b==1 and z5>=1 and z21>=1:phase='expansion'
  52         elif m21<0 and m5>0:phase='local_repair' if a==1 else 'downtrend_rebound'
  53         elif m21<0 and m5<=0:phase='decline'
  54         elif a==b==1 and (m5<0 or abs(z21)<1):phase='up_structure_consolidation'
  55         elif a==b==1:phase='up_continuation'
  56         elif a==1:phase='up_structure_building'
  57         elif a==b==0:phase='unconfirmed'
  58         else:phase='mixed_evidence'
  59         out.update(ready=True,proposal=proposal,grade=g,score=25*g,label=LABELS[g],phase=phase,z5=z5,z21=z21,fresh_up=fresh,up_reasons='|'.join(reasons),transition=transition,promotion_blocked=blocked,acute_down=down,acute_up=up,display=('freeze·' if down else '')+LABELS[g],reason=why)
  60         if transition!='unchanged':events.append(dict(date=str(dt.date()),segment=segment,previous=old,proposal=proposal,grade=g,score=25*g,kind=transition,basis=why,new_up_evidence=reasons))
  61         rows.append(out);previous_grade=g;prior_extreme=ext;prior_s21=a
  62     f=pd.DataFrame(rows).set_index('date')
  63     return f,events
```

## E0policy /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:86

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

## E0policy /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:164

```python
 164         if pending:
 165             record = dict(pending)
 166             record.update(resolved_date=None, outcome="open", response=0,
 167                           independent_entry=0, original_entry_same_day=0,
 168                           resolution_volume_ratio=None,
 169                           waiting_observations=len(bars)-1-pending["created_observation"],
 170                           segment_id=str(segment))
 171             ledger.append(record)
 172     columns = list(STATE_TYPES) + ["segment_id"]
 173     if rows:
 174         state = pd.DataFrame(rows).set_index("date").reindex(frame.index)[columns]
 175     else:
 176         state = pd.DataFrame(index=frame.index, columns=columns)
 177     # The original participation DataFrame builds its index from row dates,
 178     # which drops an input DatetimeIndex.freq.  Preserve that exact contract.
 179     state.index = pd.DatetimeIndex(state.index.to_numpy(), name="date")
 180     state_types = {column: ("Int64" if dtype == "int64" else dtype)
```

## Iproject /Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:6

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

## numeric /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:69

```python
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

## numeric /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:90

```python
  90         if not math.isfinite(sigma[t] + baseline[t]):
  91             rows.append(row)
  92             continue
  93         if ext is None:
  94             ext = t
  95         if active and not event_exit and compare(prices[t], floor) <= 0:
  96             active, row["exited"] = False, 1.0
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

## numeric /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:129

```python
 129         rows.append(row)
 130     result = pd.DataFrame(rows, index=d.index).reindex(close.index)
 131     for col in ("event", "entered", "exited"):
 132         result[col] = result[col].fillna(0.0)
 133     result["target"] = result.target.ffill().fillna(0.0)
 134     for col in ("confirmed_pivot_date", "developing_extreme_date"):
 135         result[col] = result[col].astype("string")
```

## eligibility /Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/data_utils.py:35

```python
  35     ohlc = out[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
  36     finite = np.isfinite(ohlc).all(axis=1) & ohlc.gt(0).all(axis=1)
  37     geometry = (
  38         ohlc.high.ge(ohlc.low)
  39         & ohlc.high.ge(ohlc[["open", "close"]].max(axis=1))
  40         & ohlc.low.le(ohlc[["open", "close"]].min(axis=1))
  41     )
  42     anomaly = (
  43         out.source_anomaly.fillna("").astype(str).str.strip().ne("")
  44         if "source_anomaly" in out else pd.Series(False, index=out.index)
  45     )
  46     keep = (
  47         finite & geometry
  48         & boolean_column(out, "observed_bar", True)
  49         & ~boolean_column(out, "synthetic_event_bar", False)
  50         & ~boolean_column(out, "source_invalid", False)
  51         & ~anomaly
  52         & ~out.index.isin(pd.to_datetime(list(exclude_dates)))
  53     )
  54     out.loc[:, ["open", "high", "low", "close"]] = ohlc
  55     if "volume" not in out:
  56         out["volume"] = np.nan
  57     out["volume"] = pd.to_numeric(out.volume, errors="coerce")
  58     return out.loc[keep].copy()
```
