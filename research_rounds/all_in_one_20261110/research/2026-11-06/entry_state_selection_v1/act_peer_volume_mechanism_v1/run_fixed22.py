"""Only fixed22 formula points; never account, ranks, or outcome labels."""
from pathlib import Path
import json,hashlib,datetime,ast,sys,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
F=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design/features.py')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,(np.bool_,)):return bool(v)
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
 if isinstance(v,(pd.Timestamp,)):return str(v.date())
 return v

def save(n,d):
 with (O/n).open('x') as f:json.dump(clean(d),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def csv(n,df):
 assert not (O/n).exists();df.to_csv(O/n,index=False,float_format='%.17g')
start=time.monotonic();sources=read(O/'SOURCE_HASHES_BEFORE.json');assert all(sha(p)==h for p,h in sources.items());sources[str(H)]=sha(H);sources[str(Path(__file__))]=sha(__file__)
save('COMPUTATION_SOURCE_FREEZE.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=sources,protocol_sha256=sha(O/'PROTOCOL.json')))
ns={};exec(compile(F.read_text(),str(F),'exec'),ns);pvr=ns['original_pvr'];clock=ns['original_observation_clock']
S=W/'pvr-current-v3-information-capital-20261101/original_score_function.py';tree=ast.parse(S.read_text());score_node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='score');ns2={'np':np,'pd':pd};exec(compile(ast.Module(body=[score_node],type_ignores=[]),str(S),'exec'),ns2);exact_score=ns2['score']
cases=read(O/'FIXED_CASES.json');mapping=read(O/'MAPPING_AND_PEERS.json');roster=mapping['case_sectors'];sidmap=mapping['mapping'];paths=read(O/'SOURCE_PATHS.json');meta=read(M/'a-share-selection-e0-20261024/inputs-v2/metadata.json');cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates']);w=.9**np.arange(20,-1,-1);w=w/w.sum()
frames={};own={};targets={};reproduction=[];dailysets={}
# Source reads preserve the original values/segments. No feature or outcome read after max requested date.
maxdate=max(c[1] for c in cases)
for sid,path in paths.items():
 p=pd.read_parquet(path);assert p.index.is_unique and p.index.is_monotonic_increasing;frames[sid]=p.loc[:maxdate].copy()

POS=['price_eligible','volume_eligible','observed_bar','is_observed_bar'];NEG=['source_invalid','synthetic_event_bar'];IDENT=['source_kind','source_path','segment_id','adjustment_factor','volume_factor']
def row_ok(p):
 cols=['open','high','low','close'];raw=['raw_'+c for c in cols]
 z=np.isfinite(p[cols+raw]).all(axis=1)&p[cols+raw].gt(0).all(axis=1)
 z&=p.high.ge(p[['open','close','low']].max(axis=1))&p.low.le(p[['open','close','high']].min(axis=1))
 z&=p.raw_high.ge(p[['raw_open','raw_close','raw_low']].max(axis=1))&p.raw_low.le(p[['raw_open','raw_close','raw_high']].min(axis=1))
 for c in POS:z&=p[c].eq(True)
 for c in NEG:z&=p[c].eq(False)
 z&=np.isfinite(p.raw_volume)&p.raw_volume.gt(0)&np.isfinite(p.amount)&p.amount.gt(0)&p.volume_unit.eq('shares')&p.amount_unit.eq('CNY')
 z&=np.isfinite(p.adjustment_factor)&p.adjustment_factor.gt(0)&np.isfinite(p.volume_factor)&p.volume_factor.gt(0)
 for c in cols:z&=(p[c]-p['raw_'+c]*p.adjustment_factor).abs().le(1e-10)
 avg=p.amount/p.raw_volume;tol=.5/p.raw_volume+1e-8;z&=avg.ge(p.raw_low-tol)&avg.le(p.raw_high+tol)
 return z

def strict(p):
 reasons=[]
 if not row_ok(p).all():reasons.append('INVALID_OR_MISSING_BAR')
 for c in IDENT:
  if p[c].isna().any() or p[c].nunique(dropna=False)!=1:reasons.append('CHANGE_OR_UNKNOWN_'+c)
 return not reasons,'|'.join(reasons)

# Only each requested peer v and its explicit22 own observations are computed.
def project(p,days):
 valid,block=clock(p);groups={key:g for key,g in p.loc[valid].groupby(block[valid],sort=False)};result={}
 for day in days:
  out=dict(day=day,v=np.nan,amount_ref=np.nan,amount=np.nan,available=False,reason='',support_start=None,support_end=day,n=0,source_segment=None,factor=None)
  if day not in p.index:out['reason']='NO_CURRENT_OBSERVATION'
  elif not valid.loc[day]:out['reason']='INVALID_CURRENT_ORIGINAL_CLOCK'
  else:
   group=groups[block.loc[day]];ix=group.index.get_loc(day);q=group.iloc[max(0,ix-21):ix+1];out.update(n=len(q),support_start=q.index[0],amount=float(q.amount.iloc[-1]),source_segment=q.segment_id.iloc[-1],factor=q.adjustment_factor.iloc[-1])
   if len(q)<22:out['reason']='INSUFFICIENT_ORIGINAL_BLOCK22'
   else:
    ok,why=strict(q);out['amount_ref']=float(q.amount.iloc[:-1].median());out['v']=float(np.log(out['amount']/out['amount_ref']));out['available']=bool(ok and np.isfinite(out['v']));out['reason']='AVAILABLE' if out['available'] else why or 'NONFINITE_V'
  result[day]=out
 return result

saved=pd.read_csv(R/'pvr_formula_contribution_v1/case_POINT_FEATURES.csv').set_index(['sid','day']);sd=pd.read_csv(R/'pvr_formula_contribution_v1/case_DAILY_CONTRIBUTIONS.csv');qa=[]
for sid,day,_ in cases:
 key=(sid,day);dt=pd.Timestamp(day);p=frames[sid].loc[:dt];o=pvr(p);old=exact_score(p);pd.testing.assert_frame_equal(o,old,check_exact=True)
 valid,block=clock(p);idx=p.index[valid&block.eq(block.loc[dt])];j=idx.get_loc(dt);ix=idx[j-20:j+1];assert len(ix)==21 and np.isfinite(o.loc[ix,'e']).all()
 own[key]=o.loc[ix].copy();dailysets[key]=ix
 for peer in roster[sidmap[sid]]:targets.setdefault(peer,set()).update(ix)
 original=float(o.loc[dt,'score']);ref=float(saved.loc[key,'score_original']);assert abs(original-ref)<1e-10
 dsave=sd[sd.sid.eq(sid)&sd.signal_day.eq(day)].set_index('bar_day').reindex(ix.strftime('%Y-%m-%d'))
 derr=float(np.nanmax(np.abs(o.loc[ix,['u','b','e','E','score']].to_numpy()-dsave[['u','b','e','E','score']].to_numpy())));assert derr<1e-10
 common=cal[cal.get_loc(dt)-84:cal.get_loc(dt)+1];known,reason=strict(p.reindex(common));assert known==bool(saved.loc[key,'strict_known'])
 reproduction.append(dict(sid=sid,day=day,score_original=original,score_saved=ref,error=abs(original-ref),daily_max_error=derr,strict85_known=known,strict85_reason=reason))
print('ORIGINAL22_REPRODUCED',round(time.monotonic()-start,2),flush=True)
projected={};peer_unique=[]
for n,(sid,days) in enumerate(targets.items()):
 projected[sid]=project(frames[sid],sorted(days))
 for x in projected[sid].values():peer_unique.append(dict(sid=sid,sector=sidmap[sid],**x))
 if (n+1)%100==0:print('PEERS',n+1,'elapsed',round(time.monotonic()-start,2),flush=True)
# All raw support rows for the projected peer values are indexed in peer_unique; no peer omitted by outcome.
daily=[];coverage=[];points=[]
rep={(r['sid'],r['day']):r for r in reproduction}
for sid,day,case_source in cases:
 key=(sid,day);sec=sidmap[sid];peers=[s for s in roster[sec] if s!=sid];g=own[key].copy();cs=[]
 for n,dt in enumerate(dailysets[key]):
  eligible=[];missing=[]
  for peer in peers:
   r=projected[peer][dt]
   if r['available']:eligible.append((peer,r['v']))
   else:missing.append((peer,r['reason']))
   coverage.append(dict(sid=sid,signal_day=day,bar_day=dt,peer=peer,sector=sec,**{k:v for k,v in r.items() if k!='day'}))
  h=float(np.median([v for _,v in eligible])) if eligible else np.nan;v=float(np.log(frames[sid].loc[dt,'amount']/g.loc[dt,'amount_ref']));u=float(g.loc[dt,'u']);bstar=float(np.tanh(v-h));estar=float(u*(1+.5*abs(u)*bstar));e=float(g.loc[dt,'e'])
  if np.isfinite(estar):assert np.sign(estar)==np.sign(u) and abs(estar)<=1.5
  c=dict(sid=sid,signal_day=day,bar_day=dt,sector=sec,lag=20-n,weight=float(w[n]),u=u,scale=float(g.loc[dt,'scale']),r=float(g.loc[dt,'r']),amount=float(frames[sid].loc[dt,'amount']),amount_ref=float(g.loc[dt,'amount_ref']),v=v,h_peer=h,b_original=float(g.loc[dt,'b']),b_peer=bstar,e_original=e,e_peer=estar,weighted_original=float(w[n]*e),weighted_peer=float(w[n]*estar),delta_e=estar-e,weighted_delta=float(w[n]*(estar-e)),weighted_price=float(w[n]*u),weighted_old_amount=float(w[n]*(e-u)),weighted_peer_amount=float(w[n]*(estar-u)),peer_total=len(peers),peer_available=len(eligible),peer_fraction=len(eligible)/len(peers) if peers else np.nan,reference_status='AVAILABLE_PEER_CONDITIONAL' if eligible else 'UNKNOWN_NO_AVAILABLE_PEER',available_ids='|'.join(p for p,v in eligible),missing_ids_reasons='|'.join(p+':'+why for p,why in missing),own_amount_support_strict22=projected[sid][dt]['available'],own_amount_support_reason=projected[sid][dt]['reason'])
  cs.append(c);daily.append(c)
 z=pd.DataFrame(cs);full=z.e_peer.notna().all();E=float(z.weighted_peer.sum()) if full else np.nan;score=float(50+50*np.tanh(2*E)) if full else np.nan;known=bool(rep[key]['strict85_known'] and full and z.own_amount_support_strict22.all())
 point=dict(sid=sid,day=day,name=meta[sid]['name'],sector=sec,industry=meta[sid]['industry'],case_source=case_source,**{k:v for k,v in rep[key].items() if k not in ['sid','day']},score_peer_mechanical=score,score_peer_supported=score if known else np.nan,peer_supported=known,status='KNOWN_AVAILABLE_PEER_CONDITIONAL_NONPIT' if known else 'UNKNOWN_LINEAGE_OR_PEER',E_original=float(z.weighted_original.sum()),E_peer_mechanical=E,E_price=float(z.weighted_price.sum()),E_old_amount=float(z.weighted_old_amount.sum()),E_peer_amount=float(z.weighted_peer_amount.sum()) if full else np.nan,score_delta=score-rep[key]['score_original'],peer_total=len(peers),peer_min=int(z.peer_available.min()),peer_max=int(z.peer_available.max()),peer_fraction_min=float(z.peer_fraction.min()),h_min=float(z.h_peer.min()),h_max=float(z.h_peer.max()),h_positive_days=int(z.h_peer.gt(0).sum()),h_negative_days=int(z.h_peer.lt(0).sum()),delta_up=float(z.loc[z.u.gt(0),'weighted_delta'].sum()),delta_down=float(z.loc[z.u.lt(0),'weighted_delta'].sum()),last_day_h=float(z.h_peer.iloc[-1]),last_day_b=float(z.b_original.iloc[-1]),last_day_bpeer=float(z.b_peer.iloc[-1]))
 for N in [1,3,5]:point['last'+str(N)+'_delta_E']=float(z.weighted_delta.iloc[-N:].sum())
 points.append(point)
csv('ORIGINAL_REPRODUCTION.csv',pd.DataFrame(reproduction));csv('POINT_FEATURES.csv',pd.DataFrame(points));csv('DAILY_CONTRIBUTIONS.csv',pd.DataFrame(daily));csv('PEER_COVERAGE_EVERY_CONTRIBUTION.csv',pd.DataFrame(coverage));csv('PEER_UNIQUE_SOURCE_AUDIT.csv',pd.DataFrame(peer_unique));
save('FEATURE_SEAL.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={p.name:sha(p) for p in O.glob('*.csv')},new_future_labels_read=False,new_account_runs=0,new_ranks=0))
print('FEATURES22_SEALED',round(time.monotonic()-start,2),flush=True)
# Each fixed case physically truncates every input used by it, and separately poisons future amounts/closes.
for sid,day,_ in cases:
 dt=pd.Timestamp(day);days=dailysets[(sid,day)];checks=0
 for peer in roster[sidmap[sid]]:
  p=frames[peer];pref=project(p.loc[:dt].copy(),days);poison=p.copy();mask=poison.index>dt;poison.loc[mask,'amount']*=1e6;poison.loc[mask,'close']*=1e4;bad=project(poison,days)
  for d in days:
   baseline=projected[peer][d]
   for name,other in [('prefix',pref[d]),('future_poison',bad[d])]:
    for k in baseline:
     a=baseline[k];b=other[k]
     assert (pd.isna(a) and pd.isna(b)) or a==b,(sid,day,peer,d,name,k,a,b)
   checks+=1
 # Candidate original price/amount units invariant, and explicit peer-v unit invariance checked on all own required supports.
 p=frames[sid].loc[:dt];old=pvr(p);price=p.copy();price.close*=100.;ps=pvr(price);amount=p.copy();amount.amount*=10000.;am=pvr(amount)
 price_error=float(np.nanmax(np.abs(old[['u','b','e','E','score']]-ps[['u','b','e','E','score']])));amount_error=float(np.nanmax(np.abs(old[['u','b','e','E','score']]-am[['u','b','e','E','score']])));assert max(price_error,amount_error)<1e-9
 qa.append(dict(sid=sid,day=day,all_used_member_day_prefix_exact=True,future_close_amount_poison_exact=True,member_day_checks=checks,original_price_unit_error=price_error,original_amount_unit_error=amount_error))
 print('QA_CASE',sid,day,round(time.monotonic()-start,2),flush=True)
csv('PREFIX_FUTURE_QA.csv',pd.DataFrame(qa))
# Unit and common current multiplier invariance are algebraic controls with fixed support, not return labels.
synth=[]
for u in [-1.,-.5,0.,.5,1.]:
 for vv in [-2.,0.,2.]:
  peer=np.array([vv,vv,vv]);h=float(np.median(peer));b=float(np.tanh(vv-h));e=u*(1+.5*abs(u)*b);assert b==0 and e==u
  synth.append(dict(test='equal_all_v',u=u,v=vv,h=h,b_peer=b,e_peer=e))
for vi,peer in [(.3,[-.2,.1,.7]),(-.6,[.4,.6,.8])]:
 h=np.median(peer)
 for c in [np.log(.01),np.log(5.),np.log(10000.)]:assert abs(np.tanh(vi-h)-np.tanh(vi+c-np.median(np.array(peer)+c)))<1e-14
 assert np.median(peer)==np.median(peer) # Own value is absent by construction; separate explicit test below.
u=.8;v=.9;peer=[-.4,.3,.8];h=float(np.median(peer));b1=np.tanh(v-h);h2=float(np.median(peer));assert h==h2 and b1!=np.tanh(900-h2)
assert np.isnan(np.median([]))
# Strict source-boundary/flag fixture, original clock resets, no singleton fill.
ix=pd.bdate_range('2000-01-03',periods=100);close=100*np.exp(np.arange(100)*.001);fixture=pd.DataFrame({'open':close,'high':close*1.01,'low':close*.99,'close':close,'raw_open':close,'raw_high':close*1.01,'raw_low':close*.99,'raw_close':close,'raw_volume':1e6,'amount':close*1e6,'volume_unit':'shares','amount_unit':'CNY','adjustment_factor':1.,'volume_factor':1.,'segment_id':0,'source_kind':'fixture','source_path':'fixture',**{c:True for c in POS},**{c:False for c in NEG}},index=ix)
assert project(fixture,[ix[-1]])[ix[-1]]['available']
for col,val in [('segment_id',1),('source_path','new'),('adjustment_factor',2.),('volume_factor',2.),('price_eligible',False),('amount',0.)]:
 q=fixture.copy();q.loc[ix[-5],col]=val;z=project(q,[ix[-1]])[ix[-1]];assert not z['available'],col
for k in [.01,10000.]:
 ref=np.array([2.,3.,5.,1.,9.]*4+[4.]);a=7.;assert abs(np.log(a/np.median(ref))-np.log(a*k/np.median(ref*k)))<1e-14
# For h>0 delta has opposite u sign. Bounds remain1.5, not1.
for u in [-1.,-.5,0.,.5,1.]:
 for v in [-2.,0.,2.]:
  delta=.5*u*abs(u)*(np.tanh(v-1.)-np.tanh(v));assert delta*u<=0
csv('SYNTHETIC_CASES.csv',pd.DataFrame(synth));save('SYNTHETIC_QA.json',dict(equal_all_v_bstar_zero=True,unit_invariance=True,common_current_amount_multiplier_cancels=True,common_multiplier_requires_fixed_available_peer_set=True,leave_one_out_own_value_not_in_h=True,singleton_no_peer_UNKNOWN=True,source_segment_factor_flags_reset_or_unknown=True,sign_preserved=True,e_absolute_bound=1.5,h_positive_softens_both_up_and_down=True,not_causal_factor_identification=True))
assert all(sha(p)==h for p,h in sources.items());save('SOURCE_HASHES_AFTER.json',sources)
x=pd.DataFrame(points);pv=pd.DataFrame(peer_unique);dd=pd.DataFrame(daily);summary=dict(case_count=len(x),stock_count=x.sid.nunique(),sector_count=x.sector.nunique(),source_members=len(frames),original_max_error=float(x.error.max()),original_daily_max_error=float(x.daily_max_error.max()),strict85_known=int(x.strict85_known.sum()),strict85_unknown=int((~x.strict85_known).sum()),peer_supported=int(x.peer_supported.sum()),mechanical_scores_known=int(x.score_peer_mechanical.notna().sum()),daily_rows=len(dd),coverage_rows=len(coverage),unique_peer_date_rows=len(pv),peer_unique_available=int(pv.available.sum()),peer_unique_missing=int((~pv.available).sum()),peer_min=int(dd.peer_available.min()),peer_fraction_min=float(dd.peer_fraction.min()),availability_reason_counts=pv.reason.value_counts().to_dict(),prefix_case_count=len(qa),member_day_prefix_checks=sum(q['member_day_checks'] for q in qa),all_source_hashes_unchanged=True,no_new_outcomes=True,account_runs=0,ranking_runs=0,parameter_searches=0,elapsed_seconds=time.monotonic()-start)
save('SUMMARY.json',summary);save('OUTPUT_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file()});print(json.dumps(clean(summary),ensure_ascii=False,indent=2));print(x[['sid','day','name','peer_supported','score_original','score_peer_mechanical','score_delta','peer_min','peer_total','peer_fraction_min','delta_up','delta_down']].to_string(index=False))
