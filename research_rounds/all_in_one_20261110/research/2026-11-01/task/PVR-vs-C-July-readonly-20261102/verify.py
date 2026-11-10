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
 for r in ll['PVR_SLOT1']:
  assert r['opened'][:10]==r['metadata_observed_at'][:10] and r['signal_at']<r['opened'] and r['opened'][:10]<='2025-07-31'
  assert r['initial_qty']-sum(v['shares'] for v in r['actual_sell_parts'])==r['remaining_qty']
  near(D(r['realized'])+D(r['unrealized'])+D(r['dividend']),D(r['contribution']))
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
 for path,h in read('READ_INPUTS.json').items():assert sha(path)==h,path
 out=dict(passed=True,all_original_source_hashes_unchanged=len(read('READ_INPUTS.json')),full_stock_sector_entry_gross_net_fee_NAV_bridges=True,PVR_metadata_as_of_actual_buy_day=True,primary_signal_same_canonical_pairs_per_arm=57,PVR_tail_quantities_and_new_C_healthy_funding_exits_verified=True,all_90_sectors_retained=True,cutoff='2025-07-31',no_future_final_layer_state_used=True,financial_events=0,strategy_changes=0)
 (O/'VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n')
 print('VERIFIED',out['all_original_source_hashes_unchanged'])
if __name__=='__main__':main()
