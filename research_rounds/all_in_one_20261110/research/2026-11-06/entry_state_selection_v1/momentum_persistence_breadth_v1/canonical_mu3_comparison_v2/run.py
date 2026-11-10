"""Parent-authorized clock alignment after preliminary v1; original mu preserved, state resets on source/gap."""
from pathlib import Path
import sys,importlib.util,json,hashlib,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;V=O.parent;R=V.parent;P=R/'pvr_persistence_breadth_v1'
s=importlib.util.spec_from_file_location('v1',V/'analyze.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(A.norm(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def native_mu(g):
 out=pd.Series(np.nan,index=g.index)
 for _,gg in g.groupby('segment_id',sort=False):
  q=gg[gg.valid_strength_observation];c=q.close.to_numpy();n=len(q)
  if not n:continue
  log=np.log(c/c[0]);m=np.nan;v=np.full(n,np.nan)
  for i in range(1,n):
   r=log[i]-log[i-1];m=r if i==1 else (1/3)*r+(1-1/3)*m
   if i>=64:v[i]=m
  out.loc[q.index]=v
 return out
def state(g,raw,cal):
 mu=native_mu(g).reindex(cal);p=raw.reindex(cal);q=g.reindex(cal);identity=p.segment_id.astype('string')+'|'+p.source_kind.astype('string')+'|'+p.source_path.astype('string')
 valid=q.valid_strength_observation.eq(True)&p.observed_bar.eq(True)&p.price_eligible.eq(True)&p.volume_eligible.eq(True)&~p.source_invalid.eq(True)&p.close.gt(0)&p.volume.gt(0)&np.isfinite(mu)
 known=valid&valid.shift(1,fill_value=False)&valid.shift(2,fill_value=False)&identity.eq(identity.shift(1)).fillna(False)&identity.eq(identity.shift(2)).fillna(False)
 right=known&mu.gt(0)&mu.shift(1).gt(0)&mu.shift(2).gt(0)
 return pd.DataFrame(dict(mu5=mu,known=known,right=right),index=cal)
def gate(n,k,j,d):
 return (n>=3)&(((n*3>=k)&(j>0)&(d>0))|(n*2>=k))
def with_gate(b):
 lo=gate(b.n,b.N,b.common3_K,b.entered3-b.left3);hi=gate(b.n+b.U,b.N,b.common3_K.where(b.common3_K>0,1),(b.entered3-b.left3).where(b.common3_K>0,1))
 b['observed_candidate']=np.where(b.K>0,gate(b.n,b.K,b.common3_K,b.entered3-b.left3).astype(int),-1)
 b['candidate']=np.where(lo,1,np.where(~hi,0,-1));return b
start=time.monotonic();roster=pd.read_csv(V/'FIXED_ROSTER.csv');pmeta=pd.read_csv(P/'FIXED_MEMBERSHIP.csv');assert roster.set_index('symbol').sector_id.sort_index().equals(pmeta.set_index('sid').sector_id.sort_index())
ids=sorted(roster.symbol);im=json.load(open(A.U/'INDUSTRY_MANIFEST.json'));sm=json.load(open(A.U/'STOCK_MANIFEST.json'));cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input']).index)for x in im])));cal=cal[cal<=A.END];display=cal[cal>=A.START]
dump('PROTOCOL.json',dict(version='CANONICAL_MU3_V2_AND_SOURCE_GAP_REWARM64_SENSITIVITY',authorized_parent_clarification=True,primary='Keep original G native mu5 and its original warm-up. Three common-session positive condition requires valid bars and identical segment/source_kind/source_path across three dates; gap/source change resets only three-date state. Native mu can inherit pre-gap/pre-source pace: NOT source-isolated.',sensitivity='Full bottom-layer EMA reset on every common gap or true source identity transition, then64 returns and3 usable mu. Separately reported, not substitute for primary.',candidate='n>=3 AND ((share>=1/3 AND paired same-member 3-day diffusion>0) OR share>=1/2). n/K observed plus fixed N lower/upper UNKNOWN gate. This is parent-approved post-initial-data supplemental gate, not claimed unseen preregistration.',comparison='All both-known stock identities on same dates, paired delta uses both-model known at t and t-3; no competing denominators. Same1709/90 membership exact.',prior_version='v1 outputs retained. v1 did not reset bottom layer for source_kind/source_path changes when segment unchanged; specifically2026-05-18 raw vendor switch, so v1 does not certify source isolation. Corrected strict sensitivity is in this directory.',account_runs=0))
ms={};ks={};rs={};strictK={};strictR={};audit=[];hashes={}
for ix,rec in enumerate(sm):
 sid=rec['symbol'];gp=A.IX/(sid+'.parquet');sp=Path(next(p for p in rec['source_sha256']if p.endswith('/signal.parquet')));raw=pd.read_parquet(sp,columns=['close','volume','segment_id','source_kind','source_path','observed_bar','price_eligible','volume_eligible','source_invalid']).loc[:A.END];g=pd.read_parquet(gp,columns=['close','volume','segment_id','valid_strength_observation','z5']).loc[:A.END];hashes[str(sp)]=sha(sp);hashes[str(gp)]=sha(gp);assert hashes[str(sp)]==rec['source_sha256'][str(sp)]
 gr=raw.reindex(g.index);np.testing.assert_equal(gr.close.to_numpy(),g.close.to_numpy());np.testing.assert_equal(gr.volume.to_numpy(),g.volume.to_numpy());np.testing.assert_equal(gr.segment_id.to_numpy(),g.segment_id.to_numpy())
 vraw=gr.observed_bar.eq(True)&gr.price_eligible.eq(True)&gr.volume_eligible.eq(True)&~gr.source_invalid.eq(True)&gr.close.gt(0)&gr.volume.gt(0);assert not (g.valid_strength_observation&~vraw).any()
 z=state(g,raw,cal);q=native_mu(g);cc=q.notna()&g.z5.notna();assert np.array_equal(np.sign(q[cc]),np.sign(g.z5[cc]))
 for cut in ['2022-12-01','2024-09-24','2026-05-15']:
  zz=state(g.loc[:cut],raw.loc[:cut],cal[cal<=cut]);pd.testing.assert_frame_equal(zz,z.loc[:cut],check_exact=True)
 strict=g.copy();strict.segment_id=gr.segment_id.astype('string')+'|'+gr.source_kind.astype('string')+'|'+gr.source_path.astype('string');sz=A.calc(strict,cal)
 for cut in ['2024-09-24','2026-06-30']:
  zz=A.calc(strict.loc[:cut],cal[cal<=cut]);pd.testing.assert_frame_equal(zz,sz.loc[:cut],check_exact=True)
 a=gr.source_kind.astype('string')+'|'+gr.source_path.astype('string');changes=(a.ne(a.shift())&gr.segment_id.eq(gr.segment_id.shift())).fillna(False)
 ms[sid]=z.mu5.reindex(display);ks[sid]=z.known.reindex(display);rs[sid]=z.right.reindex(display);strictK[sid]=sz.known.reindex(display);strictR[sid]=sz.right.reindex(display)
 audit.append(dict(sid=sid,canonical_mu_sign_checked=int(cc.sum()),prefixes=3,strict_prefixes=2,source_changes_unrepresented_by_segment=int(changes.sum()),source_change_days='|'.join(str(t.date())for t in gr.index[changes])))
 if (ix+1)%500==0:print('V2',ix+1,round(time.monotonic()-start,2),flush=True)
k=pd.DataFrame(ks);r=pd.DataFrame(rs);sk=pd.DataFrame(strictK);sr=pd.DataFrame(strictR);pd.DataFrame(ms).to_parquet(O/'MU5.parquet');k.to_parquet(O/'KNOWN3.parquet');r.to_parquet(O/'RIGHT3.parquet');sk.to_parquet(O/'STRICT_KNOWN3.parquet');sr.to_parquet(O/'STRICT_RIGHT3.parquet');pd.DataFrame(audit).to_csv(O/'AUDITS.csv',index=False)
pvr=pd.read_parquet(P/'STOCK_DAILY.parquet',columns=['sid','day','state']);ps=pvr.pivot(index='day',columns='sid',values='state').reindex(index=display,columns=ids);assert ps.notna().all().all();pk=ps.ge(0);pr=ps.eq(1);both=k&pk;common=[];own=[];strict=[]
old=pd.read_parquet(V/'SECTOR_DAILY.parquet');native=old[['day','sector','sector_name']+[c for c in old if c.startswith('sector_')and c!='sector_name']].copy()
for sec,g in roster.groupby('sector_id'):
 cols=g.symbol.tolist();b=with_gate(A.breadth(sec,cols,k,r));b.index.name='day';own.append(b.reset_index());b=with_gate(A.breadth(sec,cols,sk,sr));b.index.name='day';strict.append(b.reset_index())
 bm=with_gate(A.breadth(sec,cols,both,r&both));bp=with_gate(A.breadth(sec,cols,both,pr&both));z=bm[['sector','N','K','U','common3_K']].copy()
 for label,df in [('M3',bm),('PVR3',bp)]:
  for c in ['n','right_known','right_fixed_lower','right_fixed_upper','entered3','left3','delta3','observed_candidate','candidate']:z[label+'_'+c]=df[c]
 z['both_right']=(r[cols]&pr[cols]&both[cols]).sum(axis=1);z['M3_only']=((r[cols]&~pr[cols])&both[cols]).sum(axis=1);z['PVR3_only']=((pr[cols]&~r[cols])&both[cols]).sum(axis=1);z.index.name='day';common.append(z.reset_index())
for name,parts in [('SECTOR_DAILY',own),('STRICT_SECTOR_DAILY',strict),('COMMON_K_COMPARISON',common)]:
 d=pd.concat(parts).merge(native,on=['day','sector'],how='left');d.to_parquet(O/(name+'.parquet'),index=False);d[d.day.dt.strftime('%Y-%m-%d').isin(A.FIXED)].to_csv(O/('FIXED_'+name+'.csv'),index=False);d[d.sector.eq('URFI881121')].to_csv(O/('SEMICONDUCTOR_'+name+'.csv'),index=False)
new=pd.concat(own);prior=old[['day','sector','K','n','right_known','delta3']];diff=prior.merge(new[['day','sector','K','n','right_known','delta3']],on=['day','sector'],suffixes=('_v1','_canonical'));diff[diff.day.dt.strftime('%Y-%m-%d').isin(A.FIXED)].to_csv(O/'FIXED_V1_TO_CANONICAL_CHANGES.csv',index=False)
snaps=[]
for sid in ids:
 for d in pd.to_datetime(A.FIXED):
  if d in display:snaps.append(dict(sid=sid,day=str(d.date()),mu5=ms[sid].at[d],M3_known=k.at[d,sid],M3_right=r.at[d,sid],PVR3_known=pk.at[d,sid],PVR3_right=pr.at[d,sid],strict_M3_known=sk.at[d,sid],strict_M3_right=sr.at[d,sid]))
pd.DataFrame(snaps).merge(roster,left_on='sid',right_on='symbol').to_csv(O/'FIXED_STOCK_COMPARISON.csv',index=False)
dump('SOURCE_HASHES.json',hashes);summary=dict(status='COMPLETE_SIGNAL_ONLY',seconds=time.monotonic()-start,membership_exact=True,calendar_exact=True,canonical_known=int(k.values.sum()),canonical_right=int(r.values.sum()),strict_known=int(sk.values.sum()),strict_right=int(sr.values.sum()),source_transitions=sum(x['source_changes_unrepresented_by_segment']for x in audit),source_transition_stocks=sum(x['source_changes_unrepresented_by_segment']>0 for x in audit),prefixes=5127,strict_prefixes=3418,sources_unchanged=all(sha(p)==h for p,h in hashes.items()),account_runs=0);dump('SUMMARY.json',summary);print('SUMMARY',summary,flush=True)
b=pd.read_parquet(O/'COMMON_K_COMPARISON.parquet');print(b[b.sector.eq('URFI881121')&b.day.dt.strftime('%Y-%m-%d').isin(A.FIXED)][['day','N','K','M3_n','PVR3_n','M3_right_known','PVR3_right_known','M3_delta3','PVR3_delta3','M3_candidate','PVR3_candidate','sector_action']].to_string(index=False),flush=True)
