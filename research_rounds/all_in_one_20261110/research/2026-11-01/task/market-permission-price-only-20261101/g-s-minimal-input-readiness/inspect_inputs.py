"""Read-only cache inventory. No strategy imports, state replay, or accounts.

Writes only JSON manifests alongside this file. Saved numeric outputs and event
lists are inspected, never recalculated. PnL/forward-return labels are not read.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import ast
import hashlib
import json
import math
import time
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
B = O.parent
G = W / 'g-broad-s-concentrated-native-r2-20261101'
U = W / 'universe-cp1-inputs-20261031'
Y = W / '2022-normal-reference-20261031'
V = W / 'pvr-slot1-native-readiness-20261101'
P = Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
SOURCES, STATS, MISMATCHES = {}, {}, []

def sha(p):
    p = Path(p)
    if str(p) not in SOURCES:
        SOURCES[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        st = p.stat()
        STATS[str(p)] = (st.st_size, st.st_mtime_ns)
    return SOURCES[str(p)]

def bind(p, expected=None):
    p = Path(p)
    if not p.exists():
        return {'path':str(p), 'exists':False, 'expected_sha256':expected}
    actual = sha(p)
    if expected and actual != expected:
        MISMATCHES.append({'path':str(p),'expected':expected,'actual':actual})
    return {'path':str(p),'exists':True,'sha256':actual,'expected_matches':actual == expected if expected else None}

def read(p):
    sha(p)
    return json.loads(Path(p).read_text())

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,(pd.Timestamp,datetime)):return x.isoformat()
    if isinstance(x,Path):return str(x)
    if isinstance(x,float) and not math.isfinite(x):return None
    return x

def save(name,obj):
    (O/name).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def frame(p, expected=None, columns=None):
    bind(p,expected)
    return pd.read_parquet(p,columns=columns)

def exact_row(df,day):
    t=pd.Timestamp(day)
    return df.loc[t] if t in df.index else None

def finite(x):
    return bool(pd.notna(x) and np.isfinite(x))

def coverage(df):
    return {'rows':len(df),'first':str(df.index.min().date()) if len(df) else None,
            'last':str(df.index.max().date()) if len(df) else None,'unique_dates':bool(df.index.is_unique)}

def f1_inventory(cut, nodes):
    result=[]
    for node in nodes:
        d=frame(node['daily_result_path']).loc[:cut]
        if d.empty:
            result.append(dict(node,asof=cut,status='UNKNOWN_NO_PAST_OUTPUT'));continue
        # Merely locate already saved event labels. This is not Policy.evidence,
        # F1.step, or an authoritative imported context/maturity bit.
        last_context=None;last_advance=None;last_failure=None
        for day,ev in d.events.items():
            for kind in ev:
                if str(kind).startswith('price_failure') or kind=='source_changed_context_ended':
                    last_context=None;last_advance=None;last_failure=str(day)
                elif kind in ('break_started','repair_restored'):
                    last_context={'day':str(day),'kind':kind};last_advance=None
                elif kind=='price_advance' and last_context is not None:
                    last_advance=str(day)
        r=d.iloc[-1]
        active=bool(r['mode']=='ACTIVE' and pd.isna(r['pending_failure_at']))
        evidence_hint=bool(active and last_context and last_advance is not None)
        result.append(dict(node,asof=cut,observed_day=str(d.index[-1]),mode=r['mode'],
          effective_status=r['effective_status'],permit_next_open=bool(r['permit_next_open']),
          breadth=r['breadth'],ready_m=r['ready_m'],ready_industries=r.get('ready_industries'),
          current_context_creation_saved_event=last_context,last_context_advance_saved_event=last_advance,
          last_saved_failure=last_failure,active_price_support_hint=active,
          S_maturity_event_evidence_hint=evidence_hint if node['scope']!='G' else None,
          hint_is_authorized_import=False,scope_observation_sequence_asof=len(d),
          full_asof_checkpoint_found=False,
          required_action='frozen pure F1 full-prefix replay plus separately frozen market-evidence clock/bootstrap; no financial planning warmup'))
    return result

def main():
    begun=time.monotonic()
    sm=read(U/'STOCK_MANIFEST.json');ym=read(Y/'inputs/MANIFEST.json')
    vm=read(V/'SCORES_MANIFEST.json');meta=read(R/'a-share-selection-e0-20261024/inputs-v2/metadata.json')
    runtime=read(P/'manifest.json');raws={x['series_id']:x for x in runtime['series']}
    ys={x['sid']:x for x in ym if not x['industry']};vs={x['symbol']:x for x in vm['entries']}
    ids=[x['symbol'] for x in sm]
    assert len(ids)==1709 and len(set(ids))==1709 and set(ids)==set(ys)==set(vs)==set(vm['fixed_stock_ids'])
    specs={
      '2022':dict(original_start='2022-01-01',market_warm_through='2021-12-31',
        account_open='2022-01-04',first_close='2022-01-04',earliest_new_fill='2022-01-05',
        minimum_two_sessions=['2022-01-04','2022-01-05'],
        optional_five_sessions=['2022-01-04','2022-01-05','2022-01-06','2022-01-07','2022-01-10']),
      '2025_26':dict(original_start='2025-07-01',market_warm_through='2025-06-30',
        account_open='2025-07-01',first_close='2025-07-01',earliest_new_fill='2025-07-02',
        minimum_two_sessions=['2025-07-01','2025-07-02'],
        optional_five_sessions=['2025-07-01','2025-07-02','2025-07-03','2025-07-04','2025-07-07'])}
    all_days=sorted({d for s in specs.values() for d in s['optional_five_sessions']})
    perday={d:Counter() for d in all_days};actions={k:[] for k in specs}
    stocks=[]
    for n,x in enumerate(sm):
        sid=x['symbol'];refs=x['refs'];expected=x['output_sha256'];rec=raws[sid]
        f=frame(refs['facts'],expected[str(refs['facts'])]);c=frame(refs['CP1'],expected[str(refs['CP1'])])
        bind(refs['CP1_input'],expected[str(refs['CP1_input'])])
        p=V/'scores'/f'{sid}.parquet';pv=frame(p,vs[sid]['output_sha256'])
        rp=Path(rec['raw']['path']);raw=frame(rp,rec['raw']['sha256'],columns=['trade_date','open','close','price_eligible','volume_eligible','observed_bar','synthetic_event_bar'])
        raw=raw.set_index('trade_date');actionref=rec.get('adjustment',{}).get('actions')
        ac=read(actionref['path']) if actionref else None
        if actionref:bind(actionref['path'],actionref['sha256'])
        receipt_paths={'2022':ys[sid]['output_path'],'2025_26':refs['receipts']}
        rr={}
        for key,path in receipt_paths.items():
            exp=ys[sid]['output_sha256'] if key=='2022' else expected[str(path)]
            bind(path,exp);rr[key]=read(path)
        row=dict(symbol=sid,name=meta.get(sid,{}).get('name'),sector_id=meta.get(sid,{}).get('sector_id'),
          universe_status=x['status'],original_mapping=meta.get(sid),
          refs={**refs,'raw_bars':str(rp),'PVR':str(p),'receipts_2022':receipt_paths['2022'],
                'actions':actionref['path'] if actionref else None},
          full_warm_from=x.get('warm_from'),facts_coverage=coverage(f),CP1_coverage=coverage(c),
          PVR_explicit_cells=len(pv),prefix_observations={},
          action_status=ac.get('status') if ac else 'UNKNOWN',
          payments_exact_certified=ac.get('exact_pay_dates_certified') if ac else False)
        for day in all_days:
            a=exact_row(f,day);b=exact_row(c,day);v=exact_row(pv,day);r=exact_row(raw,day)
            z=dict(facts_exact=a is not None,CP1_exact=b is not None,PVR_explicit=v is not None,raw_exact=r is not None,
              I_ready=bool(a.e0_ready) if a is not None and pd.notna(a.e0_ready) else None,
              factor_known=finite(a.factor) if a is not None else False,
              CP1_ready=bool(b.ready) if b is not None and pd.notna(b.ready) else None,
              PVR_ready=finite(v.iloc[0]) if v is not None else False,
              observed_executable_price=bool(r.observed_bar and not r.synthetic_event_bar and r.price_eligible and finite(r.open) and r.open>0) if r is not None else False)
            key='2022' if day.startswith('2022') else '2025_26'
            today=[q for q in rr[key] if q['confirmed_day']==day]
            z['canonical_CP1_confirmations']=len(today);z['canonical_unknown']=sum(bool(q['trace_unknown']) for q in today)
            for q in today:
                assert q['formation_start_exclusive']<q['formation_end_inclusive']==q['confirmed_day']
                assert q['canonical_series']==sid
            row['prefix_observations'][day]=z
            for k,vv in z.items():perday[day][k]+=int(vv or 0)
        row['receipts_by_window']={k:dict(path=receipt_paths[k],total_saved=len(v),
             before_account_start=sum(t['confirmed_day']<specs[k]['first_close'] for t in v),
             within_five_sessions=sum(t['confirmed_day'] in specs[k]['optional_five_sessions'] for t in v)) for k,v in rr.items()}
        for key,s in specs.items():
            selected=[dict(symbol=sid,**ev) for ev in (ac.get('events',[]) if ac else [])
                      if s['account_open']<=ev['effective_date']<=s['optional_five_sessions'][-1]]
            actions[key].extend(selected)
        stocks.append(row)
        if (n+1)%400==0:print('READ_ONLY_STOCK_INVENTORY',n+1,round(time.monotonic()-begun,2),flush=True)
    assert all(x['sector_id'] for x in stocks)
    sectors=sorted({x['sector_id'] for x in stocks});assert len(sectors)==90
    save('STOCK_INPUT_INVENTORY.json',stocks)
    save('PREFIX_INPUT_COVERAGE.json',dict(fixed_denominator=1709,per_day=perday,short_prefix_actions=actions,
       raw_readiness_is_not_a_fill=True,no_quantity_entitlement_or_account_computed=True))
    save('STOCK_SCAN_SOURCE_SHA256.json',SOURCES)

    catalogue=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json')
    nodes=[dict(scope='G',original_F1_scope='NATIVE1709_global',node_id='NATIVE1709_global',sector=None,name='original global composite',
            daily_result_path=str(B/'historical-shadow/run-v1/NATIVE1709_global_daily.parquet'),
            input_file=str(B/'input-preparation/prepared-v2/NATIVE1709/market.parquet'))]
    for x in catalogue:
        if x['domain']=='NATIVE1709':
            nodes.append({k:x[k] for k in ('node_id','sector','name','daily_result_path','input_file')}|{'scope':x['sector'],'original_F1_scope':x['scope']})
    assert len(nodes)==91 and {x['sector'] for x in nodes if x['sector']}==set(sectors)
    f1={key:f1_inventory(s['market_warm_through'],nodes) for key,s in specs.items()}
    for node in nodes:bind(node['input_file'])
    save('F1_BOOTSTRAP_INVENTORY.json',dict(
       note='Static saved-event readiness hints only; no F1 or policy replay and no authoritative imported maturity.',windows=f1,
       final_only_checkpoint_locations=[str(B/'historical-shadow/run-v1'),str(B/'industry-coverage/run-v1/checkpoints')],
       final_checkpoints_cannot_be_rewound=True,
       full_state_fields=[n.target.id for cls in ast.parse((B/'v2-frozen/signal_core.py').read_text()).body
                          if isinstance(cls,ast.ClassDef) and cls.name=='State' for n in cls.body
                          if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name)]))
    z=np.load(P/'h1.npz',allow_pickle=False);bind(P/'h1.npz');hsyms={s:i for i,s in enumerate(z['symbols'])};hdates=pd.DatetimeIndex(z['dates'])
    hcheck={}
    for day in all_days:
        idx=hdates.get_indexer([pd.Timestamp(day)])[0];assert idx>=0
        vals=z['score'][idx,[hsyms[s] for s in ids]]
        hcheck[day]=dict(identity_cells=len(vals),finite_scores=int(np.isfinite(vals).sum()),unknown_scores=int((~np.isfinite(vals)).sum()))
    save('H1_INPUT_COVERAGE.json',dict(path=str(P/'h1.npz'),sha256=sha(P/'h1.npz'),shape=z['score'].shape,
        stock_identities=1709,index_identities=90,per_day=hcheck,priority_sort_executed=False))

    # The OLD407 numeric cache is separate. Its mere existence does not create
    # canonical 924 proof/context identities or certify source equivalence.
    op=R/'tech-compound-design-20261026/proposed-pool.csv';bind(op);oldids=pd.read_csv(op).symbol.tolist()
    old=[]
    for sid in oldids:
        p=R/'continuous-protection-lines-20261028/signals'/f'{sid}.parquet'
        q=frame(p,columns=['ready','receipt']) if p.exists() else None
        qq=q.loc['2024-09-01':'2024-10-14'] if q is not None else None
        old.append(dict(symbol=sid,numeric_CP1_path=str(p),numeric_CP1_exists=p.exists(),
          numeric_coverage=coverage(q) if q is not None else None,
          fixed_case_rows=len(qq) if qq is not None else 0,
          fixed_case_ready=int(qq.ready.fillna(False).sum()) if qq is not None else 0,
          fixed_case_receipts=int(qq.receipt.fillna(False).sum()) if qq is not None else 0,
          canonical_924_receipt_export_found=False,new_GS_historical_adapter_ready=False))
    save('OLD407_924_SEPARATE_GAP.json',dict(fixed_domain=407,nodes=old,
      gap='Old numeric CP1 exists where listed. No canonical OLD407 924 receipt/formation/episode export in the inspected native2022/native2025 exports or old trace scope; no cross-domain substitution is certified.',
      inspected_trace_scope={'path':str(W/'cp1-evidence-trace-20261031/trace.py'),'begin':'2025-07-01','end':'2026-03-31'},
      missing_is_not_claimed_to_mean_no_numeric_CP1=True,recalculation_or_export_performed=False))

    selected=[G/n for n in ('AUDIT_ENTRY.md','SOURCE_FREEZE.json','VALIDATION_SUMMARY.json','native_capital.py','policy.py','imports_native.py')]
    selected += [Y/'PROTOCOL.txt',Y/'runs/B_diag/INITIAL_STATE.json',Y/'adapter.py',V/'execution_support.py',
        V/'PRIORITY_FIELD_SCHEMA.txt',W/'case-stage-ledger-20261031/v3/joint_v3.py',
        W/'capital-capability-design-only-20261101/G_BROAD_S_CONCENTRATED_CONTRACT_PROPOSAL.txt',
        W/'capital-capability-design-only-20261101/G_BROAD_S_CONCENTRATED_CONTRACT_V2.txt',
        B/'v2-frozen/signal_core.py',B/'v2-frozen/CONTRACT.md',
        B/'input-preparation/prepared-v2/INPUT_GATE.json',B/'input-preparation/prepared-v2/CHECKPOINT_37_GATE.json',
        W/'cp1-evidence-trace-20261031/trace.py',R/'continuous-protection-lines-20261028/code/model.py',
        R/'a-share-selection-e0-20261024/code/current_pool_bridge.py',R/'temperature-sizing-20261026/code/fast_market.py',
        R/'pvr-act-comparison-20261027/execution-rules-v2.json']
    for p in selected:bind(p)
    freeze=read(G/'SOURCE_FREEZE.json')
    for name,expected in freeze['sources'].items():bind(G/name,expected)
    changed=[p for p,st in STATS.items() if (Path(p).stat().st_size,Path(p).stat().st_mtime_ns)!=st]
    fsum={key:dict(global_state=rows[0],industry_modes=dict(Counter(r['mode'] for r in rows[1:])),
         industry_active=sum(r['active_price_support_hint'] for r in rows[1:]),
         industry_permit=sum(r['permit_next_open'] for r in rows[1:]),
         industry_S_maturity_evidence_hints=sum(bool(r['S_maturity_event_evidence_hint']) for r in rows[1:])) for key,rows in f1.items()}
    save('PREPARATION_MANIFEST.json',dict(
      created_at=datetime.now(timezone.utc),scope='read-only minimal historical readiness; no account/F1/policy/model execution',
      status='PREPARATION_COMPLETE_EXECUTION_NOT_READY',
      fixed_universe=dict(stocks=1709,sectors=90,stock_statuses=Counter(x['status'] for x in sm),
         mapping_snapshot='current survivor/current sector fixed research snapshot; not historical PIT',
         metadata_extra_keys=sorted(set(meta)-set(ids))),
      anchors=specs,F1_asof_summary=fsum,source_hash_mismatches=MISMATCHES,source_stat_changes_during_read=changed,
      main_candidate_binding=dict(path=str(G),adapter_sha256=sha(G/'native_capital.py'),policy_sha256=sha(G/'policy.py'),
         contract=freeze['contract'],reported_review_status=freeze['independent_review'],historical_loader_exists=False),
      required_before_any_historical_account=['separate authorization; this package does not authorize execution',
        'freeze historical cursor adapter with original source-specific evidence identity mapping and decomposed stock eligibility; do not set legacy Q true',
        'pure frozen F1 prefix replay to each prior-close cutoff, plus market-only context/maturity proof-clock bootstrap; financial account remains uncreated until original start',
        'raw-price/factor/I-floor/CP1-floor coordinate checks; exact close known_at and next-open boundary; no current close leakage into opening',
        'freeze action/accrual/payment loader and unknown-payment handling; preserve unsupported fractional action rejection',
        'complete original PVR_SLOT1/H1/NA/tie priority and next-open frozen intent mapping',
        'do not import old SC/PVR financial checkpoint, stage, ACT, K, receipts consumed, locks or orders'],
      operations=dict(financial_accounts_created=0,financial_events=0,F1_steps=0,policy_evidence_steps=0,
        I_CP1_PVR_model_calculations=0,downloads=0,original_files_written=0,old_checkpoint_unpickles=0),
      seconds=round(time.monotonic()-begun,3)))
    save('SOURCE_SHA256.json',SOURCES)
    print('INVENTORY_COMPLETE',json.dumps(clean(dict(F1=fsum,coverage=perday,actions={k:len(v) for k,v in actions.items()},mismatches=len(MISMATCHES),changed=len(changed),seconds=time.monotonic()-begun)),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
