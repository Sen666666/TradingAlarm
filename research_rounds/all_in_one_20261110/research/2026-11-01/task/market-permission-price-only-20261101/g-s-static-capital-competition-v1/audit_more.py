"""Additional static denominator/evidence tables; no account/model imports."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import json,hashlib
import pandas as pd

O=Path(__file__).resolve().parent
N=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/g-s-historical-native-nextsession-20261101')
S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):S[str(p)]=sha(p);return json.loads(Path(p).read_text())
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def finite(x):return x is not None and pd.notna(x)

def main():
 summary=read(O/'SUMMARY.json');pair_evidence={};source_boundaries=[];next_actions=[]
 for k,day in [('2022','2022-01-06'),('2025_26','2025-07-03')]:
  cl=read(N/'run'/k/'close'/f'{day}-CLOSE.json');meta=read(N/'inputs'/k/'metadata.json');a=cl['account']
  hp=N/'inputs'/k/'extensions/h1.parquet';pv=N/'inputs'/k/'extensions/pvr.parquet';S[str(hp)]=sha(hp);S[str(pv)]=sha(pv)
  h=pd.read_parquet(hp).set_index('sid').score.to_dict();p=pd.read_parquet(pv).set_index('sid').score.to_dict();ids=list(cl['last_stock_state'])
  full=sorted(ids,key=lambda s:(-round(h[s],12) if finite(h.get(s)) else 1,s));ranks={s:i for i,s in enumerate(full)}
  mapping={x['sid']:x for x in cl['mapping'][-1]['stocks']};rows=[]
  for sid,st in cl['last_stock_state'].items():
   live=[z for z in a['layers'] if z['sid']==sid and z['qty']]
   rows.append(dict(sid=sid,name=meta[sid]['name'],sector=meta[sid]['sector'],original_stock_Q=mapping[sid]['stock_Q'],
    I_valid=st['i_valid'],new_intent_eligible=st['q'],core_event=st['core_event'],fresh_canonical=bool(st['receipt']),
    H1=h.get(sid) if finite(h.get(sid)) else None,H1_full_rank=ranks[sid],PVR=p.get(sid) if finite(p.get(sid)) else None,
    PVR_explicit=sid in p,live_mobile=sum(z['qty'] for z in live if z['kind']!='core'),live_core=sum(z['qty'] for z in live if z['kind']=='core'),
    actual_new_entry_barriers=mapping[sid]['barriers']))
  assert len(rows)==1709
  save(k+'-ALL1709_DENOMINATOR.json',rows)
  comp=read(O/(k+'-COMPETITION.json'));by={x['sid']:x for x in comp};s=summary['account_cases'][k]
  demands=[x['sid'] for x in s['A_demands']];funded=[x['sid'] for x in s['A_reductions']]
  strongest=[x for x in funded if all(by[x]['competition_rank']<by[n]['competition_rank'] for n in demands if n!=x)]
  weakest=[x for x in funded if all(by[x]['competition_rank']>by[n]['competition_rank'] for n in demands if n!=x)]
  pair_evidence[k]=dict(A_requested_out_stronger_than_every_A_new_demand=[dict(sid=x,name=by[x]['name'],rank=by[x]['competition_rank'],PVR=by[x]['PVR']) for x in strongest],
   A_requested_out_weaker_than_every_A_new_demand=[dict(sid=x,name=by[x]['name'],rank=by[x]['competition_rank'],PVR=by[x]['PVR']) for x in weakest],
   A_demand=[dict(sid=x,name=by[x]['name'],rank=by[x]['competition_rank'],PVR=by[x]['PVR']) for x in demands],
   relation_is_not_actual_one_to_one_funding_or_B_trade=True)
  nextday='2022-01-07' if k=='2022' else '2025-07-04'
  for x in comp:
   if not x['fresh_mobile']:continue
   rec=meta[x['sid']]['runtime_record'];bad=bool(rec.get('unavailable_from') and nextday>=rec['unavailable_from']) or any(a['end']<nextday<b['start'] for a,b in zip(rec.get('segments',[]),rec.get('segments',[])[1:]))
   source_boundaries.append(dict(key=k,sid=x['sid'],nextday=nextday,source_boundary_blocked=bad))
   ar=rec['adjustment']['actions'];aa=read(Path(ar['path']));assert sha(ar['path'])==ar['sha256']
   for e in aa['events']:
    if e['effective_date']==nextday:next_actions.append(dict(key=k,sid=x['sid'],**e,known_announcement_time='UNKNOWN',not_used_in_sort_or_close_proxy=True))
  paths=read(O/(k+'-POSTHOC_ALL_PRICE_PATHS.json'));pairs=read(O/(k+'-POSTHOC_HIGHER_NEWCOMER_PAIRS.json'))
  strict=[]
  for x in pairs:
   old=x['old_price_path'];new=x['new_price_path']
   if old['prior21']>0 and old['prior5']<0 and new['prior1']>0 and new['prior5']<=new['prior1'] and (x['old_beats_new_forward5'] or x['old_beats_new_forward21']):strict.append(x)
  save(k+'-POSTHOC_STRICT_ONE_DAY_COUNTEREXAMPLES.json',strict)
  pair_evidence[k]['strict_one_day_counterexamples']=len(strict)
  pair_evidence[k]['strict_first_by_existing_lexical_pair_order']=strict[:3]
  pair_evidence[k]['all_pair_metrics_are_dependent_price_comparisons_not_win_rates']=True
 for day,x in summary['extra_2026'].items():
  disp=read(O/(day+'-ALL1709_DISPOSITIONS.json'));meta=read(N/'inputs/2025_26/metadata.json')
  semi=[z for z in disp if meta[z['sid']]['sector']=='URFI881121'];chem=[z for z in disp if meta[z['sid']]['sector']=='URFI881172']
  pair_evidence[day]=dict(strict_semiconductor_identity_count=len(semi),strict_semiconductor_canonical=sum(z['canonical'] for z in semi),
   strict_semiconductor_stock_Q_pass=sum(z.get('stock_Q') is True for z in semi),
   strict_semiconductor_expansion_permission_blocked=sum(z.get('no_expansion_permission',False) for z in semi),
   chemicals_identity_count=len(chem),market_stage=x['strict_semiconductor']['market'],no_actual_GS_account_inventory=True)
 save('PAIR_EVIDENCE.json',pair_evidence);save('SOURCE_BOUNDARY_AND_NEXT_ACTION_CHECK.json',dict(source_boundaries=source_boundaries,next_actions=next_actions,
  source_boundaries_all_pass=not any(x['source_boundary_blocked'] for x in source_boundaries),
  capacity_counts_remain_close_price_conditional_not_next_open_execution=True))
 save('ADDITIONAL_SOURCE_SHA256.json',S)
 print(json.dumps({k:{a:b for a,b in v.items() if a!='strict_first_by_existing_lexical_pair_order'} for k,v in pair_evidence.items()},ensure_ascii=False,default=str,indent=2)[:6000])

if __name__=='__main__':main()
