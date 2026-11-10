"""Read frozen native inputs; write only this new research directory. No fitting/account runs."""
from pathlib import Path
import sys,json,hashlib,time,importlib.util
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent; R=O.parent
S=R/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv'
CLOCK=R/'selection_entry_diagnosis_v1/entry_probability_signal_v1/MARKET_CLOCK.csv'
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 return v
def dump(n,v):(O/n).write_text(json.dumps(clean(v),ensure_ascii=False,indent=2))
def loadmod(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
cmf=loadmod('old_cmf',R/'cmf_pvr_component_v1/experiment.py')
protocol={
 'status':'FROZEN_BEFORE_NEW_FEATURES_AND_SUPPORT_NOT_BEFORE_ALL_HISTORICAL_OUTCOMES',
 'domain':'All 2693 actual first PVR-account rounds: 1814 MOBILE/add,879 CORE. No rejected candidates/account replays.',
 'hypothesis':'PVR strength interacts with high/low directional migration and volume-weighted within-bar closing position. Not prior fixed PVR multipliers, old trend/CP mixture or sector breadth interaction.',
 'formula':'logit(p)=alpha+delta*is_MOBILE+betaP*zP+betaD*zD+betaC*zC+gammaPD*zPD+gammaPC*zPC',
 'features':{'P':'Original PVR_decision only; require finite and matching native reconstruction <=1e-8. No cache replacement.', 'D':'Wilder competitive DM14, first14 differences SMA then RMA14, D=(RMAplus-RMAminus)/(sum). Strict zero denominator UNKNOWN. Source/native full prefix; H=L invalidates state. No E0/I/CP reset.', 'C':'Existing strict CMF21: sum(CLV*raw shares)/sum(raw shares); CLV=(2C-H-L)/(H-L). Native and raw coordinate consistency, source/path stable21, positive shares, same adjustment and volume factors; H=L and factor/source changes UNKNOWN.', 'D_extra_guard':'Native prices match raw*factor, observed/eligible/non-synthetic, H>L; source_kind/path, segment, adjustment_factor,volume_factor change resets RMA; full14 new changes required. Share-factor/source unknown not imputed.', 'scaling':'Training-only median and IQR/1.349 for P,D,C; clip z to +/-5. zPD,zPC from product of clipped main z, then training median/IQR1.349 and clip5. Zero robust scale UNKNOWN. Role binary unscaled.'},
 'models':['constant historical mean','PVR+same first_kind effect','PVR+D+C+same first_kind effect','PVR+D+C+P*D+P*C+same first_kind effect','raw original priority ranking'],
 'regularization':'Summed Bernoulli NLL +0.5*(4*sum(main and role coefficient squared)+16*sum(interaction squared)); unpenalized intercept. Fixed Gaussian prior sd0.5 main/role and0.25 interaction. No class weights/tuning.',
 'clock':{'H':120,'window':504,'fit':'First common session monthly, information through preceding close. signal_t>=cut-504 and entry_t+119<cut. Every birth requires full120 potential follow-up, even early exit.2022 no prediction. Source ends2026-05-15.','U':'H=120 not fully0-to0 closed is U even if later exit known. Cannot silently drop U, impute loss or treat pW as ultimate win. If any feature-complete mature U in a month, binary final-win model UNKNOWN for that month. If this prevents coherent all-role test, stop rather than change endpoint/model after inspection.'},
 'minimum':{'n':300,'wins':50,'losses':50,'unique_signal_dates':60,'unique_stocks':100,'unique_I_roots':200,'each_role_n':50,'each_role_wins':10,'each_role_losses':20,'each_role_dates':20},
 'numerics':'full design rank7 and condition<1e6; nonfinite, zero robust scale, support failure or optimizer gradient>1e-6 => all controls UNKNOWN. No rescue retune.',
 'evaluation_if_feasible':'Same known rows and every fixed year. Date20-session blocks, stocks and stock/I-root clusters; same-day and same-day-role AUC. Fixed same-day ceil(n/2) among originally filled only, tie original priority and sid. Exact original round return mean/winner/loss/payoff. Original return>=20% and original complete60 big label retention; 924 Sep19-Oct8 and2026Q1 separately. Fixed probability bins0/.1/.2/.3/.4/.5/1. No time/threshold search.',
 'restrictions':'No account runs, parameter grids, new trading or original strategy edits. Historical/selected-only, non-PIT static universe/industry/source versions and original next-open proxy limits. Not new strategy35%.'}
if (O/'FEATURE_AUDIT.csv').exists():raise RuntimeError('Support already generated; do not silently repeat')
dump('PROTOCOL.json',protocol)
a=pd.read_csv(S);a=a[a.account.eq('PVR')].copy().reset_index(drop=True);assert len(a)==2693
cal=pd.read_csv(CLOCK,index_col=0,parse_dates=True).index;assert str(cal[-1].date())=='2026-05-15'
mp={x['symbol']:x for x in json.loads(M.read_text())}
sources={str(p):sha(p) for p in [S,CLOCK,M,O/'PROTOCOL.json',Path(__file__),R/'cmf_pvr_component_v1/experiment.py']}
fullcal=pd.DatetimeIndex(np.load(cmf.H,allow_pickle=False)["dates"]);fullcal=fullcal[(fullcal>="2013-01-01")&(fullcal<="2026-05-15")]
features=[];aud=[];prefix=[];t0=time.monotonic()
def dcalc(p):
 dc=fullcal[fullcal<=p.index.max()];q=p.reindex(dc);cols=['open','high','low','close'];raw=['raw_'+k for k in cols]
 ok=np.isfinite(q[cols+raw]).all(axis=1)&q[cols+raw].gt(0).all(axis=1)&q.high.gt(q.low)&q.raw_high.gt(q.raw_low)&q.segment_id.notna()
 ok &= q.high.ge(q[cols].max(axis=1))&q.low.le(q[cols].min(axis=1))&q.raw_high.ge(q[raw].max(axis=1))&q.raw_low.le(q[raw].min(axis=1))
 for k in ['observed_bar','is_observed_bar','price_eligible','volume_eligible']:ok &= q[k].notna()&q[k].eq(True)
 for k in ['source_invalid','synthetic_event_bar']:ok &= q[k].notna()&q[k].eq(False)
 for k in ['adjustment_factor','volume_factor']:ok &= np.isfinite(q[k])&q[k].gt(0)
 for k in ['source_kind','source_path']:ok &= q[k].notna()&q[k].astype(str).str.len().gt(0)
 for k in cols:ok &= (q[k]-q['raw_'+k]*q.adjustment_factor).abs().le(1e-10)
 change=pd.Series(False,index=dc)
 for k in ['segment_id','source_kind','source_path','adjustment_factor','volume_factor']:change |= q[k].ne(q[k].shift())
 blocks=((~ok)|(~ok.shift(fill_value=False))|change).cumsum();out=pd.Series(np.nan,index=dc);age=pd.Series(np.nan,index=dc)
 for _,g in q[ok].groupby(blocks[ok],sort=False):
  if len(g)<15:continue
  up=np.diff(g.high.to_numpy());dn=-np.diff(g.low.to_numpy());plus=np.where((up>dn)&(up>0),up,0.);minus=np.where((dn>up)&(dn>0),dn,0.)
  def rma(v):
   z=v[13:].copy();z[0]=v[:14].mean();return pd.Series(z).ewm(alpha=1/14,adjust=False).mean().to_numpy()
  u=rma(plus);v=rma(minus);den=u+v;ds=np.divide(u-v,den,out=np.full(len(u),np.nan),where=den>0)
  out.loc[g.index[14:]]=ds;age.loc[g.index[14:]]=np.arange(14,len(g))
 return out,age
for no,(sid,g) in enumerate(a.groupby('sid',sort=True)):
 m=mp[sid];path=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));h=sha(path);assert h==m['source_sha256'][path];sources[path]=h
 p=pd.read_parquet(path).loc[:'2026-05-15'];nf=pd.read_parquet(m['refs']['facts'],columns=['close','factor']).reindex(p.index);sources[m['refs']['facts']]=sha(m['refs']['facts'])
 assert (p.close-nf.close).abs().max()<1e-7 and (p.adjustment_factor-nf.factor).abs().max()<1e-10
 z=cmf.calc(p);d,age=dcalc(p);ix=pd.DatetimeIndex(g.signal_day)
 for i,row in g.iterrows():
  day=pd.Timestamp(row.signal_day);k=z.loc[day];er=abs(k.score-row.PVR_decision);reason=[]
  if not np.isfinite(row.PVR_decision):reason.append('ORIGINAL_PVR_UNKNOWN')
  elif not np.isfinite(k.score) or er>1e-8:reason.append('ORIGINAL_PVR_NATIVE_MISMATCH')
  if not np.isfinite(d.loc[day]):reason.append('DMI_STRICT_NATIVE_UNKNOWN')
  if not np.isfinite(k.CMF21):reason.append('CMF21_STRICT_NATIVE_UNKNOWN')
  recent=p.loc[:day].tail(21)
  features.append(dict(index=i,sid=sid,signal_day=row.signal_day,P=row.PVR_decision,D=d.loc[day],C=k.CMF21,native_PVR=k.score,PVR_abs_error=er,D_age=age.loc[day],feature_known=not reason,unknown_reason='|'.join(reason),H_equal_L21=bool(recent.high.eq(recent.low).any()),factor_change21=bool(recent.adjustment_factor.nunique(dropna=False)>1),volume_factor_change21=bool(recent.volume_factor.nunique(dropna=False)>1),source_change21=bool(recent.source_kind.nunique(dropna=False)>1 or recent.source_path.nunique(dropna=False)>1)))
 if no%100==0:
  day=g.iloc[0].signal_day;zp=cmf.calc(p.loc[:day]);dp,ap=dcalc(p.loc[:day]);assert np.allclose(zp.loc[day,['CMF21','score']].to_numpy(float),z.loc[day,['CMF21','score']].to_numpy(float),equal_nan=True);assert np.isclose(dp.loc[day],d.loc[day],equal_nan=True);prefix.append(dict(sid=sid,day=day,equal=True))
 aud.append(dict(sid=sid,signal_source=path,source_sha256=h,actual_rounds=len(g)))
 if (no+1)%200==0:print('FEATURE_PROGRESS',no+1,'stocks',round(time.monotonic()-t0,1),'seconds',flush=True)
