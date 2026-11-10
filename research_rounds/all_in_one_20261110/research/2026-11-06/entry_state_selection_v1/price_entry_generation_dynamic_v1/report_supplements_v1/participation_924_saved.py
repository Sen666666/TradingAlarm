"""Read-only inventory/action reconstruction on 2024-09-24 from sealed ledgers."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import csv,sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from runtime import O,SOURCE,sha,read
from run_economic import save
CUT='2024-09-24'
def rows(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def main():
    dest=O/'report_supplements_v1/participation_924';dest.mkdir(exist_ok=False)
    result={};protected={}
    for arm,d in [('baseline',SOURCE/'economic_2024'),('joint',O/'gate_2024')]:
        ps=[d/'joint/ROUNDS.csv',d/'joint/ACTIONS.csv']
        protected.update({str(p):sha(p) for p in ps});rr={r['round_id']:r for r in rows(ps[0])};aa=rows(ps[1]);qty=defaultdict(lambda:D(0));day_actions=[];in_period=[]
        for a in aa:
            side=a['side'];assert side in {'buy_core','buy_add','sell_add','sell_all'},side
            day=a['day'][:10];r=rr[a['round_id']]
            if day<=CUT:qty[a['round_id']]+=D(a['q'])*(1 if side.startswith('buy') else -1)
            if day==CUT:day_actions.append(dict(a,owner_lane=r['owner_lane'],name=r['name']))
            if side=='buy_core' and '2024-09-20'<=day<='2024-10-08':in_period.append(dict(a,owner_lane=r['owner_lane'],name=r['name']))
        held=[]
        for rid,q in qty.items():
            assert q>=0,(rid,q)
            if not q:continue
            r=rr[rid];statusday=r['status_day'][:10]
            if 'UNKNOWN' in r['status']:assert len(statusday)==10,(rid,'UNKNOWN_DATE_REQUIRED')
            unknown_asof='UNKNOWN' in r['status'] and statusday<=CUT
            held.append(dict(sid=r['sid'],name=r['name'],round_id=rid,owner_lane=r['owner_lane'],quantity_after_924_open_actions=int(q),initial_entry_day=r['entry_day'],signal_day=r['signal_day'],entered_on_924=r['entry_day'][:10]==CUT,already_held_before_924=r['entry_day'][:10]<CUT,unresolved_by_924=unknown_asof,scope='CONDITIONAL_PROXY_INVENTORY_NOT_ACTUAL_ACK_OR_FILL'))
        assert len({r['sid'] for r in held})==len(held),'OVERLAPPING_STOCK_OWNERS'
        result[arm]=dict(holdings_after_924_open_actions=held,actions_on_924=day_actions,new_initial_entries_0920_to_1008=in_period,summary=dict(held_stocks=len(held),held_by_lane=dict(Counter(x['owner_lane'] for x in held)),already_held_before_924=sum(x['already_held_before_924'] for x in held),new_on_924=sum(x['entered_on_924'] for x in held),unresolved_asof_924=sum(x['unresolved_by_924'] for x in held),action_counts=dict(Counter(x['side'] for x in day_actions)),initial_entries_0920_to_1008=len(in_period),period_initial_entries_by_lane=dict(Counter(x['owner_lane'] for x in in_period))))
    for p,h in protected.items():assert sha(p)==h
    save(dest/'ACTUAL_MODEL_PARTICIPATION_924.json',dict(cut=CUT,model='ORIGINAL_OPEN_5BP_FULL_FILL_CONDITIONAL_PROXY',meaning='Actual occurrences in saved model, not real trades. All actual ACK/fill NOT_PROVIDED; tradability UNKNOWN. Frozen cases participation_924 means only new initial entry dates 09/20..10/08; this file additionally includes preexisting 09/24 inventory and that day actions. UNKNOWN is kept separately, not assumed sold or zero.',arms=result,source_sha256=protected,script_sha256=sha(__file__),economic_runs=0,unknown_not_zero=True))
    save(dest/'OUTPUT_SHA256.json',{p.name:sha(p) for p in dest.iterdir() if p.is_file()})
    print({arm:result[arm]['summary'] for arm in result},flush=True)
if __name__=='__main__':main()
