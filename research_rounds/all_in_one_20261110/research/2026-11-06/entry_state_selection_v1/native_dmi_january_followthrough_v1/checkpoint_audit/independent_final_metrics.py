"""Read-only independent final analysis arithmetic and case audit."""
import sys,csv,json
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import independent_postcheck as q
A=q.O/'analysis/final_both'
def table(n,p=A):return list(csv.DictReader(open(p/(n+'.csv'))))
def add(v):return sum((D(x) for x in v),D(0))
def main():
 summary=q.j(A/'SUMMARY.json')
 for p,h in summary['sources'].items():assert q.sha(p)==h
 out={'passed':False,'economic_runs':0,'annual_rows':0,'cases':{},'supplement':{}}
 annual=table('ANNUAL_NAV_FEES');exportlayers=table('ALL_LAYERS');exportrounds=table('ALL_ROUNDS')
 supp=q.j(A/'treatment_period_supplement/SUMMARY.json');out['supplement_seal']=q.seal(A/'treatment_period_supplement','OUTPUT_SHA256.json')
 for p,h in supp['sources'].items():assert q.sha(p)==h
 baseds={r['at'][:10]:r for r in q.rows(q.BASE/'pair/daily.jsonl.gz') if r['account']=='PVR'}
 for label,path in [('PVR_ORIGINAL',q.BASE),('DMI_FROM_2022JAN',q.O/'2022Jan_DMI'),('DMI_FROM_2026JAN',q.O/'2026Jan_DMI')]:
  native={r['at'][:10]:r for r in q.rows(path/'pair/daily.jsonl.gz') if r['account']=='PVR'}
  ds=dict({d:r for d,r in baseds.items() if d<'2026-01-01'},**native) if label=='DMI_FROM_2026JAN' else native
  assert sorted(ds)==sorted(baseds)
  a=q.gz(path/'pair/PVR.json.gz');previous=D(1200000);peak=previous;worst=D(0)
  for year in sorted({d[:4] for d in ds}):
   days=sorted(d for d in ds if d.startswith(year));y=next(x for x in annual if x['account']==label and x['year']==year);yp=previous;yd=D(0)
   for day in days:
    v=D(ds[day]['nav']);yp=max(yp,v);yd=min(yd,v/yp-1);peak=max(peak,v);worst=min(worst,v/peak-1)
   assert D(y['start_nav'])==previous and D(y['end_nav'])==D(ds[days[-1]]['nav'])
   assert abs(float(yd)-float(y['max_drawdown_fraction']))<1e-12 and abs(float(D(y['end_nav'])/previous-1)-float(y['return_fraction']))<1e-12
   assert add(t['fees_cny'] for t in a['trades'] if t['at'].startswith(year))==D(y['fees'])
   previous=D(y['end_nav']);out['annual_rows']+=1
  assert abs(float(worst)-summary['full_accounts'][label]['max_drawdown_fraction'])<1e-12
  final=ds['2026-05-15'];vals={x['sid']:D(x['mark']) for x in table('FINAL_AND_JANUARY_VALUATION') if x['account']==label and x['cutoff']=='2026-05-15'}
  lm={l['id']:l for l in a['layers']};cost={t['layer']:D(t['gross_cny'])+D(t['fees_cny']) for t in a['trades'] if t['side']=='buy'}
  el={int(l['id']):l for l in exportlayers if l['account']==label};rr=[r for r in exportrounds if r['account']==label];firstids={int(r['initial_layer']) for r in rr}
  assert len(el)==len(lm)
  for k,l in lm.items():
   pnl=D(l['cash'])+D(l['dividend'])+D(l['qty'])*vals.get(l['sid'],D(0))
   assert abs(pnl-D(el[k]['pnl']))<q.EPS and D(el[k]['buy_cost'])==cost[k]
   assert (el[k]['initial_layer']=='True')==(k in firstids)
  early=sorted(d for d in ds if d>='2024-09-24')[:6];assert early[-1]=='2024-10-08'
  held=set().union(*(set(ds[d]['positions']) for d in early));ts=[t for t in a['trades'] if early[0]<=t['at'][:10]<=early[-1] and t['side']=='buy']
  c=dict(held_stocks=len(held),buy_fills=len(ts),new_rounds=sum(t['layer'] in firstids for t in ts),held_ADD_fills=sum(t['layer'] not in firstids and t['kind']=='add' for t in ts))
  ex=[x for x in table('2024_0924_ACTUAL_EARLY_PARTICIPATION') if x['account']==label]
  assert len(held)==sum(x['participated']=='True' for x in ex)
  assert c['buy_fills']==sum(int(x['early_BUY_fills']) for x in ex) and c['new_rounds']==sum(int(x['early_NEW_rounds']) for x in ex) and c['held_ADD_fills']==sum(int(x['early_ADD_fills']) for x in ex)
  out['cases'][label]=c
  for year in (['2022','2026'] if label=='PVR_ORIGINAL' else ['2022' if '2022' in label else '2026']):
   sr=supp['stats'][label+'_'+year];new=[r for r in rr if r['opened'][:10]>=year+'-01-01'];cl=[r for r in new if r['closed']];f=[el[int(r['initial_layer'])] for r in new];fc=[x for x in f if x['closed']]
   assert len(new)==sr['new_rounds'] and len(cl)==sr['closed_rounds']['n'] and sum(D(r['pnl'])>0 for r in cl)==sr['closed_rounds']['wins']
   assert abs(add(r['pnl'] for r in cl)-D(sr['closed_rounds']['net_pnl']))<q.EPS
   assert len(fc)==sr['closed_first_BUY_layers']['n'] and sum(D(x['pnl'])>0 for x in fc)==sr['closed_first_BUY_layers']['wins']
   assert abs(add(x['pnl'] for x in fc)-D(sr['closed_first_BUY_layers']['net_pnl']))<q.EPS
   tails=[r for r in cl if D(r['pnl'])/D(r['buy_cost'])>=D('.30')]
   assert len(tails)==sr['closed_rounds']['fee_net_30pct_tails']
   out['supplement'][label+'_'+year]={'new':len(new),'closed':len(cl),'wins':sr['closed_rounds']['wins'],'first_closed':len(fc),'first_wins':sr['closed_first_BUY_layers']['wins'],'tails':len(tails),'open':len(new)-len(cl)}
 out['passed']=True
 print(json.dumps(out,indent=2))
 if len(sys.argv)>1:
  p=Path(sys.argv[1]);assert not p.exists();p.write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
