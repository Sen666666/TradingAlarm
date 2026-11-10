"""One frozen fixed-case signal calculation; no economics, ranking, labels or external writes."""
from pathlib import Path
import json,hashlib,datetime
import numpy as np,pandas as pd

O=Path(__file__).resolve().parent
R=O.parent
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
P=R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(p,expected=None):
 p=Path(p);v=sha(p)
 if expected is not None:assert v==expected,(str(p),'hash mismatch')
 S[str(p)]=v;return p
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(pd.Timestamp,datetime.datetime)):return str(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if x is pd.NA or x is pd.NaT:return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2))
def bounds(l,h,j,qminus,qplus):
 if l>j:return 1.,1.
 if h<=j:return 0.,0.
 lb=max(0.,(qminus-j)/(h-j))
 ub=min(1.,(qplus-l)/(j-l)) if l<j else (0. if qplus<=l else 1.)
 return lb,ub

def evaluate(raw,rec,case,calendar):
 day=pd.Timestamp(case['day']);raw=raw.loc[:day].copy()
 out=dict(case,known_at=str(day.date())+' CLOSE',status='UNKNOWN',candidate_permit=None)
 if rec is None:
  out.update(status='NOT_RECEIPT',unknown_reason='No saved original PRICE receipt on fixed day')
  return out
 for c in ['root_day','born','phase','E0','I','Q','R','receipt_id']:
  out[c]=rec[c]
 if not bool(rec['receipt']) or not bool(rec['active']):
  out.update(status='NOT_RECEIPT',unknown_reason='Not a current active fresh original PRICE receipt');return out
 if not bool(rec['valid']) or bool(rec['root_unknown']):
  out['unknown_reason']='Original price root unknown';return out
 if day not in raw.index or pd.isna(rec['root_day']):
  out['unknown_reason']='Missing current source bar or root birth';return out
 rd=pd.Timestamp(rec['root_day'])
 if rd>day or rd not in raw.index:
  out['unknown_reason']='Invalid or missing root birth';return out
 pos=calendar.get_indexer([day])[0]
 if pos<0:
  out['unknown_reason']='Missing current common calendar date';return out
 if bool(rec['born']):
  if pos<20:
   out['unknown_reason']='Fewer than20 prior common dates';return out
  dates=calendar[pos-20:pos+1]
 else:dates=calendar[(calendar>=rd)&(calendar<=day)]
 hist=raw.reindex(dates)
 if len(hist)==0 or hist[['raw_open','raw_high','raw_low','raw_close','open','high','low','close','adjustment_factor']].isna().any().any():
  out['unknown_reason']='Missing comparison-path price/factor';return out
 if not ((hist[['raw_open','raw_high','raw_low','raw_close','open','high','low','close','adjustment_factor']]>0).all().all()):
  out['unknown_reason']='Nonpositive price/factor';return out
 for c in ['observed_bar','is_observed_bar','price_eligible']:
  if not hist[c].eq(True).all():
   out['unknown_reason']='Not observed/eligible comparison path: '+c;return out
 for c in ['source_invalid','synthetic_event_bar']:
  if not hist[c].eq(False).all():
   out['unknown_reason']='Invalid/synthetic comparison path: '+c;return out
 for c in ['source_kind','source_path','segment_id']:
  if hist[c].isna().any() or hist[c].nunique(dropna=False)!=1:
   out['unknown_reason']='Source lineage discontinuity: '+c;return out
 factor=float(hist.adjustment_factor.iloc[-1])
 if not np.isclose(hist.adjustment_factor,factor,rtol=1e-12,atol=1e-12).all():
  out['unknown_reason']='Adjustment factor discontinuity';return out
 for c in ['open','high','low','close']:
  if not np.isclose(hist[c],hist['raw_'+c]*hist.adjustment_factor,rtol=1e-12,atol=1e-8).all():
   out['unknown_reason']='Native/raw coordinate mismatch: '+c;return out
 r=raw.loc[day]
 if not (r.volume_unit=='shares' and r.amount_unit=='CNY' and bool(r.volume_eligible)):
  out['unknown_reason']='Unknown share/amount units or ineligible volume';return out
 if not (np.isfinite(r.amount) and r.amount>0 and np.isfinite(r.raw_volume) and r.raw_volume>0):
  out['unknown_reason']='Missing/nonpositive volume or amount';return out
 if bool(rec['born']):
  j=float(rec['U'])
  if not np.isclose(j,hist.high.iloc[:-1].max(),rtol=1e-12,atol=1e-8):
   out['unknown_reason']='Original birth U mismatch with prior20High';return out
 else:j=float(hist.close.iloc[:-1].max())
 if not (np.isfinite(j) and j>0 and float(r.close)>j and np.isclose(float(rec['C']),float(r.close),rtol=1e-12,atol=1e-8)):
  out['unknown_reason']='New receipt/frontier coordinate contradiction';return out
 j/=factor;l=float(r.raw_low);h=float(r.raw_high);q=float(r.amount/r.raw_volume);eps=float(.5/r.raw_volume+1e-8)
 if not (l<=float(r.raw_open)<=h and l<=float(r.raw_close)<=h and l-eps<=q<=h+eps):
  out['unknown_reason']='Invalid OHLC or mean outside raw range';return out
 qm=max(l,q-eps);qp=min(h,q+eps)
 lb,ub=bounds(l,h,j,qm,qp)
 assert 0<=lb<=ub+1e-12 and ub<=1
 out.update(status='KNOWN',unknown_reason=None,boundary_raw=j,raw_O=float(r.raw_open),raw_H=h,raw_L=l,raw_C=float(r.raw_close),raw_q=q,q_epsilon=eps,q_lower=qm,q_upper=qp,raw_shares=float(r.raw_volume),amount=float(r.amount),factor=factor,LB=lb,UB=ub,candidate_permit=bool(lb>.5),point_q_above_boundary=bool(q>j),comparison_bars=len(hist),source_kind=r.source_kind,source_path=r.source_path,segment_id=r.segment_id)
 return out

