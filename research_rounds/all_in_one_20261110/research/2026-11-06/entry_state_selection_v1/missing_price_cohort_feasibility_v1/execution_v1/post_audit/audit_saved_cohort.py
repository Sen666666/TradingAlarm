"""Independent saved-ledger audit. Never imports/runs a historical consumer."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
from types import SimpleNamespace
import argparse, ast, csv, datetime, hashlib, json, math, sys, time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent.parent
R=O.parent.parent
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
sys.path.insert(0,str(O));sys.path.insert(0,str(B/'code'))
from cohort_config import CONFIG,TEMPLATE_ID
from report_adapter import financial_coverage
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def csvrows(p):
    with Path(p).open(newline='') as f: return list(csv.DictReader(f))
def dec(v, default=None):
    if v is None or v=='': return default
    z=D(str(v));return z if z.is_finite() else default
def day(v): return str(v)[:10] if v not in (None,'') else None
def truth(v): return v is True or str(v).lower()=='true'
def clock(v): return (v['day'],int(v['sequence']))
def norm(v): return json.dumps(v,sort_keys=True)
def approximately(a,b): return a is not None and b is not None and abs(D(str(a))-D(str(b)))<D('0.0000001')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=list(CONFIG),required=True)
    ap.add_argument('--stage',choices=['cash','full'],default='full');args=ap.parse_args()
    w=args.window;dest=O/('economic_'+w);stage=args.stage;started=time.monotonic()
    assert (dest/'ECONOMIC_LOOP_COMPLETE.json').exists(),'NO_SAVED_COMPLETE_LOOP'
    if stage=='full':assert (dest/'COMPLETE.json').exists(),'LABELS_NOT_COMPLETE'
    out=O/'post_audit'/('INDEPENDENT_POST_'+w+'_'+stage.upper()+'.json')
    assert not out.exists(),'NEVER_OVERWRITE_AUDIT'
    inputs=read(O/'FROZEN_INPUT_SHA256.json');code=read(O/'FROZEN_CODE_SHA256.json')
    auth=read(O/'ROOT_EXTENSION_AUTHORIZATION.json')
    failures=[];checks=Counter();errors=defaultdict(float);artifacts={}
    def check(ok,category,detail=None):
        checks[category]+=1
        if not bool(ok):failures.append(dict(check=category,detail=detail))
    def near(a,b,category,detail=None):
        aa,bb=dec(a),dec(b);ok=approximately(aa,bb);check(ok,category,detail)
        if aa is not None and bb is not None:errors[category]=max(errors[category],float(abs(aa-bb)))
    def source(p):
        p=Path(p).resolve();h=sha(p);check(inputs.get(str(p))==h,'consumed_source_hash',str(p));return p
    def saved(name):
        p=dest/name;artifacts[name]=sha(p);return p
    final_source_verified=False
    if stage=='full':
        complete=read(saved('COMPLETE.json'));sv=read(saved('SOURCE_VERIFIED.json'))
        check(sv.get('all_sources_passed') is True and sv.get('old_tree_unchanged') is True,'runner_final_source_verified')
        check(complete['summary_sha256']==sha(dest/'SUMMARY.json') and complete['old_outputs_unchanged'] is True,'complete_summary_hash')
        final_source_verified=sv.get('all_sources_passed') is True
    for n,h in code.items():check(sha(O/n)==h,'frozen_code',n)
    for p,h in read(O.parent/'OLD_TREE_SHA256_BEFORE.json').items():check(sha(p)==h,'protected_old_file',p)
    for p,h in read(saved('joint/SOURCE_HASHES.json')).items():check(inputs.get(str(Path(p).resolve()))==h,'saved_source_map',p)
    for n,h in read(saved('joint/OUTPUT_HASHES.json')).items():check(sha(dest/'joint'/n)==h,'saved_ledger_hash',n)
    check(auth['independent_review_sha256']==sha(O/'INDEPENDENT_EXTENSION_REVIEW.json'),'authorization_review_hash')
    marker=read(O/('ECONOMIC_RUN_ONCE_'+w+'.json'))
    check(marker['authorization_sha256']==sha(O/'ROOT_EXTENSION_AUTHORIZATION.json'),'run_once_authorization')
    check(marker['window']==w,'run_once_window')
    rounds=csvrows(saved('joint/ROUNDS.csv'));rd={x['round_id']:x for x in rounds}
    actions=csvrows(saved('joint/ACTIONS.csv'));by=defaultdict(list)
    for a in actions:by[a['round_id']].append(a);check(a['round_id'] in rd,'no_orphan_action',a['round_id'])
    claims=read(saved('joint/CLAIMS.json'));cb=defaultdict(list)
    for c in claims:cb[c['owner_round_id']].append(c)
    bridges=read(saved('joint/BRIDGES.json'))
    regs=csvrows(saved('joint/REGISTRATIONS.csv'))
    ledger=csvrows(saved('joint/CLAIM_LEDGER.csv'))
    qas=read(saved('joint/LEDGER_QA.json'));qa={q['round_id']:q for q in qas}
    ends=csvrows(saved('joint/END_STATES.csv'));endsid={x['sid']:x for x in ends}
    check(len(rd)==len(rounds)==len(qa),'unique_round_ids')
    check(set(rd)==set(qa),'ledger_qa_round_set')
    rules=read(source(B/'inputs-v2/market-rules.json'));proxies=read(source(B/'inputs-v2/economic-protocol.json'))['approved_proxy_ids']
    feeenv=dict(D=D,meta={},rules=rules,proxies=proxies,version_on=version_on,market_identity_on=market_identity_on,
                QuantityRule=QuantityRule,FeeSchedule=FeeSchedule,FeeComponent=FeeComponent)
    src=source(R/'m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py')
    for n in ast.parse(src.read_text()).body:
        if isinstance(n,ast.FunctionDef) and n.name in {'getmeta','fee'}:
            exec(compile(ast.Module(body=[n],type_ignores=[]),str(src)+':fee_definitions_only','exec'),feeenv)
    localenv=dict(Path=Path,D=D,pd=pd,AS=AS,actions_sources={},hashes={},sha=lambda p:sha(source(p)),read=lambda p:read(source(p)))
    src=source(R/'m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1/engine.py')
    node=next(n for n in ast.parse(src.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='local_actions')
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(src)+':local_actions_definition_only','exec'),localenv)
    rights=read(source(R/'m3_stock_birth_during_sector_v1/cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json'))
    eventids={x['economic_event_id_candidate']:x for x in rights}
    events={(x['sid'],pd.Timestamp(x['ex_date'])):dict(x,economic_event_id=x['economic_event_id_candidate'],entitlement_verified=True,event_type='PURE_CASH') for x in rights}
    coverage_engine=SimpleNamespace(local_actions=localenv['local_actions'],read=lambda p:read(source(p)),sha=lambda p:sha(source(p)),EVENT_AT=events)
    hp=source(Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'))
    with np.load(hp,allow_pickle=False) as h:cal=[str(pd.Timestamp(x).date()) for x in h['dates'] if pd.Timestamp(x)<=pd.Timestamp('2026-06-30')]
    cset=set(cal);nxt=dict(zip(cal[:-1],cal[1:]))
    statuscounts=Counter();lanecounts=Counter();reconstructed={};position_at=defaultdict(list);add_profit_keys=set()
    noentry={'NEXT_OPEN_BELOW_PROTECTION_NOFILL','MINIMUM_LOT_NOT_FUNDED_NOFILL','PRECHECK_OPEN_AT_OR_BELOW_S_NO_SUBMIT','PRECHECK_Q0_NO_SUBMIT'}
    for r in rounds:
        rid=r['round_id'];aa=by[rid];q=core=add=0;cash=spent=fees=D(0);lots=[];lastday='';role_buys=Counter()
        check(r['window']==w and rid.startswith(w+'|'),'cohort_identity',rid)
        check(CONFIG[w][0]<=day(r['signal_day'])<=CONFIG[w][1],'birth_window',rid)
        check(r['historical_tradability']=='UNKNOWN','tradability_unknown',rid)
        for a in aa:
            d=day(a['day']);n=int(dec(a['q']));px=dec(a['price']);fee=dec(a['fee']);side=a['side']
            check(d>=lastday and d in cset,'action_common_order',rid);lastday=d
            check(n>0 and px>0 and fee>=0,'positive_action',rid)
            qr,fs,par=feeenv['getmeta'](r['sid'],pd.Timestamp(d))
            expectedfee=feeenv['fee'](n,px,fs,'buy' if side.startswith('buy') else 'sell',par)
            near(fee,expectedfee,'dated_action_fee',dict(round_id=rid,day=d,side=side))
            if side.startswith('buy'):
                check(qr.buy_floor(n)==n,'dated_buy_lot',rid)
                raw_open=px/D('1.0005')
                if side=='buy_core':
                    floor=dec(r['entry_floor_raw']);sell_floor=floor*D('.9995')
                    risk=max(D(0),D(n)*(px-sell_floor)+fee+feeenv['fee'](n,sell_floor,fs,'sell',par))
                    near(risk,r['entry_risk'],'initial_plan_risk_rebuilt',rid)
                    check(risk<=D(3000)+D('.0000001') and D(n)*px+fee<=D(24000)+D('.0000001'),'initial_budget_and_risk_bound',rid)
                    near(raw_open,r['entry_open'],'entry_open_slippage',rid)
                else:
                    budget=min(D(24000),max(D(0),D(48000)-D(q)*raw_open))
                    check(D(n)*px+fee<=budget+D('.0000001'),'ADD_current_slot_budget',rid)
                    recognized_at_open=sum((dec(c['amount']) for c in cb[rid] if c['recognized'] and day(c['ex_date'])<=d),D(0))
                    net=cash+recognized_at_open+D(q)*raw_open*D('.9995')-feeenv['fee'](q,raw_open*D('.9995'),fs,'sell',par)
                    near(net,a.get('prior_round_net'),'ADD_prior_NET80_rebuilt',rid);check(net>0,'ADD_open_positive_NET80',rid)
                    previous=cal[cal.index(d)-1];add_profit_keys.add((rid,previous,'CLOSE'));add_profit_keys.add((rid,d,'OPEN'))
                role='core' if side=='buy_core' else 'add';role_buys[role]+=1
                lots.append(dict(day=d,qty=n,role=role));q+=n;cash-=n*px+fee;spent+=n*px+fee
                if role=='core':core+=n
                else:add+=n
            else:
                available=sum(l['qty'] for l in lots if l['day']<d and (side!='sell_add' or l['role']=='add'))
                check(n<=available,'T_plus_1_every_lot',dict(round_id=rid,day=d,q=n,available=available))
                remaining=n
                for l in lots:
                    if l['day']>=d or (side=='sell_add' and l['role']!='add'):continue
                    take=min(remaining,l['qty']);l['qty']-=take;remaining-=take
                    if l['role']=='core':core-=take
                    else:add-=take
                    if not remaining:break
                check(remaining==0,'sell_has_inventory',rid);q-=n;cash+=n*px-fee
            fees+=fee;check(q>=0 and core>=0 and add>=0,'nonnegative_inventory',rid)
            position_at[rid].append((d,core,add))
        check(role_buys['core']<=1 and role_buys['add']<=1,'proxy_single_probe_and_add',rid)
        if aa:
            check(day(r['entry_day'])==day(aa[0]['day']) and aa[0]['side']=='buy_core','first_positive_fill_entry',rid)
            check(nxt.get(day(r['signal_day']))==day(r['entry_day']),'immediate_next_common_entry',rid)
            near(q,dec(r.get('core_qty'),D(0))+dec(r.get('add_qty'),D(0)),'round_inventory',rid)
            near(spent,r.get('total_buy_cash'),'round_buy_cash',rid);near(fees,r.get('all_fees'),'round_total_fees',rid)
        check(q==qa[rid]['qty'] and truth(qa[rid]['reconciled']),'independent_qty_vs_native_qa',rid)
        near(cash,qa[rid]['trade_cash'],'independent_trade_cash_vs_native_qa',rid)
        near(fees,qa[rid]['fees'],'independent_fees_vs_native_qa',rid);near(spent,qa[rid]['buy_cash'],'independent_buy_cash_vs_native_qa',rid)
        if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':
            check(bool(aa) and q==0 and aa[-1]['side'].startswith('sell'),'complete_zero_to_zero',rid)
            check(day(r['exit_day'])==day(aa[-1]['day']),'last_positive_fill_exit',rid)
        if r['status'] in noentry:check(not aa and not cb[rid],'no_submit_no_actions_or_claims',rid)
        recognized=sum((dec(c['amount']) for c in cb[rid] if c['recognized']),D(0))
        paid=sum((dec(c['amount']) for c in cb[rid] if c['settled']),D(0))
        near(cash+paid,r['cash_after_payouts'],'round_final_cash',rid)
        near(recognized-paid,r['receivable_after_payouts'],'round_final_receivable',rid)
        near(recognized,r['dividend_net80_total'],'round_recognized_income',rid)
        near(paid,r['dividend_net80_paid'],'round_paid_income',rid)
        near(paid,qa[rid]['paid'],'qa_paid_income',rid);near(recognized-paid,qa[rid]['receivable'],'qa_receivable',rid)
        if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':
            near(cash+recognized,r['net_pnl'],'complete_cash_plus_entitlement_net',rid)
            near((cash+recognized)/spent,r['net_return_on_buy_cash'],'complete_return_on_buy_cash',rid)
        if 'UNKNOWN' in r['status']:
            check(endsid.get(r['sid'],{}).get('final_state')=='UNKNOWN' and endsid.get(r['sid'],{}).get('round_id')==rid,'unknown_final_owner_lock',rid)
            check(not any(day(a['day'])>day(r['status_day']) for a in aa),'unknown_no_later_trade',rid)
            check(not any(z['sid']==r['sid'] and z['round_id']!=rid and day(z['signal_day'])>=day(r['status_day']) for z in rounds),'unknown_no_reentry_or_slot_release',rid)
            check(r.get('net_pnl') in ('',None),'unknown_no_total_pnl_zero',rid)
        cov=financial_coverage(coverage_engine,{k:(None if v == "" else v) for k,v in r.items()},cb[rid])
        reconstructed[rid]=dict(q=q,core=core,add=add,cash=cash,spent=spent,fees=fees,recognized=recognized,paid=paid,coverage=cov,entered=bool(aa))
        statuscounts[r['status']]+=1;lanecounts[r['owner_lane']]+=1
    # Every admitted distribution has a separate cohort registration, including UNKNOWN/no holder.
    check(len(regs)==165 and len({z['economic_event_id'] for z in regs})==165,'registry_complete_165')
    regmap={}
    for z in regs:
        eid=z['economic_event_id'];key=ast.literal_eval(z['key']);r=eventids[eid];d=day(z['inventory_snapshot_day'])
        check(key[0]==w and key[1]=='A_UNION_B_PLUS_PRICE' and key[2]==z['sid'] and key[3]==eid,'registration_cohort_key',eid)
        check(d==r['record_date'] and z['sid']==r['sid'] and z['evidence_version']==r['evidence_version'],'registration_identity_clock',eid)
        regmap[eid]=z;rid=z['owner_round_id']
        if z['state']=='UNKNOWN':check(z['record_q']=='' and z['core_record_q']=='' and not rid,'unknown_registration_not_zero',eid)
        elif z['state']=='HELD':
            check(rid in rd,'registration_owner_exists',eid)
            hist=[x for x in position_at[rid] if x[0]<=d];cc,ad=hist[-1][1:] if hist else (0,0)
            near(cc+ad,z['record_q'],'registration_own_qty',eid);near(cc,z['core_record_q'],'registration_own_core_qty',eid)
        else:check(dec(z['record_q'])==0 and not rid,'nonheld_registration_zero',eid)
    ledgerby=defaultdict(list)
    for x in ledger:ledgerby[(x['round_id'],x['economic_event_id'])].append(x)
    claimed_keys=set();paid_clock={}
    for c in claims:
        rid=c['owner_round_id'];eid=c['economic_event_id'];r=eventids[eid];key=(rid,eid)
        check(key not in claimed_keys,'claim_unique_owner_event',key);claimed_keys.add(key)
        check(rid in rd and c['sid']==rd[rid]['sid'] and c['key'][0]==w,'claim_scope_owner',key)
        near(dec(c['record_q'])*dec(r['d_cash'])*D('.8'),c['amount'],'claim_NET80_own_quantity',key)
        near(dec(c['core_record_q'])*dec(r['d_cash'])*D('.8'),c['core_amount'],'claim_core_NET80',key)
        check(regmap[eid]['owner_round_id']==rid and dec(regmap[eid]['record_q'])==dec(c['record_q']),'claim_matches_registration',key)
        evs=ledgerby[key];acc=[x for x in evs if x['event']=='ACCRUE_NET80'];pay=[x for x in evs if x['event']=='PAY_CLOSE_TRANSFER']
        check(len(acc)==int(c['recognized']) and len(pay)==int(c['settled']),'claim_ledger_event_count',key)
        for x in acc:
            check(day(x['day'])==r['ex_date'] and day(x['day']) in cset,'actual_accrual_clock',key)
            near(x['cash_delta'],0,'accrual_no_cash',key);near(x['receivable_delta'],c['amount'],'accrual_receivable',key)
        for x in pay:
            d=day(x['day']);check(d==r['pay_date'] and d in cset,'actual_payment_common_clock',key)
            near(x['cash_delta'],c['amount'],'payment_cash',key);near(x['receivable_delta'],-dec(c['amount']),'payment_receivable',key)
            check(day(x.get('available_from'))==nxt.get(d),'payment_available_next_common',key)
            paid_clock[key]=d
    check(set(ledgerby)<=claimed_keys,'no_orphan_claim_ledger')
    # Final responsibility books and complete event ordering.
    books=read(saved('EXECUTION_BOOKS.json'));priceaudit=read(saved('PRICE_AUDIT.json'))
    for rid,book in books.items():
        r=rd[rid];a=reconstructed[rid];resp=book['responsibility'];parents=book['parents'];orders=book['orders'];events_=book['events'];lots=book['lots']
        check(r['owner_lane']=='PRICE','book_only_price',rid)
        check(resp['held_qty']==a['q'] and sum(l['remaining'] for l in lots.values())==a['q'],'book_saved_inventory',rid)
        check(resp['evidence_domain']=='PROXY' and resp['actual_fill']=='NOT_PROVIDED','book_proxy_not_real',rid)
        if 'UNKNOWN' in r['status']:check(resp['unknown'] and resp['owner_locked'],'unknown_book_not_released',rid)
        if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND':check(not resp['unknown'] and resp['held_qty']==0 and resp['live_leaves']==0 and resp['all_orders_reconciled'] and not resp['owner_locked'],'closed_book_responsibility_zero',rid)
        consumed=[norm(e['receipt_id']) for e in events_ if e['event']=='proxy_receipt_consumed']
        check(len(consumed)==len(set(consumed)),'receipt_consumed_once',rid)
        parentroles=[p['target']['role'] for p in parents.values()];check(len(parentroles)==len(set(parentroles)) and set(parentroles)<={'PROBE','ADD'},'one_parent_per_role',rid)
        buy_values=[];sell_values=[];probe_complete=None
        for p in parents.values():
            t=p['target'];pid=t['parent_id'];reg=[(i,e) for i,e in enumerate(events_) if e['event']=='proxy_target_registered' and e.get('parent_id')==pid]
            check(len(reg)==1 and reg[0][1]['target_Q']==t['target_Q'],'target_registered_once_before_fills',dict(round_id=rid,parent=pid))
            check(t['evidence_version']==auth['protocol_sha256'] and t['evidence_domain']=='PROXY','target_frozen_evidence',rid)
            check(t['root_id']==resp['root_id'] and t['signal_receipt_id'][0]==resp['root_id'],'target_root_identity',rid)
            check(nxt.get(t['signal_receipt_id'][1])==t['decision_open'],'target_next_common_open',rid)
            os=[z for z in orders.values() if z.get('parent_id')==pid and z['side']=='BUY']
            total=sum(z['terminal_filled'] or 0 for z in os)
            check(total==p['filled_F']<=t['target_Q'],'fixed_target_filled_quantity',rid)
            cost=sum(D(l['quantity'])*D(str(l['price']))+D(str(l['fee'])) for l in lots.values() if l['parent_id']==pid)
            check(cost<=D(str(t['budget']))+D('.0000001') and t['budget']<=24000,'target_budget_conserved',rid)
            for z in os:
                filled=[(i,e) for i,e in enumerate(events_) if e['event']=='proxy_fill' and e.get('order_id')==z['order_id']]
                check(len(filled)==1 and reg[0][0]<filled[0][0] and clock(t['registered_known_at'])<clock(filled[0][1]['known_at']),'target_before_positive_fill_clock',rid)
                check(z['quantity']==z['terminal_filled']==t['target_Q'] and z['live_leaves']==0 and not z['cancel_pending'],'full_fill_proxy_exact',rid)
                if t['role']=='PROBE':probe_complete=clock(z['terminal_known_at'])
                if t['role']=='ADD':check(probe_complete is not None and (t['signal_receipt_id'][1],100)>probe_complete,'ADD_receipt_after_probe_complete',rid)
        for oid,z in orders.items():
            fe=[e for e in events_ if e['event']=='proxy_fill' and e.get('order_id')==oid]
            term=[e for e in events_ if e['event']=='proxy_terminal_reconciled' and e.get('order_id')==oid]
            check(len(fe)==len(term)==1 and clock(z['registered_known_at'])<clock(fe[0]['known_at'])<clock(term[0]['known_at']),'order_fill_terminal_order',rid)
            if z['side']=='SELL':
                check(sum(q for lid,q in z['allocations'])==z['quantity'],'exit_lot_allocation',rid)
                for lid,q in z['allocations']:check(lid in lots and lots[lid]['buy_day']<z['decision_open'],'book_T_plus_1_lot',rid)
        for lot in lots.values():
            role=lot['role'];side='buy_core' if role=='PROBE' else 'buy_add'
            matches=[x for x in by[rid] if x['side']==side and day(x['day'])==lot['buy_day']]
            check(len(matches)==1 and int(dec(matches[0]['q']))==lot['quantity'],'book_lot_matches_cash_action',rid)
            if matches:near(lot['price'],matches[0]['price'],'book_lot_price_matches_action',rid);near(lot['fee'],matches[0]['fee'],'book_lot_fee_matches_action',rid)
            target=next(p['target'] for p in parents.values() if p['target']['parent_id']==lot['parent_id'])
            qrl,fs,par=feeenv['getmeta'](r['sid'],pd.Timestamp(lot['buy_day']))
            floor=D(str(target['protection_raw']));px=D(str(lot['price']));qty=lot['quantity'];bf=D(str(lot['fee']))
            risk=max(D(0),D(qty)*(px-floor*D('.9995'))+bf+feeenv['fee'](qty,floor*D('.9995'),fs,'sell',par))
            existing=D(0)
            if role=='ADD':
                probes=[l for l in lots.values() if l['role']=='PROBE'];held=sum(l['quantity'] for l in probes);initial_fees=sum((D(str(l['fee'])) for l in probes),D(0))
                existing=max(D(0),D(held)*(px-floor*D('.9995'))+initial_fees+feeenv['fee'](held,floor*D('.9995'),fs,'sell',par))
            check(risk<=max(D(0),D(3000)-existing)+D('.0000001'),'PRICE_combined_plan_risk_bound',rid)
        check(sum(z['terminal_filled'] for z in orders.values() if z['side']=='BUY')==sum(int(dec(x['q'])) for x in by[rid] if x['side'].startswith('buy')),'book_buy_fill_vs_actions',rid)
        check(sum(z['terminal_filled'] for z in orders.values() if z['side']=='SELL')==sum(int(dec(x['q'])) for x in by[rid] if x['side'].startswith('sell')),'book_sell_fill_vs_actions',rid)
    for r in rounds:
        if r['owner_lane']=='PRICE' and by[r['round_id']]:check(r['round_id'] in books,'entered_price_has_book',r['round_id'])
    frozen=read(saved('FROZEN_RESPONSIBILITIES.json'))
    for x in frozen:
        rid=x['round_id'];check(rid in rd and 'UNKNOWN' in rd[rid]['status'],'frozen_responsibility_round_unknown',rid)
        if x.get('core') is not None:near(dec(x.get('core'),D(0))+dec(x.get('add'),D(0)),reconstructed[rid]['q'],'frozen_responsibility_quantity_retained',rid)
    # Queue reservation and UNKNOWN ownership controls on recorded decisions.
    decisions=csvrows(saved('joint/DECISIONS.csv'));selected=[d for d in decisions if truth(d.get('selected'))]
    counts=Counter((day(d['day']),d['sector']) for d in selected)
    check(all(n<=2 for n in counts.values()),'two_initial_reservations_per_sector_close')
    check(len(selected)==len(rd) and {d['round_id'] for d in selected}==set(rd),'selected_rounds_complete')
    check(len({(d['sid'],day(d['day'])) for d in selected})==len(selected),'one_stock_option_per_close')
    for d in decisions:
        if d.get('decision','').startswith('BLOCKED_UNKNOWN'):check(d.get('blocking_round_id') in rd and 'UNKNOWN' in rd[d['blocking_round_id']]['status'],'recorded_unknown_block_kept',d.get('event_id'))
    observed_profit_keys=set()
    with saved('joint/PROFIT_GATES.csv').open(newline='') as f:
        for g in csv.DictReader(f):
            key=(g['round_id'],day(g['day']),g['phase'])
            if key in add_profit_keys:
                observed_profit_keys.add(key);check(dec(g['net_equity'])>0 and truth(g['strictly_positive']),'ADD_close_and_open_recorded_positive',key)
    check(observed_profit_keys==add_profit_keys,'ADD_both_profit_clocks_present')
    label_summary={};cut_rebuilt=[];label_rows=[]
    if stage=='full':
        label_rows=csvrows(saved('ALL_LANE_LABELS.csv'));labels={r['round_id']:r for r in label_rows};price_labels=csvrows(saved('PRICE_LABELS.csv'))
        check(set(labels)==set(rd) and len(labels)==len(label_rows),'all_registered_labels_denominator')
        check({x['round_id'] for x in price_labels}=={rid for rid,r in rd.items() if r['owner_lane']=='PRICE'},'all_price_labels_denominator')
        touched={c['owner_round_id'] for c in claims}|{x.get('round_id') for x in bridges}|{x.get('round_id') for x in ledger}|{x.get('owner_round_id') for x in regs}
        label_states=Counter();expected_labels={}
        for rid,r in rd.items():
            z=labels[rid];a=reconstructed[rid];cs=cb[rid];cov=a['coverage'];closed=r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND'
            pending=any(not c['recognized'] or not c['settled'] for c in cs)
            fin=closed and cov['financial_covered'] and a['q']==0 and bool(by[rid]) and dec(r.get('net_pnl')) is not None
            settled=fin and not pending and a['recognized']==a['paid'] and all((rid,c['economic_event_id']) in paid_clock for c in cs)
            ordinary=bool(settled and cov['reason']=='LOCAL_NO_ACTION_EVIDENCE' and rid not in touched and all(dec(r.get(k))==0 for k in ['core_qty','add_qty','dividend_at_termination','receivable_at_termination','receivable_after_payouts','dividend_net80_total','dividend_net80_paid']) and all(approximately(a['cash'],dec(r.get(k))) for k in ['net_pnl','cashflow_to_date','cash_after_payouts']))
            expected_status='STRICT_ORDINARY_MATURE_PROXY' if ordinary else 'FINANCIAL_SETTLED_NONORDINARY_SCENARIO' if settled else 'RIGHTS_PENDING' if closed and pending else 'FINANCIAL_COVERAGE_UNKNOWN' if closed and not cov['financial_covered'] else r['status']
            check(truth(z['ordinary_label_mature'])==ordinary,'strict_ordinary_independent',rid)
            check(truth(z['financial_settled_label_mature'])==settled and truth(z['financial_settled_nonordinary'])==(settled and not ordinary),'financial_settled_separate',rid)
            check(truth(z['financial_covered'])==cov['financial_covered'] and z['financial_coverage_reason']==cov['reason'],'financial_coverage_independent',rid)
            check(truth(z['rights_touched'])==(rid in touched) and truth(z['rights_pending'])==pending,'rights_labels_independent',rid)
            check(z['label_status']==expected_status,'label_status_independent',dict(round_id=rid,expected=expected_status,actual=z['label_status']))
            ordinary_clock=day(r['exit_day'])+'T15:00:00' if ordinary else ''
            settle_day=max([day(r['exit_day'])]+[paid_clock[(rid,c['economic_event_id'])] for c in cs]) if settled else None
            settle_clock=settle_day+'T15:00:00' if settled else ''
            check(z['label_usable_proxy_at']==ordinary_clock and z['financial_settlement_proxy_at']==settle_clock,'actual_label_proxy_clock',rid)
            check(z['source_available_at']=='' and z['source_evidence_domain']=='HISTORICAL_VERSION_UNVERIFIED_NON_PIT_PROXY' and z['proxy_clock_timezone']=='Asia/Shanghai','nonPIT_clock_separation',rid)
            if ordinary:near(z['label_net_cny'],r['net_pnl'],'ordinary_label_net',rid);near(z['label_R'],dec(r['net_pnl'])/D(3000),'ordinary_label_R',rid)
            else:check(z['label_net_cny']=='' and z['label_R']=='','no_ordinary_label_imputation',rid)
            if settled:near(z['financial_scenario_net_cny'],r['net_pnl'],'financial_label_net',rid);near(z['financial_scenario_R'],dec(r['net_pnl'])/D(3000),'financial_label_R',rid)
            else:check(z['financial_scenario_net_cny']=='' and z['financial_scenario_R']=='','no_financial_label_imputation',rid)
            check(z['cohort_id']==w and z['template_id']==TEMPLATE_ID and z['sid_cluster']==r['sid'],'label_cohort_template_cluster',rid)
            check(json.loads(z['decision_dedup_key'])==[r['sid'],day(r['signal_day']),TEMPLATE_ID],'decision_dedup_key',rid)
            expected_labels[rid]=dict(ordinary=ordinary,settled=settled,nonordinary=settled and not ordinary,ordinary_day=day(r['exit_day']) if ordinary else None,settlement_day=settle_day,R=dec(r['net_pnl'])/D(3000) if settled else None)
            if r['owner_lane']=='PRICE':label_states[expected_status]+=1
        check(len({z['decision_dedup_key'] for z in label_rows})==len(label_rows),'decision_keys_unique_in_cohort')
        savedcuts=csvrows(saved('PRICE_MATURITY_BY_CUT.csv'))
        for cut in ['2023-12-31','2024-08-31','2024-12-31','2025-12-31','2026-06-30']:
            for scope,flag,clk in [('STRICT_ORDINARY','ordinary','ordinary_day'),('FINANCIAL_SETTLED_ALL','settled','settlement_day'),('FINANCIAL_SETTLED_NONORDINARY','nonordinary','settlement_day')]:
                ids=[rid for rid,x in expected_labels.items() if rd[rid]['owner_lane']=='PRICE' and x[flag] and x[clk]<=cut]
                vals=[expected_labels[rid]['R'] for rid in ids]
                e=dict(cohort_id=w,cut=cut,scope=scope,mature_price_labels=len(ids),unique_sids=len({rd[rid]['sid'] for rid in ids}),tail_gt_3R=sum(v>3 for v in vals),tail_gt_1R=sum(v>1 for v in vals),nonpositive=sum(v<=0 for v in vals))
                got=[z for z in savedcuts if z['cut']==cut and z['scope']==scope]
                check(len(got)==1 and all(int(got[0][k])==v for k,v in e.items() if isinstance(v,int)),'historical_cut_counts',e);cut_rebuilt.append(e)
        label_summary=dict(price_label_status_counts=dict(label_states),price_registered=sum(r['owner_lane']=='PRICE' for r in rounds),strict_ordinary_price=sum(x['ordinary'] for rid,x in expected_labels.items() if rd[rid]['owner_lane']=='PRICE'),settled_price=sum(x['settled'] for rid,x in expected_labels.items() if rd[rid]['owner_lane']=='PRICE'))
    for n,h in artifacts.items():check(sha(dest/n)==h,'saved_artifact_unchanged_during_audit',n)
    result=dict(result=('PASS_SAVED_LEDGER_AND_LABEL_AUDIT' if stage=='full' else 'PASS_SAVED_LEDGER_CASH_AUDIT') if not failures else 'BLOCKED_POST_RUN_AUDIT',window=w,stage=stage,code_and_input_review_is_not_result_certification=True,
        historical_economic_loops_executed=0,source_native_recomputation=0,source_validation=dict(runner_final_source_verified=final_source_verified,full_input_rehash_during_concurrent_run=False,direct_audit_sources_hash_checked=True,protected_old_files_directly_checked=204),checks=dict(checks),check_count=sum(checks.values()),failures=failures,max_abs_errors=dict(errors),
        counts=dict(rounds=len(rounds),actions=len(actions),claims=len(claims),registrations=len(regs),books=len(books),frozen_responsibilities=len(frozen),status_counts=dict(statuscounts),lane_counts=dict(lanecounts)),
        label_summary=label_summary,rebuilt_cut_counts=cut_rebuilt,artifact_sha256=artifacts,script_sha256=sha(__file__),parent_authorization_sha256=sha(O/'ROOT_EXTENSION_AUTHORIZATION.json'),
        protocol_sha256=auth['protocol_sha256'],audited_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seconds=time.monotonic()-started,
        limitations=['Conditional full-fill proxy and NON-PIT inputs only. This is not real execution/PIT/tax certification.','Unknown observed-fill arithmetic is not a claim that remaining total liability is known.','Cross-cohort dependence and duplicate audit is separate after both saved cohorts exist.'])
    with out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
    print(json.dumps(dict(result=result['result'],window=w,stage=stage,checks=result['check_count'],failures=failures[:12],counts=result['counts'],labels=label_summary,report=str(out),sha256=sha(out),seconds=result['seconds']),ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
