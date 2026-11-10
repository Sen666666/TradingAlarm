"""Supplement actual capital bases and all-entry stock coverage; no account."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D,getcontext
import json,gzip,hashlib
getcontext().prec=65
O=Path(__file__).parent;P=O/'results_v1';ROOT=O.parent;OLDROOT=ROOT.parent/'trend_exit_controls_v1';Z=D(0);SRC={};ARMS=['BASELINE','R_ONLY','P_ONLY','JOINT']
def read(p,gz=False,lines=False):
 SRC[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(name,x):
 with (P/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def eq(a,b,k):assert abs(D(str(a))-D(str(b)))<D('1e-6'),(k,a,b)
def sums(rr):
 return dict(layers=len(rr),stocks=len({r['sid'] for r in rr}),cost=sum((D(r['cost']) for r in rr),Z),net=sum((D(r['net']) for r in rr),Z),
   strict_realized=sum((D(r['strict_realized']) for r in rr),Z),open_unrealized=sum((D(r['open_unrealized']) for r in rr),Z),AR=sum((D(r['AR']) for r in rr),Z))
matrix=read(P/'PERIOD_ACCOUNT_MATRIX.json');look={(x['arm'],x['period']):x for x in matrix};caps={};post122={}
for arm in ARMS:
 led=read(P/(arm+'_2022_2024_DAILY_WEALTH_SPLIT.json'));ix=[i for i,x in enumerate(led) if x['day'][:7]=='2022-12'];assert len(ix)==22
 prev=[led[i-1] for i in ix];curr=[led[i] for i in ix];decrows=read(P/(arm+'_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json'));rm={x['layer_in_this_book']:x for x in decrows}
 path=(OLDROOT if arm=='BASELINE' else ROOT)/'runs'/arm/'2022_2024/pair/daily.jsonl.gz';raw=read(path,gz=True,lines=True);bounds={d['at'][:10]:d for d in raw if d['at'][:10] in ['2022-11-30','2022-12-30']};roles={}
 for role in ['core','mobile']:
  rr=[r for r in decrows if r['role']==role];c={}
  for day,which in [('2022-11-30','Nov30'),('2022-12-30','Dec30')]:
   held=[x for x in bounds[day]['layers'] if rm[x['id']]['role']==role];basis=Z;mark=Z
   for h in held:
    comp=rm[h['id']][which+'_components'];b=D(comp['real'])-D(h['cash']);basis+=b;mark+=D(comp['unreal'])+b
   c[which]=dict(held_layers=len(held),stocks=len({x['sid'] for x in held}),remaining_buyfee_inclusive_basis=basis,actual_marked_inventory=mark)
  c.update(Dec_new_actual_buycash=sum((D(r['cost']) for r in rr if r['cohort'].startswith('Dec_new_')),Z),
    Dec_wealth=sum((D(r['Dec_components']['wealth']) for r in rr),Z),mean_previous_CLOSE_mark=sum((D(r['capitaltime']['previous_CLOSE_mark_yuan_observations']) for r in rr),Z)/22)
  roles[role]=c
 for day,which in [('2022-11-30','Nov30'),('2022-12-30','Dec30')]:eq(sum((roles[r][which]['actual_marked_inventory'] for r in roles),Z),bounds[day]['inventory'],'role capital mark bridge')
 meanclose=sum((D(x['exposure']) for x in curr),Z)/22;eq(meanclose,look[arm,'Dec2022']['mean_close_exposure'],'fixed period close exposure')
 caps[arm]=dict(NAV_begin=prev[0]['NAV'],NAV_end=curr[-1]['NAV'],Dec_actual_wealth=D(curr[-1]['NAV'])-D(prev[0]['NAV']),
  mean_previous_CLOSE_exposure=sum((D(x['exposure']) for x in prev),Z)/22,mean_CLOSE_exposure=meanclose,
  mean_previous_CLOSE_inventory=sum((D(x['inventory']) for x in prev),Z)/22,mean_available_cash=sum((D(x['available']) for x in curr),Z)/22,
  by_role=roles,interpretation='Actual own path bases and marked capital, not equal-Nov30 cash or equal-quantity controls. CORE rule untouched does not fix actual CORE amounts.')
 cc=read(P/(arm+'_ORIGINAL122_FULL_KEY_CORRESPONDENCE.json'));own=[r for r in decrows if r['cohort'].startswith('Dec_new_')];matched={r['original_full_entry_key'] for r in cc['rows'] if r['candidate_exact_entry'] is not None};new=[r for r in own if r['key'] not in matched]
 post122[arm]=dict(same_key_count=len(matched),baseline_these_samekeys_Dec_wealth=sum((D(r['original_layer']['Dec_components']['wealth']) for r in cc['rows'] if r['candidate_exact_entry'] is not None),Z),
   candidate_samekeys_Dec_wealth=sum((D(r['candidate_Dec_components']['wealth']) for r in cc['rows'] if r['candidate_Dec_components'] is not None),Z),
   baseline_missing_keys_Dec_wealth=sum((D(r['original_layer']['Dec_components']['wealth']) for r in cc['rows'] if r['candidate_exact_entry'] is None),Z),
   own_new_replacement_entry_keys=len(new),own_new_replacement_Dec_wealth=sum((D(r['Dec_components']['wealth']) for r in new),Z),
   own_new_replacement_buycash=sum((D(r['cost']) for r in new),Z),not_a_same_hold_counterfactual=True)
save('DEC_EXPOSURE_AND_CAPITAL_BASES.json',caps);save('ORIGINAL122_AND_NEW_REPLACEMENT_BRIDGE.json',post122)
meta=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
base=read(P/'BASELINE_strong_LAYERS.json');bs=defaultdict(list)
for r in base:bs[r['sid']].append(r)
coverage={};stock_effects={};ownwinners={};allstock=[]
for arm in ARMS:
 rows=read(P/(arm+'_strong_LAYERS.json'));by=defaultdict(list)
 for r in rows:by[r['sid']].append(r)
 controls=read(P/(arm+'_strong_FIXED83_94_TAILS.json'));rr=controls['rows'];fixed_sids={r['original_fixed_member']['sid'] for r in rr};matched_sids={r['original_fixed_member']['sid'] for r in rr if r['baseline_current_exact_match'] is not None}
 bytail=defaultdict(list)
 for t in rr:bytail[t['original_fixed_member']['sid']].append(t)
 nohold94=[r for r in rr if r['candidate_no_actual_holding_during_original_tail_interval']];nohold67=[r for r in nohold94 if r['baseline_current_exact_match'] is not None]
 coverage[arm]=dict(original94_members=len(rr),baseline_exact67_members=sum(r['baseline_current_exact_match'] is not None for r in rr),
   no_holding_in_original94_layer_intervals=len(nohold94),no_holding_in_original67_matched_layer_intervals=len(nohold67),
   original94_unique_stocks=len(fixed_sids),original67_unique_stocks=len(matched_sids),
   original94_stocks_with_at_least_one_unheld_winner_interval=sum(any(t['candidate_no_actual_holding_during_original_tail_interval'] for t in tt) for tt in bytail.values()),
   original94_stocks_with_all_original_winner_intervals_unheld=sum(all(t['candidate_no_actual_holding_during_original_tail_interval'] for t in tt) for tt in bytail.values()),
   original94_stocks_never_traded_in_candidate_fullstrong=sum(s not in by for s in fixed_sids),
   candidate_all_entries_in_original94_stocks=sums([r for r in rows if r['sid'] in fixed_sids]),candidate_all_entries_in_original67_stocks=sums([r for r in rows if r['sid'] in matched_sids]),
   nohold94_details=[dict(sid=r['original_fixed_member']['sid'],name=meta[r['original_fixed_member']['sid']]['name'],original_opened=r['original_fixed_member']['opened'],original_closed=r['original_fixed_member']['closed'],baseline_exact_match=r['baseline_current_exact_match'] is not None) for r in nohold94],
   caveat='Binary some-stock-holding in original winner intervals is not same capital allocation. Exact-entry contribution drops are not pure exit damage or total missed stock winners.')
 effects=[]
 for sid in bs.keys()|by.keys():
  b=sums(bs.get(sid,[]));a=sums(by.get(sid,[]));d=a['net']-b['net'];effects.append(dict(sid=sid,name=meta[sid]['name'],baseline_all_strong_entries=b,candidate_all_strong_entries=a,net_difference=d,stock_in_original94=sid in fixed_sids,stock_in_original67=sid in matched_sids))
 stock_effects[arm]=dict(positive=sorted([x for x in effects if x['net_difference']>0],key=lambda x:x['net_difference'],reverse=True)[:5],negative=sorted([x for x in effects if x['net_difference']<0],key=lambda x:x['net_difference'])[:5],original_winner_stock_rows=[x for x in effects if x['stock_in_original94']])
 # Inherited 30% layer evaluation boundary only, explicitly NOT a new control
 # cohort, exit rule or outcome-selected threshold; fixed83/94 remain intact.
 tails=[r for r in rows if D(r['net'])/D(r['cost'])>=D('.30')]
 ownwinners[arm]=dict(evaluation_only_boundary='own actual layer terminal net / actual buyfee-inclusive cost >=30%; fixed controls unchanged',own_tail=sums(tails),all_layers=sums(rows),
   top_stocks=sorted([dict(sid=s,name=meta[s]['name'],**sums(rrr)) for s,rrr in by.items()],key=lambda x:x['net'],reverse=True)[:5],
   note='Endpoint includes marked open equity and AR. Own profitable layers do not replace fixed original94/67 and do not prove future repeatability.')
save('STRONG_ORIGINAL94_67_ALL_ENTRY_STOCK_COVERAGE.json',coverage);save('STRONG_ALL_ENTRY_STOCK_EFFECTS.json',stock_effects);save('CANDIDATE_OWN_WINNER_DIAGNOSTIC.json',ownwinners)
SRC[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('SUPPLEMENT_SOURCE_SHA256.json',SRC)
print('CAPITAL',json.dumps(caps,default=str));print('COVERAGE',json.dumps(coverage,default=str));print('OWN_WINNERS',json.dumps(ownwinners,default=str))
