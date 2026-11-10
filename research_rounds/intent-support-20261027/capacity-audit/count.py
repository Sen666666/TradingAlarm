import pathlib,json,gzip,csv,collections
P=pathlib.Path(__file__).resolve().parents[1];O=P/'capacity-audit';ROOT=P.parents[1]
meta={r['symbol']:r for r in csv.DictReader((ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').open())}
windows={'full':('2023-12-29','2026-10-27'),'local_pullback':('2025-11-24','2025-12-08'),'after_sale':('2025-11-26','2026-10-27')};data=[]
with gzip.open(P/'S0/accounts-v2/decisions.jsonl.gz','rt') as f:
 for l in f:
  r=json.loads(l)
  if r['account'] in [x+'__S0_base' for x in ['ACT','W3','W10','F','W10F']]:data.append(r)
reports=[];details=[]
for account in sorted({r['account'] for r in data}):
 a=json.loads((P/'S0/accounts-v2'/f'{account}.json').read_text());risk={r['at']:r['on'] for r in a['audit_log'] if r['kind']=='risk_checkpoint'}
 for label,(start,end) in windows.items():
  if label!='full' and account!='F__S0_base':continue
  rows=[r for r in data if r['account']==account and start<=r['at'][:10]<=end];counts=collections.Counter();unique=set();by=collections.Counter();episodes=0;last={};new=[]
  for ix,r in enumerate(rows):
   counts['decision_days']+=1
   if not risk[r['at']]:counts['paused_days']+=1;continue
   occ=r['occupancy'];occupied={o['security_id'] for o in occ};held=[o for o in occ if o['has_position']];sectors=collections.Counter(o['sector_id'] for o in occ);existing=collections.Counter(o['sector_id'] for o in held)
   eligible=set(r['eligible']);counts['qualified_stock_days_including_held']+=len(eligible)
   for sid in eligible-occupied-set(r['accepted']):
    counts['qualified_unheld_unaccepted_stock_days']+=1;sector=meta[sid]['sector_id'];total=len(occupied)>=6;single=sectors[sector]>=2;industry=sector not in sectors and len(sectors)>=3
    reason='six_slots' if total else 'two_per_industry' if single else 'three_industries' if industry else 'not_capacity'
    counts[reason]+=1
    if reason=='not_capacity':continue
    counts['blocked']+=1;counts['overlap_two_per_industry']+=single;counts['overlap_three_industries']+=industry
    priorblock=len(held)>=6 or existing[sector]>=2 or (sector not in existing and len(existing)>=3);counts['already_blocked_by_existing_holdings']+=priorblock;counts['blocked_after_other_candidates_accepted']+=not priorblock
    unique.add(sid);by[sid]+=1
    if last.get(sid)!=ix-1:episodes+=1
    last[sid]=ix
    new.append(dict(account=account,window=label,date=r['at'][:10],symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],primary_reason=reason,total_full=total,industry_two_full=single,three_industries_full=industry,existing_holdings=len(held),after_decision_occupancy=len(occ),other_accepted=','.join(r['accepted'])))
  details+=new;reports.append(dict(account=account,window=label,start=start,end=end,counts=dict(counts),unique_stocks=len(unique),consecutive_blocked_episodes=episodes,top20=[dict(symbol=s,name=meta[s]['name'],days=n) for s,n in by.most_common(20)]))
(O/'summary.json').write_text(json.dumps({'definition':'Qualified unheld/unaccepted candidate stock-day with final actual occupancy blocking admission; not submitted rejected orders, not counterfactual profit. Exclusive primary reason six first then per-industry two then three industries; overlaps reported separately. Existing hold vs same-day newly reserved split. Initial decision 2023-12-29 included.','reports':reports},ensure_ascii=False,indent=2))
with (O/'details.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
for r in reports:print(r['account'],r['window'],r['counts'],'unique',r['unique_stocks'],'episodes',r['consecutive_blocked_episodes']);print('top',r['top20'][:5])
