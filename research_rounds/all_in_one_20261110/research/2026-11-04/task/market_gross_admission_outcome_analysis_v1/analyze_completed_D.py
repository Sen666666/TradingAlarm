"""Closed D book only, existing saved reader; archived B reports stay immutable."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import argparse,csv,gzip,hashlib,importlib.util,inspect,json
O=Path(__file__).resolve().parent;T=O.parent;Z=D(0);EPS=D('.000001')
HP=T/'capacity_cost_guard_analysis_v1/analyze_completed_v1.py';sp=importlib.util.spec_from_file_location('original_saved_reporting_only',HP);H=importlib.util.module_from_spec(sp);sp.loader.exec_module(H)
n=H.n;day=H.day;read=H.read;sha=H.sha;save=H.save
SOURCE=inspect.getsource(H.A.account)
DERIVED=SOURCE.replace('def account(win,ref,root):','def account(win,ref,root,expected_days):').replace("root/'pair/B.json.gz'","root/'pair/D_GROSS10.json.gz'").replace('len(ds)==len(checks)==242','len(ds)==len(checks)==expected_days')
assert DERIVED.replace('def account(win,ref,root,expected_days):','def account(win,ref,root):').replace("root/'pair/D_GROSS10.json.gz'","root/'pair/B.json.gz'").replace('len(ds)==len(checks)==expected_days','len(ds)==len(checks)==242')==SOURCE
env=dict(H.A.__dict__);exec(compile(DERIVED,str(O/'REUSED_READER_PATH_AND_DAY_PARAMETERS.py.txt'),'exec'),env);account=env['account']
def csvout(p,rs):
 if rs:
  with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def layer_groups_existing_boundary_method(a,spells):
 # Same boundary cash/dividend/actualqty/rawmark contract as audited
 # ma63_down_replenishment_v1/analyze_saved_spells_v3.py; no cost basis.
 by=a['byday'];layers={x['layer']:x for x in a['layers']};final={x['id']:x for x in a['book']['layers']};bounds={};reports=[];allrows=[]
 def boundary(d):
  if d in bounds:return bounds[d]
  live={x['id']:x for x in by[d]['layers']} if d else {};w={}
  for lid,l in layers.items():
   if d is None or day(l['opened'])>d:v=Z
   elif lid in live:
    x=live[lid];v=n(x['cash'])+n(x['dividend'])+D(x['qty'])*H.A.price(l['sid'],d)
   else:
    x=final[lid];assert x['qty']==0 and x['closed'] and day(x['closed'])<=d;v=n(x['cash'])+n(x['dividend'])
   w[lid]=v
  assert abs(sum(w.values(),Z)-(n(by[d]['nav'])-D(1000000) if d else Z))<=EPS
  bounds[d]=(w,live);return w,live
 def group(rr):return dict(layers=len(rr),wealth=sum((r['period_wealth'] for r in rr),Z),positive_wealth=sum((r['period_wealth'] for r in rr if r['period_wealth']>0),Z),negative_wealth=sum((r['period_wealth'] for r in rr if r['period_wealth']<0),Z),zero_layers=sum(r['period_wealth']==0 for r in rr))
 for s in spells:
  lo,hi=s['days'][0],s['days'][-1];w0,l0=boundary(s['previous_close']);w1,l1=boundary(hi);new={t['layer'] for t in a['book']['trades'] if t['side']=='buy' and lo<=day(t['at'])<=hi};assert not(new&set(l0));rr=[]
  for lid in sorted(set(l0)|new):
   l=layers[lid];rr.append(dict(spell_id=s['spell_id'],layer=lid,sid=l['sid'],role=l['role'],opened=l['opened'],group='new_actual_fill_in_spell' if lid in new else 'carry_at_previous_CLOSE',boundary_wealth=w0[lid],end_wealth=w1[lid],period_wealth=w1[lid]-w0[lid],qty_at_boundary=l0.get(lid,{}).get('qty',0),qty_at_end=l1.get(lid,{}).get('qty',0)))
  assert all(w0[i]==w1[i] for i in set(layers)-set(l0)-new);actual=n(by[hi]['nav'])-(n(by[s['previous_close']]['nav']) if s['previous_close'] else D(1000000));residual=actual-sum((r['period_wealth'] for r in rr),Z);assert abs(residual)<=EPS
  reports.append(dict(spell_id=s['spell_id'],start=lo,end=hi,previous_close=s['previous_close'],native_period_NAV_change=actual,rounding_residual_not_allocated=residual,old=group([r for r in rr if r['group']=='carry_at_previous_CLOSE']),new=group([r for r in rr if r['group']=='new_actual_fill_in_spell'])));allrows+=rr
 return reports,allrows
def run(win):
 count=726 if win=='long' else 242;root=T/'market_gross_admission_native_v1'/f'full-{win}-v1';out=O/f'full_{win}_v1'
 # Do not read any candidate book until all closed-publication markers exist.
 for file in ('DONE.json','TIMING.json','WINDOW_RESULT.json'):assert (root/file).is_file(),('NOT_PUBLISHED',file)
 done=read(root/'DONE.json');tim=read(root/'TIMING.json');result=read(root/'WINDOW_RESULT.json');assert done['completed'] and tim['completed'] and result['passed'] and result['source_post_exact'] and result['days']==count and result['executed_arms']==['D_GROSS10']
 assert not(out/'COMPLETED.json').exists(),'reuse saved output; no duplicate analysis';out.mkdir(parents=True,exist_ok=True)
 binding=read(T/'market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json')[win]
 for p,h in binding['source_sha256'].items():assert sha(p)==h
 H.A.O=out;a=account(win,'D_GROSS10',root,count);dr=H.flow_daily(a);cal=read(T/'market_gross_admission_native_v1/prepared'/win/'EXPECTED_CLOSE_CALENDAR.json');expected=[s[:10] for s in cal['closes'] if cal['full_start']<=s[:10]<=cal['full_end']];assert list(a['byday'])==expected
 assert n(a['book']['ending_NAV'])==n(result['ending_NAV']);save(out/'REUSED_READER_PATH_AND_DAY_PARAMETERS.py.txt',DERIVED)
 bp=T/'capacity_cost_guard_analysis_v1'/f'full_{win}_v1';bs=read(bp/'SUMMARY.json')['B'];bdr=[{k:n(v) if isinstance(v,str) and k!='day' else v for k,v in r.items()} for r in read(bp/'B_DAILY_WEALTH.json')];bm={r['day']:r for r in bdr};assert list(bm)==expected
 summary=dict(D_GROSS10=dict(account_metrics=a['metrics'],whole_calendar=H.period(dr)),ARCHIVED_B=bs,source_control='immutable ARCHIVED_B_CONTROL_BINDING; preexisting B result xref only',financial_review='PENDING',derived_review='PENDING');save(out/'D_DAILY_WEALTH.json',dr)
 periods=[]
 for grain in ('year','quarter','month'):
  key=lambda d:d[:4] if grain=='year' else d[:7] if grain=='month' else d[:4]+'Q'+str((int(d[5:7])-1)//3+1)
  for label in sorted({key(r['day']) for r in dr}):
   periods.append(dict(grain=grain,period=label,D_GROSS10=H.period([r for r in dr if key(r['day'])==label]),ARCHIVED_B=H.period([r for r in bdr if key(r['day'])==label])))
 frozen=read(O/'ALL_PREDECLARED_MARKET_STATE_SEGMENTS.json')['windows'][win];dm={r['day']:r for r in dr};segments=[]
 for s in frozen['clocks']['OPEN']['segments']:segments.append(dict(definition=s,D_GROSS10=H.period([dm[d] for d in s['days']]),ARCHIVED_B=H.period([bm[d] for d in s['days']])))
 phase={};semis={x['sid'] for x in read(T/'capacity_cost_guard_analysis_v1/STRICT_SEMICONDUCTOR_MEMBERS.json')['members']}
 for p in read(T/'capacity_cost_guard_analysis_v1/FIXED_PHASES.json')['diagnostic_phases']:
  rr=[r for r in dr if p['lo']<=r['day']<=p['hi']]
  if rr:phase[p['name']]=dict(definition=p,own_NAV_account_period=H.period(rr),D_actual_stock_wealth=H.interval_stocks(a,p['lo'],p['hi'],semis if p.get('sector_id')=='URFI881121' else None),ARCHIVED_B_phase=read(bp/'FIXED_PHASE_WEALTH.json')['B'].get(p['name']))
 if win=='long':
  phase['post924_old_new_D']=H.after924(a);oldspells=read(O/'ORIGINAL_NINE_AUDITED_2022_2023_DOWN_BOUNDARIES.json')['spells'];spells,layerrows=layer_groups_existing_boundary_method(a,oldspells);save(out/'ORIGINAL_NINE_DOWN_D_OLD_NEW.json',spells);save(out/'ORIGINAL_NINE_DOWN_D_LAYER_ROWS.json',layerrows)
 states={d:x['state'] for x in frozen['clocks']['OPEN']['segments'] for d in x['days']};cross=[]
 for state in ['DOWN','NOT_DOWN','UNKNOWN']:
  for on in [False,True]:
   rr=[r for r in dr if states[r['day']]==state and r['ACT_at_OPEN']==on];cross.append(dict(market_state_at_OPEN=state,own_ACT_at_OPEN=on,days=len(rr),actual_buy_cash=sum((n(r['actual_buy_cash']) for r in rr),Z),actual_fees=sum((n(r['actual_fees']) for r in rr),Z),buy_fills=sum(r['buy_fills'] for r in rr),diagnostic_selected_day_wealth_sum_not_account_return=sum((n(r['wealth_change']) for r in rr),Z)))
 summary['market_ACT_cross']=cross;summary['ACT_rule']='unchanged original ACT20/BREAK63; own original risk_checkpoint events in account_metrics; archived B events diagnostic only'
 base_stock={r['sid']:n(r['net']) for r in read(bp/'analysis'/win/'B/STOCKS.json')};groups={}
 for label,ids in [('common',set(base_stock)&set(a['stock'])),('D_newly_funded',set(a['stock'])-set(base_stock)),('B_only_funded',set(base_stock)-set(a['stock']))]:
  rr=[dict(sid=s,name=H.A.META[s]['name'],archived_B=base_stock.get(s,Z),D=a['stock'].get(s,Z),delta=a['stock'].get(s,Z)-base_stock.get(s,Z)) for s in ids];groups[label]=dict(stocks=len(rr),delta=sum((r['delta'] for r in rr),Z),members=sorted(rr,key=lambda r:-r['delta']))
 H.expect(sum((r['delta'] for r in groups.values()),Z),n(a['book']['ending_NAV'])-D(1000000)*(1+n(bs['account_metrics']['return_pct'])/100),'actual_stock_path_difference')
 save(out/'SUMMARY.json',summary);save(out/'ALL_PERIODS_VS_ARCHIVED_B.json',periods);save(out/'ALL_PREDECLARED_OPEN_SEGMENTS_VS_ARCHIVED_B.json',segments);save(out/'FIXED_PHASE_WEALTH.json',phase);save(out/'ACT_MARKET_CROSS.json',cross);save(out/'ACTUAL_FUNDED_STOCK_PATH_COMPARISON.json',groups)
 flat=[dict(grain=r['grain'],period=r['period'],D_wealth=r['D_GROSS10']['wealth_change'],B_wealth=r['ARCHIVED_B']['wealth_change'],D_return_pct=r['D_GROSS10']['return_pct'],B_return_pct=r['ARCHIVED_B']['return_pct'],D_own_end_NAV=r['D_GROSS10']['end_NAV'],B_own_end_NAV=r['ARCHIVED_B']['end_NAV'],D_mean_lag_exposure_pct=r['D_GROSS10']['mean_lag_exposure_pct'],B_mean_lag_exposure_pct=r['ARCHIVED_B']['mean_lag_exposure_pct'],D_fees=r['D_GROSS10']['actual_fees'],B_fees=r['ARCHIVED_B']['actual_fees']) for r in periods]
 csvout(out/'ALL_MONTHS.csv',[r for r in flat if r['grain']=='month']);csvout(out/'ALL_YEARS.csv',[r for r in flat if r['grain']=='year'])
 sources={str(root/f):sha(root/f) for f in ['DONE.json','TIMING.json','WINDOW_RESULT.json','pair/D_GROSS10.json.gz','pair/daily.jsonl.gz','pair/balances.jsonl.gz']};sources.update({str(bp/f):sha(bp/f) for f in ['SUMMARY.json','B_DAILY_WEALTH.json','FIXED_PHASE_WEALTH.json',f'analysis/{win}/B/STOCKS.json']})
 save(out/'SOURCE_BINDING.json',dict(source_sha256=sources,archived_B=binding,new_accounts=0,new_B_views_or_books=0,original_reader_source=str(H.P),original_reader_sha256=sha(H.P),only_reader_changes=['book pathname B to D_GROSS10','expected day count parameter'],helpers_sha256=sha(HP),analysis_sha256=sha(__file__),derived_independent_review='PENDING'))
 save(out/'COMPLETED.json',dict(passed=True,days=count,new_accounts=0,window=win,financial_review='PENDING',derived_review='PENDING'))
 print('READ_D_CLOSED',win,a['metrics']['return_pct'],a['metrics']['global_DD']['percent'],flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['long','strong'],required=True);args=ap.parse_args();run(args.window)
