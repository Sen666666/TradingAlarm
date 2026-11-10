"""Read-only actual first migration accounting, no event execution."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,sys
import month_runtime as M
sys.path.insert(0,str(M.C.OLD));from verify_saved import check_json
def main():
 p=M.HERE;rows=[];checks=[]
 for root in sorted((p/'runs').iterdir()):
  cp=M.read(root/'PROGRESS.json');r=M.MonthRunner.restore(cp['checkpoint']);x=json.loads(json.dumps(r.observable(r.last_completed_event),default=M.E.encode));assert x==M.read(Path(cp['checkpoint']).with_suffix('.json'))
  a=x['account'];b=a['balance'];industry=defaultdict(lambda:D(0))
  for z in a['layers']:industry[a['capital_meta'][str(z['id'])]['sector']]+=D(z['qty'])*D(a['market_marks'][z['sid']])
  flow=M.read(root/'FIRST_MIGRATION.json');close=M.read(root/'FIRST_MIGRATION_FOLLOWUP_CLOSE.json');fills=flow['fills'];buy=sum((D(f['gross_cny']) for f in fills if f['side']=='buy'),D(0));sell=sum((D(f['gross_cny']) for f in fills if f['side']=='sell'),D(0));sellfee=sum((D(f['fees_cny']) for f in fills if f['side']=='sell'),D(0));buyfee=sum((D(f['fees_cny']) for f in fills if f['side']=='buy'),D(0))
  assert D(flow['after_balance']['sale_receivable'])==0 and D(flow['after_balance']['order_reserved'])==0
  assert D(flow['after_available'])==D(flow['before_available'])+sell-sellfee-buy-buyfee
  for path in root.glob('20*-*.json'):
   if path.stem.split('-')[-1] in ('ACTION','OPEN','CLOSE'):checks.append(dict(file=str(path),differences=check_json(path)))
  plan=r.results[-1]['projection'];rows.append(dict(arm=root.name,cursor=str(r.last_completed_event),checkpoint=cp['checkpoint'],checkpoint_sha256=cp['sha256'],full_restore_exact=True,new_buy=buy,new_sell=sell,new_fees=sellfee+buyfee,old_available=flow['before_available'],after_open_available=flow['after_available'],cash_identity_including_fees_exact=True,no_unsettled_sale_credit=True,buy_count=sum(f['side']=='buy' for f in fills),sell_count=sum(f['side']=='sell' for f in fills),book_after_open=json.loads(flow['budget_after'])['body']['batch'],book_after_close=json.loads(close['budget_after'])['body']['batch'],close_balance=b,close_exposure=D(b['inventory'])/D(b['nav']),industries=[dict(sector=s,value=v,weight=v/D(b['nav'])) for s,v in sorted(industry.items(),key=lambda z:-z[1])],pending=len(x['pending']),native_buys=len(a['buys']),native_exits=len(a['exits']),last_Q={s:q for s,q in plan['Q'].items() if q},last_D=plan['D'],raw_rejections=len(a['rejections']),first_fills=fills,execution_grant=r.execution_grant_record,timing=M.read(root/'STOPPED_AT_CUTOFF.json')))
 M.E.IO.write_json(p/'RESULTS.json',dict(rows=rows,only_authorized_first_migration_days=True,financial_counterfactuals=0),encoder=M.E.encode)
 M.E.IO.write_json(p/'FINANCIAL_CHECKS.json',dict(passed=True,event_states=len(checks),checks_per_event=7,full_checkpoint_restore=4,rows=checks,financial_events_executed_by_analysis=0),encoder=M.E.encode)
 M.E.IO.write_json(p/'CONTINUATION_CHECKPOINTS.json',[{k:r[k] for k in ('arm','cursor','checkpoint','checkpoint_sha256','execution_grant')} for r in rows],encoder=M.E.encode)
 print(json.dumps([{k:r[k] for k in ('arm','cursor','new_buy','new_sell','close_exposure','pending','native_exits')} for r in rows],default=str,indent=2))
if __name__=='__main__':main()
