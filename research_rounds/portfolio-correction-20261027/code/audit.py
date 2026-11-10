from study import *
from collections import Counter
import gzip
COHORT='S0'
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def check_contract(aid,obj,ds,facts,records):
 intents={};rotations={};ctx={};pairs={};checks=Counter();h=dict(np.load(Path(read(O/'input.json')['snapshot'])/'h1.npz'));dates=pd.DatetimeIndex(h['dates']);cols={str(s):i for i,s in enumerate(h['symbols'])}
 for r in obj['audit_log']:
  k=r['kind']
  if k=='entry_contract':intents[r['order_id']]=r;assert D(r['budget'])<=D('.15')*D(r['nav'])+D('.01');checks['budget']+=1
  elif k=='rotation_started':
   z=r['rotation'];T=pd.Timestamp(z['signal_at'][:10]);new,old=z['candidate'],z['victim'];assert bool(facts[new].loc[T,'i_buy']) and bool(facts[new].loc[T,'i_target']);assert z['held_observations']>=10
   for sid,key in [(new,'candidate_score'),(old,'victim_score')]:assert float(np.round(h['score'][dates.get_loc(T),cols[sid]],12))==z[key]
   assert gap_ok(z['candidate_score'],z['victim_score']);assert T.date().isoformat() in WEEKS and T.date().isoformat() not in FIRST
   if z['strategy']=='COR':assert bool(SIGNALS[new].loc[T,'new_ok']) and bool(SIGNALS[old].loc[T,'weak'])
   rotations[z['id']]=z;checks['rotation_evidence_buffer_age_and_week']+=1
  elif k=='same_day_rotation_contract':ctx[r['rotation_id']]=r;z=rotations[r['rotation_id']];assert D(r['support'])==D(str(facts[z['candidate']].loc[pd.Timestamp(z['signal_at'][:10]),'i_floor']))
  elif k=='rotation_buy_reserved':
   z=r['rotation'];assert z['id'] in rotations and z['sold_at']==r['at'];pairs[r['order_id']]=z;checks['fund_after_full_sale']+=1
  elif k=='fill' and r['receipt']['side']=='buy':
   f=r['receipt'];z=intents[r['order_id']];T=pd.Timestamp(z['decision_at']);S=pd.Timestamp(f['at']);assert T.date()<S.date();sid=f['security_id'];ff=facts[sid];ix=ff.index.searchsorted(pd.Timestamp(S.date()),side='right')-1;factor=D(str(ff.iloc[ix].factor));assert D(r['raw_open'])>D(z['floor_signal'])/factor
   if r['order_id'] in pairs:
    p=pairs[r['order_id']];assert pd.Timestamp(p['sold_at'])<S and S.second==1 and str(S.date())<=p['buy_deadline'];assert z['floor_signal']==ctx[p['id']]['support'];assert any(g['security_id']==p['victim'] and g['side']=='sell' and g['at']==p['sold_at'] for g in obj['fills']);checks['pair_fill']+=1
   else:assert bool(ff.loc[pd.Timestamp(T.date()),'i_buy']);checks['original_buy']+=1
 return dict(passed=True,checks=dict(checks))

def audit(cohort,stage):
 global COHORT,FIRST,WEEKS,SIGNALS
 import study
 COHORT=cohort;study.setup(cohort);FIRST=study.FIRST;WEEKS=study.WEEKS;SIGNALS=study.SIGNALS;root=O/cohort;A.CORE=PRIOR/'input';A.PREP=Path(read(O/'input.json')['snapshot']);A.HERE=root;A.check_contract=check_contract;A.main('short' if stage=='short' else 'full')
FIELDS=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
def admission():
 assert read(O/'tests.json')['passed'];assert read(O/'graph-review.json')['reviewed'];assert read(O/'signal-validation.json')['passed']
 ref={(r['account'],r['at']):r for r in rows(PRIOR/'RS/accounts-v2/daily.jsonl.gz')};n=0
 for cohort in STARTS:
  assert read(O/cohort/'technical/short-analysis/accounting.json')['passed'];ds=rows(O/cohort/'technical/short-v2/daily.jsonl.gz')
  if cohort=='S0':
   for r in ds:
    if not r['account'].startswith('ACT0__'):continue
    old=ref[r['account'].replace('ACT0__','I__'),r['at']]
    for k in FIELDS:assert r[k]==old[k],(cohort,r['at'],k)
    n+=1
  # Same-seed initial window portfolios must be identical across mechanisms.
  dates=sorted({r['at'] for r in ds})[:5];look={(r['account'],r['at']):r for r in ds}
  for r in ds:
   if r['at'] not in dates:continue
   v=r['account'][:3]
   if v not in ['BUF','COR']:continue
   b=look['ACT'+r['account'][3:],r['at']]
   for k in FIELDS:assert r[k]==b[k],(cohort,r['account'],r['at'],k)
 save(O/'admission.json',{'passed':True,'short_paths':63,'old_control_daily_rows':n,'same_seed_initial_windows_exact':True})
if __name__=='__main__':admission() if sys.argv[1]=='admission' else audit(sys.argv[1],sys.argv[2])
