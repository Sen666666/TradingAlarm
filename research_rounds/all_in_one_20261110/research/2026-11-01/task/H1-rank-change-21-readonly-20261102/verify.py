"""Independent saved-table checks; no runner or new outcome labels."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
def read(n):return json.loads((O/n).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 rows=read('ALL_INDUSTRY_DAYS.json');prior=read('RANKS_BEFORE_LABELS.json');ready=read('READINESS_FIRST.json');assert sha(O/'RANKS_BEFORE_LABELS.json')==ready['rank_before_labels_sha256'];assert len(rows)==3780==len(prior)
 for p,h in read('READ_INPUTS.json').items():assert sha(p)==h,p
 assert not any('g-s-C-R0-' in p for p in read('READ_INPUTS.json'))
 hp=next(p for p in read('READ_INPUTS.json') if p.endswith('/h1.npz'));z=np.load(hp,allow_pickle=False);sectors=sorted(str(s) for s in z['symbols'] if str(s).startswith('URFI'));columns=[list(map(str,z['symbols'])).index(s) for s in sectors];scores=z['score'][:,columns];price=z['close'][:,columns];dates=pd.DatetimeIndex(z['dates']);cuts=[]
 for case,rr in [('2022Jan',[r for r in prior if r['case']=='2022Jan']),('2025Jul',[r for r in prior if r['case']=='2025Jul'])]:
  days=sorted({r['day'] for r in rr})
  for day in [days[0],days[len(days)//2],days[-1]]:
   t=int(dates.get_indexer([pd.Timestamp(day)])[0]);p=scores[:t+1].copy();pc=price[:t+1].copy()
   order=sorted(range(90),key=lambda j:(-round(float(p[t,j]),12),sectors[j]));prev=sorted(range(90),key=lambda j:(-round(float(p[t-21,j]),12),sectors[j]));a={j:k+1 for k,j in enumerate(order)};b={j:k+1 for k,j in enumerate(prev)}
   for r in rr:
    if r['day']!=day:continue
    j=sectors.index(r['sector']);assert r['H1_rank90']==a[j] and r['prior21_rank90']==b[j] and r['rank_improvement21']==b[j]-a[j]
    assert abs(r['industry_absolute_price_change21_pct']-(pc[t,j]/pc[t-21,j]-1)*100)<1e-10
   cuts.append(dict(case=case,day=day,physical_prefix_rows=t+1,industries=90,price_and_ranks_exact=True))
 stock=read('ALL_FRESH_Q_STOCK_EVENTS.json');assert len(stock)==4410 and len({(r['case'],r['day'],r['sid'],r['receipt']) for r in stock})==4410
 assert all(type(r['C_Q']) is int and r['C_Q']>=0 for r in stock if r['C_requested'])
 assert all(r['C_Q'] is None for r in stock if not r['C_requested'])
 for r in rows:
  assert r['H1_nref']==90 and r['industry_future21'] is None and r['industry_future63'] is None
  for family,col in [('M1','fresh_Q_pass'),('M2','C_requested_count')]:
   for h in ['21','63']:
    assert r[f'{family}_{h}_label_n']+r[f'{family}_{h}_label_missing_n']==r[col]
    if not r[f'{family}_{h}_label_n']:assert r[f'{family}_{h}_return'] is None
 df=pd.DataFrame(rows);comp=read('MATCHED_DATE_PROXY_SUMMARY.json')
 for c in comp:
  family=c['family'];h=c['horizon'];r=df[(df.case==c['case'])&(df[f'{family}_{h}_label_n']>0)]
  u=r.groupby(['day',family+'_rank_group'])[f'{family}_{h}_return'].mean().unstack();u=u[['A_promoted','B_promoted']].dropna();assert len(u)==c['common_days'];assert abs((u.B_promoted-u.A_promoted).mean()-c['return_difference'])<1e-10
 output=dict(passed=True,industry_days=3780,full90_reference=True,unique_fresh_Q_events=4410,stock_label_missing_is_not_zero=True,all_industry_future_labels_remain_unknown=True,physical_prefix_score_price_tests=cuts,matched_date_statistics_independently_groupby_verified=len(comp),ranking_inputs='original past/current H1 ranks only; original-account endpoint contribution is hindsight annotation, never a rank input',account_events=0,new_outcome_labels=0,R0_directories_read=0,original_input_hashes_unchanged=len(read('READ_INPUTS.json')))
 (O/'VERIFICATION.json').write_text(json.dumps(output,indent=2)+'\n')
 print('VERIFIED',output['industry_days'],len(cuts),len(comp))
if __name__=='__main__':main()
