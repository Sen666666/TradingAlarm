# Add first-entry signal/open/day-close decomposition without loading or running accounts.
anchors=[]
for r in closed:
 sid=r['sid'];first=min((buys[i] for i in r['layer_ids']),key=lambda t:(t['at'],t['layer']));day=pd.Timestamp(first['at'].date());signal=pd.Timestamp(first['signal_at'].date());df=raw[sid];fac=factor_frames[sid]
 f0=D(str(float(fac.loc[day,'factor'])));signal_ok=signal in df.index and signal in fac.index and bool(df.loc[signal,'price_eligible']) and bool(df.loc[signal,'observed_bar']) and not bool(df.loc[signal,'synthetic_event_bar'])
 adjusted_signal_close=D(str(df.loc[signal,'close']))*D(str(float(fac.loc[signal,'factor']))) if signal_ok else None
 adjusted_open=first['raw_open']*f0;fill=first['price']*f0;cost=(first['gross_cny']+first['fees_cny'])/D(first['shares'])*f0;close=D(str(df.loc[day,'close']))*f0
 base=dict(account='PVR',sid=sid,round_id=r['id'],opened=r['opened'],signal_at=str(first['signal_at']),outcome='WIN' if r['pnl']>0 else 'LOSS',entry_quarter=r['opened'][:4]+'Q'+str((int(r['opened'][5:7])-1)//3+1),signal_close_observed=signal_ok,signal_close_adjusted=adjusted_signal_close,entry_raw_open=first['raw_open'],entry_factor=f0,signal_to_open_gap=adjusted_open/adjusted_signal_close-D(1) if signal_ok else None,open_to_fill_slippage=fill/adjusted_open-D(1),first_buy_fee_per_share=first['fees_cny']/D(first['shares']),first_fee_inclusive_cost_per_share=(first['gross_cny']+first['fees_cny'])/D(first['shares']),fill_to_same_day_close_return=close/fill-D(1),first_fee_cost_to_same_day_close_return=close/cost-D(1),signal_to_entry_close_return=close/adjusted_signal_close-D(1) if signal_ok else None)
 for n in horizons:
  seq=[z for z in samples if z['sid']==sid and z['round_id']==r['id'] and z['observation']==n]
  z=seq[0] if seq else None;base[f'fixed_day{n}_fee_anchor_return']=z['raw_close']*z['factor']/cost-D(1) if z and z['factor'] else None
 anchors.append(base)
assert len(anchors)==692 and len({(r['account'],r['sid'],r['round_id']) for r in anchors})==692
pd.DataFrame(anchors).to_csv(EP/'ENTRY_ANCHORS.csv',index=False)
anchor_summary=[]
for quarter in ['ALL']+sorted({r['entry_quarter'] for r in anchors}):
 for outcome in ['WIN','LOSS']:
  group=[r for r in anchors if r['outcome']==outcome and (quarter=='ALL' or r['entry_quarter']==quarter)]
  for col in ['signal_to_open_gap','fill_to_same_day_close_return','first_fee_cost_to_same_day_close_return','signal_to_entry_close_return']:
   vv=np.array([float(r[col]) for r in group if r[col] is not None]);anchor_summary.append(dict(entry_quarter=quarter,outcome=outcome,metric=col,n=len(vv),mean=float(vv.mean()),median=float(np.median(vv)),positive_fraction=float((vv>0).mean())))
print('ANCHORS_ALL',[r for r in anchor_summary if r['entry_quarter']=='ALL'],flush=True)
pd.DataFrame(anchor_summary).to_csv(EP/'ANCHOR_SUMMARY.csv',index=False)
