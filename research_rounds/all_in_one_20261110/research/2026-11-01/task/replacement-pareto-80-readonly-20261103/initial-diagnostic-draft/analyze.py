"""Fixed 80-batch score relations only. No accounts, optimizer or price labels."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,hashlib,math,gc
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
A=W/'g-s-C-August-continuation-v1-20261102'
COV=O.parent/'pre-sell-quote-coverage-readonly-20261102'
DES=W/'replacement-aug18-design-v1-20261102'
USED={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);USED[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def finite(x):return x is not None and math.isfinite(float(x))

# Select only original mother IDs/Q, actual donor fills and their amounts.
# Existing outcome fields in the source are never referenced.
batches=[]
for b in read(COV/'BATCHES.json'):
 dd={}
 for t in b['source_fills']:
  v=dd.setdefault(t['security_id'],dict(qty=0,gross=Z,layers=set()))
  v['qty']+=t['shares'];v['gross']+=D(t['gross_cny']);v['layers'].update(p['layer'] for p in t['parts'])
 assert not (set(dd)&set(b['Q']))
 batches.append(dict(cell=b['cell'],day=b['original_plan_at'][:10],certificate=b['certificate'],Q=b['Q'],donors=dd))
assert len(batches)==80

def tables(root,keys,days):
 m=read(root/'MANIFEST.json');out={}
 for key in keys:
  rr=[]
  for group in ['files','extensions','month_extension','continuation_extension']:
   if key not in m.get(group,{}):continue
   ref=m[group][key];p=root/ref['path'];assert sha(p)==ref['sha256'];USED[str(p)]=ref['sha256']
   f=pd.read_parquet(p);rr.append(f[f.day.isin(days)])
  f=pd.concat(rr,ignore_index=True)
  if key in ['h1','pvr']:
   for _,g in f.groupby(['sid','day']):
    vv=g.score.tolist();assert all((pd.isna(v) and pd.isna(vv[0])) or v==vv[0] for v in vv),'conflicting original duplicate scores'
  assert not f.duplicated(['sid','day']).any(),'overlapping original input rows; do not silently choose'
  out[key]=f.set_index(['sid','day'])
 return m,out
days={b['day'] for b in batches}
m,cache=tables(A/'full-August',['pvr','h1','facts','cp'],days)
ids=set(m['fixed_ids']);sectors=set(m['sectors']);assert len(ids)==1709 and len(sectors)==90 and not ids&sectors
names=read(A/'full-August/metadata.json')

three=read(DES/'THREE_BATCHES.json')
jan=next(r for r in three if r['arm']=='2022-C10');janD={r['sid']:dict(qty=r['actual_qty'],gross=D(r['actual_gross']),layers={u['layer'] for u in r['units']}) for r in jan['rows'] if r['side']=='D' and r['actual_qty']}
janB=dict(cell='JAN_C10_SEPARATE',day='2022-01-12',certificate=jan['certificate'],Q={k:v for k,v in jan['original_Q'].items() if v},donors=janD)
jm,jcache=tables(W/'g-s-C-month-continuation-20261102/inputs/2022',['pvr','h1','facts','cp'],{'2022-01-12'})
assert set(jm['fixed_ids'])==ids and set(jm['sectors'])==sectors

requests={(s,b['day']) for b in batches+[janB] for s in set(b['Q'])|set(b['donors'])}
assert all(s in ids for s,_ in requests)
hp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
bind=read(W/'g-s-readonly-historical-loader-r2-20261101/input-v1/SOURCE_BINDINGS.json')
assert sha(hp)==bind[str(hp)];USED[str(hp)]=bind[str(hp)]
hz=np.load(hp,allow_pickle=False);hd={str(pd.Timestamp(t).date()):i for i,t in enumerate(hz['dates'])};hc={str(s):i for i,s in enumerate(hz['symbols'])}
history={key:{} for key in ['score','h','obs_count','nref']}
for key in history:
 arr=hz[key]
 for sid,day in requests:history[key][sid,day]=arr[hd[day],hc[sid]].item()
 del arr;gc.collect()

def value(table,sid,day,col):
 if (sid,day) not in table.index:return None
 x=table.loc[(sid,day),col]
 return float(x) if finite(x) else None

scores={}
for sid,day in sorted(requests):
 cc=jcache if day.startswith('2022') else cache
 pv=value(cc['pvr'],sid,day,'score');h1=value(cc['h1'],sid,day,'score')
 native=history['score'][sid,day]
 assert (h1 is None and not finite(native)) or (h1 is not None and h1==native),'H1 long cache differs from frozen native npz'
 hist={k:int(history[k][sid,day]) for k in ['h','obs_count','nref']}
 ready=5<=hist['h']<=252 and hist['obs_count']>=6 and hist['nref']>=20
 assert h1 is None or ready,'finite H1 with invalid original history'
 f=cc['facts'];cp=cc['cp'];fresh=None
 if (sid,day) in cp.index:
  receipt=cp.loc[(sid,day),'receipt'];fresh=receipt is not None and not (isinstance(receipt,float) and math.isnan(receipt))
 scores[sid,day]=dict(sid=sid,day=day,name=names.get(sid,{}).get('name'),PVR=pv,stock_H1=h1,
  H1_history=hist,H1_ready_native=ready,I_target=value(f,sid,day,'i_target'),old_fresh_descriptive_only=fresh,
  comparable=pv is not None and h1 is not None and ready)

def relation(old,new,rounded=False):
 if not old['comparable'] or not new['comparable']:return 'NA'
 op,oh,np_,nh=old['PVR'],old['stock_H1'],new['PVR'],new['stock_H1']
 if rounded:op,oh,np_,nh=map(lambda x:round(x,12),(op,oh,np_,nh))
 if op==np_ and oh==nh:return 'TIE'
 if np_>=op and nh>=oh:return 'NEW_DOMINATES'
 if op>=np_ and oh>=nh:return 'OLD_DOMINATES'
 return 'CROSS'

def compute(b):
 donors=[];pairs=[]
 for old,v in sorted(b['donors'].items()):
  oo=scores[old,b['day']];edges=[]
  for new in b['Q']:
   nn=scores[new,b['day']];cat=relation(oo,nn)
   p=dict(old=old,new=new,category=cat,hard_allowed=cat=='NEW_DOMINATES',weak_allowed=cat in ['NEW_DOMINATES','CROSS','TIE'],
    same_H1_h=oo['H1_history']['h']==nn['H1_history']['h'],raw_vs_round12_same=cat==relation(oo,nn,True))
   edges.append(p);pairs.append(p)
  donors.append(dict(sid=old,name=oo['name'],actual_qty=v['qty'],actual_gross=v['gross'],layers=sorted(v['layers']),score=oo,
   pairs=edges,has_hard_recipient=any(p['hard_allowed'] for p in edges),has_weak_recipient=any(p['weak_allowed'] for p in edges),
   hard_recipients=[p['new'] for p in edges if p['hard_allowed']],weak_recipients=[p['new'] for p in edges if p['weak_allowed']],
   unknown_recipients=[p['new'] for p in edges if p['category']=='NA']))
 return dict(cell=b['cell'],day=b['day'],certificate=b['certificate'],target_Q=b['Q'],recipient_scores={s:scores[s,b['day']] for s in b['Q']},donors=donors,pair_counts=dict(Counter(p['category'] for p in pairs)))
out=[compute(b) for b in batches];jout=compute(janB)

def summarize(rr):
 dd=[d for b in rr for d in b['donors']];pp=[p for d in dd for p in d['pairs']]
 total=sum((d['actual_gross'] for d in dd),Z)
 categories={}
 for cat in ['NEW_DOMINATES','OLD_DOMINATES','CROSS','TIE','NA']:
  matched=[d for d in dd if any(p['category']==cat for p in d['pairs'])]
  categories[cat]=dict(pair_count=sum(p['category']==cat for p in pp),batch_count=sum(any(p['category']==cat for d in b['donors'] for p in d['pairs']) for b in rr),
   donor_count=len(matched),donor_gross_exposure=sum((d['actual_gross'] for d in matched),Z),
   warning='gross counted once per donor within category; categories overlap and must not be added')
 gates={}
 for label,field in [('hard','has_hard_recipient'),('weak','has_weak_recipient')]:
  eligible=[d for d in dd if d[field]]
  gates[label]=dict(eligible_donors=len(eligible),total_donors=len(dd),eligible_donor_gross=sum((d['actual_gross'] for d in eligible),Z),
   blocked_or_unknown_donor_gross=total-sum((d['actual_gross'] for d in eligible),Z),
   batches_any_donor_eligible=sum(any(d[field] for d in b['donors']) for b in rr),
   batches_all_donors_eligible=sum(all(d[field] for d in b['donors']) for b in rr),
   batches_no_donors_eligible=sum(not any(d[field] for d in b['donors']) for b in rr),
   warning='each donor only needs one qualifying positive-Q recipient here; no quantity/cash/risk/flow matching or joint feasibility')
 return dict(batches=len(rr),donor_stocks=len(dd),pairs=len(pp),total_actual_source_gross=total,relations=categories,gates=gates,
  pairs_different_H1_h=sum(not p['same_H1_h'] for p in pp),raw_vs_round12_changed_pairs=sum(not p['raw_vs_round12_same'] for p in pp),
  donors_without_fresh=sum(d['score']['old_fresh_descriptive_only'] is False for d in dd),donors_with_unknown_fresh=sum(d['score']['old_fresh_descriptive_only'] is None for d in dd),
  unique_market_day_pairs=len({(b['day'],p['old'],p['new']) for b in rr for d in b['donors'] for p in d['pairs']}))
summary={c:summarize([b for b in out if c=='COMBINED' or b['cell']==c]) for c in ['C10','C20','COMBINED']}
save('BATCH_RELATIONS.json',out);save('SUMMARY.json',summary);save('JAN_SEPARATE.json',dict(batch=jout,summary=summarize([jout])))
save('SCORES_AND_HISTORY.json',list(scores.values()))

# Existing same-time independent extracts are exact numerical controls only.
checks=[]
for b in three:
 for r in b['rows']:
  s=scores.get((r['sid'],b['day']))
  if s is None:continue
  assert (not finite(r['PVR']) and s['PVR'] is None) or r['PVR']==s['PVR']
  assert (not finite(r['stock_H1']) and s['stock_H1'] is None) or r['stock_H1']==s['stock_H1']
  checks.append(dict(cell=b['arm'],day=b['day'],sid=r['sid'],same_scores=True))
save('EXISTING_CASE_SCORE_CHECKS.json',checks)
save('SOURCE_SHA256.json',USED)
save('CHECKS.json',dict(passed=True,financial_events=0,account_restores=0,optimizer_calls=0,new_indicator_calculations=0,new_price_labels=0,
 fixed_80_batches=True,Jan_separate=True,stock_reference=1709,industry_reference_separate=90,
 h1_long_cache_exactly_matches_native_npz=True,H1_finite_history_valid=True,full_precision_primary=True,NA_not_zero=True,
 amount_not_repeated_per_pair=True,no_old_fresh_requirement=True,existing_same_time_control_rows=len(checks)))
for cell,s in summary.items():print(cell,json.dumps({k:v for k,v in s.items() if k not in ['relations']},default=str),flush=True)
print('RELATIONS',json.dumps(summary['COMBINED']['relations'],default=str),flush=True)
print('JAN',json.dumps(summarize([jout]),default=str),flush=True)
