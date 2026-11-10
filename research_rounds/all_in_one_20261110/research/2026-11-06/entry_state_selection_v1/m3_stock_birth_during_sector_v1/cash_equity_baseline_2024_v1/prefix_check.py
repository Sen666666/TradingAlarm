"""Physical consumer-input truncation regression; does not certify upstream PIT features."""
import engine as s
from engine import pd,Path
from run import compare_table
cut=pd.Timestamp('2024-11-07');assert (s.O/'economic/QA.json').exists()
s.reset(True);s.ev=s.ev[s.ev.day<=cut];s.cal=s.cal[s.cal<=cut];s.sector={k:{d:v for d,v in m.items() if d<=cut} for k,m in s.sector.items()}
oldload=s.load
for book in [s.raw,s.facts,s.cp]:
 for obj in book.values():obj.frame=obj.frame.loc[:cut]
s.capacity={sid:{d:v for d,v in m.items() if d<=cut} for sid,m in s.capacity.items()}
def load(sid):
 oldload(sid)
 for book in [s.raw,s.facts,s.cp]:book[sid].frame=book[sid].frame.loc[:cut]
 s.capacity[sid]={d:v for d,v in s.capacity[sid].items() if d<=cut}
s.load=load;s.run_window('A_UNION_B',cut);checks={}
for name,arr,keys,datecol in [('ACTIONS',s.actions,['round_id','day','side'],'day'),('DECISIONS',s.decisions,['event_id'],'day'),('RANKING_AUDIT',s.ranking_audit,['event_id'],'day'),('CLAIM_LEDGER',s.claim_ledger,['round_id','economic_event_id','day','event'],'day'),('REGISTRATIONS',s.registrations,['economic_event_id'],'inventory_snapshot_day')]:
 b=pd.read_csv(s.O/'economic'/(name+'.csv'));b=b[pd.to_datetime(b[datecol])<=cut];a=pd.DataFrame(arr);cols=[c for c in b if c!='available_from'];checks[name]=compare_table(a,b,keys,cols)
checks.update(cutoff=str(cut.date()),raw_facts_cp_capacity_calendar_births_sector_truncated=True,source_prepared_feature_PIT_certified=False,engine_sha256=s.sha(s.O/'engine.py'),driver_sha256=s.sha(s.O/'run.py'))
s.save(s.O/'PREFIX_QA.json',checks);print('PREFIX_PASS',checks)
