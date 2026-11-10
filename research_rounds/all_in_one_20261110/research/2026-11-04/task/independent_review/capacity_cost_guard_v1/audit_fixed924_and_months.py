"""Read-only fixed period/cohort audit from native saved layer cash and snapshots."""
from pathlib import Path
from decimal import Decimal as D
import importlib.util,json,gzip,collections
O=Path(__file__).resolve().parent;A=Path('capacity_cost_guard_analysis_v1/full_long_v1');N=Path('capacity_cost_guard_v1/runs/long-v1')
s=importlib.util.spec_from_file_location('native_saved_reader',O/'audit_saved_native.py');R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
ph=R.read(A/'FIXED_PHASE_WEALTH.json');periods=R.read(A/'ALL_PERIODS.json');ds=R.rows(N/'pair/daily.jsonl.gz');out={}
for arm in ['B','G10','G20','G40','NR20']:
 b=R.book(N/'pair'/f'{arm}.json.gz');daily=[r for r in ds if r['account']==arm];byday={str(r['at'])[:10]:r for r in daily};end=daily[-1];boundary=byday['2024-10-08'];active={x['id']:x for x in boundary['layers']};groups=collections.defaultdict(lambda:dict(layers=0,wealth=D(0)))
 cash=collections.defaultdict(lambda:D(0))
 for t in b['trades']:
  if t['side']=='buy':cash[t['layer']]-=D(t['gross_cny'])+D(t['fees_cny'])
  else:
   for p in t['parts']:cash[p['layer']]+=D(p['net_cash'])
 for l in b['layers']:
  lid=l['id'];R.near(cash[lid],l['cash'],'native layer actualtrade cash');contrib=D(l['cash'])+D(l['dividend'])
  if l['qty']:contrib+=D(l['qty'])*R.mark(l['sid'],end['at'])
  if str(l['opened'])[:10]>'2024-10-08':group='new_fill_after_boundary';before=D(0)
  elif lid in active:
   group='actually_held_at_boundary';x=active[lid];before=D(x['cash'])+D(x['dividend'])+D(x['qty'])*R.mark(l['sid'],boundary['at'])
  else:group='already_closed_at_boundary';before=contrib
  groups[group]['layers']+=1;groups[group]['wealth']+=contrib-before
 actual=sum((g['wealth']for g in groups.values()),D(0));R.near(actual,D(end['nav'])-D(boundary['nav']),'post924 group wealth bridge')
 for g,v in groups.items():assert v['layers']==ph[arm]['post924_old_vs_new_layers']['groups'][g]['layers'];R.near(v['wealth'],ph[arm]['post924_old_vs_new_layers']['groups'][g]['wealth'],'analysis selectedcohort')
 monthly=[r for r in periods if r['arm']==arm and r['grain']=='month'];assert len(monthly)==36;prev=D(1000000)
 for month in sorted(monthly,key=lambda r:r['period']):
  rr=[r for r in daily if str(r['at']).startswith(month['period'])];wealth=D(rr[-1]['nav'])-prev;R.near(wealth,month['wealth_change'],'native36months NAV difference');R.near(prev,month['initial_own_NAV'],'monthlystart');prev=D(rr[-1]['nav'])
 R.near(sum((D(r['wealth_change'])for r in monthly),D(0)),D(end['nav'])-D(1000000),'36monthssum')
 six=ph[arm]['924_six_closes'];rr=[r for r in daily if six['start']<=str(r['at'])[:10]<=six['end']];assert len(rr)==6
 R.near(D(rr[-1]['nav'])-D(byday[six['previous_close']]['nav']),six['interval_wealth'],'sixclosingdatewealth')
 out[arm]=dict(post924_NAV_change=str(actual),post924_groups={k:{'layers':v['layers'],'wealth':str(v['wealth'])}for k,v in groups.items()},six_close_wealth=six['interval_wealth'],all36monthly_NAV_wealth_changes_exact=True)
x={'status':'PASS_FIXED924_WEALTH_COHORT_AND36MONTH_NATIVE_BRIDGES','boundary':'2024-10-08 CLOSE','end':'2024-12-31 CLOSE','arms':out,'scope':'Period wealth from actual layer cash+dividend+current inventory snapshots, not full lifecycle return confused with period return. Group counts are actual receipt layers; not episodes or lost-profit counterfactual.','source_sha256':R.SRC,'checker_sha256':R.sha(__file__)}
p=O/'FIXED924_AND_MONTHS_INDEPENDENT_AUDIT.json';p.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'status':x['status'],'arms':out,'path':str(p),'sha256':R.sha(p)}))
