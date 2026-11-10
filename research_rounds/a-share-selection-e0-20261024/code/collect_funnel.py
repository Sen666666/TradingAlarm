"""Lossless source stays immutable; extract compact diagnostic counters live.

Each candidate/day counted once from the first recommendation, while executor
acknowledgements remain separate. This never writes strategy state or orders.
"""
from pathlib import Path
import json,zlib,codecs,time,collections,datetime,sys
import pandas as pd
from build_inputs import HERE,read,write,now,ref

def main(group=None):
 if group not in (None,'G0','G1'):raise ValueError('Unknown group')
 out=HERE/('funnel-v2-'+group if group else 'funnel-v2');out.mkdir(exist_ok=False)
 annual=pd.read_csv(HERE/'opportunities-v2/annual-all-current-A.csv',keep_default_na=False)
 known_bse={x['code']+'.BJ' for x in read(HERE/'audit/bse-listing-facts.json')['rows']}
 # Keep global raw-sample outcomes, but qualified top20 is the main comparable
 # opportunity set. Unverified BSE history is never called an A-entry opportunity.
 eligible=annual.current_cap_disposition.eq('selected')
 qualified=annual.loc[eligible].sort_values(['year','adjusted_price_return'],ascending=[True,False]).groupby('year').head(20)
 write(out/'qualified-annual-top20.json',qualified.to_dict('records'))
 targets=collections.defaultdict(dict)
 for x in read(HERE/'opportunities-v2/annual-top20.json')+qualified.to_dict('records'):
  if x['symbol'].endswith('.BJ') and x['symbol'] not in known_bse:continue
  targets[int(x['year'])][x['symbol']]=f'annual:{x["symbol"]}:{int(x["year"])}'
 episodes=read(HERE/'opportunities-v2/structural-winners.json');events=[]
 for x in episodes:
  if x['current_cap_disposition']!='selected':continue
  start=max(x['entry_date'],'2015-01-01');end=(pd.Timestamp(x['end_date'])+pd.Timedelta(days=1)).date().isoformat()
  events.append((start,1,x['symbol'],'episode:'+x['episode_id']));events.append((end,-1,x['symbol'],'episode:'+x['episode_id']))
 events.sort();event_cursor=0;active=collections.defaultdict(set);day=None;interest={};totals=collections.defaultdict(collections.Counter);details={};daily=[];lines=0
 def consume(x):
  nonlocal day,event_cursor,interest,lines
  aid=x['account'];date=x['at'][:10];ack=x['ack'];decisions=ack['decisions'];first=decisions[0];lines+=1
  if date!=day:
   day=date
   while event_cursor<len(events) and events[event_cursor][0]<=day:
    _,direction,sid,key=events[event_cursor];event_cursor+=1
    if direction==1:active[sid].add(key)
    else:active[sid].discard(key)
   interest={sid:set(v) for sid,v in active.items() if v}
   for sid,key in targets[int(day[:4])].items():interest.setdefault(sid,set()).add(key)
  elig={e['security_id']:e for e in first['eligibility']};mem={m['security_id']:m for m in ack['memories']};occ={o['security_id']:o for o in ack['occupancy']}
  accepted=set(ack['accepted']);exec_rej=dict(ack['rejected']);strategy_rej={sid:reason for d in decisions for sid,reason in d['rejected']}
  fallbacks=sorted(set(v for d in decisions for v in d['ranking_fallbacks']))
  row=dict(account=aid,date=day,eligible_true=sum(e['q'] is True for e in elig.values()),eligible_false=sum(e['q'] is False for e in elig.values()),
   eligible_unknown=sum(e['q'] is None for e in elig.values()),waiting=len(first['waiting']),recommended=len(first['selected']),accepted=len(accepted),
   execution_rejections=len(exec_rej),ranking_fallback=bool(fallbacks),ranking_fallbacks='|'.join(fallbacks))
  daily.append(row)
  totals[aid].update(dict(decision_days=1,**{k:row[k] for k in ['eligible_true','eligible_false','eligible_unknown','accepted','execution_rejections','ranking_fallback']}))
  for sid,keys in interest.items():
   e=elig.get(sid);reasons=e['reasons'] if e else ['outside_fixed_strategy_pool']
   if e is None:reason='current_cap_not_selected_or_identity_unknown'
   elif e['q'] is None:reason='data_or_identity_unknown'
   elif e['q'] is False:
    reason='stock_not_confirmed' if 'stock_up:false' in reasons else 'sector_not_valid' if 'sector_up:false' in reasons else 'other_eligibility_false'
   elif sid in accepted:reason='reservation_accepted'
   elif sid in occ and occ[sid]['has_position']:reason='already_held'
   elif sid in occ and occ[sid]['pending_buy']:reason='pending_buy_not_yet_filled'
   elif sid in exec_rej:reason='execution_rejected:'+exec_rej[sid]
   elif sid in strategy_rej:reason='selection_rejected:'+strategy_rej[sid]
   elif mem.get(sid,{}).get('waiting'):reason='waiting_not_selected'
   else:reason='no_new_eligibility_edge_or_consumed_candidate'
   for key in keys:
    full=aid+'|'+key
    if full not in details:details[full]=dict(account=aid,key=key,symbol=sid,counts=collections.Counter(),component_counts=collections.Counter(),rank_fallback_days=0,first_q_true=None)
    d=details[full];d['counts'][reason]+=1;d['component_counts'].update(reasons);d['rank_fallback_days']+=bool(fallbacks)
    if e and e['q'] is True and d['first_q_true'] is None:
     d['first_q_true']=dict(at=x['at'],reason=reason,recommendations=first['selected'],actual_reservations=ack['accepted'],
      occupants=[dict(security_id=o['security_id'],has_position=o['has_position'],pending_buy=o['pending_buy'],sector_id=o['sector_id']) for o in ack['occupancy']],ranking_fallbacks=fallbacks)
  if lines%1000==0:
   write(out/'progress.json',dict(lines=lines,last_date=day,last_account=aid,diagnostic_groups=len(details),recorded_at=now()))
 decompressor=zlib.decompressobj(16+zlib.MAX_WBITS);decoder=codecs.getincrementaldecoder('utf-8')();buffer='';position=0
 path=HERE/'accounts-v2/groups'/group/'decisions.jsonl.gz' if group else HERE/'accounts-v2/decisions.jsonl.gz'
 while not path.exists():
  summary=HERE/'accounts-v2/summary.json'
  if summary.exists() and read(summary).get('status')=='failed_partial_run':raise RuntimeError('Main failed before merge')
  time.sleep(1)
 with path.open('rb') as source:
  while True:
   block=source.read(1024*1024)
   if block:
    position+=len(block);buffer+=decoder.decode(decompressor.decompress(block))
    while '\n' in buffer:
     line,buffer=buffer.split('\n',1)
     if line:consume(json.loads(line))
    if decompressor.eof:break
   else:
    summary=HERE/'accounts-v2/summary.json'
    if summary.exists() and read(summary).get('status')=='failed_partial_run':raise RuntimeError('Main account run failed; compact extraction incomplete')
    time.sleep(1)
 assert not buffer.strip()
 pd.DataFrame(daily).to_csv(out/'daily-candidate-counts.csv',index=False,encoding='utf-8-sig')
 write(out/'target-counters.json',list(details.values()));write(out/'totals.json',{k:dict(v) for k,v in totals.items()})
 write(out/'summary.json',dict(recorded_at=now(),source=ref(path),decision_rows=lines,diagnostic_groups=len(details),
  counting_unit='candidate-day; not trades or unique stocks; one eligibility evaluation per account/day, executor rejection separate',
  source_retained_full=True,unverified_nonqualified_BSE_annual_outcomes_excluded_from_A_opportunity_labels=True))
 print({'decision_rows':lines,'diagnostic_groups':len(details)},flush=True)

if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else None)
