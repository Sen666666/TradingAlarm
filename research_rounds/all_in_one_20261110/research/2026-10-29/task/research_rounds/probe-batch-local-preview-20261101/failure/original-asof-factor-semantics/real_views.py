"""Two fixed allocation projections from existing original records only."""
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
import copy,json,gzip,collections,hashlib,time
import pandas as pd
import planner as P
W=P.W;O=P.O;Z=D(0);SOURCES={};FF={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SOURCES[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def book(p):
    SOURCES[str(Path(p).resolve())]=sha(p)
    with gzip.open(p,'rt') as f:return json.load(f)
def stream(p):
    SOURCES[str(Path(p).resolve())]=sha(p)
    with gzip.open(p,'rt') as f:
        for x in f:yield json.loads(x)
def save(n,x):
    p=O/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n');t.replace(p)
def dated(rows,d):
    z=[r for r in rows if r['from']<=d and (not r.get('to') or d<r['to'])];assert len(z)==1;return z[0]
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};IM=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
META=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
RULES=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json'))
def factor(sid,d):
    if sid not in FF:
        r=SM[sid];p=Path(r['refs']['facts']);assert sha(p)==r['output_sha256'][str(p)];SOURCES[str(p)]=sha(p);FF[sid]=pd.read_parquet(p,columns=['factor'])
    assert pd.Timestamp(d) in FF[sid].index;return D(str(FF[sid].loc[d,'factor']))

def industry_projection(previous,logs):
    last={x['sector']:x for x in logs if x['day']<=previous};out={};proof=[]
    for r in IM:
        p=Path(r['refs']['state']);assert sha(p)==r['output_sha256'][str(p)];SOURCES[str(p)]=sha(p);f=pd.read_parquet(p);f=f[f.day<=previous]
        cur=f.iloc[-1];sid=r['series'];log=last.get(sid);assert log is not None
        active=pd.notna(cur.attempt_id) and cur.stage>0
        ep=cur.E0_episode if bool(cur.E0_valid) else log['episode'];assert isinstance(ep,str)
        ep_rows=f[f.E0_episode.eq(ep)&f.E0_valid.eq(True)];assert not ep_rows.empty;ep_start=P.J.ordinal(ep_rows.iloc[0].day)
        if active:
            a=f[f.attempt_id.eq(cur.attempt_id)];first=a[a.action.eq('probe')].iloc[0];attempt=ep+':'+first.receipt_id;level=int(cur.stage)-1;started=P.J.ordinal(first.day)
            assert log['episode']==ep and log['attempt']==attempt and log['financial_level']==level
            # No admission function reads old status before migrate overwrites
            # it. Keep unlogged prior migration status explicitly unknown.
            status='probe' if level==0 else None
        else:
            level=log['financial_level'] if log['episode']==ep else 0;attempt=log['attempt'] if log['episode']==ep else None;started=None
            status='awaiting_first_cp1' if log['episode']!=ep else 'invalidated'
        out[sid]=NS(episode=ep,episode_started=ep_start,started=started,attempt=attempt,active=bool(active),level=level,status=status)
        proof.append(dict(sector=sid,active=bool(active),episode=ep,attempt=attempt,level=level,status=status,status_unknown_but_not_read_by_admission=status is None,active_fields_crosschecked_with_saved_financial_industry_events=bool(active)))
    return out,proof

def reconstruct(day,previous,root,receipt_manifest,market):
    b=book(root/'B.json.gz');daily={x['at'][:10]:x for x in stream(root/'daily.jsonl.gz')};prev=daily[previous];cur=daily[day]
    at=P.J.M.N.iso(day+'T09:30:00+08:00');previous_cutoff=P.J.M.N.iso(previous+'T15:10:00+08:00')
    assert prev['order_reserved']=='0' and not prev['pending_sells']
    assert all(D(prev[k])==0 for k in ['sale_receivable','settlement_locked','payable'])
    pre=[x for x in b['journal'] if previous<x['at'][:10]<=day and (x['at'][:10]<day or '09:30:00' not in x['at']) and x['kind'] in ['actual_split','real_sell_fill','real_buy_fill']]
    assert not pre,'requires additional exact overnight ledger reconstruction'
    accruals=[x['receivable'] for x in b['audit'] if x['kind']=='dividend_accrual' and previous_cutoff<P.J.M.N.iso(x['receivable']['ex_at'].replace(' ','T'))<=at]
    assert all(x['currency']=='CNY' and x['paid_at'] is None for x in accruals),'requires explicit recorded paid/FX bridge'
    opening_dividend_AR=D(prev['dividend_receivable'])+sum((D(x['net_local']) for x in accruals),Z)
    if day=='2022-06-29':
        assert not [x for x in b['journal'] if x['at'][:10]==day]
        assert all(prev[k]==cur[k] for k in ['available','sale_receivable','order_reserved'])
        assert opening_dividend_AR==D(cur['dividend_receivable'])
    industry=list(stream(root/'industry.jsonl.gz'));sectors,stageproof=industry_projection(previous,industry)
    marks=market.marks(at,{x['sid'] for x in prev['layers']});lots=[];prices={}
    for x in prev['layers']:
        sid=x['sid'];assert x['qty']>0;prices[sid]=float(marks[sid].cny_price(at));rawfloor=D(str(x['last_core_line'] if x['role']=='core' else x['floor']))/factor(sid,day)
        lots.append(P.N.Lot(str(x['id']),sid,x['sector'],x['episode'],x['pool'],x['qty'],x['unit_cost'],float(rawfloor),x['role'],x['attempt']))
    old=[x for x in b['journal'] if x['kind']=='real_reserve' and x['at'][:10]<day];consumed={x['receipt'] for x in old if x['role']=='mobile'};assert None not in consumed
    state=P.State(cash=D(prev['available']),available_exact=D(prev['available']),receivables=opening_dividend_AR,lots=lots,orders={},sectors=sectors,prices=prices,consumed=consumed,stock_requests={x['budget_order'] for x in old},sector_by_sid={sid:x['sector_id'] for sid,x in META.items()},decision_nav=prev['nav'],historical_shared_loss=prev['shared_loss'])
    source_dec=next(x for x in b['decisions'] if x['at'][:10]==previous);assert source_dec['nav']==prev['nav']
    mins=read(W/'probe-batch-design-review-20261101'/f'{day}_MINIMUM_INPUT_PREVIEW.json');minrows={(x['sid'],x['role']):x for x in mins['rows']};missing={(x['sid'],x['role']) for x in mins['unknown']}
    recs={x['sid']:x for x in read(receipt_manifest)};intents=[]
    for src in source_dec['intents']:
        i=copy.deepcopy(src);sid=i['sid'];i['clock']=NS(decision_at=P.J.M.N.iso(previous+'T15:10:00+08:00'),earliest_execution_at=at);i['quote']=NS(par_value=RULES['security_metadata'][sid].get('par_value'))
        for k in ['floor','budget','risk_budget']:
            if k in i:i[k]=D(str(i[k]))
        i['CP1_trace']=None
        if i['role']=='mobile':
            rr=read(recs[sid]['output_path']);cp=next(x for x in rr if x['confirmed_day']==previous);assert cp['receipt_id']==i['CP1_id'];i['CP1_trace']=cp
        else:assert i['epoch'] is not None
        if (sid,i['role']) in missing:i['_preview']=None;i['_preview_failure']='missing_open'
        else:
            m=minrows[(sid,i['role'])]
            if m['independent_preview_reason']:i['_preview']=None;i['_preview_failure']=m['independent_preview_reason']
            else:
                p=D(m['minimum_gross'])/D(m['minimum_shares']);op=p/(1+P.LR.SLIP)
                rule=P.J.LR.L.QuantityRule(**dated(RULES['quantity_versions'][sid],day)['rule']);venue=dated(RULES['venue_versions'][sid],day)['venue'];sd=dated(RULES['fee_versions'][venue],day)['schedule'];schedule=P.J.LR.L.FeeSchedule(sd['schedule_id'],tuple(P.J.LR.L.FeeComponent(**x) for x in sd['components']))
                x,why=P.LR.preview(i,op,factor(sid,day),rule,schedule);assert why is None and x['maxq']==m['original_independent_maximum'];x['known_open']=op;i['_preview']=x;i['_preview_failure']=None
        intents.append(i)
    actual=[x for x in b['journal'] if x['kind']=='real_reserve' and x['at'][:10]==day];audits={x['order_id']:x for x in b['audit'] if x['kind']=='reserve'}
    expected=[dict(sid=x['sid'],role=x['role'],pool=x['pool'],quantity=x['shares'],price=D(x['price']),fee=D(audits[x['order']]['fee_reserved_cny'])) for x in actual]
    if day=='2023-01-20':
        cap=[x for x in stream(root/'capacity-checks.jsonl.gz') if x['at'][:10]==day];assert abs(state.nav-cap[0]['live_budget_NAV'])<1e-8 and abs(state.cash-cap[0]['cash'])<1e-8
    proof=dict(day=day,previous=previous,pending_orders_zero_from_original_reserved_balance=True,pending_exits_zero=True,no_overnight_account_actions=True,all_lots_from_previous_actual_daily=True,last_decision_core_lines_only=True,original_native_open_marks=True,
        cash=prev['available'],receivables=opening_dividend_AR,recorded_unpaid_dividend_accrual_bridge=accruals,AR_not_spendable=True,open_inventory=sum(x.qty*state.prices[x.stock] for x in lots),open_NAV=state.nav,decision_NAV=state.decision_nav,
        original_open_marks={sid:dict(price=prices[sid],source=marks[sid].source_id,known_at=marks[sid].known_at) for sid in prices},
        historical_shared_loss_preserved=prev['shared_loss'],lots=len(lots),frozen_role_intents=len(intents),active_financial_stage_fields=stageproof,
        field_projection_not_full_runner_restore=True,
        explicitly_not_reconstructed_and_not_read=['prior confirmed/expanded status before native migrate overwrites it','old zero-quantity order statuses; prior IDs preserved in stock_requests','ACT peak/global_watch/core_epoch object: frozen original intent membership proves eligibility and no overnight fills change core lock'],
        resource_reconstruction_does_not_call_original_economic_runner=True)
    return state,intents,expected,proof,at

def main():
    assert read(O/'SYNTHETIC_RESULTS.json')['passed'];begun=time.monotonic()
    codepaths=[O/'planner.py',O/'test_planner.py',Path(__file__),P.ROUTE_PATH,W/'account-risk-ablation-20261031/model_without_account_check.py',W/'probe-batch-design-review-20261101/CONTRACT_PROPOSAL.v2.txt',Path(P.LR.__file__),W/'case-stage-ledger-20261031/v3/joint_v3.py']
    freeze={str(p.resolve()):sha(p) for p in codepaths};save('CODE_FREEZE.json',dict(before_final_fixed_opening_previews=True,sha256=freeze,contract_version='v2',new_financial_paths=0))
    configs=[('2023-01-20','2023-01-19',W/'recovery-2023-readiness-20261101/runs/Bdiag/pair',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json'),('2022-06-29','2022-06-28',W/'2022-normal-reference-20261031/runs/B_diag/pair',W/'2022-normal-reference-20261031/inputs/MANIFEST.json')]
    with gzip.open(configs[1][2]/'daily.jsonl.gz','rt') as f:prev=next(json.loads(s) for s in f if configs[1][1] in s)
    # Market-only access to 44 original held layers. No Account/Contract or runner.
    ids=sorted({x['sid'] for x in prev['layers']});_,market,_=P.J.M.context('2023-01-20',ids=ids)
    summaries=[]
    for day,previous,root,rm in configs:
        s,intents,expected,proof,at=reconstruct(day,previous,root,rm,market);save(day+'_INPUT_VIEW.json',dict(state=s.view(),intents=[P.intent_view(i) for i in intents],proof=proof))
        native=P.plan(s,intents,at,'single_pass')
        compare=[{k:x[k] for k in ['sid','role','pool','quantity','price','fee']} for x in native['orders']]
        assert compare==expected,(day,'BASELINE_ORDER_IDENTITY_FAILURE',compare,expected)
        save(day+'_BASELINE_IDENTITY.json',dict(passed=True,original_orders=len(expected),all_order_sequence_role_pool_quantity_price_fee_exact=True,expected=expected,baseline=native))
        # Only after mandatory saved-baseline identity: local alternative plan.
        new=P.plan(s,intents,at,'two_pass');save(day+'_TWO_PASS.json',new)
        oldmap={x['sid']:x for x in native['orders']};newmap={x['sid']:x for x in new['orders']};changed=[]
        for sid in sorted(set(oldmap)|set(newmap)):
            a=oldmap.get(sid);b=newmap.get(sid)
            if a is None or b is None or any(a[k]!=b[k] for k in ['role','pool','quantity']):changed.append(dict(sid=sid,old=a,new=b))
        summary=dict(day=day,baseline_orders=len(native['orders']),two_pass_orders=len(new['orders']),added_stocks=sorted(set(newmap)-set(oldmap)),lost_stocks=sorted(set(oldmap)-set(newmap)),changes=changed,
            baseline={k:native[k] for k in ['capital','nominal_risk','cash_reserve','available','fees']},two_pass={k:new[k] for k in ['capital','nominal_risk','cash_reserve','available','fees']},input_pure=True,
            original_named_stock_check={sid:dict(baseline=oldmap.get(sid),two_pass=newmap.get(sid)) for sid in ['300308.SZ','300502.SZ']},migrations_baseline=len(native['migrations']),migrations_two_pass=len(new['migrations']),all_changes_local_no_followup_account=True)
        if day=='2022-06-29':assert not changed and not new['orders']
        save(day+'_COMPARISON.json',summary);summaries.append(summary)
    save('REAL_PREVIEW_SUMMARY.json',dict(passed=True,seconds=time.monotonic()-begun,days=summaries,no_economic_replay=True,no_account_progression=True,no_PnL=True,no_all_batch_preview=True))
    assert all(sha(p)==h for p,h in SOURCES.items());assert all(sha(p)==h for p,h in freeze.items());save('SOURCE_INPUT_HASHES.json',SOURCES)
    print('TWO_FIXED_OPENINGS_COMPLETE',round(time.monotonic()-begun,3),[(x['day'],x['baseline_orders'],x['two_pass_orders'],len(x['added_stocks']),len(x['lost_stocks'])) for x in summaries],flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        import traceback
        save('FAILURE.json',dict(reason=str(e),traceback=traceback.format_exc(),no_economic_replay=True,no_account_progression=True));raise
