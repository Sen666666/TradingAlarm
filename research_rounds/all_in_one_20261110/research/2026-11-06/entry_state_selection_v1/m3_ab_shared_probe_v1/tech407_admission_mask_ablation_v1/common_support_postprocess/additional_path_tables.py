"""Only event-matched tables over already saved actual arms; no replay."""
from pathlib import Path
import collections,sys
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from runner import read,save
START=pd.Timestamp('2024-09-24');END=pd.Timestamp('2024-10-08')

def table(arm):
    out=ROOT/('run_'+arm+'_once');dec=read(out/'DECISIONS.json');aa=read(out/'ACTIONS.json');audit=read(out/'AUDIT.json');sr=read(out/'SOURCE_ROUNDS.json')
    ds=[x for x in dec if START<=pd.Timestamp(x['day'])<=END];selected=[x for x in ds if x['selected']];records=[]
    for d in selected:
        rid=d['round_id'];fills=[x for x in aa if x['round_id']==rid and x['side']=='buy_core'];rejects=[x for x in audit if x.get('round_id')==rid and x['type']=='BUDGET_REJECTED' and x['kind']=='INIT']
        terminal=[x for x in sr if x['round_id']==rid]
        reason_sets=[set(r for t in x['trials'] for r in t['reasons']) for x in rejects]
        records.append(dict(event_id=d['event_id'],sid=d['sid'],round_id=rid,signal_day=d['day'],selected_rank=d['selected_rank'],actual_initial_fill=fills,shared_budget_rejects=rejects,
            reason_union=sorted(set().union(*reason_sets)) if reason_sets else [],source_terminal_records_if_never_filled=terminal if not fills else []))
    reasons=collections.Counter(r for x in records for r in x['reason_union'])
    return dict(signal_window=dict(start=str(START.date()),end=str(END.date())),evaluated_candidates=len(ds),CLOSE_decision_counts=dict(collections.Counter(x['decision'] for x in ds)),selected_pending=len(selected),
        actual_next_OPEN_initial_fills=sum(bool(x['actual_initial_fill']) for x in records),actual_shared_budget_rejected=sum(bool(x['shared_budget_rejects']) for x in records),other_nonfills=sum(not x['actual_initial_fill'] and not x['shared_budget_rejects'] for x in records),
        shared_reject_reason_counts=dict(reasons),records=records,
        note='Each pending receipt matched by its actual event and round, including Oct9 fills of Oct8 signals. Do not confuse with OPEN-clock Sep24-Oct8 table, which includes Sep23 signals and excludes Oct9 executions.')
def main():
    value={a:table(a) for a in ['all1709','tech407']}
    r=read(ROOT/'path_reporting/ACTUAL_PATH_REPORT.json');d=r['divergence']['all_decision_divergences']
    impactful=[x for x in d if (x['all1709'] or {}).get('selected') or (x['tech407'] or {}).get('selected')]
    value['earliest_selected_pending_divergence']=impactful[0] if impactful else None
    # Fixed named candidates get their actual rejection trials, not hypothetical PnL.
    cases={}
    for arm in ['all1709','tech407']:
        out=ROOT/('run_'+arm+'_once');ar=read(out/'ARCHIVES.json');audit=read(out/'AUDIT.json')
        cases[arm]=[x for x in audit if x.get('round_id') in ar and ar[x['round_id']]['sid'] in ('300085.SZ','300570.SZ','000833.SZ') and x['type'] in ('RESERVED','BUDGET_REJECTED','UNKNOWN')]
    value['fixed_case_reservation_audits']=cases
    save(HERE/'EVENT_MATCHED_WINDOW_FUNNEL.json',value);print('SAVED_EVENT_MATCHED_FUNNEL')
if __name__=='__main__':main()
