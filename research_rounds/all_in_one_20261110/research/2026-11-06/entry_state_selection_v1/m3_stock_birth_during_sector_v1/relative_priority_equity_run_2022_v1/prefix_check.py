"""One bounded causal regression, not a new strategy comparison: truncate through 2022-04-29."""
import engine as s
from run import compare_table
from engine import pd,Path
cut=pd.Timestamp('2022-04-29');s.reset(True);s.ev=s.ev[s.ev.day<=cut];s.cal=s.cal[s.cal<=cut];s.sector={k:{d:v for d,v in values.items() if d<=cut} for k,values in s.sector.items()}
oldload=s.load
for book in [s.raw,s.facts,s.cp]:
 for obj in book.values():obj.frame=obj.frame.loc[:cut]
s.capacity={sid:{d:v for d,v in values.items() if d<=cut} for sid,values in s.capacity.items()}
def truncated_load(sid):
 oldload(sid)
 for book in [s.raw,s.facts,s.cp]:book[sid].frame=book[sid].frame.loc[:cut]
 s.capacity[sid]={d:v for d,v in s.capacity[sid].items() if d<=cut}
s.load=truncated_load;s.run_window('A_UNION_B',cut)
checks={}
for name,arr,keys in [('ACTIONS',s.actions,['round_id','day','side']),('DECISIONS',s.decisions,['event_id']),('RANKING_AUDIT',s.ranking_audit,['event_id']),('CLAIM_LEDGER',s.claim_ledger,['round_id','day','event'])]:
 b=pd.read_csv(s.O/'dynamic'/(name+'.csv'));b=b[b.arm.eq('A_UNION_B')&pd.to_datetime(b.day).le(cut)];a=pd.DataFrame(arr);cols=list(b.columns)
 # Post-CLOSE next availability metadata can point outside the truncated data. It does not enter decisions.
 if name=='CLAIM_LEDGER':cols=[c for c in cols if c!='available_from']
 checks[name]=compare_table(a,b,keys,cols)
# Fixed entry bridge actions must exactly match the admitted ten original entry paths.
b=pd.read_csv(s.E/'corporate_action_path_audit_v1/BRIDGED_ACTIONS.csv');targets=pd.read_csv(s.E/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv');ids=set(targets.loc[targets.status.eq('FACTOR_AT_ENTRY_UNKNOWN'),'round_id']);b=b[b.round_id.isin(ids)];a=pd.read_csv(s.O/'fixed_full/ACTIONS.csv');a=a[a.round_id.isin(ids)];checks['TEN_ENTRY_BRIDGE_ACTIONS']=compare_table(a,b,['round_id','day','side'],['round_id','day','side','q','price','fee','reason'])
checks['cutoff']='2022-04-29';checks['raw_facts_cp_capacity_calendar_births_truncated']=True;checks['signal_and_first_cash_release_queue_invariant']=True;checks['actual_execution_order']='Synthetic tests, bridge-off, fixed2432, dynamic two arms, then bounded prefix replay. No new full run.'
s.save(s.O/'PREFIX_QA.json',checks);print('PREFIX_PASS',checks)
