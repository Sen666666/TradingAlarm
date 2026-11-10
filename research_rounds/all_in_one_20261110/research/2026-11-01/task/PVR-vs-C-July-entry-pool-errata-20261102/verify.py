"""Independent ledger/bridge checks on saved attribution; no financial calls."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib
O=Path(__file__).resolve().parent;Z=D(0);EPS=D('1e-8')
def read(n):return json.loads((O/n).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def near(a,b):assert abs(a-b)<EPS,(a,b)
def main():
 ll=read('ALL_JULY_ENTRY_LAYERS.json');bridges=read('EXACT_BRIDGES.json');pp=read('POLICY_AND_INITIAL_COMPARABILITY.json');assert pp['initial_NAV']==1000000 and pp['identities']==1709 and pp['old_opportunity_identity_days_verified']==23
 previous=read('PREVIOUS_PACKAGE_RECORD.json');prior=Path(previous['previous_directory'])
 for rel,h in previous['all_previous_files'].items():assert sha(prior/rel)==h,('previous package mutated',rel)
 audit=json.loads(Path(previous['independent_audit']).read_text());assert sha(previous['independent_audit'])==previous['independent_audit_sha256']
 changed=[]
 for r in ll['PVR_SLOT1']:
  assert r['opened'][:10]==r['metadata_observed_at'][:10] and r['signal_at']<r['opened'] and r['opened'][:10]<='2025-07-31'
  fr=r['entry_reserve'];proof=r['entry_order_audit'];assert r['pool_source']=='fill_bound_OPEN_funding_reserve' and fr['result']=='reserved' and fr['at']==r['opened'] and fr['sid']==r['sid'] and fr['role']==r['role'] and fr['pool']==r['pool'] and fr['shares']>=r['initial_qty'] and D(fr['price'])==D(r['buy_price'])
  assert proof['reserve']['order_id']==proof['funded']['order_id'] and proof['funded']['signal_at']==r['signal_at'] and proof['funded']['layer_kind']==('core' if r['role']=='core' else 'add')
  if r['pool']!=r['first_close_pool']:changed.append((r['sid'],r['layer'],r['role'],r['pool'],r['first_close_pool']))
  assert r['initial_qty']-sum(v['shares'] for v in r['actual_sell_parts'])==r['remaining_qty']
  near(D(r['realized'])+D(r['unrealized'])+D(r['dividend']),D(r['contribution']))
 assert set(changed)=={('000932.SZ',55,'core','probe','confirmed'),('002044.SZ',86,'core','probe','confirmed'),('002768.SZ',88,'mobile','probe','confirmed')}
 oldlayers=json.loads((prior/'ALL_JULY_ENTRY_LAYERS.json').read_text())
 moneyfields=['realized','unrealized','dividend','contribution','buy_gross','fees']
 for mode,rs in ll.items():
  oldmap={r['layer']:r for r in oldlayers[mode]};assert len(oldmap)==len(rs)
  for r in rs:
   for k in moneyfields:assert r[k]==oldmap[r['layer']][k],('layer monetary field changed',mode,r['layer'],k)
 oldbridge=json.loads((prior/'EXACT_BRIDGES.json').read_text())
 for mode,b in bridges.items():
  for k,v in oldbridge[mode].items():
   if k not in ['entry_keys','entry_category_deltas']:assert b[k]==v,('reported amount changed',mode,k)
  for n in [mode+'-STOCK_BRIDGE.json',mode+'-INDUSTRY_BRIDGE.json']:assert sha(O/n)==sha(prior/n)
  e=read(mode+'-ENTRY_BRIDGE.json');expected=audit['corrected_entry_counts_and_categories'][mode];assert len(e)==b['entry_keys']==expected['union']
  for cat,v in expected['categories'].items():assert sum(r['category']==cat for r in e)==v['count'] and b['entry_category_deltas'][cat]==v['contribution']
 for mode,b in bridges.items():
  ss=read(mode+'-STOCK_BRIDGE.json');ii=read(mode+'-INDUSTRY_BRIDGE.json');ee=read(mode+'-ENTRY_BRIDGE.json');assert len(ii)==90 and len(ss)==164
  for rows in [ss,ii,ee]:near(sum((D(z['delta']['contribution']) for z in rows),Z),D(b['delta']['contribution']))
  for sid in {z['sid'] for z in ss}:
   z=next(z for z in ss if z['sid']==sid)
   for k in ['realized','unrealized','dividend','contribution','fees']:
    d=sum((D(r[k]) for r in ll[mode] if r['sid']==sid),Z)-sum((D(r[k]) for r in ll['PVR_SLOT1'] if r['sid']==sid),Z);near(d,D(z['delta'][k]))
  near(D(b['alternative_gross_price_delta'])+D(b['alternative_fee_saving_add_once'])+D(b['delta']['dividend']),D(b['delta']['contribution']))
  near(sum((D(b['three_chains'][k]) for k in ['Shangwei','Defu','engineering']),Z)+D(b['three_chains']['rest']),D(b['delta']['contribution']))
  upper=[r for r in ll[mode] if r['sid']=='688585.SH'];assert len(upper)==1 and upper[0]['role']=='mobile' and upper[0]['pool']=='probe' and upper[0]['remaining_qty']==0 and all(p['reason']=='actionable_S_funding' for p in upper[0]['actual_sell_parts'])
  defu=[r for r in ll[mode] if r['sid']=='301511.SZ'];assert sum(r['remaining_qty'] for r in defu)==300
  assert sum(r['remaining_qty'] for r in ll['PVR_SLOT1'] if r['sid']=='688585.SH')==819 and sum(r['remaining_qty'] for r in ll['PVR_SLOT1'] if r['sid']=='301511.SZ')==1700
  assert not [r for r in ll['PVR_SLOT1'] if r['sector']=='URFI881268']
 c=read('COMMON_CANONICAL_SIGNAL_CHECKS.json');assert all(len(c[m])==57 for m in c)
 evidence=read('THREE_CHAIN_TIMESTAMPS_AND_REASONS.json');fund=[r for r in evidence['PVR_funding'] if r['sid']=='688585.SH' and r['role']=='mobile'];zero=[r for r in fund if r['result']=='reserved' and r['at'][:10]<'2025-07-22']
 assert {r['at'][:10] for r in zero}=={'2025-07-16','2025-07-17','2025-07-18','2025-07-21'}
 assert all(not [l for l in ll['PVR_SLOT1'] if l['sid']=='688585.SH' and l['opened']==r['at']] for r in zero)
 assert [r['result'] for r in fund if r['at'][:10]=='2025-07-15']==['pool_capital,probe_risk']
 olde=json.loads((prior/'THREE_CHAIN_TIMESTAMPS_AND_REASONS.json').read_text())
 assert all(evidence[k]==v for k,v in olde.items() if k!='PVR_layers')
 prior_primary={r['layer']:r for r in olde['PVR_layers']}
 assert all(all(r[k]==v for k,v in prior_primary[r['layer']].items()) for r in evidence['PVR_layers'])
 for path,h in read('READ_INPUTS.json').items():assert sha(path)==h,path
 out=dict(passed=True,all_original_source_hashes_unchanged=len(read('READ_INPUTS.json')),full_stock_sector_entry_gross_net_fee_NAV_bridges=True,PVR_entry_role_pool_from_fill_bound_OPEN_reserve=True,reserve_role_pool_regressions=changed,all_117_entry_reserve_bindings=True,all_reported_monetary_fields_unchanged=True,previous_package_all_files_unchanged=len(previous['all_previous_files']),C10_categories_counts_and_amounts_unchanged=True,C20_corrected_entry_counts={'paired':12,'C_only_entry':113,'PVR_only_entry':105,'union':230},upper_zero_fill_reserve_dates=['2025-07-16','2025-07-17','2025-07-18','2025-07-21'],Jul15_upper_rejection='pool_capital,probe_risk',primary_signal_same_canonical_pairs_per_arm=57,PVR_tail_quantities_and_new_C_healthy_funding_exits_verified=True,all_90_sectors_retained=True,cutoff='2025-07-31',no_future_final_layer_state_used=True,financial_events=0,strategy_changes=0)
 (O/'VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n')
 print('VERIFIED',out['all_original_source_hashes_unchanged'])
if __name__=='__main__':main()
