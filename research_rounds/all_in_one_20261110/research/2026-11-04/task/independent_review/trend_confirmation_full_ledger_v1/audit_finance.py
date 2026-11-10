"""Full native financial audit for four trend-plan arms; no price feature/cap model."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import argparse,bisect,importlib.util,json
O=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('frozen_generic_native_finance',O/'generic_saved_finance_reader.py');R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
ARMS=['A_ONLY','A_OR_B','B','UNIFORM50'];Z=D(0)
def main():
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-days',type=int,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 ds=R.rows(a.run/'pair/daily.jsonl.gz');bs=R.rows(a.run/'pair/balances.jsonl.gz');start=R.read(a.run/'STARTED.json');end=max(str(d['at'])for d in ds);arms=sorted({d['account']for d in ds});assert arms==ARMS
 schema=start.get('full_schema',start);assert schema.get('cost_guard') is False
 report={};edges=[]
 for arm in arms:
  b=R.book(a.run/'pair'/f'{arm}.json.gz');daily=[d for d in ds if d['account']==arm];assert len(daily)==a.expected_days;layers={x['id']:x for x in b['layers']};clocks=[];last=R.ts(ds[0]['at'])-R.pd.Timedelta(days=10000)
  for e in b['audit']:
   t=e.get('at')or e.get('receipt',{}).get('at')or e.get('receivable',{}).get('ex_at');t=R.ts(t)if t else last;assert t>=last,('auditclock',arm,last,t);clocks.append(t);last=t
  peak=D(1000000);mdd=Z
  for d in daily:
   v=R.prefix(b,bisect.bisect_right(clocks,R.ts(d['at'])));quant=defaultdict(int)
   for lid,q in v['q'].items():quant[layers[lid]['sid']]+=q
   assert{s:q for s,q in quant.items()if q}==d['positions'],('qty',arm,d['at'])
   inv=sum((D(q)*R.mark(sid,d['at'])for sid,q in quant.items()if q),Z)
   R.near(inv,d['inventory'],'original raw mark×native actualqty')
   R.near(v['cash']+v['divincome']+inv,d['nav'],'cash+recognized dividends+inventory')
   R.near(v['cash']+v['divincome'],sum((D(d[k])for k in('available','order_reserved','sale_receivable','dividend_receivable')),Z),'native liquid+AR bridge')
   R.near(v['fees'],d['fees_cny'],'actual cumulative fees')
   peak=max(peak,D(d['nav']));mdd=max(mdd,1-D(d['nav'])/peak)
  final=R.prefix(b,len(b['audit']));R.near(sum((D(l['cash'])for l in b['layers']),Z),final['cash']-D(1000000),'native actual layertrade cash total');R.near(sum((D(l['dividend'])for l in b['layers']),Z),final['divincome'],'native dividend attribution');R.near(b['ending_NAV'],daily[-1]['nav'],'terminal NAV')
  for r in bs:
   if r['account']==arm:
    for k in('independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference'):R.near(r[k],0,k)
    for k,v in r.get('pool_occupancy_difference',{}).items():R.near(v,0,'pool:'+k)
  tx={t['receipt_id']:t for t in b['trades']}
  partialbuy=[];partialbatch=[];ca=[];expiry=[]
  for ix,e in enumerate(b['audit']):
   if e['kind']=='fill':
    t=tx[e['receipt']['receipt_id']]
    if t['side']=='buy'and int(e.get('share_cap_remaining',0))>0:partialbuy.append(dict(at=t['at'],sid=t['security_id'],order=e['order_id'],receipt=t['receipt_id'],filled=t['shares'],remaining=e['share_cap_remaining']))
    elif t['side']=='sell':
     before=R.prefix(b,ix)
     for part in t['parts']:
      if part['shares']<before['q'][part['layer']]:partialbatch.append(dict(at=t['at'],sid=t['security_id'],order=e['order_id'],receipt=t['receipt_id'],layer=part['layer'],sold=part['shares'],before_qty=before['q'][part['layer']]))
   elif e['kind']in('split','split_fraction_floor_proxy'):
    before=R.prefix(b,ix);ca.append(dict(at=e['at'],sid=e['sid'],ratio=e['ratio'],native_kind=e['kind'],pending_order_ids=[k for k,v in before['pending'].items()if v['sid']==e['sid']]))
   elif e['kind']=='release_buy'and D(e['gross_released'])>0:expiry.append(dict(at=e['at'],sid=e['sid'],order=e['order_id'],gross_released=e['gross_released']))
  for k,items in [('actual_partial_buy',partialbuy),('actual_same_batch_partial_sell',partialbatch),('actual_CA',ca),('nonzero_gross_order_release',expiry)]:edges.extend(dict(arm=arm,kind=k,**x)for x in items)
  report[arm]=dict(financial_closes=len(daily),terminal_NAV=b['ending_NAV'],return_pct=str((D(b['ending_NAV'])/D(1000000)-1)*100),MDD_close_pct=str(mdd*100),actual_fees_CNY=daily[-1]['fees_cny'],actual_trades=len(b['trades']),recognized_dividend=str(final['divincome']),native_ending_inventory=daily[-1]['inventory'],native_ending_dividend_receivable=daily[-1]['dividend_receivable'],actual_split_callbacks=final['split_events'],actual_partial_buy_receipts=len(partialbuy),actual_same_batch_partial_sell_parts=len(partialbatch),nonzero_gross_releases=len(expiry))
 old=Path('ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair')if end[:4]<='2024'and end[:4]>'2022'else Path('pvr_pool_feasibility/runs')/('2022'if end[:4]=='2022'else'2025_26')/'pair'
 gold=R.book(old/'B.json.gz');new=R.book(a.run/'pair/B.json.gz');assert[t for t in gold['trades']if R.ts(t['at'])<=R.ts(end)]==new['trades'];assert[d for d in R.rows(old/'daily.jsonl.gz')if R.ts(d['at'])<=R.ts(end)]==[d for d in ds if d['account']=='B'];assert[d for d in gold['decisions']if R.ts(d['at'])<=R.ts(end)]==new['decisions']
 if a.expected_days>9:assert new==gold, 'NONE complete native book differs, including open orders/exits/claims/budget/metadata'
 source=schema.get('sources',{});assert all(R.sha(k)==v for k,v in source.items()),'frozen strategy source changed'
 x=dict(status='PASS_TREND_FULL_NATIVE_FINANCE_NO_CAPACITY_PREDICATE',run=str(a.run),arms=report,NONE_daily_actualtrades_decisions_exact=True,NONE_full_terminal_layers_exact=a.expected_days>9,NONE_complete_native_book_including_orders_exits_claims_exact=a.expected_days>9,source_post_exact=len(source),capacity_predicate_checked_or_applied=False,source_sha256=R.SRC,reader_sha256=R.sha(O/'generic_saved_finance_reader.py'),checker_sha256=R.sha(__file__),limits=['A/B/m price-feature and plan/order binding have a separate independent reviewer.','Original daily-bar execution is a proxy; closing NAV drawdown only.','Acquisition-basis observation is not a second finance or admission engine.','Technical and accounting correctness do not imply acceptable absolute economics.'])
 (a.out/'AUDIT.json').write_text(json.dumps(x,indent=2)+'\n');(a.out/'ACTUAL_EDGE_KEYS.json').write_text(json.dumps(edges,indent=2)+'\n');print(json.dumps({k:v for k,v in x.items()if k!='source_sha256'}))
if __name__=='__main__':main()
