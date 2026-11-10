"""Independent exact-index oracle and original-path coverage cross-check."""
from pathlib import Path
from collections import Counter,defaultdict
import json,gzip,pickle,hashlib,sys,time,ast,copy
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;R=P.parent/'trend_exit_controls_v1';S=P/'signal_context';H=S/'held_h2_diagnostic'
sys.path.insert(0,str(P));from context_provider import ContextProvider
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def gz(p,lines=False):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f] if lines else json.load(f)
def ints(x):return np.asarray(x).astype('datetime64[D]').astype('int64')
def at_exact(f,days,col):
 fd=ints(f.index);ii=np.searchsorted(fd,days);ok=(ii<len(fd));ok[ok]&=fd[ii[ok]]==days[ok];v=np.full(len(days),np.nan);v[ok]=f[col].to_numpy(float)[ii[ok]];return v
def eq(a,b):
 aa=np.asarray(a);bb=np.asarray(b)
 if aa.dtype.kind=='b' or bb.dtype.kind=='b':assert np.array_equal(aa,bb)
 else:assert np.allclose(aa,bb,equal_nan=True,rtol=1e-12,atol=1e-12),(aa,bb)
C=Counter();start=time.monotonic();manifest=read(P/'relative_context/MANIFEST.json');assert sha(P/'prepare_relative_context.py')==manifest['script_sha256'];assert sha(P/'DIAGNOSTIC_FREEZE.json')==manifest['diagnostic_freeze_sha256'];assert sha(manifest['data_file'])==manifest['data_sha256']
for p,h in manifest['sources'].items():assert sha(p)==h,p;C['source_SHA_verified']+=1
provider=ContextProvider();data=provider.data;om=read(R/'indicators/MANIFEST.json')
with gzip.open(om['data_file'],'rb') as f:old=pickle.load(f)
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');sm={r['symbol']:r for r in read(W/'STOCK_MANIFEST.json')};im={r['series']:r for r in read(W/'INDUSTRY_MANIFEST.json')};meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
mp=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USZI399300.csv');market=pd.read_csv(mp,index_col=0,parse_dates=True);md=ints(market.index);mc=market.close.to_numpy(float);assert (np.isfinite(mc)&(mc>0)).all();assert len(set(md))==len(md) and (np.diff(md)>0).all()
SF={};IF={};oracle={}
for sid,z in data.items():
 f=pd.read_parquet(sm[sid]['refs']['facts'],columns=['close','segment_id','i_target']);SF[sid]=f;sector=meta[sid]['sector_id'];assert sector==z['sector']
 if sector not in IF:IF[sector]=pd.read_parquet(next(p for p in im[sector]['source_sha256'] if '/industry-facts/' in p),columns=['close','segment_id'])
 g=IF[sector];days=z['days'].astype('int64');mi=np.searchsorted(md,days);ok=mi<len(md);ok[ok]&=md[mi[ok]]==days[ok];ok&=mi>=20
 anchor=np.full(len(days),np.iinfo('int32').min,dtype='int64');anchor[ok]=md[mi[ok]-20]
 sc=at_exact(f,days,'close');sp=at_exact(f,anchor,'close');ss=at_exact(f,days,'segment_id');sa=at_exact(f,anchor,'segment_id');ic=at_exact(g,days,'close');ip=at_exact(g,anchor,'close');iseg=at_exact(g,days,'segment_id');ia=at_exact(g,anchor,'segment_id');mr=np.full(len(days),np.nan);mr[ok]=mc[mi[ok]]/mc[mi[ok]-20]-1
 ready=old[sid]['observed_valid'].copy()&ok&np.isfinite(sc)&np.isfinite(sp)&np.isfinite(ic)&np.isfinite(ip)&(sc>0)&(sp>0)&(ic>0)&(ip>0)&(ss==sa)&(iseg==ia)
 sr=np.full(len(days),np.nan);ir=sr.copy();rs=sr.copy();sr[ready]=sc[ready]/sp[ready]-1;ir[ready]=ic[ready]/ip[ready]-1;rs[ready]=sr[ready]-np.maximum(ir[ready],mr[ready]);rp=old[sid]['observed_valid']&np.isfinite(old[sid]['values'][:,1])
 for k,v in dict(anchor_days=anchor,close=sc,EMA20=old[sid]['values'][:,1],source_segment=ss,ready_R=ready,ready_P=rp,stock_return20=sr,industry_return20=ir,market_return20=mr,RS20=rs).items():eq(z[k],v);C['full_array_fields_verified']+=1
 oracle[sid]=dict(days=days,anchor_days=anchor,close=sc,EMA20=old[sid]['values'][:,1],source_segment=ss,ready_R=ready,ready_P=rp,RS20=rs,stock_return20=sr,industry_return20=ir,market_return20=mr)
 co=dict(rows=len(days),ready_R=int(ready.sum()),ready_P=int(rp.sum()),ready_joint=int((ready&rp).sum()),double_weak=int((ready&rp&(rs<=0)&(sc<old[sid]['values'][:,1])).sum()));assert manifest['counts'][sid]==co
 C['symbols']+=1;C['rows']+=len(days);C['ready_R']+=int(ready.sum());C['ready_P']+=int(rp.sum());C['empty_symbols']+=len(days)==0
 if C['symbols']%400==0:print('INDEPENDENT_INPUT',C['symbols'],flush=True)
assert C['symbols']==manifest['symbols'] and C['rows']==manifest['rows']
def scalar_check(q,b,fieldmap):
 for new,prev in fieldmap.items():
  if new in {'RS20','anchor_day','stock_return20','industry_return20','market_return20'} and not q['ready_R']:continue
  if b.get(prev) is not None:
   assert q.get(new) is not None,(new,prev,b)
   if isinstance(b[prev],(int,float)):eq(q[new],b[prev])
   else:assert q[new]==b[prev],(new,q[new],b[prev])