f=pd.DataFrame(features).set_index('index').sort_index();a=a.join(f.drop(columns=['sid','signal_day']))
q=pd.read_parquet(R/'selection_entry_diagnosis_v1/mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');q=q[q.account.eq('PVR')][['sid','day','epoch']]
qc=pd.read_parquet(R/'core_stock_selection_dmi_v1/DOMAIN.parquet')[['sid','day','epoch']]
ep=pd.concat([q,qc]).drop_duplicates(['sid','day']);a=a.merge(ep,left_on=['sid','signal_day'],right_on=['sid','day'],how='left',validate='one_to_one')
a['root_known']=a.epoch.notna()&~a.epoch.astype(str).isin(['None','nan','[None, None]']);a['root']=a.sid+'|'+a.epoch.astype(str)
for col,day in [('t','signal_day'),('entry_t','entry_day'),('close_t','closed_day')]:a[col]=cal.get_indexer(pd.to_datetime(a[day]))
a['mature120']=a.entry_t+119<len(cal);a['closed_H']=a.closed&a.close_t.lt(a.entry_t+120);a['W']=a.closed_H&a.round_pnl.gt(0);a['L']=a.closed_H&a.round_pnl.le(0);a['U']=~a.closed_H
a['final_win_known']=a.closed&a.round_pnl.gt(0)
a['known_for_fit']=a.feature_known&a.root_known
assert a.t.ge(0).all() and a.entry_t.gt(a.t).all()
support=[]
for month in sorted(set(cal[cal.year>=2023].to_period('M').astype(str))):
 cut=next(i for i,d in enumerate(cal) if str(d.to_period('M'))==month)
 alltr=a[(a.t>=cut-504)&(a.entry_t+119<cut)]
 tr=alltr[alltr.known_for_fit];s=dict(month=month,cutoff=str(cal[cut].date()),all_n=len(alltr),n=len(tr),W=int(tr.W.sum()),L=int(tr.L.sum()),U=int(tr.U.sum()),dates=tr.signal_day.nunique(),stocks=tr.sid.nunique(),I_roots=tr.root.nunique(),test_all=int(a.signal_day.str.startswith(month).sum()),test_feature_known=int((a.signal_day.str.startswith(month)&a.known_for_fit).sum()))
 ok=len(tr)>=300 and tr.W.sum()>=50 and tr.L.sum()>=50 and tr.signal_day.nunique()>=60 and tr.sid.nunique()>=100 and tr.root.nunique()>=200
 for role in ['core','add']:
  ar=alltr[alltr.first_kind.eq(role)];z=tr[tr.first_kind.eq(role)];s.update({role+'_all':len(ar),role+'_known':len(z),role+'_W':int(z.W.sum()),role+'_L':int(z.L.sum()),role+'_U':int(z.U.sum()),role+'_unknown':int((~ar.known_for_fit).sum()),role+'_dates':z.signal_day.nunique()})
  ok=ok and len(z)>=50 and z.W.sum()>=10 and z.L.sum()>=20 and z.signal_day.nunique()>=20
 s['support_without_U']=bool(ok);s['binary_target_identified']=bool(not tr.U.any());s['fit_possible']=bool(ok and not tr.U.any());support.append(s)
