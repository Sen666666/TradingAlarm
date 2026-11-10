"""Fixed-window read-only actual ledger reconstruction; never advances a trading engine."""
from pathlib import Path
from decimal import Decimal as D
import collections,hashlib,json,sys
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
from runner import read,save
ZERO=D(0)
START='2024-09-24';END='2024-10-08'
CASES={'300085.SZ':'银之杰','300570.SZ':'太辰光','000833.SZ':'粤桂股份'}
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')

def date(x):return str(pd.Timestamp(x).date())
def reconstruct(out):
    manifest={m['symbol']:m for m in read(MANIFEST)}
    raw={};facts={}
    def load(sid):
        if sid in raw:return
        m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==m['source_sha256'][p]
        fp=m['refs']['facts'];assert hashlib.sha256(Path(fp).read_bytes()).hexdigest()==m['output_sha256'][fp]
        raw[sid]=pd.read_parquet(p,columns=['raw_open','raw_close','adjustment_factor']);facts[sid]=pd.read_parquet(fp,columns=['i_floor'])
    journals=read(out/'EXACT_TRADE_JOURNAL.json');ledger=read(out/'DAY_LEDGER.json');claims=read(out/'CLAIM_LEDGER.json');audit=read(out/'AUDIT.json');archives=read(out/'ARCHIVES.json')
    byday=collections.defaultdict(list);clday=collections.defaultdict(list);prday=collections.defaultdict(list)
    for a in journals:byday[date(a['day'])].append(a)
    for a in claims:clday[date(a['day'])].append(a)
    for a in audit:
        if a['type']=='PROMOTED':prday[date(a['day'])].append(a)
    pos={};pools={};cash=D(1200000);recv=ZERO;planning=D(1200000);prior_day=None;rows=[];phase_checks=[]
    def apply(a):
        nonlocal cash
        rid=a['round_id'];p=pos.setdefault(rid,{'core':0,'add':0})
        for kind,x in a['report_only_allocations'].items():
            p[kind]+=int(x['q'])*(1 if a['side'].startswith('buy') else -1);cash+=D(x['cash_delta']);assert p[kind]>=0
        if a['side']=='buy_core':pools[rid]='probe'
    def gross(day,field):
        val=ZERO
        for rid,qs in pos.items():
            q=sum(qs.values())
            if not q:continue
            sid=archives[rid]['sid'];load(sid);z=raw[sid].loc[day,field]
            assert pd.notna(z) and z>0
            val+=D(q)*D(str(z))
        return val
    def reconcile(day,phase,expected):
        assert abs(cash-D(expected['cash']))<D('1e-7'),('CASH',day,phase,cash,expected['cash'])
        assert abs(recv-D(expected['receivable']))<D('1e-7'),('RECEIVABLE',day,phase)
        if expected['certified']:
            g=gross(day,'raw_open' if phase=='OPEN' else 'raw_close');nav=cash+recv+g
            assert abs(nav-D(expected['NAV']))<D('1e-7'),('NAV',day,phase,nav,expected['NAV'])
            assert abs(g-D(expected['gross_inventory']))<D('1e-7'),('INVENTORY',day,phase)
        phase_checks.append(dict(day=str(day.date()),phase=phase,cash_and_receivable_match=True,NAV_match=bool(expected['certified']),certified=expected['certified']))
    for n,row in enumerate(ledger):
        day=pd.Timestamp(row['day']);ds=str(day.date());acts=byday[ds]
        for cl in clday[ds]:
            if cl['event']=='ACCRUE_NET80':recv+=D(cl['receivable_delta']);cash+=D(str(cl['cash_delta']))
        for a in acts:
            if a['side'].startswith('sell'):apply(a)
        for p in prday[ds]:pools[p['round_id']]='confirmed'
        if START<=ds<=END:
            certified=row['OPEN'] is not None and row['OPEN']['certified']
            probe_cap=ZERO;probe_risk=ZERO;details=[];nav=None
            if certified:
                nav=cash+recv+gross(day,'raw_open')
                for rid,qs in pos.items():
                    if not sum(qs.values()) or pools.get(rid)!='probe':continue
                    assert qs['add']==0,('PROBE_WITH_ADD_REQUIRES_EXPLICIT_FLOOR_RECONSTRUCTION',rid)
                    sid=archives[rid]['sid'];load(sid);z=raw[sid].loc[day]
                    fl=D(str(facts[sid].loc[prior_day,'i_floor']))/D(str(z.adjustment_factor));mark=D(str(z.raw_open));q=qs['core']
                    cap=D(q)*mark;risk=D(q)*max(ZERO,mark-fl);probe_cap+=cap;probe_risk+=risk
                    details.append(dict(round_id=rid,sid=sid,q=q,raw_open=mark,prior_i_floor_raw=fl,capital=cap,nominal_risk=risk))
            rows.append(dict(day=ds,phase='POST_SELL_AND_PROMOTION_PRE_ALL_NEW_BUY_RESERVATIONS',certified=certified,NAV=nav,cash=cash,receivable=recv,planning_NAV=planning,
                probe_capital=probe_cap if certified else None,probe_nominal_risk=probe_risk if certified else None,
                probe_capital_headroom=nav*D('.10')-probe_cap if certified else None,probe_nominal_risk_headroom=nav*D('.005')-probe_risk if certified else None,
                cash_after_original_reserve=min(cash-planning*D('.10'),cash),unbooked_new_buy_fees_at_this_snapshot='0; each later reservation reduces effective NAV and cash by its fee',probe_holdings=details,
                unknown=[] if certified else row['OPEN'].get('unknown',[])))
        for a in acts:
            if a['side'].startswith('buy'):apply(a)
        if n:reconcile(day,'OPEN',row['OPEN'])
        for cl in clday[ds]:
            if cl['event']=='PAY_CLOSE_TRANSFER':cash+=D(cl['cash_delta']);recv+=D(str(cl['receivable_delta']))
        reconcile(day,'CLOSE',row['CLOSE'])
        if row['CLOSE']['certified']:planning=D(row['CLOSE']['NAV'])
        prior_day=day
    return dict(fixed_window=rows,reconciled_phases=len(phase_checks),certified_NAV_phase_checks=sum(x['NAV_match'] for x in phase_checks),phase_checks=phase_checks)

