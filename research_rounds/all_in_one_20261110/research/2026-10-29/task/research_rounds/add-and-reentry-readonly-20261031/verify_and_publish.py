"""Verify saved classification, export tables and concrete journal chains."""
from pathlib import Path
from decimal import Decimal as D
import collections,json,gzip,csv,hashlib,bisect
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def n(v):return D(str(v))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 p=O/p;t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def csvsave(name,rs):
 p=O/name;t=p.with_name(p.name+'.tmp')
 with t.open('w') as f:
  c=csv.DictWriter(f,fieldnames=list(rs[0]));c.writeheader();c.writerows(rs)
 t.replace(p)
def main():
 checks=[];summaryrows=[];entryrows=[];chains=[]
 for win,base in [('2022','2022-normal-reference-20261031'),('2025_26','q2-normal-continuation-20261031')]:
  es=read(O/win/'ENTRIES.json');s=read(O/win/'SUMMARY.json');b=book(W/base/'runs/B_diag/pair/B.json.gz');ds=rows(W/base/'runs/B_diag/pair/daily.jsonl.gz');prev={r['at'][:10]:r for r in ds};ld={x['id']:x for x in b['layers']};cash={};sold=collections.defaultdict(list)
  for t in b['trades']:
   if t['side']=='buy':cash[t['layer']]=n(t['gross_cny'])+n(t['fees_cny'])
   else:
    for part in t['parts']:sold[part['layer']].append(t['at'])
  initial=read(W/'stage-progress-R-diagnostic-20261031'/win/'B_diag/ENTRIES.json');assert sum((n(e['net_contribution']) for e in es),Z)==sum((n(e['net_contribution']) for e in initial),Z)
  assert sum((n(v['buy_cash']) for v in s['action'].values()),Z)==n(s['total']['buy_cash'])
  # Independent raw-price check of only the old holding marks actually used.
  # The snapshot inventory is authoritative; no guessed adjusted-raw splice.
  sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};ps={};maxdiff=Z;partial_count=0;qtychanges=0;rights_cases=0;source_stale=[]
  used_days={e['known_snapshot_day'] for e in es if e['old_live_layers_at_previous_close']};inventory_max=Z
  for date in sorted(used_days):
   snap=prev[date];value=Z
   for sid,qty in snap['positions'].items():
    if sid not in ps:ps[sid]=pd.read_parquet(sm[sid]['refs']['facts'],columns=['factor','raw_close'])
    f=ps[sid];ix=f.index.searchsorted(pd.Timestamp(date),side='right')-1
    assert ix>=0,(win,date,sid,'no previous known source price')
    raw=n(f.iloc[ix].raw_close);assert raw.is_finite() and raw>0
    value+=D(qty)*raw
   delta=abs(value-n(snap['inventory']));inventory_max=max(inventory_max,delta)
   assert delta<D('.00001'),(win,date,'source marked inventory differs saved ledger',delta)
  for e in es:
   assert n(e['actual_buy_cash'])==cash[e['layer']]
   for x in e['old_live_layers_at_previous_close']:
    sid=e['sid']
    if sid not in ps:ps[sid]=pd.read_parquet(sm[sid]['refs']['facts'],columns=['factor','raw_close'])
    f=ps[sid];ix=f.index.searchsorted(pd.Timestamp(e['known_snapshot_day']),side='right')-1;r=f.iloc[ix]
    assert n(x['raw_mark'])==n(r.raw_close)
    assert abs(n(x['raw_protection'])*n(r.factor)-n(x['adjusted_protection']))<D('.00000001')
    snap=next(a for a in prev[e['known_snapshot_day']]['layers'] if a['id']==x['layer'])
    assert n(x['cash'])==n(snap['cash']) and n(x['dividend'])==n(snap['dividend']) and x['qty']==snap['qty']
    assert n(x['adjusted_protection'])==n(snap['last_core_line'] if snap['role']=='core' else snap['floor'])
   if e['actual_action']=='add':
    if any(any(t[:10]<=e['known_snapshot_day'] for t in sold[x['layer']]) for x in e['old_live_layers_at_previous_close']):partial_count+=1
    if sum(x['qty'] for x in e['old_live_layers_at_previous_close'])!=e['actual_prefill_qty']:qtychanges+=1
    if any(n(x['dividend'])!=0 for x in e['old_live_layers_at_previous_close']):rights_cases+=1
    # Verify the full stock snapshot using its own marked value if one exists.
    for x in e['old_live_layers_at_previous_close']:
     maxdiff=max(maxdiff,abs(n(x['economic_net'])-(n(x['cash'])+n(x['dividend'])+D(x['qty'])*n(x['raw_mark']))))
   comparison=e['last_actual_buy_comparison'];priorcycle=e['prior_completed_cycle']
   if priorcycle:
    assert n(priorcycle['net'])==sum((n(ld[k]['cash'])+n(ld[k]['dividend']) for k in priorcycle['layers']),Z)
    assert all(ld[k]['qty']==0 for k in priorcycle['layers']) and priorcycle['exit_at']<=e['fill_at']
   entryrows.append(dict(window=win,layer=e['layer'],sid=e['sid'],name=e['name'],fill_at=e['fill_at'],action=e['actual_action'],old_sign=e['old_live_economic_sign'],known_snapshot_day=e['known_snapshot_day'],old_economic_net=e['old_live_layer_economic_net'],buy_qty=e['actual_buy_qty'],buy_cash=e['actual_buy_cash'],below_last_buy=comparison['fill_below_previous'] if comparison else None,prior_cycle_sign=e['reentry_previous_cycle_sign'],same_E0=e['reentry_same_stock_E0'],same_industry_attempt=e['reentry_same_industry_attempt'],closed=e['closed'],new_layer_net=e['net_contribution'],open_qty=e['terminal_quantity']))
  for type_,parts in [('action',s['action']),('add_previous_close_economic_sign',s['adds_prior_close_sign']),('reentry_previous_complete_exit_sign',s['reentry_prior_full_exit_sign'])]:
   for group,metrics in parts.items():summaryrows.append(dict(window=win,partition=type_,group=group,**metrics))
  for m in s['adds_sign_by_below_last_actual_buy']:summaryrows.append(dict(window=win,partition='add_sign_x_below_last_actual_buy',group=m['old_sign']+' / below='+str(m['below_last_actual_buy']),**{k:v for k,v in m.items() if k not in ('old_sign','below_last_actual_buy')}))
  checks.append(dict(window=win,all_selected_layers_and_new_cash_reconcile=True,exact_journal_quantity_days=s['daily_quantity_reconciliation_days'],source_price_inventory_checked_days=len(used_days),maximum_source_price_inventory_difference=str(inventory_max),old_snapshot_cash_dividend_qty_protection_exact=True,maximum_old_layer_economic_identity_error=str(maxdiff),add_snapshots_with_prior_partial_exit=partial_count,add_previous_close_qty_differs_actual_prefill=qtychanges,add_snapshots_with_dividends=rights_cases,price_mark_status='same-source cached raw_close; previous-close snapshot only, not exact opening mark'))
  if win=='2022':
   for sid,choice in [('600986.SH','chronologically first negative-old-holding add'),('000620.SZ','largest new-layer loss among positive-old-holding adds')]:
    chosen=[e for e in es if e['sid']==sid and e['actual_action']=='add'];start='2022-01-01';end='2022-02-28';layers=[x for x in b['layers'] if x['sid']==sid and start<=x['opened'][:10]<=end]
    chains.append(dict(window=win,sid=sid,choice=choice,cutoff=end,existing_full_trade_records=[t for t in b['trades'] if t['security_id']==sid and start<=t['at'][:10]<=end],selected_entry_audits=[e for e in chosen if start<=e['fill_at'][:10]<=end],original_final_layers=layers,only_new_layer_net_belongs_to_new_entry=True))
 save('VERIFICATION.json',checks);save('EXAMPLE_CHAINS.json',chains);csvsave('FUNDED_LAYER_CLASSIFICATIONS.csv',entryrows);csvsave('CLASS_METRICS.csv',summaryrows)
 match=read(O/'FIRST_LATER_MATCHED.json');flat=[]
 for r in match:
  z={k:v for k,v in r.items() if k not in ['first','later']}
  for k in ['first','later']:
   z.update({k+'_'+a:b for a,b in r[k].items()})
  flat.append(z)
 csvsave('FIRST_LATER_MATCHED.csv',flat)
 print(json.dumps(checks,ensure_ascii=False))
if __name__=='__main__':main()
