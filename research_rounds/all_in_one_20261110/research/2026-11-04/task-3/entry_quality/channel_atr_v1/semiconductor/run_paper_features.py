"""Frozen OHLC indicators and fixed-date paper facts only, no account/quantity."""
from pathlib import Path
import hashlib,importlib.util,json,math
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
spec=importlib.util.spec_from_file_location('frozen_channel_ATR_indicators',P/'indicators.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
TARGETS={'603061.SH':dict(launch='2025-11-06',days=['2026-01-16','2026-01-19','2026-01-20','2026-01-28','2026-02-12']),'300623.SZ':dict(launch='2025-12-16',days=['2026-01-29','2026-02-02','2026-02-03','2026-02-05','2026-03-04'])}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
m={r['symbol']:r for r in json.loads(MANIFEST.read_text())};sources={str(MANIFEST):sha(MANIFEST),str(P/'PAPER_SPEC.md'):sha(P/'PAPER_SPEC.md'),str(P/'indicators.py'):sha(P/'indicators.py')};fixed=[];launches=[];confirms=[];prefix=[]
for sid,tgt in TARGETS.items():
 price_path=O/(sid.replace('.','_')+'_ORIGINAL_OHLC_FULL_PREFIX.parquet');price=pd.read_parquet(price_path);sources[str(price_path.resolve())]=sha(price_path)
 r=m[sid];fp=Path(r['refs']['facts']);ep=Path(next(x for x in r['source_sha256'] if x.endswith('/events.parquet')))
 assert sha(fp)==r['output_sha256'][str(fp)] and sha(ep)==r['source_sha256'][str(ep)]
 sources[str(fp)]=sha(fp);sources[str(ep)]=sha(ep);facts=pd.read_parquet(fp);events=pd.read_parquet(ep)
 z=M.features(price);z.to_parquet(O/(sid.replace('.','_')+'_FULL_PREFIX_FEATURES.parquet'),index=True)
 launch=pd.Timestamp(tgt['launch']);assert launch in events.index and events.loc[launch,'event']==1
 launches.append(dict(sid=sid,launch=tgt['launch'],original_event=events.loc[launch].to_dict(),original_native=facts.loc[launch].to_dict(),OHLC=price.loc[launch].to_dict(),feature=z.loc[launch].to_dict(),entry_date_not_used_as_launch=True))
 stop=pd.Timestamp(max(tgt['days']));look=z.loc[launch:stop]
 for L in [20,55]:
  hit=look.loc[look[f'break{L}'].eq(True)];ct=None if hit.empty else hit.index[0]
  rec=dict(sid=sid,L=L,E0_launch=tgt['launch'],scan_end=str(stop.date()),confirmed_at=None if ct is None else str(ct.date()),A=None if ct is None else float(price.loc[ct,'close']),S=None if ct is None else float(z.loc[ct,'ATR14_prior']),U_at_confirmation=None if ct is None else z.loc[ct,f'U{L}'],z_at_confirmation=None if ct is None else z.loc[ct,f'z{L}'],confirmation_feature=None if ct is None else z.loc[ct].to_dict(),scope='First raw channel condition since fixed original E0 launch; order/ATR exits not assumed absent.')
  if ct is not None:
   start_known=facts.loc[launch:ct]
   rec['any_original_E0_off_before_confirmation']=bool(start_known['e0_target'].eq(0).any());rec['any_original_I_off_before_confirmation']=bool(start_known['i_target'].eq(0).any())
  confirms.append(rec)
 for day in tgt['days']:
  t=pd.Timestamp(day);a=price.loc[t];b=z.loc[t];n=facts.loc[t]
  out=dict(sid=sid,day=day,raw_O=float(a.raw_open),raw_H=float(a.raw_high),raw_L=float(a.raw_low),raw_C=float(a.raw_close),factor=float(a.adjustment_factor),O=float(a.open),H=float(a.high),L=float(a.low),C=float(a.close),**b.to_dict(),original_E0_event=events.loc[t,'event'],original_I_target=n.i_target,original_I_floor=n.i_floor,original_E0_target=n.e0_target,original_E0_floor=n.e0_floor)
  for L in [20,55]:
   rec=next(x for x in confirms if x['sid']==sid and x['L']==L);ct=None if rec['confirmed_at'] is None else pd.Timestamp(rec['confirmed_at'])
   if ct is None or t<ct:out[f'channel{L}_A']=None;out[f'channel{L}_S']=None;out[f'channel{L}_j']=None;out[f'channel{L}_fresh_net_step']=False
   else:
    pp=price.loc[ct:t,'close'];F=float(pp.max());prev=pp.iloc[:-1];Fprev=rec['A'] if prev.empty else float(prev.max());j=math.floor((F-rec['A'])/rec['S']);jprev=math.floor((Fprev-rec['A'])/rec['S']);out[f'channel{L}_A']=rec['A'];out[f'channel{L}_S']=rec['S'];out[f'channel{L}_close_frontier']=F;out[f'channel{L}_j']=j;out[f'channel{L}_fresh_net_step']=bool(M.gt(float(a.close),Fprev) and j>jprev)
   out[f'channel{L}_net_step_scope']='Conditional only if no prior candidate/hard exit; not a filled or still-live candidate path.'
  fixed.append(out)
 # One actual truncation check per source, no account or N path.
 cut=pd.Timestamp(tgt['days'][2]);short=M.features(price.loc[:cut]);pd.testing.assert_frame_equal(short,z.loc[:cut],check_exact=True);prefix.append(dict(sid=sid,cutoff=str(cut.date()),exact=True))
save('TEN_FIXED_FEATURE_ROWS.json',fixed);pd.DataFrame(clean(fixed)).to_csv(O/'TEN_FIXED_FEATURE_ROWS.csv',index=False);save('E0_LAUNCH_SOURCE_ROWS.json',launches);save('FIRST_CHANNEL_CONFIRMATIONS.json',confirms);save('FEATURE_PREFIX_CHECKS.json',prefix)
save('FEATURE_RUN_RECEIPT.json',dict(status='PAPER_FEATURES_ONLY_COMPLETE',stocks=2,fixed_days=len(fixed),source_sha256=sources,script_sha256=sha(__file__),helper='Frozen indicators.features; original fullprefix then fixed dates',new_accounts=0,new_quantities=0,new_returns=0,new_N_paths=0,net_steps='Raw conditional progress diagnostics only; no exit assumed away.'))
for r in fixed:print(json.dumps(clean({k:r[k] for k in ['sid','day','raw_C','C','H','L','U20','U55','ATR14_prior','z20','z55','channel20_A','channel20_S','channel20_j','channel20_fresh_net_step','channel55_A','channel55_S','channel55_j','channel55_fresh_net_step','original_I_target']})))
print(json.dumps(clean([{k:r[k] for k in ['sid','L','E0_launch','confirmed_at','A','S','U_at_confirmation','z_at_confirmation','any_original_E0_off_before_confirmation','any_original_I_off_before_confirmation']} for r in confirms])))