fields={'close':'stock_current_causal_close','EMA20':'stock_EMA20','RS20':'RS20','anchor_day':'anchor_day','source_segment':'stock_current_source_segment','stock_return20':'stock_return20','industry_return20':'industry_return20','market_return20':'HS300_price_index_return20','sector':'sector'}
for ref in ['2022_2024','strong']:
 rr=read(S/(ref+'_ALL_DECISION_CONTEXT_EXTENDED.json'))
 for z in rr:
  q=provider.at(z['sid'],z['decision_at']);scalar_check(q,z,fields);assert q['ready_P']==(z['EMA20_provider_status']=='READY');assert q['ready_R']==(z['RS20'] is not None);C['entry_contexts']+=1
for z in read(S/'DEC122_ACTUAL_FILL_DECISION_CONTEXT.json'):
 q=provider.at(z['sid'],z['decision_at']);scalar_check(q,z,fields);C['Dec_actual_fill_contexts']+=1
heldsummary={}
for ref in ['2022_2024','strong']:
 pair=R/'runs/BASELINE'/ref/'pair';book=gz(pair/'B.json.gz');daily=gz(pair/'daily.jsonl.gz',True);dby={d['at']:d for d in daily};layers={x['id']:x for x in book['layers']};requests=defaultdict(list)
 for a in book['audit']:
  if a['kind']=='pilot_layer_exit':
   for lid in a['layers']:requests[lid].append(a['at'])
 rows=read(H/(ref+'_LAYER_FIRST_ELIGIBLE_H2.json'));rr={r['layer']:r for r in rows};first={};decfirst={};seen=Counter();eligible_n=0;unknown_n=0
 with (H/(ref+'_ALL_HELD_RS_EMA_CONTEXT.jsonl')).open() as inp:
  for line in inp:
   z=json.loads(line);lid=z['layer'];d=dby[z['at']];assert any(x['id']==lid for x in d['layers']);assert layers[lid]['sid']==z['sid'];q=provider.at(z['sid'],z['at']);b=z['context'];scalar_check(q,b,{'close':'causal_close','EMA20':'stock_EMA20','RS20':'RS20','anchor_day':'anchor_day','source_segment':'source_segment','stock_return20':'stock_return20','industry_return20':'industry_return20','market_return20':'HS300_price_index_return20'})
   known=q['ready_R'] and q['ready_P'];assert known==(b['status']=='KNOWN');di=int(np.datetime64(z['at'][:10],'D').astype('int64'));sf=SF[z['sid']];iv=at_exact(sf,np.array([di]),'i_target')[0];it=None if not np.isfinite(iv) else bool(iv);assert it==b['stock_I_target']
   earliest=min(requests[lid],default=None);assert earliest==rr[lid]['first_original_specific_request'];role=layers[lid]['kind']=='add';assert role==(z['role']=='mobile')
   priority='ORIGINAL_LAYER_REQUEST_ALREADY_OR_SAME_CLOSE' if earliest and z['at']>=earliest else 'ORIGINAL_ACT_OFF' if not d['on'] else 'ORIGINAL_I_OFF' if it is False else 'UNKNOWN_CURRENT_INPUT' if it is None or not known else 'ORIGINAL_ACT_I_ON_LAYER_NOT_PENDING'
   assert priority==z['original_priority_status'];weak=bool(q['RS20']<=0 and q['close']<q['EMA20']) if known else None;assert weak==b['jointweak'];eligible=bool(role and priority=='ORIGINAL_ACT_I_ON_LAYER_NOT_PENDING' and weak is True);assert eligible==z['H2_condition_eligible_on_original_path'];assert role==z['H2_role_eligible_mobile']
   if eligible:
    first.setdefault(lid,z['at'])
    if z['at'][:7]=='2022-12':decfirst.setdefault(lid,z['at'])
   eligible_n+=eligible;unknown_n+=not known;seen[lid]+=1;C['held_contexts']+=1
 for r in rows:
  for name,truth in [('global_first_eligible_H2',first),('Dec_first_eligible_H2',decfirst)]:
   assert (None if r[name] is None else r[name]['at'])==truth.get(r['layer']);C['first_event_fields']+=1
 assert sum(seen.values())==sum(len(d['layers']) for d in daily)
 heldsummary[ref]=dict(held_rows=sum(seen.values()),eligible_held_rows=eligible_n,unknown=unknown_n,global_eligible_layers=len(first),Dec_eligible_layers=len(decfirst),core_events=sum(layers[lid]['kind']!='add' for lid in first))
 print('INDEPENDENT_HELD_DONE',ref,heldsummary[ref],flush=True)
result=dict(status='PASS_FULL_RELATIVE_CONTEXT_AND_ORIGINAL_PATH_DOMAIN',source_sha256={str(P/'prepare_relative_context.py'):sha(P/'prepare_relative_context.py'),str(P/'context_provider.py'):sha(P/'context_provider.py'),str(P/'relative_context/MANIFEST.json'):sha(P/'relative_context/MANIFEST.json'),str(Path(__file__)):sha(__file__)},checks=dict(C),held=heldsummary,market_domain=dict(rows=len(market),all_close_finite_positive=True),seconds=time.monotonic()-start,limits=['Full retained relative arrays and all original 3436/122/57213 cross-checked; prior all-source EMA audit reused, not recomputed.','Original-path first hits describe coverage, not candidate savings or preservation of later original layers.','Frozen current industry snapshot is not point-in-time classification.','Preparation relies on immutable HS300 positive-close and eligible stock-facts contract; current all input rows satisfy required domain.'])
(O/'RELATIVE_CONTEXT_FULL_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