def details(out):
    dec=read(out/'DECISIONS.json');actions=read(out/'ACTIONS.json');audit=read(out/'AUDIT.json');ar=read(out/'ARCHIVES.json');mask=read(out/'MASK_AUDIT.json') if (out/'MASK_AUDIT.json').exists() else []
    reports={x['round_id']:x for x in read(out/'ROUND_REPORT.json')}
    window=[]
    daily=read(out/'DAY_LEDGER.json')
    for dayrow in daily:
        day=date(dayrow['day'])
        if not START<=day<=END:continue
        d=[x for x in dec if date(x['day'])==day];a=[x for x in actions if date(x['day'])==day];u=[x for x in audit if date(x['day'])==day]
        rejected=[x for x in u if x['type']=='BUDGET_REJECTED'];reserved=[x for x in u if x['type']=='RESERVED']
        all_reasons=collections.Counter();reject_reasons=collections.Counter()
        for x in rejected+reserved:
            for reason in set(r for trial in x['trials'] for r in trial['reasons']):all_reasons[(x['kind'],reason)]+=1
        for x in rejected:
            for reason in set(r for trial in x['trials'] for r in trial['reasons']):reject_reasons[(x['kind'],reason)]+=1
        signal_ids={x['round_id']:x['signal_day'] for x in a if x['side']=='buy_core'}
        window.append(dict(day=day,CLOSE_decisions=len(d),CLOSE_decision_counts=dict(collections.Counter(x['decision'] for x in d)),CLOSE_selected_pending=sum(x['selected'] for x in d),
            OPEN_actual_fills=dict(collections.Counter(x['side'] for x in a)),OPEN_buy_core_signal_days=signal_ids,
            OPEN_rejected_initials=sum(x['kind']=='INIT' for x in rejected),OPEN_reserved_initials=sum(x['kind']=='INIT' for x in reserved),
            all_trial_reasons_by_proposal=[dict(kind=k[0],reason=k[1],proposals=n) for k,n in sorted(all_reasons.items())],
            rejected_proposal_reasons=[dict(kind=k[0],reason=k[1],proposals=n) for k,n in sorted(reject_reasons.items())],
            reason_scope='A proposal may have multiple limiting reasons and multiple trial quantities; each reason counted once per proposal here; not mutually exclusive causal attribution.'))
    cases=[]
    for sid,name in CASES.items():
        births=[x for x in dec if x['sid']==sid]
        excluded=[{**x,'day':r['day']} for r in mask for x in r['excluded'] if x['sid']==sid]
        paths=[]
        for rid,st in ar.items():
            if st['sid']!=sid:continue
            aa=[x for x in actions if x['round_id']==rid]
            paths.append(dict(event_id=st['event_id'],round_id=rid,signal_day=st['signal_day'],state=st['state'],actions=aa,terminal_report=reports.get(rid),unknown_reason=st.get('unknown_reason')))
        cases.append(dict(sid=sid,name=name,decisions=births,mask_exclusions=excluded,actual_paths=paths))
    unknown=[x for x in audit if x['type']=='UNKNOWN']
    return dict(fixed_window_funnel=window,named_cases=cases,UNKNOWN_audit_total=len(unknown),UNKNOWN_explicit_zero_liability=sum(x.get('liability_free_initial') is True for x in unknown),UNKNOWN_not_proved_zero_by_flag=sum(x.get('liability_free_initial') is not True for x in unknown),unknown_semantics='Not proved zero is not a new liability classifier or a loss; original economic snapshot remains authoritative.')

