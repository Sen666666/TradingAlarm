# Saved-evidence analysis only, executed in existing inspection process; no account run.
OUT2=P/'analysis/2022_exit_protection'
bhigh=[r for r in checks if r['group']=='B_POSITIVE_AT_LEAST_3PCT']
sm={r['symbol']:r for r in json.loads((C.U/'STOCK_MANIFEST.json').read_text())}
ff={s:pd.read_parquet(sm[s]['refs']['facts'],columns=['factor','close','raw_close','i_target','i_floor']) for s in {r['sid'] for r in bhigh}}
layer_snaps={(str(d['at'])[:10],l['id']):l for d in ds for l in d['layers']}
days=list(dmap);day_index={d:i for i,d in enumerate(days)}
peak_layers=[];peak_rounds=[]
for r in bhigh:
 oo=[o for o in obsmap[r['sid'],r['opened']] if o['valid_actual_close']]
 peak=max(oo,key=lambda o:o['U']);day=peak['day'];sid=r['sid'];fact=ff[sid].loc[pd.Timestamp(day)];factor=D(str(float(fact.factor)));avg=peak['K_remaining']/peak['Q']
 relevant=[layer_snaps[day,i] for i in r['layer_ids'] if (day,i) in layer_snaps]
 assert sum(l['qty'] for l in relevant)==peak['Q']
 qbelow=0;mobile_q=0;mobile_below=0;core_q=0;core_below=0
 for l in relevant:
  line=D(str(l['last_core_line'])) if l['kind']=='core' else l['floor'];rawline=line/factor
  prevday=days[day_index[day]-1] if day_index[day]>0 else None
  prev=layer_snaps.get((prevday,l['id']));oldline=(D(str(prev['last_core_line'])) if l['kind']=='core' else prev['floor']) if prev else next(t['floor'] for t in A['trades'] if t['side']=='buy' and t['layer']==l['id'])
  below=rawline<avg;qbelow+=l['qty']*below
  if l['kind']=='core':core_q+=l['qty'];core_below+=l['qty']*below
  else:mobile_q+=l['qty'];mobile_below+=l['qty']*below
  peak_layers.append(dict(round_id=r['id'],sid=sid,peak_day=day,layer=l['id'],kind=l['kind'],qty=l['qty'],close=peak['close'],Krem_average=avg,factor=factor,postclose_line_signal=line,postclose_line_raw=rawline,old_line_raw=oldline/factor,line_below_stock_average=below,core_line_is_not_direct_stop=l['kind']=='core'))
 peak_rounds.append(dict(round_id=r['id'],sid=sid,pnl=r['pnl'],peak_day=day,peak_U=peak['U'],peak_U_over_K=peak['U_over_K'],Q=peak['Q'],Krem=peak['K_remaining'],average=avg,stock_close=peak['close'],all_lines_below_average=qbelow==peak['Q'],any_line_below_average=qbelow>0,qty_below_average=qbelow,qty_fraction_below=D(qbelow)/peak['Q'],mobile_qty=mobile_q,mobile_qty_below=mobile_below,all_mobile_below_average=mobile_q>0 and mobile_q==mobile_below,core_qty=core_q,core_qty_below=core_below,final_exit_reason=r['final_exit_reason']))
print('PEAK_PROTECTION',dict(rounds=len(peak_rounds),any_line_below=sum(r['any_line_below_average'] for r in peak_rounds),all_lines_below=sum(r['all_lines_below_average'] for r in peak_rounds),with_mobile=sum(r['mobile_qty']>0 for r in peak_rounds),all_mobile_below=sum(r['all_mobile_below_average'] for r in peak_rounds),layers=len(peak_layers),mobile_layers=sum(l['kind']=='add' for l in peak_layers),mobile_below=sum(l['kind']=='add' and l['line_below_stock_average'] for l in peak_layers),core_layers=sum(l['kind']=='core' for l in peak_layers),core_line_below=sum(l['kind']=='core' and l['line_below_stock_average'] for l in peak_layers)),flush=True)
layer_to_round={i:r for r in bhigh for i in r['layer_ids']};triggers=[]
for e in A['audit_log']:
 if e['kind']!='pilot_layer_exit':continue
 day=str(e['at'])[:10];idx=day_index[day];prevday=days[idx-1] if idx else None
 for i in e['layers']:
  if i not in layer_to_round:continue
  r=layer_to_round[i];sid=r['sid'];fact=ff[sid].loc[pd.Timestamp(day)];factor=D(str(float(fact.factor)));cur=layer_snaps.get((day,i));prev=layer_snaps.get((prevday,i))
  if cur is None:continue
  kind=cur['kind'];old=(prev['floor'] if kind=='add' else D(str(prev['last_core_line']))) if prev else next(t['floor'] for t in A['trades'] if t['side']=='buy' and t['layer']==i)
  sells=[(t,p) for t in A['trades'] if t['side']=='sell' and t['at']>e['at'] for p in t['parts'] if p['layer']==i]
  nextsell=sells[0][0] if sells else None
  triggers.append(dict(round_id=r['id'],sid=sid,layer=i,kind=kind,trigger_at=str(e['at']),reason=e['reason'],qty=cur['qty'],i_target=bool(fact.i_target),signal_close=D(str(fact.close)),raw_close=D(str(fact.raw_close)),old_floor_signal=old,old_floor_raw=old/factor,signal_close_minus_old_floor=D(str(fact.close))-old,raw_close_minus_old_floor=D(str(fact.raw_close))-old/factor,next_fill_at=str(nextsell['at']) if nextsell else None,wait_common_sessions=day_index[str(nextsell['at'])[:10]]-idx if nextsell else None))
cp=[t for t in triggers if t['reason']=='CP1_add_protection'];assert all(t['signal_close_minus_old_floor']<=0 for t in cp)
print('TRIGGER_CHECK',len(triggers),len(cp),Counter(t['wait_common_sessions'] for t in triggers),flush=True)
examples=[]
for sid in ['000620.SZ','002911.SZ','000029.SZ']:
 r=min([r for r in bhigh if r['sid']==sid],key=lambda z:z['pnl'])
 for o in obsmap[r['sid'],r['opened']]:
  day=o['day'];fact=ff[sid].loc[pd.Timestamp(day)];fac=D(str(float(fact.factor)))
  ls=[layer_snaps[day,i] for i in r['layer_ids'] if (day,i) in layer_snaps]
  examples.append(dict(round_id=r['id'],**o,i_target=bool(fact.i_target),factor=fac,layers=[dict(id=l['id'],kind=l['kind'],qty=l['qty'],floor_signal=l['floor'],last_core_line=l['last_core_line'],line_raw=(D(str(l['last_core_line'])) if l['kind']=='core' else l['floor'])/fac) for l in ls]))
pd.DataFrame(peak_layers).to_csv(OUT2/'PEAK_LAYERS.csv',index=False);pd.DataFrame(peak_rounds).to_csv(OUT2/'PEAK_ROUNDS.csv',index=False);pd.DataFrame(triggers).to_csv(OUT2/'EXIT_TRIGGERS.csv',index=False)
(OUT2/'THREE_EXAMPLES_DAILY.json').write_text(json.dumps(examples,default=str,indent=2))
