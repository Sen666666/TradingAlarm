"""Saved-ledger readout only; explicit native fill/layer/order schema joins."""
from driver import *
import collections

def main():
 out=PARENT/'analysis';out.mkdir(exist_ok=True);metrics={};plans=[]
 save(out/'ANALYSIS_ERRATA.json',dict(errors=['FillReceipt has no order_id','serialized Position shares is computed from lots, not a shares field'],correction='native_buy receipt->layer->capital_meta.order; sum native lots shares',financial_events_rerun=0))
 for window,first,last in [('2022','2022-01-04','2022-01-05'),('2025_26','2025-07-01','2025-07-02')]:
  end=LD.read(PARENT/'runs'/window/'primary-resume'/(last+'-CLOSE.json'));a=end['account'];audit=end['account_audit']
  links={r['receipt']:a['capital_meta'][str(r['layer'])]['order'] for r in a['native_callbacks'] if r['kind']=='native_buy'}
  filled=collections.Counter();quantities=collections.Counter()
  for f in a['fills']:
   assert f['side']=='buy';filled[links[f['receipt_id']]]+=f['shares'];quantities[f['security_id']]+=f['shares']
  assert {s:sum(l['shares'] for l in p['lots']) for s,p in a['native_inventory'].items()}==dict(quantities)
  reserves=[r for r in audit if r['kind']=='reserve'];by={r['sid']:r for r in reserves}
  for day,sub in [(first,'primary'),(last,'primary-resume')]:
   state=LD.read(PARENT/'runs'/window/sub/(day+'-CLOSE.json'))
   for i in state['pending']:
    r=by.get(i['sid']) if day==first else None
    status=('reserved_filled' if filled[r['order_id']] else 'reserved_unfilled') if r else ('rejected_before_reserve' if day==first else 'pending_after_authorized_terminal')
    plans.append(dict(window=window,decision_day=day,sid=i['sid'],priority=i['priority'],H1_rank=i.get('original_H1_rank'),PVR=i.get('PVR_score'),status=status,reserve=r,
      fill_qty=filled[r['order_id']] if r else None,rejections=[v for v in a['rejections'] if v['sid']==i['sid'] and str(v['at'])[:10]==last] if day==first and not r else []))
  for e in end['events']:
   b=e['bridge'];assert D(b['independent_nav_difference'])==D(b['cash_asset_difference'])==D(b['layer_cash_difference'])==0
  for r in reserves:
   rule=a['order_meta'][r['order_id']]['quote']['quantity'];assert r['target_shares']>=rule['buy_minimum']
   assert a['supports'][r['order_id']]['priority']==a['supports'][r['order_id']]['original_intent']['priority']
  roles=collections.Counter((r['role'],r['pool']) for r in a['capital_meta'].values())
  incomplete=[dict(sid=r['sid'],reserved=r['target_shares'],filled=filled[r['order_id']]) for r in reserves if filled[r['order_id']]<r['target_shares']]
  metrics[window]=dict(all_native_cash_equity_fee_layer_bridges_zero=True,independent_fill_share_flow_matches_native_lots=True,
   reserves=len(reserves),buy_fill_receipts=len(a['fills']),role_pool={str(k):v for k,v in roles.items()},incomplete=incomplete,
   new_buy_gross=sum((D(f['gross_cny']) for f in a['fills']),Z),fees=sum((D(f['fees_cny']) for f in a['fills']),Z),
   pending_exit_duties=a['exit_duties'],execution_locks=a['policy']['locks'],source_actions=end['action_log'],native_action_ids=a['native_actions'],
   factor688608=a['market_factors']['688608.SH'],share_ratio688608=a['share_ratio']['688608.SH'],
   batch_markers=[r for r in a['native_callbacks'] if r['kind']=='entire_batch_reserved_before_windows'])
 IO.write_gzip_jsonl(out/'PLAN_FUNNEL.jsonl.gz',plans,encoder=N.encode);save(out/'VERIFICATION.json',metrics)
 print(json.dumps({k:dict(reserved=v['reserves'],fills=v['buy_fill_receipts'],incomplete=v['incomplete']) for k,v in metrics.items()}))
if __name__=='__main__':main()