a.to_csv(O/'ALL_ORIGINAL_ROUNDS_FEATURE_SUPPORT.csv',index=False);f.to_csv(O/'FEATURE_AUDIT.csv',index=True);pd.DataFrame(aud).to_csv(O/'SOURCE_AUDIT.csv',index=False);pd.DataFrame(support).to_csv(O/'MONTHLY_SUPPORT.csv',index=False)
a[a.mature120&a.U].to_csv(O/'MATURE120_UNRESOLVED_ROUNDS.csv',index=False)
dump('PREFIX_AUDIT.json',prefix);dump('INPUT_HASHES.json',sources);assert all(sha(p)==h for p,h in sources.items())
summary=dict(status='PREFLIGHT_COMPLETE_NO_MODELS_FIT',total=len(a),roles=a.groupby('first_kind').agg(n=('sid','size'),features=('feature_known','sum'),I_roots=('root_known','sum'),mature=('mature120','sum')).to_dict(orient='index'),known_mature_U=int((a.mature120&a.U&a.known_for_fit).sum()),all_mature_U=int((a.mature120&a.U).sum()),months=len(support),support_months=int(pd.DataFrame(support).support_without_U.sum()),binary_possible_months=int(pd.DataFrame(support).fit_possible.sum()),PVR_mismatch=int(a.unknown_reason.str.contains('MISMATCH').sum()),prefix_checks=len(prefix),elapsed_seconds=time.monotonic()-t0,model_fits=0,account_runs=0,parameter_searches=0,original_sources_unchanged=True)
dump('PREFLIGHT_SUMMARY.json',summary);print('SUMMARY',json.dumps(clean(summary),ensure_ascii=False),flush=True);print(pd.DataFrame(support).to_string(index=False),flush=True)
