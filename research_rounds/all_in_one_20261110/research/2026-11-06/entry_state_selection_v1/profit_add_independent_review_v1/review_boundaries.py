from pathlib import Path
import json,hashlib
from decimal import Decimal as D
from collections import Counter,defaultdict
BASE=Path(__file__).resolve().parent
exec((BASE/'review_existing.py').read_text().split('for f in sorted(RUN.glob')[0])
checks=Counter();o=R/'profit_funded_add_case_audit_v1';z=read(o/'ADD_CLOCK_SNAPSHOTS.json');a=read(o/'CLOCK_BOUNDARY_FLAGS.json');am={(r['round_id'],r['new_layer_id'],r['clock']):r for r in a};results=[]
for r in z:
 sid=r['sid'];at=r['at'];g=defaultdict(int);mark=dec(r['mark_raw']);fac=dec(r['factor']);oldfee=Z
 for l in r['layer_details']:g[dec(l['floor_raw'])]+=l['qty'];oldfee+=dec(l['scenario_sell_fee'])
 before=sum((dec(q)*f*D('.9995')-fee(sid,at,'sell',q,f*D('.9995')) for f,q in g.items()),Z)+dec(r['cumulative_trade_cash_from_zero'])+dec(r['booked_dividend_accrual']);n=r['new_quantity'];f=dec(r['new_floor_raw']);g[f]+=n
 after=sum((dec(q)*f*D('.9995')-fee(sid,at,'sell',q,f*D('.9995')) for f,q in g.items()),Z)+dec(r['cumulative_trade_cash_from_zero'])+dec(r['booked_dividend_accrual'])-dec(r['new_buy_cost'])
 aa=am[r['round_id'],r['new_layer_id'],r['clock']];eq(before,aa['old_floor_scenario_net_grouped'],'same_floor_old_value');eq(after,aa['post_add_floor_net_same_floor_grouped'],'same_floor_post_value');assert not any(dec(l['floor_raw'])>=mark for l in r['layer_details']);checks['known_mark_above_all_old_floors']+=1
 if r['clock']=='OPEN':results.append(dict(round_id=r['round_id'],new_layer=r['new_layer_id'],at=at,standalone=dec(r['full_round_protection_net_after']),fully_grouped=after,sign_changed=(dec(r['full_round_protection_net_after'])<0)!=(after<0)))
condition=read(R/'conditional_profit_add_risk_audit_v1/SNAPSHOTS.json');c=Counter()
for r in condition:
 if r['phase']=='t_close':continue
 c['actual_ADDs']+=1;assert not r['mark_below_any_old_floor'];c['OPEN_above_all_old_floors']+=1;assert dec(r['U_round_confirmed_paid'])>0;c['positive_cycle_cash_ADDs']+=1
# Confirm neither sealed source nor author arithmetic tables changed during our review.
maps=[json.loads((OUT/n).read_text()) for n in ['SOURCE_SHA256.json','AUTHOR_SOURCE_SHA256.json']];frozen={k:v for m in maps for k,v in m.items()};changed=[p for p,h in frozen.items() if sha(Path(p))!=h];assert not changed,changed
r=dict(status='PASS',checks=checks,conditional=c,original_OPEN_standalone_negative=sum(v['standalone']<0 for v in results),original_OPEN_fully_grouped_negative=sum(v['fully_grouped']<0 for v in results),original_fee_boundary=[r for r in results if r['sign_changed']],unchanged_review_sources=len(frozen),no_new_policy=True)
(OUT/'BOUNDARY_CHECKS.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(r,ensure_ascii=False,default=str))