def run():
 if (O/'RUN_ONCE.json').exists():raise RuntimeError('Refuse to repeat frozen fixed-case run')
 for p in [Path(__file__),O/'CONTRACT.md',O/'FIXED_CASES.json']:src(p)
 save('RUN_ONCE.json',dict(started=str(datetime.datetime.now(datetime.timezone.utc)),precompute_hashes=S.copy(),accounts=0))
 manifest={x['symbol']:x for x in json.loads(src(M).read_text())}
 cases=json.loads((O/'FIXED_CASES.json').read_text())
 with np.load(src(H),allow_pickle=False) as n:cal=pd.DatetimeIndex(n['dates'])
 cols=['sid','day','C','U','root_day','born','receipt','active','valid','root_unknown','phase','E0','I','Q','R','receipt_id']
 receipts=pd.read_parquet(src(P),columns=cols,filters=[('sid','in',sorted({c['sid'] for c in cases}))])
 sources={}
 for sid in sorted({c['sid'] for c in cases}):
  m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
  sources[sid]=pd.read_parquet(src(p,m['source_sha256'][p]))
 rows=[];qa=[]
 for c in cases:
  d=pd.Timestamp(c['day']);a=receipts[receipts.sid.eq(c['sid'])&receipts.day.eq(d)]
  assert len(a)<=1,(c,len(a))
  rec=a.iloc[0].to_dict() if len(a) else None
  raw=sources[c['sid']]
  ans=evaluate(raw,rec,c,cal)
  truncated=evaluate(raw.loc[:d],rec,c,cal[cal<=d])
  assert clean(ans)==clean(truncated),(c,'prefix mismatch')
  perturbed=raw.copy();future=perturbed.index>d
  perturbed.loc[future,['open','high','low','close','raw_open','raw_high','raw_low','raw_close','amount','raw_volume']]=1e100
  assert clean(ans)==clean(evaluate(perturbed,rec,c,cal)),(c,'future perturbation')
  qa.append(dict(sid=c['sid'],day=c['day'],new_calculation_prefix=True,future_perturbation_invariant=True,native_receipt_scope='trusted frozen receipt, not a fresh root-state replay'))
  rows.append(ans)
 df=pd.DataFrame(rows);df.to_csv(O/'FIXED_CASE_RESULTS.csv',index=False);save('FIXED_CASE_RESULTS.json',rows)
 # Structural tests. Point-value tests below set epsilon zero by construction.
 tests={}
 tests['all_range_above'] = bounds(11,12,10,11.5,11.5)==(1.,1.)
 tests['all_range_below'] = bounds(8,10,10,9,9)==(0.,0.)
 tests['equal_threshold_not_allowed'] = bounds(8,12,10,11,11)[0]==.5
 tests['same_q_different_H_different_permission'] = bounds(8,12,10,11.1,11.1)[0]>.5 and bounds(8,14,10,11.1,11.1)[0]<.5
 tests['sharp_lower_bound_two_price_mass'] = np.isclose(.55*12+.45*10,11.1)
 tests['degenerate_above_range'] = bounds(12,12,10,12,12)==(1.,1.)
 tests['boundary_equal_price_not_strictly_above'] = bounds(10,10,10,10,10)==(0.,0.)
 known=[r for r in rows if r['status']=='KNOWN'];seed=next(r for r in rows if r['status']=='KNOWN');case=next(c for c in cases if c['sid']==seed['sid'] and c['day']==seed['day']);d=pd.Timestamp(case['day'])
 rr=receipts[receipts.sid.eq(case['sid'])&receipts.day.eq(d)].iloc[0].to_dict();raw=sources[case['sid']]
 bad=raw.copy();bad.loc[d,'amount']=float(bad.loc[d,'raw_volume'])*float(bad.loc[d,'raw_high'])*2
 tests['impossible_mean_UNKNOWN']=evaluate(bad,rr,case,cal)['status']=='UNKNOWN'
 bad=raw.copy();bad.loc[d,'source_path']='__synthetic_discontinuity__'
 tests['source_change_UNKNOWN']=evaluate(bad,rr,case,cal)['status']=='UNKNOWN'
 bad=raw.copy();bad.loc[d,'adjustment_factor']*=2
 tests['factor_change_UNKNOWN']=evaluate(bad,rr,case,cal)['status']=='UNKNOWN'
 bad=raw.copy();bad.loc[d,'volume_unit']='lots'
 tests['unverified_units_UNKNOWN']=evaluate(bad,rr,case,cal)['status']=='UNKNOWN'
 assert all(tests.values())
 save('PREFIX_QA.json',qa)
 unchanged=all(sha(p)==h for p,h in S.items());assert unchanged
 save('SOURCE_HASHES.json',S)
 save('QA.json',dict(cases=len(cases),known=len(known),permitted=sum(r['candidate_permit'] for r in known),unknown=sum(r['status']=='UNKNOWN' for r in rows),not_receipt=sum(r['status']=='NOT_RECEIPT' for r in rows),prefix_checks=len(qa),synthetic=tests,input_hashes_unchanged=unchanged,economic_runs=0,rankings=0,filtered_PnL=0,parameters_scanned=0,source_receipts_not_recomputed=True,technical_failures_before_computation=['read-only shell heredoc temp file prohibited','shell JSON quoting emitted literal newline escape; fixed before computation']))
 print(df[['sid','day','role','status','boundary_raw','raw_q','raw_H','raw_L','LB','UB','candidate_permit','unknown_reason']].to_string(index=False))
 print('QA',json.dumps(clean(tests),ensure_ascii=False))
if __name__=='__main__':run()