def divergence(a,t):
    da={x['event_id']:x for x in read(a/'DECISIONS.json')};dt={x['event_id']:x for x in read(t/'DECISIONS.json')}
    excluded={x['event_id']:{**x,'day':m['day']} for m in read(t/'MASK_AUDIT.json') for x in m['excluded']}
    rows=[]
    for eid in set(da)|set(dt):
        x=da.get(eid);y=dt.get(eid)
        if x and y and (x['decision'],x.get('close_q'),x.get('selected'),x.get('selected_rank'))==(y['decision'],y.get('close_q'),y.get('selected'),y.get('selected_rank')):continue
        row=x or y;rows.append(dict(event_id=eid,sid=row['sid'],day=row['day'],all1709=x,tech407=y,tech_mask_excluded=excluded.get(eid)))
    rows.sort(key=lambda x:(date(x['day']),x['event_id']))
    def fillmap(out):
        arc=read(out/'ARCHIVES.json');return {(arc[x['round_id']]['event_id'],x['sid'],x['side'],x['day']):x for x in read(out/'ACTIONS.json')}
    fa=fillmap(a);ft=fillmap(t);fills=[]
    for k in set(fa)|set(ft):
        x=fa.get(k);y=ft.get(k)
        if x and y and all(x.get(v)==y.get(v) for v in ('q','price','fee')):continue
        fills.append(dict(event_id=k[0],sid=k[1],side=k[2],day=k[3],all1709=x,tech407=y))
    fills.sort(key=lambda x:(date(x['day']),x['event_id'],x['side']))
    return dict(first_decision_divergence=rows[0] if rows else None,first_fill_or_quantity_divergence=fills[0] if fills else None,
        all_decision_divergences=rows,all_fill_or_quantity_divergences=fills)

def main():
    if sys.argv[1]=='old_reference_test':
        out=ROOT.parent/'indexed_execution_v1/cohort_2024_924';v=reconstruct(out);save(HERE/'OLD_REFERENCE_RECONSTRUCTION_QA.json',v);print('PASS_OLD_REFERENCE',v['reconciled_phases']);return
    a=ROOT/'run_all1709_once';t=ROOT/'run_tech407_once'
    from analyze_outputs_v2 import validate
    validate(a);validate(t)
    result={arm:{'resources_and_headroom':reconstruct(out),'funnel_and_cases':details(out)} for arm,out in [('all1709',a),('tech407',t)]}
    result['divergence']=divergence(a,t);save(HERE/'ACTUAL_PATH_REPORT.json',result)
    print('SAVED_ACTUAL_PATH_REPORT')
if __name__=='__main__':main()
