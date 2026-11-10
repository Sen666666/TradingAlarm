"""Saved-book analysis only. No account construction, strategy call or price forecast."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,hashlib,time,statistics
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
SM={r['symbol']:r for r in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())};frames={}
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def num(x):return D(str(x))
def day(x):return str(x)[:10]
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');tmp.replace(p)
def price(sid,d):
 if sid not in frames:frames[sid]=pd.read_parquet(SM[sid]['refs']['facts'],columns=['raw_close'])
 f=frames[sid];i=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert i>=0;return num(f.iloc[i].raw_close)
def drawdown(values):
 high=values[0][1];peakday=values[0][0];worst=Z;worstday=peakday;fromday=peakday
 for d,n in values:
  if n>high:high=n;peakday=d
  v=1-n/high
  if v>worst:worst=v;worstday=d;fromday=peakday
 return dict(percent=100*worst,day=worstday,preceding_peak_day=fromday)
def aggregate(ls):
 return dict(layers=len(ls),stocks=len({x['sid'] for x in ls}),buy_cash=sum((x['cost'] for x in ls),Z),closed_positive=sum((x['net'] for x in ls if not x['qty'] and x['net']>0),Z),closed_negative=sum((x['net'] for x in ls if not x['qty'] and x['net']<0),Z),open_net=sum((x['net'] for x in ls if x['qty']),Z),closed_tail=sum((x['net'] for x in ls if not x['qty'] and x['cost']>0 and x['net']/x['cost']>=D('.3')),Z),open_tail=sum((x['net'] for x in ls if x['qty'] and x['cost']>0 and x['net']/x['cost']>=D('.3')),Z))
def analyze(ref,parent):
 root=O/'runs'/ref;assert read(root/'DONE.json')['completed'];b=book(root/'pair/B.json.gz');old=book(parent/'pair/B.json.gz');all_daily=rows(root/'pair/daily.jsonl.gz');ds=[r for r in all_daily if day(r['at']).startswith('2023')];checks=rows(root/'pair/balances.jsonl.gz');assert len(ds)==242 and len(all_daily)==len(checks)==484
 assert all(num(x['independent_NAV_difference'])==0 and num(x['maximum_stock_quantity_difference'])==0 for x in checks)
 initial=num(old['ending_NAV']);end=num(b['ending_NAV']);tx=[x for x in b['trades'] if day(x['at']).startswith('2023')];jr={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill'};cost=collections.defaultdict(lambda:Z)
 for t in b['trades']:
  if t['side']=='buy':cost[t['layer']]+=num(t['gross_cny'])+num(t['fees_cny'])
 oldlayers={x['id']:x for x in old['layers']};ls=[];oldchange=Z
 for x in b['layers']:
  net=num(x['cash'])+num(x['dividend'])+(D(x['qty'])*price(x['sid'],'2023-12-29') if x['qty'] else Z)
  if x['id'] in oldlayers:
   ol=oldlayers[x['id']];assert ol['qty']==0;oldchange+=net-num(ol['cash'])-num(ol['dividend']);continue
  assert day(x['opened']).startswith('2023');j=jr[x['id']];m=b['metadata'][str(x['id'])]
  ls.append(dict(layer=x['id'],sid=x['sid'],opened=x['opened'],closed=x['closed'],signal_day=day(x['signal_at']),qty=x['qty'],cost=cost[x['id']],net=net,role=j['role'],pool_at_fill=j['pool'],current_pool=m['pool'],sector=m['sector'],attempt=m['attempt'],receipt=j['CP1_id']))
 assert abs(oldchange+sum((x['net'] for x in ls),Z)-(end-initial))<D('.00000001')
 # Whole original cash-flow journal independently reconstructs ending wealth.
 flow=sum((num(t['gross_cny']) if t['side']=='sell' else -num(t['gross_cny']))-num(t['fees_cny']) for t in b['trades'])
 div=sum(num(x['receivable']['net_local']) for x in b['audit'] if x['kind']=='dividend_accrual');inventory=sum(D(x['qty'])*price(x['sid'],'2023-12-29') for x in b['layers'] if x['qty'])
 assert abs(D(1000000)+flow+div+inventory-end)<D('.00000001') and abs(inventory-num(ds[-1]['inventory']))<D('.00000001')
 confirmed=[x for x in ls if x['role']=='mobile' and x['pool_at_fill']=='confirmed'];acts=[x for x in b['audit'] if x['kind']=='risk_checkpoint' and day(x['at']).startswith('2023')];actevents=[x for x in acts if x.get('event')]
 quarters=[];previous=initial
 for q in ['2023Q1','2023Q2','2023Q3','2023Q4']:
  ss=[x for x in ds if str(pd.Timestamp(day(x['at'])).to_period('Q'))==q];tr=[x for x in tx if str(pd.Timestamp(day(x['at'])).to_period('Q'))==q]
  quarters.append(dict(quarter=q,start_NAV=previous,end_NAV=ss[-1]['nav'],return_pct=(num(ss[-1]['nav'])/previous-1)*100,DD=drawdown([('prior_close',previous)]+[(day(x['at']),num(x['nav'])) for x in ss]),mean_exposure_pct=sum((num(x['inventory'])/num(x['nav'])*100 for x in ss),Z)/len(ss),mean_confirmed_pct=sum((num(x['pool_confirmed'][0])/num(x['nav'])*100 for x in ss),Z)/len(ss),mean_available_cash_pct=sum((num(x['available'])/num(x['nav'])*100 for x in ss),Z)/len(ss),buy_cash=sum((num(x['gross_cny'])+num(x['fees_cny']) for x in tr if x['side']=='buy'),Z),buy_fills=sum(x['side']=='buy' for x in tr),paused_closes=sum(not x['on'] for x in ss)));previous=num(ss[-1]['nav'])
 metrics=dict(policy=ref,opening_NAV=initial,ending_NAV=end,year2023_return_pct=(end/initial-1)*100,year2023_DD=drawdown([('2022-12-30',initial)]+[(day(x['at']),num(x['nav'])) for x in ds]),cumulative_from_2022_return_pct=(end/D(1000000)-1)*100,cumulative_from_2022_DD=drawdown([('original1m',D(1000000))]+[(day(x['at']),num(x['nav'])) for x in all_daily]),mean_exposure_pct=sum((num(x['inventory'])/num(x['nav'])*100 for x in ds),Z)/242,peak_exposure_pct=max(num(x['inventory'])/num(x['nav'])*100 for x in ds),mean_confirmed_pct=sum((num(x['pool_confirmed'][0])/num(x['nav'])*100 for x in ds),Z)/242,peak_confirmed_pct=max(num(x['pool_confirmed'][0])/num(x['nav'])*100 for x in ds),mean_available_cash_pct=sum((num(x['available'])/num(x['nav'])*100 for x in ds),Z)/242,fees_2023=sum((num(t['fees_cny']) for t in tx),Z),buy_fills_2023=sum(t['side']=='buy' for t in tx),sell_fills_2023=sum(t['side']=='sell' for t in tx),paused_closes=sum(not x['on'] for x in ds),ACT_events=actevents,new2023_layers=aggregate(ls),newconfirmed_mobile=aggregate(confirmed),old_layer_contribution_change=oldchange,cumulative_record_only_gross_loss_and_fees=ds[-1]['shared_loss'],new_record_only_gross_loss_and_fees=num(ds[-1]['shared_loss'])-num(all_daily[241]['shared_loss']),terminal_inventory=inventory,terminal_dividend_AR=ds[-1]['dividend_receivable'],quarters=quarters,first_actual_new_buy=next((t for t in tx if t['side']=='buy'),None),first_actual_confirmed_mobile=next(iter(confirmed),None),all484_journal_and_quantity_bridges_zero=True,final_independent_journal_residual=D(1000000)+flow+div+inventory-end)
 funding=rows(root/'pair/funding.jsonl.gz');ops=[x for x in rows(root/'pair/opportunities.jsonl.gz') if x['day'].startswith('2023') and x['CP1_id'] and x['mobile_Q'] is True];assert len({(x['sid'],x['day'],x['CP1_id']) for x in ops})==len(ops)
 native_states={r['series']:pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index') for r in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 candidates=[x for x in ops if native_states[x['sector']][x['day']]['stage']>=2 and native_states[x['sector']][x['day']]['E0_valid']]
 caps=rows(root/'pair/capacity-checks.jsonl.gz');caps=[x for x in caps if day(x['at']).startswith('2023') and x['role']=='mobile'];capkeys={(x['sid'],day(x['decision_at']),x['CP1_id']) for x in caps};filledids={x['receipt'] for x in confirmed};reserved={x['CP1_id'] for x in funding if day(x['at']).startswith('2023') and x['role']=='mobile' and x['result']=='reserved' and x.get('pool')=='confirmed'}
 # These are actual per-route minimum-unit rejection reasons, not an alternative account.
 cr=[(x,r) for x in caps for r in x['routes'] if r['pool']=='confirmed'];blocked=[(x,r) for x,r in cr if r['legal_quantity']==0];exclusive=[(x,r) for x,r in blocked if r['minimum_reasons']==['pool_capital']];migration=[x for x in caps if x['confirmed_migration_reason']=='confirmed_unfunded_raw_unknown']
 capreport=dict(canonical_Q_pass_fresh_CP1=len(ops),market_stage_confirmed_expanded_candidates=len(candidates),ACT_paused_among_market_candidates=sum('ACT_paused' in x['barriers'] for x in candidates),actually_entered_mobile_route_receipts=len(capkeys),confirmed_route_evaluations=len(cr),confirmed_minimum_unit_rejected=len(blocked),confirmed_minimum_only_pool_capital=len(exclusive),confirmed_minimum_pool_capital_with_or_without_other_reasons=sum('pool_capital' in r['minimum_reasons'] for x,r in blocked),confirmed_migration_raw_unfunded=len(migration),migration_unique_stocks=len({x['sid'] for x in migration}),confirmed_reserved_receipts=len(reserved),confirmed_receipts_with_actual_fill=len(filledids),route_reasons_counter=dict(collections.Counter(reason for x,r in blocked for reason in r['minimum_reasons'])),account_risk_check_absent=True,exclusive_C1_policy_causality='not established; pool rejection is actual contemporaneous route constraint, not a frozen-state c60 policy replay',migration_other_cause='raw unknown retained; not all confirmed_unfunded means C1 cap',first20_minimum_only_pool_examples=[dict(**x,route_detail=r) for x,r in exclusive[:20]],first20_migration_raw_examples=migration[:20])
 candidatekeys={(x['sid'],x['day'],x['CP1_id']) for x in candidates}
 capreport.update(route_scope='route rows include probe-stage mobile as well; market-qualified intersection stated separately; confirmed-route rejection need not mean whole opportunity rejected',actual_mobile_route_among_market_stage_candidates=len(capkeys&candidatekeys),all_routes_rejected_receipts=sum(x['selected_quantity']==0 for x in caps),all_routes_rejected_and_confirmed_minimum_only_pool_capital=sum(x['selected_quantity']==0 for x,r in exclusive),confirmed_route_rejected_but_probe_allowed=sum(x['selected_quantity']>0 for x,r in blocked))
 groups={}
 for x,r in exclusive:
  if x['selected_quantity']!=0:continue
  key=(x['sid'],x['attempt']);g=groups.setdefault(key,dict(sid=x['sid'],attempt=x['attempt'],first_rejected_open=day(x['at']),last_rejected_open=day(x['at']),canonical_receipts=0,minimum_c=num(x['c']),maximum_c=num(x['c']),first_snapshot=x))
  g['last_rejected_open']=day(x['at']);g['canonical_receipts']+=1;g['minimum_c']=min(g['minimum_c'],num(x['c']));g['maximum_c']=max(g['maximum_c'],num(x['c']))
 for g in groups.values():
  g['first_later_fresh_actual_confirmed_fill']=next((l for l in confirmed if l['sid']==g['sid'] and l['attempt']==g['attempt'] and day(l['opened'])>g['first_rejected_open']),None)
 save(Path('analysis')/ref/'REPEATED_POOL_BLOCKS.json',dict(unit='stock x real industry attempt, distinct fresh receipts at actual rejected opens; not independent trials or a new policy',exclusive_meaning='confirmed minimum passes every other recorded confirmed-route constraint, and neither original route admitted quantity; does not prove replacing c would improve results',groups=sorted(groups.values(),key=lambda x:(x['first_rejected_open'],x['sid']))))
 save(Path('analysis')/ref/'METRICS.json',metrics);save(Path('analysis')/ref/'LAYERS_2023.json',ls);save(Path('analysis')/ref/'CAPACITY_FUNNEL.json',capreport)
 stock=collections.defaultdict(lambda:Z)
 for x in ls:stock[x['sid']]+=x['net']
 ordered=sorted(stock,key=lambda s:-stock[s]);save(Path('analysis')/ref/'STOCK_CONTRIBUTIONS.json',[dict(sid=s,net=stock[s],layers=[x for x in ls if x['sid']==s]) for s in ordered])
 if ref=='C1':
  cc=read(root/'pair/C1.json')['decisions'];assert len(cc)==484;cs=[x for x in cc if day(x['at']).startswith('2023')];assert len(cs)==242;high=D(1000000)
  for close,r in zip(all_daily,cc):
   assert day(close['at'])==day(r['at'])
   high=max(high,num(close['nav']));dd=max(Z,1-num(close['nav'])/high);assert num(r['high'])==high and num(r['decision_nav'])==num(close['nav']) and num(r['drawdown'])==dd and num(r['fraction'])==D('.1')+D('.5')*max(Z,1-dd/D('.2'))
  milestones=[]
  for label,test in [('above10',lambda x:num(x['fraction'])>D('.1')),('at_least35',lambda x:num(x['fraction'])>=D('.35')),('full60',lambda x:num(x['fraction'])==D('.6'))]:
   first=next((x for x in cs if test(x)),None);d=day(first['at']) if first else None;after=next((l for l in confirmed if d and l['signal_day']>=d and day(l['opened'])>d),None)
   milestones.append(dict(formula_milestone=label,first_decision=first,first_later_fresh_confirmed_actual_fill=after,not_same_as_cash_or_exposure_recovery=True,right_censored_if_never=first is None))
  crossings=[dict(day=day(r['at']),prior_capital=previous['confirmed_capital'],cap=r['confirmed_cap'],commitment=r['confirmed_capital'],gap=r['cap_minus_commitment']) for previous,r in zip(cc,cc[1:]) if day(r['at']).startswith('2023') and num(previous['cap_minus_commitment'])<=0<num(r['cap_minus_commitment'])]
  restoration=dict(H_end=cs[-1]['high'],c_end=cs[-1]['fraction'],c_min=min(num(x['fraction']) for x in cs),c_max=max(num(x['fraction']) for x in cs),days_at10=sum(num(x['fraction'])==D('.1') for x in cs),days_at60=sum(num(x['fraction'])==D('.6') for x in cs),over_cap_closes=sum(x['over_cap'] for x in cs),max_over_cap=max([max(Z,-num(x['cap_minus_commitment'])) for x in cs]),initial_cap_space='already positive because original ACT liquidated; ACT pause and other eligibility still apply',milestones=milestones,observed_nonpositive_to_positive_cap_space_crossings=crossings,formula_from_all484_closes_verified=True,ACT_phase_does_not_reset_H=True)
  save('analysis/C1/RESTORATION.json',restoration);metrics['C1_capacity_restoration']=restoration
 # Raw migration failure is not automatically an exclusive cap rejection.
 events=[r for r in rows(root/'pair/industry.jsonl.gz') if r['day'].startswith('2023') and r['result']=='confirmed_unfunded'];dmap={day(r['at']):r for r in ds};first={}
 for r in events:
  for l in dmap[r['day']]['layers']:
   if l['pool']=='probe' and l['sector']==r['sector'] and l['attempt']==r['attempt']:first.setdefault(l['id'],r['day'])
 snapshots={d:{l['id']:l for l in r['layers']} for d,r in dmap.items()};dates=list(dmap);ix={d:i for i,d in enumerate(dates)};final_layers={x['id']:x for x in b['layers']};wait=[]
 for lid,d in first.items():
  moved=next((dd for dd in dates[ix[d]+1:] if lid in snapshots[dd] and snapshots[dd][lid]['pool']=='confirmed'),None);l=final_layers[lid]
  wait.append(dict(layer=lid,sid=l['sid'],first_raw_unfunded_with_current_probe=d,first_later_observed_confirmed=moved,lag_market_observations=ix[moved]-ix[d] if moved else None,actual_exit=l['closed'],status='migrated' if moved else 'exited' if l['closed'] else 'censored',causal_scope='observed migration failure and subsequent pool transition; exclusive cap cause unknown'))
 lags=[x['lag_market_observations'] for x in wait if x['status']=='migrated'];save(Path('analysis')/ref/'MIGRATION_WAITS.json',dict(raw_failed_industry_events=len(events),tracked_probe_layers=len(wait),migrated=sum(x['status']=='migrated' for x in wait),exited=sum(x['status']=='exited' for x in wait),censored=sum(x['status']=='censored' for x in wait),migrated_only_lag_median=statistics.median(lags) if lags else None,migrated_only_lag_max=max(lags) if lags else None,layers=wait))
 save(Path('analysis')/ref/'METRICS.json',metrics);print('RESULT',ref,json.dumps({k:metrics[k] for k in ['opening_NAV','ending_NAV','year2023_return_pct','year2023_DD','cumulative_from_2022_return_pct','cumulative_from_2022_DD','mean_exposure_pct','fees_2023','paused_closes']},default=str),flush=True);return metrics
def main():
 started=time.monotonic();out=[]
 for ref,parent in [('Bdiag',W/'2022-normal-reference-20261031/runs/B_diag'),('C1',W/'c1-drawdown-capacity-20261101/runs/2022')]:
  if (O/'runs'/ref/'DONE.json').exists():out.append(analyze(ref,parent))
 save('COMPARISON_2023.json',out);save('analysis/COMPLETION.json',dict(policies=len(out),read_only=True,seconds=time.monotonic()-started,no_new_account_calls=True))
if __name__=='__main__':main()
