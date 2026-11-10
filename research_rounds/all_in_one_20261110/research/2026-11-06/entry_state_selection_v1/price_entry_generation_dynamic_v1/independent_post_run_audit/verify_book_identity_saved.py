"""Read saved execution-book identity; never imports the consumer."""
from pathlib import Path
from collections import Counter,defaultdict
import json,csv,hashlib,argparse
D=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/price_entry_generation_dynamic_v1');O=D/'independent_post_run_audit'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open() as f:return list(csv.DictReader(f))
def audit(w):
    p=D/('gate_'+w);books=read(p/'EXECUTION_BOOKS.json');rs={r['round_id']:r for r in rows(p/'joint/ROUNDS.csv')};ar=defaultdict(list)
    for a in rows(p/'joint/ACTIONS.csv'):ar[a['round_id']].append(a)
    issues=[];counts=Counter();above=[]
    for rid,b in books.items():
        rd=rs[rid];resp=b['responsibility'];counts['books']+=1
        for k in ['actual_order_id','actual_ack','actual_fill']:
            if resp.get(k)!='NOT_PROVIDED':issues.append([rid,'REAL_BROKER_CLAIM',k,resp.get(k)])
        if resp.get('evidence_domain')!='PROXY':issues.append([rid,'NOT_PROXY'])
        lots=b['lots'];orders=b['orders'];parents=b['parents'];rem=sum(x['remaining'] for x in lots.values())
        if resp['held_qty']!=rem:issues.append([rid,'BOOK_HELD_MISMATCH'])
        rawheld=sum(float(a['q'])*(1 if a['side'].startswith('buy') else -1) for a in ar[rid])
        if rawheld!=rem:issues.append([rid,'ACTION_HELD_MISMATCH'])
        for role,parent in parents.items():
            t=parent['target'];pid=t['parent_id'];counts['parents']+=1
            qs=sum(x['quantity'] for x in lots.values() if x['parent_id']==pid)
            if qs!=parent['filled_F'] or not 0<=qs<=t['target_Q']:issues.append([rid,role,'FIXED_Q_F_MISMATCH'])
            if t['registered_known_at']['day']!=t['decision_open'] or t['registered_known_at']['sequence']!=20:issues.append([rid,role,'TARGET_NOT_AT_OPEN'])
            if t['role']=='PROBE':
                if t['budget']!=24000:issues.append([rid,role,'PROBE_BUDGET'])
                if rd['close_q'] and t['target_Q']>float(rd['close_q']):above.append(dict(round_id=rid,sid=rd['sid'],close_q=float(rd['close_q']),open_target_Q=t['target_Q'],open_day=t['decision_open']))
            elif t['role']=='ADD' and t['budget']!=48000:issues.append([rid,role,'ADD_BUDGET'])
        for oid,order in orders.items():
            counts['orders']+=1
            if order['evidence_domain']!='PROXY':issues.append([rid,oid,'ORDER_NOT_PROXY'])
            if order['registered_known_at']['day']!=order['decision_open'] or order['registered_known_at']['sequence']!=20:issues.append([rid,oid,'ORDER_PHASE'])
            if order['terminal_filled'] not in (None,order['quantity']):issues.append([rid,oid,'PARTIAL_UNEXPECTED',order['terminal_filled'],order['quantity']])
            if order['side']=='BUY' and order['terminal_filled']:
                ll=[x for x in lots.values() if x['lot_id'].startswith(oid+':')]
                if sum(x['quantity'] for x in ll)!=order['terminal_filled']:issues.append([rid,oid,'LOT_FILL_MISMATCH'])
                if any(x['known_at']['day']!=order['decision_open'] or x['known_at']['sequence']!=30 for x in ll):issues.append([rid,oid,'FILL_PHASE'])
    out=dict(window=w,status='PASS_SAVED_BOOK_IDENTITIES' if not issues else 'FAIL_REVIEW_REQUIRED',economic_runs=0,counts=dict(counts),open_targets_above_close_feasibility_quantity=len(above),above_close_examples=above[:10],issues=issues,limitation='This verifies identities and saved phases. It does not prove real fills or independently recompute strategy sizing. Partial/zero-fill continuation contract is established by pre-run synthetic checks; saved path may not exercise it.')
    dest=O/('BOOK_IDENTITIES_'+w+'.json')
    with dest.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(out,ensure_ascii=False));print(dest,sha(dest))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--window',required=True);audit(ap.parse_args().window)
