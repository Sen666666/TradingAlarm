# Saved-path observational labels, not a re-entry strategy or account run.
GP=EP/'gap_recovery_v1'
neg=[r for r in anchors if r['signal_to_open_gap']<0]
assert Counter(r['outcome'] for r in neg)=={'WIN':56,'LOSS':323}
rmap={(r['sid'],r['id']):r for r in closed};checksmap={(r['sid'],r['id']):r for r in checks}
fixedmap={(r['sid'],r['round_id']):r for r in labels if r['mode']=='fixed_future_label'}
nf={s:pd.read_parquet(sm[s]['refs']['facts'],columns=['factor','close','i_target','i_floor','i_buy']) for s in {r['sid'] for r in neg}}
recrows=[];sequences=[]
for an in neg:
 sid=an['sid'];rid=an['round_id'];r=rmap[sid,rid];ff=nf[sid];df=raw[sid];entry=pd.Timestamp(an['opened'][:10]);exitday=pd.Timestamp(r['closed'][:10]);signal=an['signal_close_adjusted'];first=min((buys[i] for i in r['layer_ids']),key=lambda t:(t['at'],t['layer']));entryfloor=first['floor']
 valid=df.price_eligible & df.observed_bar & ~df.synthetic_event_bar
 allobs=df.loc[valid & (df.index>=entry) & (df.index<=cutoff)]
 for mode in ['fixed20','actual_holding']:
  window=allobs.iloc[:20] if mode=='fixed20' else allobs.loc[allobs.index<exitday]
  seq=[]
  for day,row in window.iterrows():
   if day not in ff.index:continue
   fr=ff.loc[day];factor=D(str(float(fr.factor)));adjusted=D(str(row.close))*factor
   seq.append(dict(account='PVR',sid=sid,round_id=rid,mode=mode,day=str(day.date()),observation=len(seq)+1,raw_close=D(str(row.close)),factor=factor,adjusted_close=adjusted,ratio_to_original_signal=adjusted/signal-D(1),return_to_first_fill=adjusted/(first['price']*an['entry_factor'])-D(1),i_target=bool(fr.i_target),below_original_entry_floor=adjusted<=entryfloor,held=day<exitday))
  recovered=next((z for z in seq if z['adjusted_close']>=signal),None)
  before=[z for z in seq if recovered is None or z['day']<recovered['day']]
  through=[z for z in seq if recovered is None or z['day']<=recovered['day']]
  low=min(before,key=lambda z:z['adjusted_close']) if before else None
  stopday=recovered['day'] if recovered else (seq[-1]['day'] if seq else an['opened'][:10])
  actual_triggers=[z for z in A['audit_log'] if z['kind']=='pilot_layer_exit' and z.get('sid')==sid and an['opened'][:10]<=str(z['at'])[:10]<=stopday and set(z['layers'])&set(r['layer_ids'])]
  unique_triggers=sorted({(str(z['at']),z['reason']) for z in actual_triggers})
  row=dict(account='PVR',sid=sid,round_id=rid,outcome=an['outcome'],entry_quarter=an['entry_quarter'],mode=mode,opened=an['opened'],signal_at=an['signal_at'],closed=r['closed'],signal_to_open_gap=an['signal_to_open_gap'],signal_adjusted_close=signal,entry_raw_open=first['raw_open'],entry_fill_price=first['price'],original_entry_floor_signal=entryfloor,first_role=first['kind'],n_observations=len(seq),recovered=recovered is not None,recovery_day=recovered['day'] if recovered else None,recovery_observation=recovered['observation'] if recovered else None,recovery_same_day=bool(recovered and recovered['day']==an['opened'][:10]),recovery_before_actual_exit=bool(recovered and recovered['held']),lowest_close_before_recovery_day=low['day'] if low else None,lowest_adjusted_close_before_recovery=low['adjusted_close'] if low else None,lowest_ratio_to_signal_before_recovery=low['ratio_to_original_signal'] if low else None,any_I_false_through_recovery=any(not z['i_target'] for z in through),any_close_below_entry_floor_through_recovery=any(z['below_original_entry_floor'] for z in through),actual_exit_triggers_through_recovery=unique_triggers,actual_round_pnl=r['pnl'],actual_holding_peak_cumulative_pnl=checksmap[sid,rid]['max_cumulative_round_pnl'],actual_holding_peak_remaining_U=checksmap[sid,rid]['max_U'],fixed20_price_return=fixedmap[sid,rid]['day20_return'],fixed20_price_MFE=fixedmap[sid,rid]['day20_MFE'])
  if recovered:
   recday=pd.Timestamp(recovered['day']);after=df.loc[(df.index>recday)&(df.index<=cutoff)]
   after=after[after.observed_bar & after.open.gt(0)]
   if len(after):
    nd=after.index[0];nr=after.iloc[0];fac=ff.loc[nd,'factor'] if nd in ff.index else None;adjusted_open=D(str(nr.open))*D(str(float(fac))) if fac is not None and pd.notna(fac) else None
    known=ff.loc[recday]
    row.update(next_observed_open_day=str(nd.date()),next_observed_raw_open=D(str(nr.open)),next_open_factor=fac,next_open_adjusted=adjusted_open,next_open_at_or_above_signal=adjusted_open>=signal if adjusted_open else None,next_open_above_original_entry_floor=adjusted_open>entryfloor if adjusted_open else None,recovery_close_I_target=bool(known.i_target),recovery_close_I_buy=bool(known.i_buy),next_open_still_held_baseline=nd<exitday,quote_only_no_execution_or_admission_claim=True)
  recrows.append(row);sequences.extend(seq)
print('RECOVERY_SUMMARY',[(mode,outcome,len(z),sum(r['recovered'] for r in z),sum(r['recovery_same_day'] for r in z),sum(r.get('next_open_at_or_above_signal') is True for r in z),sum(r['any_I_false_through_recovery'] for r in z)) for mode in ['fixed20','actual_holding'] for outcome in ['WIN','LOSS'] for z in [[r for r in recrows if r['mode']==mode and r['outcome']==outcome]]],flush=True)
pd.DataFrame(recrows).to_csv(GP/'RECOVERY_PATHS.csv',index=False);pd.DataFrame(sequences).to_csv(GP/'RECOVERY_DAILY_SEQUENCES.csv',index=False)
(GP/'RECOVERY_METADATA.json').write_text(json.dumps(dict(checkpoint_sha256=h,filter='ENTRY_ANCHORS.signal_to_open_gap < 0',counts=dict(Counter(r['outcome'] for r in neg)),join_key=['account','sid','round_id','mode'],reclaim='observed eligible non-synthetic close times original same-day factor >= original signal adjusted close',original_floor='fixed first-buy signal-unit floor; not claimed to replace actual dynamic mobile floor',next_open='next observed positive raw opening quote, no use of same-day HLC/V for eligibility; adjusted using same-date factor; no fill/admission guarantee',actual_stop_events='saved pilot_layer_exit through reclaim date, filtered by actual round layer IDs',cutoff=str(cutoff.date()),account_runs=0),indent=2))
