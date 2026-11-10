"""Group already frozen information-clock states; no new indicators/accounts."""
from pathlib import Path
from collections import Counter
import json,hashlib
O=Path(__file__).resolve().parent;T=O.parent;P=T/'market_gross_admission_native_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
windows={};sources={};total=0
for win,expected in [('long',726),('strong',242)]:
 p=P/f'prepared/{win}/MARKET_INFO_FULL_CLOCKS.json';r=read(p);assert r['passed'] and r['new_accounts']==0;sources[str(p)]=sha(p);rows=r['all_scheduled_OPEN_CLOSE'];assert len(rows)==expected*2;total+=len(rows);clocks={}
 for clock,hour in [('OPEN','09:30'),('CLOSE','15:10')]:
  rr=[x for x in rows if hour in x['at']];assert len(rr)==expected and len({x['at'][:10] for x in rr})==expected
  segments=[];counts=Counter();current=None
  for i,x in enumerate(rr):
   assert x['state'] in ('DOWN','NOT_DOWN','UNKNOWN');assert x['available_at']<=x['at']
   if current is None or current['state']!=x['state']:
    counts[x['state']]+=1;current=dict(segment_id=f"{clock}_{x['state']}_{counts[x['state']]:02}",state=x['state'],start=x['at'][:10],end=x['at'][:10],previous_execution_close=rr[i-1]['at'][:10] if i else None,first_information_day=x['day'],last_information_day=x['day'],days=[],source_information_clocks=[]);segments.append(current)
   current['end']=x['at'][:10];current['last_information_day']=x['day'];current['days'].append(x['at'][:10]);current['source_information_clocks'].append(dict(at=x['at'],information_day=x['day'],available_at=x['available_at']))
  for g in segments:g['observations']=len(g['days'])
  assert sum(g['observations'] for g in segments)==expected
  clocks[clock]=dict(state_counts=dict(Counter(x['state'] for x in rr)),segments=segments)
 windows[win]=dict(expected_days=expected,source_clock_path=str(p),source_clock_sha256=sha(p),clocks=clocks)
oldpath=T/'ma63_down_replenishment_v1/ALL_SPELLS_FROZEN.json';old=read(oldpath);sources[str(oldpath)]=sha(oldpath)
if isinstance(old,dict):
 original=old.get('spells',old.get('all_spells'))
 assert original is not None,list(old)
else:original=old
down=[x for x in windows['long']['clocks']['OPEN']['segments'] if x['state']=='DOWN'];cutoff=original[-1]['days'][-1];clipped=[(x,[d for d in x['days'] if d<=cutoff]) for x in down if x['start']<=cutoff];assert len(clipped)==len(original)==9
for (new,days),prior in zip(clipped,original):
 assert days==prior['days'] and new['previous_execution_close']==prior['previous_close'],(new['segment_id'],prior['spell_id'])
 new['original_audited_DOWN_id']=prior['spell_id'];new['original_audited_cutoff']=prior['days'][-1];new['identical_entire_audited_interval']=new['days']==prior['days']
save(O/'ORIGINAL_NINE_AUDITED_2022_2023_DOWN_BOUNDARIES.json',dict(source=str(oldpath),source_sha256=sha(oldpath),source_cutoff=cutoff,spells=original,all_prefix_days_and_previous_CLOSE_exact=True,scope='Original9 are2022–23 diagnostic boundaries. Full-window DOWN09 continues into2024; do not equate its full interval to prior cutoff.'))
save(O/'ALL_PREDECLARED_MARKET_STATE_SEGMENTS.json',dict(status='FROZEN_EXISTING_CLOCK_SEGMENTS_ALL_STATES_NO_ACCOUNT_READS',windows=windows,clock_rows=total,old9_DOWN_prefix_through_2023_cutoff_exact=True,sources=sources,code_sha256=sha(__file__),new_features=0,new_accounts=0,scope='Information-clock diagnostic grouping only; preserve every positive/negative/zero future outcome, no economic selection. OPEN uses last completed CLOSE; no future labels become signals. Original9 only through2023 cutoff; full-long has12DOWN spells.'))
binding=read(P/'ARCHIVED_B_CONTROL_BINDING.json')
for win,r in binding.items():
 for p,h in r['source_sha256'].items():assert sha(p)==h,(win,p,'archived identity changed')
sources[str(P/'ARCHIVED_B_CONTROL_BINDING.json')]=sha(P/'ARCHIVED_B_CONTROL_BINDING.json')
save(O/'ANALYSIS_INPUT_FREEZE.json',dict(sources=sources,archived_B_control=binding,B_saved_analysis_only={w:str(T/f'capacity_cost_guard_analysis_v1/full_{w}_v1') for w in ['long','strong']},segment_sha256=sha(O/'ALL_PREDECLARED_MARKET_STATE_SEGMENTS.json'),protocol_sha256=sha(O/'PROTOCOL.txt'),new_accounts=0,new_B_books_or_views=0,full_output_books_read=0))
print('FROZEN',total,{w:{c:(v['state_counts'],len(v['segments'])) for c,v in z['clocks'].items()} for w,z in windows.items()},flush=True)
