# Natural existing-source events, observational only. Never reuses an old receipt.
for sid in nf:
 nf[sid]['segment_id']=pd.read_parquet(sm[sid]['refs']['facts'],columns=['segment_id']).segment_id
cpfs={sid:pd.read_parquet(sm[sid]['refs']['CP1'],columns=['receipt','candidate']) for sid in nf}
sectors={x['runner']['sector_by_sid'][sid] for sid in nf}
isf={s:pd.read_parquet(im[s]['refs']['state']).set_index('day') for s in sectors}
opp={(r['sid'],r['day']):r for r in x['runner']['opportunities'] if r['account']=='PVR' and r['sid'] in nf}
natural=[];ngdaily=[]
def quote_after(sid,day,first,entryfac,signal,floor=None):
 df=raw[sid];q=df.loc[(df.index>pd.Timestamp(day))&(df.index<=cutoff)];q=q[q.observed_bar & q.open.gt(0)]
 if not len(q):return {}
 nd=q.index[0];f=nf[sid].loc[nd,'factor'] if nd in nf[sid].index else None
 if f is None or not pd.notna(f):return dict(next_open_day=str(nd.date()),next_open_adjusted=None)
 px=D(str(q.iloc[0].open))*D(str(float(f)));orig=first['raw_open']*entryfac
 return dict(next_open_day=str(nd.date()),next_open_raw=D(str(q.iloc[0].open)),next_open_factor=D(str(float(f))),next_open_adjusted=px,next_open_vs_original_O=px/orig-D(1),next_open_vs_signal=px/signal-D(1),next_open_above_new_floor=px>floor if floor is not None else None,next_open_calendar_delay=(nd-pd.Timestamp(first['at'].date())).days)
for an in neg:
 sid=an['sid'];rid=an['round_id'];r=rmap[sid,rid];ff=nf[sid];first=min((buys[i] for i in r['layer_ids']),key=lambda t:(t['at'],t['layer']));sigday=pd.Timestamp(first['signal_at'].date());initial=ff.loc[sigday];seg=initial.segment_id
 rr=next(t for t in recrows if t['sid']==sid and t['round_id']==rid and t['mode']=='fixed20')
 seq=[t for t in sequences if t['sid']==sid and t['round_id']==rid and t['mode']=='fixed20'];endday=seq[-1]['day'];firstbad=None;badwhy=None
 for d,z in ff.loc[sigday:pd.Timestamp(endday)].iterrows():
  if pd.isna(z.segment_id) or z.segment_id!=seg:firstbad=str(d.date());badwhy='source_segment_changed';break
  if pd.isna(z.i_target) or not bool(z.i_target):firstbad=str(d.date());badwhy='I_target_false_or_unknown';break
 eventrows=[]
 for z in seq:
  day=z['day'];d=pd.Timestamp(day);f=ff.loc[d];industry=isf[x['runner']['sector_by_sid'][sid]];ir=industry.loc[day] if day in industry.index else None;oo=opp.get((sid,day));c=cpfs[sid].loc[d] if d in cpfs[sid].index else None
  same=firstbad is None or day<firstbad
  cpnew=c is not None and pd.notna(c.receipt) and bool(c.receipt) and d>sigday
  recid=oo.get('CP1_id') if oo else None
  if recid is not None:assert recid!=first.get('CP1_id')
  floor=max(D(str(float(f.i_floor))),D(str(float(c.candidate)))) if cpnew and pd.notna(f.i_floor) and pd.notna(c.candidate) else None
  er=dict(account='PVR',sid=sid,round_id=rid,outcome=an['outcome'],day=day,observation=z['observation'],same_original_I_run=same,current_I_target=bool(f.i_target) if pd.notna(f.i_target) else None,current_I_buy=bool(f.i_buy) if pd.notna(f.i_buy) else None,current_price_reclaimed=z['adjusted_close']>=an['signal_close_adjusted'],fresh_CP1=cpnew,CP1_id=recid,mobile_Q=oo.get('mobile_Q') if oo else None,core_Q=oo.get('core_Q') if oo else None,industry_E0_valid=bool(ir.E0_valid) if ir is not None else None,industry_stage=ir.stage_name if ir is not None else None,new_mobile_floor_signal=floor,baseline_ACT_on=dmap[day]['on'] if day in dmap else None)
  eventrows.append(er);ngdaily.append(er)
 row=dict(account='PVR',sid=sid,round_id=rid,outcome=an['outcome'],entry_quarter=an['entry_quarter'],opened=an['opened'],signal_at=an['signal_at'],actual_round_pnl=r['pnl'],first_reclaim_day=rr['recovery_day'],first_original_run_invalid_day=firstbad,run_invalid_reason=badwhy,same_original_run_at_first_reclaim=bool(rr['recovered'] and (firstbad is None or rr['recovery_day']<firstbad)))
 if rr['recovered']:
  row.update({'reclaim_'+k:v for k,v in quote_after(sid,rr['recovery_day'],first,an['entry_factor'],an['signal_close_adjusted'],first['floor']).items()})
  cand=[z for z in eventrows if z['day']>=rr['recovery_day'] and z['same_original_I_run']]
  for label,pred in [('first_fresh_CP1',lambda z:z['fresh_CP1']),('first_I_buy',lambda z:z['current_I_buy']),('first_CP1_price_market_event',lambda z:z['fresh_CP1'] and z['current_price_reclaimed'] and z['mobile_Q'] is True and z['industry_E0_valid'] is True),('first_Ibuy_price_market_event',lambda z:z['current_I_buy'] and z['current_price_reclaimed'] and z['core_Q'] is True and z['industry_E0_valid'] is True)]:
   ev=next((z for z in cand if pred(z)),None);row[label+'_day']=ev['day'] if ev else None
   if ev:
    row[label+'_evidence']=ev
    line=ev['new_mobile_floor_signal'] if 'CP1' in label else D(str(float(ff.loc[pd.Timestamp(ev['day']),'i_floor'])))
    row.update({label+'_'+k:v for k,v in quote_after(sid,ev['day'],first,an['entry_factor'],an['signal_close_adjusted'],line).items()})
 natural.append(row)
print('NATURAL_COUNTS',[(o,len(z),sum(r['same_original_run_at_first_reclaim'] for r in z),sum(bool(r.get('first_fresh_CP1_day')) for r in z),sum(bool(r.get('first_I_buy_day')) for r in z),sum(bool(r.get('first_CP1_price_market_event_day')) for r in z),sum(bool(r.get('first_Ibuy_price_market_event_day')) for r in z)) for o in ['WIN','LOSS'] for z in [[r for r in natural if r['outcome']==o]]],flush=True)
pd.DataFrame(natural).to_csv(GP/'NATURAL_RETRIGGER_EVENTS.csv',index=False);pd.DataFrame(ngdaily).to_csv(GP/'NATURAL_DAILY_STATE.csv',index=False)
(GP/'NATURAL_RETRIGGER_EVENTS.json').write_text(json.dumps(natural,default=str,ensure_ascii=False,indent=2))
