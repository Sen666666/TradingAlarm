"""Input-only two-window extension. No historical cash/holdings consumer loaded."""
from pathlib import Path
import ast,textwrap,sys,json,hashlib,time,resource
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;F=O.parent;R=F.parent;J=R/'independent_channel_joint_economic_v1'
START=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,indent=2,ensure_ascii=False,default=str);f.write('\n')
assert not (O/'INPUTS_STARTED.json').exists();save('INPUTS_STARTED.json',dict(script_sha256=sha(__file__),started_utc=str(pd.Timestamp.now(tz='UTC')),no_economics=True))
sys.path.insert(0,str(J));from market_adapter import MarketAdapter,_reasons
p=R/'fast_entry_equity_2022_v1/prepare_inputs.py';src=p.read_text();env={'__file__':str(p)};exec(compile(src[:src.index('\ndef main():')],str(p)+':helpers','exec'),env)
node=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=='main');body=textwrap.dedent('\n'.join(ast.get_source_segment(src,node).splitlines()[1:]));setup=body[:body.index('tpath=W/')];exec(compile(setup,str(p)+':full_pool_native_setup_no_consumer','exec'),env)
f=env['f'];b=env['b'];ids=env['ids'];cal=env['cal'];manifest=env['manifest'];sources=env['SOURCES'];sources[str(p)]=sha(p);sources[str(__file__)]=sha(__file__)
for sid in ids:
 pp=Path(manifest[sid]['refs']['facts']);actual=sha(pp);assert actual==manifest[sid]['output_sha256'][str(pp)];sources[str(pp)]=actual;ff=pd.read_parquet(pp).loc[:'2026-06-30'];f.f[sid]=ff;b.series[sid].states=ff[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
oldpaths=[R/'fast_entry_equity_2022_v1/ALL_MARKET_INPUTS_2022.parquet',R/'independent_channel_full1709_preflight_v1/overlap/OLD_NATIVE_Q_EXTENDED.parquet'];old_days=pd.DatetimeIndex([])
for pp in oldpaths:sources[str(pp)]=sha(pp);old_days=old_days.union(pd.DatetimeIndex(pd.read_parquet(pp,columns=['day']).day.unique()))
dates=cal[(cal>='2022-01-01')&~cal.isin(old_days)];pvpath=R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet';sources[str(pvpath)]=sha(pvpath);pv=pd.read_parquet(pvpath).set_index(['sid','day']);rows=[]
for n,d in enumerate(dates):
 clock,stocks,sectors=f.packet(env['datetime'].combine(d.date(),env['time'](15,10),env['TZ']),'I');ss={s.sector_id:s for s in sectors}
 for stock in stocks:
  sid=stock.security_id;elig=env['native_elig'](stock,ss,clock,'S0');pr=pv.loc[(sid,d)] if (sid,d) in pv.index else None
  rows.append(dict(sid=sid,day=d,sector=elig.sector_id,event_Q_reasons='|'.join(elig.reasons),PVR_known=bool(pr is not None and np.isfinite(pr.score) and pr.state>=0 and pr.valid_observation),PVR_score=float(pr.score) if pr is not None else np.nan))
 if (n+1)%50==0:print('NATIVE_DAYS',n+1,len(dates),'rows',len(rows),'seconds',round(time.monotonic()-START,1),flush=True)
qual=pd.DataFrame(rows);assert len(qual)==len(dates)*1709 and not qual.duplicated(['sid','day']).any();qual.to_parquet(O/'NATIVE_QUAL_EXTRA.parquet',index=False)
# Match original single-stock native calls at frozen sample endpoints.
a=MarketAdapter(native_cache_limit=2);qc=qual.set_index(['sid','day']);checks=[];proto=json.loads((F/'PROTOCOL.json').read_text())
for sid in proto['fixture_sids']:
 for wn,ds in proto['fixture_dates'].items():
  for d in pd.DatetimeIndex([ds[0],ds[-1]]):
   actual=a.native_industry(sid,d,cut=d);got=dict(sector=qc.loc[(sid,d),'sector'],**_reasons(qc.loc[(sid,d),'event_Q_reasons']));assert actual==got,(sid,d,actual,got);checks.append(dict(sid=sid,day=str(d.date()),original_native_prefix_equal=True))
# Every market root retains original full warm history; only invitations are sliced.
roster=env['roster'];parts=[];counts=[];wins={'2023':('2023-01-01','2023-12-31'),'2024JanAug':('2024-01-01','2024-08-31')}
for n,sid in enumerate(ids):
 z=a.load_sid(sid)
 for wn,(lo,hi) in wins.items():
  g=z.loc[lo:hi];g=g[g.receipt].copy();g['sid']=sid;g['day']=g.index;g['window']=wn;g['name']=roster.loc[sid,'name'];g['industry']=roster.loc[sid,'industry'];g['valid']=g.price_valid;g['receipt_id']=g.legacy_receipt_id;g['volume_capacity_shares']=g.capacity_shares
  if len(g):
   qq=qc.loc[[(sid,d) for d in g.index]];g['sector']=qq.sector.to_numpy();g['old_PVR_known']=qq.PVR_known.to_numpy();g['old_PVR_score']=qq.PVR_score.to_numpy();reasons=[_reasons(x) for x in qq.event_Q_reasons]
   for c in ['sector_known','sector_observed_today','sector_rs_ready_fresh','sector_up']:g['old_'+c]=[r[c] for r in reasons]
   cols=['sid','day','name','industry','sector','window','root_day','identity','receipt_id','valid','raw_close','adjustment_factor','S_new','phase','born','receipt','old_PVR_known','old_PVR_score','old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up','volume_capacity_shares'];parts.append(g[cols].reset_index(drop=True))
  counts.append(dict(sid=sid,window=wn,receipts=len(g)))
 a._market.clear()
 if (n+1)%200==0:print('PRICE_INPUT_SIDS',n+1,1709,'seconds',round(time.monotonic()-START,1),flush=True)
candidates=pd.concat(parts,ignore_index=True);assert not candidates.duplicated(['window','sid','day']).any();candidates.to_parquet(O/'PRICE_CANDIDATES.parquet',index=False);pd.DataFrame(counts).to_csv(O/'PRICE_RECEIPT_COUNTS.csv',index=False)
sources.update(a.verify_sources())
for mod in list(sys.modules.values()):
 pp=getattr(mod,'__file__',None)
 if pp and str(pp).endswith('.py') and any(str(pp).startswith(str(env[k])) for k in ['RR','W']):sources[str(pp)]=sha(pp)
for pp,h in sources.items():assert sha(pp)==h,(pp,'input drift')
save('NATIVE_SAMPLE_QA.json',checks);save('PREPARED_SOURCE_SHA256.json',sources);save('PREPARED_OUTPUT_SHA256.json',{n:sha(O/n) for n in ['NATIVE_QUAL_EXTRA.parquet','PRICE_CANDIDATES.parquet','PRICE_RECEIPT_COUNTS.csv','NATIVE_SAMPLE_QA.json']})
save('INPUTS_COMPLETE.json',dict(no_economics=True,stocks=1709,native_extra_days=len(dates),native_extra_rows=len(qual),candidate_counts=candidates.groupby('window').size().to_dict(),sample_prefix_checks=len(checks),seconds=time.monotonic()-START,peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20))
print('INPUTS_COMPLETE',json.loads((O/'INPUTS_COMPLETE.json').read_text()),flush=True)
