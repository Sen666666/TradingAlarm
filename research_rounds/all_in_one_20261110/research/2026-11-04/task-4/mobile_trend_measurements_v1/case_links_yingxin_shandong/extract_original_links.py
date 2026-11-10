"""Join saved original CP/opportunities/intents to next original OPEN. No indicator/model calls."""
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PAIR = ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
YINGXIN = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structure_risk_position_review_v2/cases/000620_SZ_DAILY_PAPER_INPUTS.json')
SHANDONG = ROOT/'reentry_event_identity_v1/shandong/ALL_SAVED_DAILY_CHAIN.json'
RULES = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
CASES = {'000620.SZ':('2022-01-04','2022-02-08'), '601019.SH':('2023-03-20','2023-05-09')}

def dump(name, value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

with gzip.open(PAIR/'B.json.gz','rt') as f:book=json.load(f)
calendar=json.loads(RULES.read_text())['calendars']['A']
nextopen={at[:10]:calendar[i+1].replace('T',' ') for i,at in enumerate(calendar[:-1])}
reuse={'000620.SZ':{d['day']:d for d in json.loads(YINGXIN.read_text())['days']},
       '601019.SH':{d['day']:d for d in json.loads(SHANDONG.read_text())}}
decisions={d['at'][:10]:d for d in book['decisions']}
daily={}
with gzip.open(PAIR/'daily.jsonl.gz','rt') as f:
    for line in f:
        d=json.loads(line)
        if d['account']=='B' and any(start<=d['at'][:10]<=end for start,end in CASES.values()):daily[d['at'][:10]]=d
opps=defaultdict(list);funding=defaultdict(list)
for file,target in [('opportunities',opps),('funding',funding)]:
    with gzip.open(PAIR/(file+'.jsonl.gz'),'rt') as f:
        for line in f:
            r=json.loads(line);sid=r.get('sid');day=r.get('day',r.get('at',''))[:10]
            if sid not in CASES:continue
            start,end=CASES[sid]
            if start<=day<=nextopen[end][:10]:target[(sid,day)].append(r)

rows=[];original=[];summaries=[]
for sid,(start,end) in CASES.items():
    case_rows=[]
    for day in sorted(d for d in daily if start<=d<=end):
        d=daily[day];saved=reuse[sid].get(day);op=opps[(sid,day)]
        assert len(op)==1
        op=op[0]
        decision=decisions[day]
        intents=[i for i in decision['intents'] if i['sid']==sid]
        mi=[i for i in intents if i['role']=='mobile']
        assert len(mi)<=1
        opening=nextopen[day];od=opening[:10]
        nxtfund=[f for f in funding[(sid,od)] if f['at']==opening]
        mfund=[f for f in nxtfund if f['role']=='mobile']
        nxttrades=[t for t in book['trades'] if t['security_id']==sid and t['at']==opening]
        mbuys=[t for t in nxttrades if t['side']=='buy' and t['kind']=='add' and t['signal_at']==d['at']]
        corebuys=[t for t in nxttrades if t['side']=='buy' and t['kind']=='core' and t['signal_at']==d['at']]
        if not mi:
            status='NO_ORIGINAL_MOBILE_INTENT'
        elif mbuys:
            status='ACTUAL_MOBILE_FILL'
        elif mfund:
            status='ORIGINAL_OPEN_REJECTION' if not any(f['result']=='reserved' for f in mfund) else 'RESERVED_NO_MOBILE_FILL'
        elif corebuys:
            status='SAME_SID_CORE_FUNDED_FIRST_DONE_SKIPS_MOBILE'
        else:status='INTENT_WITHOUT_SAVED_MOBILE_OPEN_RESULT'
        canonical=None;cp_cache=None;facts=None
        if saved:
            canonical=saved.get('original_CP_canonical_receipt',saved.get('canonical_CP_receipt'))
            cp_cache=saved.get('original_CP_cache',saved.get('original_CP'))
            facts=saved.get('original_stock_facts',saved.get('actual_facts'))
            if isinstance(canonical,dict):assert canonical['receipt_id']==op['CP1_id']
            if isinstance(cp_cache,dict):assert bool(cp_cache['receipt'])==bool(op['CP1_id'])
            prior_intents=saved.get('original_intents')
            if prior_intents is not None:assert prior_intents==intents
        layers=[x for x in d['layers'] if x['sid']==sid]
        live_mobile=[x for x in layers if x['kind']=='add']
        phase=('FIRST_MOBILE_ROUND_ATTEMPT_OR_HOLD' if day<'2022-01-20' else 'SECOND_MOBILE_ROUND_AFTER_FIRST_ACTUAL_CLEAR') if sid=='000620.SZ' else ('FIRST_MOBILE_ROUND_ATTEMPT_OR_HOLD' if day<'2023-04-11' else 'SECOND_MOBILE_ROUND_AFTER_FIRST_ACTUAL_CLEAR')
        row=dict(sid=sid,day=day,original_CLOSE_at=d['at'],next_original_OPEN_at=opening,
                 original_CP_receipt=bool(op['CP1_id']),CP1_id=op['CP1_id'] or '',
                 CP_canonical_payload_status='REUSED_SAVED_CANONICAL' if isinstance(canonical,dict) else ('NOT_IN_REUSED_TABLE_ONLY_ORIGINAL_BOOK_ID' if op['CP1_id'] else 'NO_RECEIPT'),
                 CP_original_E0_episode_id=canonical['original_E0_episode_id'] if isinstance(canonical,dict) else ('NOT_IN_REUSED_TABLE' if op['CP1_id'] else ''),
                 original_CP_candidate=cp_cache.get('candidate','NOT_SAVED') if isinstance(cp_cache,dict) else 'NOT_IN_REUSED_TABLE',
                 original_E0_target=facts.get('e0_target','NOT_SAVED') if facts else 'NOT_IN_REUSED_TABLE',
                 original_I_target=facts.get('i_target','NOT_SAVED') if facts else 'NOT_IN_REUSED_TABLE',
                 original_I_buy=facts.get('i_buy','NOT_SAVED') if facts else 'NOT_IN_REUSED_TABLE',
                 original_core_Q=op['core_Q'],original_mobile_Q=op['mobile_Q'],
                 original_mobile_role='mobile' in op['roles'],original_held=op['held'],
                 original_opportunity_pre_PVR_rank=op['rank'],original_barriers=';'.join(op['barriers']),
                 original_mobile_intent_count=len(mi),original_intent_budget=mi[0]['budget'] if mi else '',
                 original_intent_cap=mi[0]['cap'] if mi else '',original_intent_floor=mi[0]['floor'] if mi else '',
                 original_intent_actual_priority_rank=mi[0]['rank'] if mi else '',
                 original_runner_I_epoch=json.dumps(mi[0]['epoch']) if mi else '',
                 original_live_runner_I_epochs=json.dumps(sorted({json.dumps(x['epoch']) for x in layers})),
                 original_live_stock_structures=json.dumps(sorted({x.get('stock_structure','NOT_SAVED') for x in layers})),
                 MOBILE_round_label=phase,round_is_descriptive_not_new_E0_or_I=True,
                 original_qty_at_signal_CLOSE=d['positions'].get(sid,0),
                 original_MOBILE_qty_at_signal_CLOSE=sum(x['qty'] for x in live_mobile),
                 original_live_mobile_layer_ids='|'.join(str(x['id']) for x in live_mobile),
                 next_OPEN_status=status,
                 next_OPEN_original_mobile_results=';'.join(f['result'] for f in mfund),
                 failure_reason_list_is_unique_first_cause=False,
                 next_OPEN_actual_mobile_shares=sum(t['shares'] for t in mbuys),
                 next_OPEN_actual_mobile_layer_ids='|'.join(str(t['layer']) for t in mbuys),
                 next_OPEN_actual_mobile_prices='|'.join(t['price'] for t in mbuys),
                 next_OPEN_other_core_shares=sum(t['shares'] for t in corebuys),
                 next_OPEN_actual_stock_sell_shares=sum(t['shares'] for t in nxttrades if t['side']=='sell'))
        original.append(dict(sid=sid,day=day,original_opportunity=op,
                             original_decision={k:v for k,v in decision.items() if k!='intents'},original_stock_intents=intents,
                             original_CP_reused_cache=cp_cache,original_CP_reused_canonical=canonical,
                             original_next_OPEN_funding=nxtfund,original_next_OPEN_stock_trades=nxttrades,
                             original_current_stock_layers=layers,
                             missing_early_shandong_fields='Original book/opportunity only; no CP or E0/G1 recomputation and no newly read indicator/facts parquet' if not saved else None))
        case_rows.append(row);rows.append(row)
    with (OUT/(sid+'.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(case_rows[0]));w.writeheader();w.writerows(case_rows)
    summaries.append(dict(sid=sid,window=[start,end],CLOSE_rows=len(case_rows),CP_receipts=sum(r['original_CP_receipt'] for r in case_rows),
                          mobile_roles=sum(r['original_mobile_role'] for r in case_rows),mobile_intents=sum(r['original_mobile_intent_count'] for r in case_rows),
                          next_OPEN_status_counts=dict(Counter(r['next_OPEN_status'] for r in case_rows)),
                          newly_linked_early_saved_book_days=[r['day'] for r in case_rows if r['original_E0_target']=='NOT_IN_REUSED_TABLE']))
dump('ALL_DAILY_LINKS.json',rows);dump('ORIGINAL_SOURCE_LINK_RECORDS.json',original);dump('COUNTS.json',summaries)
dump('ROUND_AND_IDENTITY_RULES.json',dict(
    labels='Descriptive original Mobile inventory rounds split at already actual first Mobile clear OPEN; they are not new E0/I episodes or trading signals',
    first_clear_OPEN={'000620.SZ':'2022-01-20 09:30:00+08:00','601019.SH':'2023-04-11 09:30:00+08:00'},
    actual_round_layer_sets={'000620.SZ':[[69,75,78],[113,122]],'601019.SH':[[1161,1183],[1230,1267,1283]]},
    original_CORE_layers={'000620.SZ':68,'601019.SH':1148},
    runner_I_epochs={'000620.SZ':[0,2],'601019.SH':[0,5]},
    warning='Runner I epoch, canonical stock E0 id, budget industry episode and account ACT episode are separate; equal runner epoch does not establish E0 identity',
    early_shandong='2023-03-20 through 03-27 only original book/daily/opportunities/funding were read; 03-22 CP receipt ID and next OPEN fill exist, but full canonical CP payload/E0 facts are NOT_IN_REUSED_TABLE'))
sources=[YINGXIN,SHANDONG,RULES,PAIR/'B.json.gz',PAIR/'daily.jsonl.gz',PAIR/'funding.jsonl.gz',PAIR/'opportunities.jsonl.gz',ROOT/'mobile_trend_measurements_v1/FROZEN_DEFINITIONS.txt']
dump('SOURCE_SHA256.json',[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources])
print(json.dumps(summaries,ensure_ascii=False))
