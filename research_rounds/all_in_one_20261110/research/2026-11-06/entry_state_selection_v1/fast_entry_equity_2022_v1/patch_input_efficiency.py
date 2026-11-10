from pathlib import Path
p=Path(__file__).with_name('prepare_inputs.py');s=p.read_text()
s=s.replace(" b,m,f=M.context(str(END.date()),ids=ids)",""" # Construct exactly the native Q-only fields. Do not materialize raw OHLC/account
 # execution arrays just to call market_buyable and Facts.packet.
 b=M.BP.C.load_bundle(M.BP.C.OLD/'inputs-v2/input-manifest.json',materialize=False)
 keep=set(ids);b.lines=tuple(x for x in b.lines if x.security_id in keep);sectors={x.sector_id for x in b.lines}
 b.series={k:v for k,v in b.series.items() if k in keep|sectors};b.sector_series={k:v for k,v in b.sector_series.items() if k in sectors}
 records={x['series_id']:x for x in read(M.P/'manifest.json')['series']}
 for sid,item in b.series.items():item.record=records[sid]
 with np.load(H,allow_pickle=False) as hh:b._h1_cache=(pd.DatetimeIndex(hh['dates']),{str(s):j for j,s in enumerate(hh['symbols'])},hh['score'].copy())
 m=M.E.FastMarket.__new__(M.E.FastMarket);m.bundle=b;m.rules=read(RR/'pvr-act-comparison-20261027/execution-rules-v2.json');m.protocol=read(M.BP.C.OLD/'inputs-v2/economic-protocol.json');m.lines={x.security_id:x for x in b.lines}
 m.sessions={k:tuple(sorted(datetime.fromisoformat(t) for t in vv)) for k,vv in m.rules['calendars'].items()}
 f=M.E.Facts.__new__(M.E.Facts);f.b=b;f.market=m;f.f={};f.cache={};f.day=None;f.structure_lookup={}
 for sid in sectors:
  pp=M.O/'industry-facts'/(sid+'.parquet');source(pp);ff=pd.read_parquet(pp).loc[:END];f.f[sid]=ff;b.series[sid].states=ff[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 print('NATIVE_Q_CONTEXT_READY',round(timer.monotonic()-began,2),flush=True)""")
a=s.index('  last=None;counter=0;root_known=False;root_reason=');bb=s.index('  epochs[sid]=rows',a)
s=s[:a]+'''  last=None;counter=0;root_known=False;root_reason='NO_KNOWN_ACTIVE_ROOT';prev_exact=None;prev_i=None;rows={}
  exact=ff[['i_target','segment_id']].reindex(cal);asof=ff[['i_target','segment_id']].reindex(cal,method='ffill');rz=raw[sid][['source_kind','source_path','segment_id']].reindex(cal)
  af=asof.to_dict('records');ef=exact.to_dict('records');rf=rz.to_dict('records')
  targets=set(cal22)
  if sid in startup_ids:
   sw=startup[startup.sid.eq(sid)].iloc[0];targets|={d for d in cal if pd.Timestamp(sw.window_start)<=d<=pd.Timestamp(sw.window_end)}
  for d,ar,er,rr in zip(cal,af,ef,rf):
   target=tri(ar['i_target']) if finite(ar['segment_id']) else False;seg=int(ar['segment_id']) if finite(ar['segment_id']) else -1;key=(target,seg)
   if key!=last:counter+=1;last=key
   lin=lineage(rr);known=tri(er['i_target']) is not None and finite(er['segment_id']) and all(pd.notna(rr.get(k)) for k in ['source_kind','source_path','segment_id']) and int(er['segment_id'])==int(rr['segment_id'])
   current=tri(er['i_target']);adjacent=known and prev_exact is not None and lin==prev_exact
   if current is False:root_known=False;root_reason='I_OFF'
   elif current is True and prev_i is False and adjacent:root_known=True;root_reason='KNOWN_I_0_TO_1'
   elif current is True and not adjacent:root_known=False;root_reason='MISSING_OR_CHANGED_LINEAGE'
   elif current is None:root_known=False;root_reason='CURRENT_I_UNKNOWN'
   if d in targets:rows[d]=dict(i_epoch=f'{sid}|{seg}|{counter}',epoch_lineage_known=bool(root_known),epoch_lineage_reason=root_reason,i_target=current,source_kind=rr.get('source_kind'),source_path=rr.get('source_path'),raw_segment=rr.get('segment_id'),source_adjacent_known=bool(adjacent))
   prev_exact=lin if known else None;prev_i=current
''' + s[bb:]
s=s.replace("  raw[sid]=pd.read_parquet(sp).loc[:END]", "  raw[sid]=pd.read_parquet(sp).loc[:END]")
p.write_text(s)
