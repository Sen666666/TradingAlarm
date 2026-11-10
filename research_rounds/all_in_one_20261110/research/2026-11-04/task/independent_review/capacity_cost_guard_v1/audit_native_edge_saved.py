"""Read saved actual-native fixture; no account/strategy/guard import or replay."""
import importlib.util,json,hashlib
from pathlib import Path
from decimal import Decimal as D
spec=importlib.util.spec_from_file_location('read_saved_native',Path(__file__).with_name('audit_saved_native.py'))
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
F=Path('native_edge_fixture_v1');b=R.read(F/'NATIVE_ACCOUNT_AFTER_EDGE.json');p=R.read(F/'ACTUAL_NATIVE_EDGE_PROOF.json')
layer={x['id']:x for x in b['layers']};checks=[]
receipts=[p['buy']['receipt1'],p['buy']['receipt2'],p['actual_partial_sell']]
for t in receipts:
 assert next(x for x in b['trades'] if x['receipt_id']==t['receipt_id']).items()>=t.items()
for label,snapshot,receipt in [('after_first',p['buy']['after_first'],receipts[0]),('after_second',p['buy']['after_second'],receipts[1]),('after_exit',p['after_exit'],receipts[2])]:
 cut=next(i+1 for i,r in enumerate(b['audit']) if r['kind']=='fill' and r['receipt']['receipt_id']==receipt['receipt_id'])
 q=R.prefix(b,cut);at=snapshot['at'];inv=sum((D(v)*R.mark(layer[i]['sid'],at) for i,v in q['q'].items() if v),D(0));v=snapshot['balance']
 R.near(inv,v['inventory'],label+' independent original mark inventory')
 R.near(q['cash']+inv,v['nav'],label+' cash+qty+fees NAV')
 R.near(q['fees'],v['fees_cny'],label+' actual native fees')
 liquid=sum((D(v[k]) for k in ('available','order_reserved','sale_receivable','dividend_receivable')),D(0))
 R.near(q['cash'],liquid,label+' native cash buckets')
 R.near(D(v['settlement_locked']),D(v['payable']),label+' unsettled payable bridge')
 for i,amt in snapshot['basis'].items():R.near(q['basis'][int(i)],amt,label+' actual remaining cost')
 for i,qty in snapshot['live'].items():assert q['q'][int(i)]==qty
 ctx=snapshot['cost_context'];P=sum((x['gross']+x['fee'] for x in q['pending'].values()),D(0));Dp=sum((x['fee']+x['gross']*D('.0005')/D('1.0005') for x in q['pending'].values()),D(0))
 R.near(P,ctx['pending_cost'],label+' pending gross+fee');R.near(Dp,ctx['pending_drag'],label+' pending forecast drag')
 R.near(q['cash']+inv-Dp,ctx['guard_NAV'],label+' guard NAV')
 checks.append(label)
assert D(receipts[0]['fees_cny'])-D(receipts[1]['fees_cny'])==5
for c in p['split_callbacks']:
 ratio=D(c['ratio'])
 for i,v in c['before_basis'].items():
  if c['after_live'].get(i,0):assert D(c['after_basis'][i])==D(v)
  else:assert D(c['after_basis'][i])==0
 assert c['post_CA_economic_NAV_continuity_NOT_TESTED'] if 'post_CA_economic_NAV_continuity_NOT_TESTED' in c else True
assert p['post_CA_economic_NAV_continuity_NOT_TESTED'] is True
result={'status':'PASS_INDEPENDENT_SAVED_ACTUAL_NATIVE_EDGE_BRIDGES','checked_snapshots':checks,'actual_partial_buy_receipts':2,'actual_position_level_partial_sell_receipts':1,'native_split_callbacks':2,'same_batch_nonzero_partial_exit_not_in_fixture':True,'split_economic_NAV_continuity_not_claimed':True,'source_sha256':R.SRC,'checker_sha256':R.sha(__file__)}
out=Path(__file__).with_name('NATIVE_EDGE_INDEPENDENT_AUDIT.json');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'}))
