"""Independent read-only arithmetic/coverage audit; no engine imports or economics.
Writes only uniquely named audit artifacts, never original or new ledger/report files.
"""
from pathlib import Path
from decimal import Decimal as N, ROUND_CEILING, ROUND_HALF_UP
from collections import defaultdict, Counter, deque
import argparse,json,csv,hashlib,math,re
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
D=R/'price_entry_generation_dynamic_v1'; J=R/'independent_channel_joint_economic_v1'; OUT=D/'independent_post_run_audit'
RULEPATH=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json')
ACTIONROOT=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CLOSED='COMPLETE_CONDITIONAL_STOCK_ROUND'; END='2026-06-30'
ZERO={'NEXT_OPEN_BELOW_PROTECTION_NOFILL','MINIMUM_LOT_NOT_FUNDED_NOFILL','PRECHECK_OPEN_AT_OR_BELOW_S_NO_SUBMIT','PRECHECK_Q0_NO_SUBMIT'}
read=lambda p:json.loads(Path(p).read_text()); sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
num=lambda x:N(str(x)); day=lambda x:str(x)[:10] if x is not None and str(x) not in ('','nan','NaT') else None
rules=read(RULEPATH); manifests={x['symbol']:x for x in read(MANIFEST)}
proxies=set(read(RULEPATH.with_name('economic-protocol.json'))['approved_proxy_ids'])
def rows(path):
    with Path(path).open(newline='') as f:return list(csv.DictReader(f))
def version(vs,d):
    found=[v for v in vs if v['from']<=d and (v.get('to') is None or d<v['to'])]
    assert len(found)==1,('BAD_DATED_VERSION',d)
    v=found[0];assert v.get('source_id')
    assert (v['basis']=='official_rule' and v.get('verification_status')=='verified') or (v['basis']=='explicit_research_proxy' and v['proxy_id'] in proxies)
    return v

def fee(sid,d,q,p,side):
    venue=version(rules['venue_versions'][sid],d)['venue']
    assert venue!='NEEQ'
    if venue in rules.get('venue_not_before',{}):assert d>=rules['venue_not_before'][venue]['from']
    sched=version(rules['fee_versions'][venue],d)['schedule']
    total=N(0)
    for c in sched['components']:
        if c.get('side','both') not in ('both',side):continue
        base={'notional':q*p,'shares':q,'par_value':q*num(rules['security_metadata'][sid]['par_value'])}[c.get('amount_basis','notional')]
        val=max(num(c.get('minimum_local',0)),base*num(c['rate']))
        if c.get('maximum_local') is not None:val=min(val,num(c['maximum_local']))
        if c.get('rounding_unit') is not None:
            u=num(c['rounding_unit']);val=(val/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
        total+=val
    return total

def close_enough(a,b,label,errs):
    if a is None or b is None:
        if a!=b:errs.append(dict(kind=label,expected=a,actual=b))
    elif not math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7):errs.append(dict(kind=label,expected=float(a),actual=float(b)))

def cov(rd,claims,events,cache):
    if rd['status'] in ZERO and not rd['_entered'] and not claims:return True,[]
    start=day(rd.get('entry_day')); end=day(rd.get('exit_day') if rd['status']==CLOSED else rd.get('status_day'))
    if start is None:return False,['NO_CONFIRMED_HOLDING']
    if end is None:return False,['MISSING_INTERVAL_END']
    inclusive=rd['status']==CLOSED or 'CENSORED' in rd['status']
    inside=lambda dt:bool(dt and start<dt and (dt<=end if inclusive else dt<end))
    sid=rd['sid']
    if sid not in cache:
        reasons=[];unparsed=[]
        p=ACTIONROOT/(sid+'.json')
        if not p.exists():cache[sid]=({},['MISSING_ACTION_SOURCE'],[])
        else:
            ac=read(p)
            if ac.get('series_id')!=sid or ac.get('currency')!='CNY':reasons.append('SOURCE_IDENTITY')
            if ac.get('raw_response_empty'):reasons.append('ACTION_RAW_RESPONSE_EMPTY')
            if not ac.get('coverage_evidence'):reasons.append('NO_RIGHTS_SOURCE')
            unparsed.extend(ac.get('unresolved',[]))
            dates=[]
            for ev in ac.get('events',[]):
                dt=ev.get('effective_date');dates.append(dt)
                if not dt or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',dt) or num(ev['split_ratio'])<=0 or num(ev['cash_per_old_share'])<0:reasons.append('BAD_ACTION')
            if len(dates)!=len(set(dates)):reasons.append('DUP_ACTION_DATE')
            for src in ac.get('coverage_evidence',[]):
                p=Path(src['path'])
                if not p.exists() or sha(p)!=src['sha256']:reasons.append('RIGHTS_HASH');continue
                raw=read(p)
                if not raw.get('records'):reasons.append('RIGHTS_EMPTY')
                unparsed.extend(raw.get('unparsed',[]))
            cache[sid]=(ac,reasons,unparsed)
    ac,reasons,unparsed=cache[sid];reasons=list(reasons)
    for u in unparsed:
        row=u.get('row',u) if isinstance(u,dict) else {}
        dt=row.get('1') or row.get('effective_date') or row.get('date')
        if not dt:
            m=re.search(r'\d{4}-\d{2}-\d{2}',str(u));dt=m.group() if m else None
        if dt and re.fullmatch(r'\d{8}',str(dt)):dt=f'{str(dt)[:4]}-{str(dt)[4:6]}-{str(dt)[6:]}'
        if not dt or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(dt)):reasons.append('UNPARSED_UNDATED')
        elif inside(dt):reasons.append('UNPARSED_IN_HELD_INTERVAL')
    for ev in ac.get('events',[]):
        if not inside(ev['effective_date']):continue
        adm=events.get((sid,ev['effective_date']))
        owned=[c for c in claims if adm and c['economic_event_id']==adm['economic_event_id'] and c.get('recognized') is True]
        if not adm or adm.get('entitlement_verified') is not True or not owned:reasons.append('UNVERIFIED_HELD_ACTION:'+ev['effective_date'])
        if adm and adm['event_type']!='PURE_CASH':reasons.append('UNADMITTED_QUANTITY_ACTION')
    return not reasons,sorted(set(reasons))

def metrics(vals):
    v=[float(x) for x in vals];win=[x for x in v if x>0];loss=[x for x in v if x<0]
    return dict(n=len(v),wins=len(win),losses=len(loss),zeros=len(v)-len(win)-len(loss),win_rate=len(win)/len(v) if v else None,net=sum(v),avg_net=sum(v)/len(v) if v else None,avg_win=sum(win)/len(win) if win else None,avg_loss=sum(loss)/len(loss) if loss else None,gross_win=sum(win),gross_loss=sum(loss),payoff=(sum(win)/len(win))/abs(sum(loss)/len(loss)) if win and loss else None,profit_factor=sum(win)/abs(sum(loss)) if loss else None)

def audit(window):
    nd=D/('gate_'+window); assert (nd/'COMPLETE_SAVED_SNAPSHOT.json').exists() and not (nd/'FAILED_NO_RETRY.json').exists(),'SNAPSHOT_NOT_READY'
    seal=read(nd/'OUTPUT_SEAL.json');assert sha(nd/'OUTPUT_SEAL.json')==read(nd/'COMPLETE_SAVED_SNAPSHOT.json')['output_seal_sha256']
    for name,h in seal.items():assert sha(nd/name)==h,('RAW_SEAL',name)
    repdir=D/('report_'+window);report=read(repdir/'COMPARISON_REPORT.json') if (repdir/'OUTPUT_SHA256.json').exists() else None
    if report:
        for name,h in read(repdir/'OUTPUT_SHA256.json').items():assert sha(repdir/name)==h,('REPORT_SEAL',name)
    orig=R/'m3_stock_birth_during_sector_v1'/('relative_priority_equity_run_2022_v1' if window=='2022' else 'cash_equity_baseline_2024_v1')
    events={(e['sid'],day(e['ex_date'])):e for e in read(orig/'ECONOMIC_EVENTS.json')}
    ebyid={e['economic_event_id']:e for e in events.values()}
    roster=[r['sid'] for r in rows(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')];assert len(roster)==len(set(roster))==1709
    result=[]; errors=[];stock_out=[];cache={};prices={};sources={str(RULEPATH):sha(RULEPATH),str(orig/'ECONOMIC_EVENTS.json'):sha(orig/'ECONOMIC_EVENTS.json')}
    for arm,path in [('baseline',J/('economic_'+window)),('joint',nd)]:
        rr=rows(path/'joint/ROUNDS.csv');aa=rows(path/'joint/ACTIONS.csv');cc=read(path/'joint/CLAIMS.json');books=read(path/'EXECUTION_BOOKS.json')
        ar=defaultdict(list);cr=defaultdict(list)
        for a in aa:ar[a['round_id']].append(a)
        for c in cc:cr[c['owner_round_id']].append(c)
        allids={r['round_id'] for r in rr};assert set(ar)<=allids and set(cr)<=allids
        for rd in rr:
            rid=rd['round_id'];sid=rd['sid'];act=ar[rid];claims=cr[rid];err0=len(errors)
            rd['_entered']=any(a['side']=='buy_core' for a in act)
            lots={'PROBE':deque(),'ADD':deque()};q={'PROBE':N(0),'ADD':N(0)};cf=N(0);corecf=N(0);fees=N(0);corefees=N(0)
            for a in act:
                qty=num(a['q']);p=num(a['price']);f=num(a['fee']);dt=day(a['day']);isbuy=a['side'].startswith('buy')
                assert qty>0 and qty==qty.to_integral_value(); calc=fee(sid,dt,qty,p,'buy' if isbuy else 'sell')
                close_enough(calc,f,'FULL_FEE:'+rid+':'+dt,errors);fees+=f
                cf+=(-qty*p-f if isbuy else qty*p-f)
                if isbuy:
                    role='PROBE' if a['side']=='buy_core' else 'ADD';q[role]+=qty;lots[role].append([qty,qty*p+f,dt])
                    if role=='PROBE':corecf-=qty*p+calc;corefees+=calc
                else:
                    takes={'PROBE':q['PROBE'],'ADD':q['ADD']} if a['side']=='sell_all' else {'ADD':qty}
                    assert sum(takes.values())==qty,(rid,'SELL_Q',a,takes)
                    for role,take in takes.items():
                        if role=='PROBE' and take:
                            cfee=fee(sid,dt,take,p,'sell');corefees+=cfee;corecf+=take*p-cfee
                        q[role]-=take; rem=take
                        while rem>0:
                            assert lots[role],('OVERSELL',rid)
                            lot=lots[role][0];assert lot[2]<dt,('T1_FAIL',rid,lot[2],dt)
                            z=min(rem,lot[0]);frac=z/lot[0];lot[1]-=lot[1]*frac;lot[0]-=z;rem-=z
                            if lot[0]==0:lots[role].popleft()
            inc=N(0);coreinc=N(0);paid=N(0);recv=N(0)
            for c in claims:
                e=ebyid[c['economic_event_id']];assert e['entitlement_verified'] and e['event_type']=='PURE_CASH'
                assert c['evidence_version']==e['evidence_version'] and day(c['ex_date'])==day(e['ex_date']) and day(c['pay_date'])==day(e['pay_date'])
                snapshot_q=N(0);snapshot_core=N(0)
                for a in act:
                    if day(a['day'])>day(c['inventory_snapshot_day']):continue
                    aq=num(a['q']);side=a['side'];snapshot_q+=aq if side.startswith('buy') else -aq
                    if side=='buy_core':snapshot_core+=aq
                    elif side=='sell_all':snapshot_core=N(0)
                close_enough(snapshot_q,num(c['record_q']),'CLAIM_RECORD_Q:'+rid,errors);close_enough(snapshot_core,num(c['core_record_q']),'CLAIM_CORE_Q:'+rid,errors)
                expected=num(c['record_q'])*num(c['d_cash'])*N('.8');expected_core=num(c['core_record_q'])*num(c['d_cash'])*N('.8')
                close_enough(expected,num(c['amount']),'CLAIM_NET80:'+rid,errors);close_enough(expected_core,num(c['core_amount']),'CLAIM_CORE_NET80:'+rid,errors)
                if c.get('recognized'):
                    inc+=num(c['amount']);coreinc+=num(c['core_amount'])
                    if c.get('settled'):paid+=num(c['amount'])
                    else:recv+=num(c['amount'])
            covered,reason=cov(rd,claims,events,cache)
            resp=books.get(rid,{}).get('responsibility');bookunknown=bool(resp and (resp.get('unknown') or resp.get('live_leaves',0) or resp.get('exit_pending') or not resp.get('all_orders_reconciled',False)))
            unknown='UNKNOWN' in rd['status'] or 'PENDING' in rd['status'] or bookunknown
            cost=sum(l[1] for ls in lots.values() for l in ls);realized=cf+cost;held=sum(q.values());terminal=None
            closed=rd['status']==CLOSED and rd['_entered']
            if closed:
                assert held==0,(rid,'CLOSED_INVENTORY')
                close_enough(cf+paid,num(rd['cash_after_payouts']),'CLOSED_CASH:'+rid,errors)
                close_enough(recv,num(rd['receivable_after_payouts']),'CLOSED_RECV:'+rid,errors)
                close_enough(cf+inc,num(rd['cash_after_payouts'])+num(rd['receivable_after_payouts']),'CLOSED_TOTAL:'+rid,errors)
            if not unknown:
                if held==0:terminal=N(0)
                elif day(rd.get('last_known_mark_day'))==END:
                    if sid not in prices:
                        sp=[(p,h) for p,h in manifests[sid]['source_sha256'].items() if p.endswith('/signal.parquet')];assert len(sp)==1
                        p,h=sp[0];assert sha(p)==h; frame=pd.read_parquet(p,columns=['raw_close']);prices[sid]=num(frame.loc[pd.Timestamp(END),'raw_close']);sources[p]=h
                    raw=prices[sid];close_enough(raw,num(rd['last_raw_close']),'END_RAW:'+rid,errors)
                    terminal=held*raw*N('.9995')-fee(sid,END,held,raw*N('.9995'),'sell')
                else:errors.append(dict(kind='UNVERIFIED_KNOWN_END_INVENTORY',rid=rid))
            total=cf+inc+terminal if terminal is not None else None
            full=cf+inc if closed else None
            coreclosed=corecf+coreinc if act and q['PROBE']==0 and not unknown else None
            record=dict(arm=arm,round_id=rid,sid=sid,lane=rd['owner_lane'],event_id=rd['event_id'],signal_day=rd['signal_day'],entry_day=rd.get('entry_day'),status=rd['status'],entered=rd['_entered'],financial_covered=covered,coverage_reasons=reason,unknown=unknown,book_derived_unresolved=bookunknown,full_closed=full,core_closed=coreclosed,independent_core_fees=corefees,full_fees=fees,trade_cashflow=cf,realized=realized,remaining_cost=cost,held_qty=held,net80=inc,net80_receivable=recv,terminal_net_liquidation=terminal,total=total,checks_new_errors=len(errors)-err0)
            result.append(record)
            if report:
                rc=next((c for c in report['round_coverage'] if c['arm']==arm and c['round_id']==rid),None);assert rc is not None
                if rc['financial_covered']!=covered:errors.append(dict(kind='COVERAGE_MISMATCH',rid=rid,arm=arm,report=rc,independent=reason))
                core=next((c for c in report['core_independent_dated_fee_diagnostics'] if c['arm']==arm and c['round_id']==rid),None)
                if core:
                    close_enough(corefees,core['independent_dated_fees'],'CORE_FEES:'+rid,errors)
                    # Engine diagnostics may include a closed core with book liability; summary must exclude it.
                    expected_core=corecf+coreinc if act and q['PROBE']==0 and 'UNKNOWN' not in rd['status'] else None
                    close_enough(expected_core,core['closed_net'],'CORE_NET:'+rid,errors)
        for sid in roster:
            rs=[r for r in result if r['arm']==arm and r['sid']==sid]
            unknown=any(r['unknown'] for r in rs); covered=all(r['financial_covered'] for r in rs)
            total=sum((r['total'] for r in rs),N(0)) if all(r['total'] is not None for r in rs) else None
            s=dict(arm=arm,sid=sid,rounds=len(rs),entered_rounds=sum(r['entered'] for r in rs),financial_covered=covered,unknown=unknown,total=total,realized=sum((r['realized'] for r in rs),N(0)),net80=sum((r['net80'] for r in rs),N(0)),net80_receivable=sum((r['net80_receivable'] for r in rs),N(0)),remaining_cost=sum((r['remaining_cost'] for r in rs),N(0)),known_terminal_net_liquidation=sum((r['terminal_net_liquidation'] for r in rs),N(0)) if all(r['terminal_net_liquidation'] is not None for r in rs) else None)
            stock_out.append(s)
            if report:
                sr=next(x for x in report['stock_rows'] if x['arm']==arm and x['sid']==sid)
                close_enough(total,sr['known_total_pnl'],'STOCK_TOTAL:'+arm+':'+sid,errors)
                if unknown!=sr['unknown_liability'] or covered!=sr['financial_covered']:errors.append(dict(kind='STOCK_COVERAGE_OR_UNKNOWN',sid=sid,arm=arm,independent=s,report=sr))
    stocks={(s['arm'],s['sid']):s for s in stock_out};common={sid for sid in roster if all(stocks[a,sid]['financial_covered'] and stocks[a,sid]['total'] is not None for a in ['baseline','joint'])}
    met=[];summary=[]
    for arm in ['baseline','joint']:
        rs=[r for r in result if r['arm']==arm];ss=[s for s in stock_out if s['arm']==arm]
        summary.append(dict(arm=arm,fixed_stocks=1709,registered_rounds=len(rs),entered_rounds=sum(r['entered'] for r in rs),unknown_registered_rounds=sum(r['unknown'] for r in rs),unknown_entered_rounds=sum(r['unknown'] and r['entered'] for r in rs),uncovered_registered_rounds=sum(not r['financial_covered'] for r in rs),uncovered_entered_rounds=sum(not r['financial_covered'] and r['entered'] for r in rs),entered_stocks=sum(s['entered_rounds']>0 for s in ss),unknown_stocks=sum(s['unknown'] for s in ss),financial_uncovered_stocks=sum(not s['financial_covered'] for s in ss),common_stocks=len(common),common_net=sum((s['total'] for s in ss if s['sid'] in common),N(0)),common_realized=sum((s['realized'] for s in ss if s['sid'] in common),N(0)),common_net80=sum((s['net80'] for s in ss if s['sid'] in common),N(0)),common_remaining_cost=sum((s['remaining_cost'] for s in ss if s['sid'] in common),N(0)),common_terminal_net_liquidation=sum((s['known_terminal_net_liquidation'] for s in ss if s['sid'] in common),N(0)),unknown_remaining_cost=sum((s['remaining_cost'] for s in ss if s['unknown']),N(0))))
        for scope in ['ALL_FIXED_1709','COMMON_COMPARABLE_STOCKS']:
            for lane in ['ALL','AB','PRICE']:
                subset=[r for r in rs if r['entered'] and (scope=='ALL_FIXED_1709' or r['sid'] in common) and (lane=='ALL' or r['lane']==lane)]
                for role,col in [('FULL_ROUND','full_closed'),('FIRST_PROBE_INDEPENDENT_DATED_FEES','core_closed')]:
                    vals=[r[col] for r in subset if r['financial_covered'] and not r['unknown'] and r[col] is not None]
                    met.append(dict(arm=arm,cohort=scope,lane=lane,role=role,entered_rounds=len(subset),unknown_entered=sum(r['unknown'] for r in subset),financial_uncovered_entered=sum(not r['financial_covered'] for r in subset),**metrics(vals)))
    if report:
        published=read(repdir/'ROUND_METRICS.json')
        for m in met:
            p=next(x for x in published if all(x[k]==m[k] for k in ['arm','cohort','lane','role']) and x['coverage_filter']=='FINANCIALLY_COVERED_CLOSED')
            for ours,theirs in [('n','closed_net_denominator'),('net','net'),('win_rate','win_rate'),('avg_net','net_per_known_unit'),('avg_win','mean_win'),('avg_loss','mean_loss'),('profit_factor','profit_factor')]:close_enough(m[ours],p[theirs],'ROUND_METRIC:'+str((m['arm'],m['cohort'],m['lane'],m['role'],ours)),errors)
        for s in summary:
            p=next(x for x in report['summary'] if x['arm']==s['arm'])
            close_enough(s['common_net'],p['common_covered_pnl'],'COMMON_TOTAL:'+s['arm'],errors)
            assert set(p['common_covered_sids'])==common
    def clean(v):
        if isinstance(v,N):return float(v)
        if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
        if isinstance(v,list):return [clean(x) for x in v]
        return v
    output=clean(dict(window=window,status='PASS_INDEPENDENT_SAVED_LEDGER_FINANCIAL_AUDIT' if not errors else 'FAIL_REVIEW_REQUIRED',report_available=report is not None,new_economic_runs=0,source_sha256=sources,new_snapshot_seal_sha256=sha(nd/'OUTPUT_SEAL.json'),limitations=['Conditional per-stock currency PnL, not shared-cash account ROI.','Actual broker ACK/fill not provided.','Unknown PnL is null; remaining cost is recorded separately.','Financial coverage is independent source and held interval evidence, not closed flag.'],summary=summary,metrics=met,errors=errors,rounds=result,stocks=stock_out))
    target=OUT/('FINANCIAL_'+window+('_WITH_REPORT' if report else '_RAW')+'.json')
    with target.open('x') as f:json.dump(output,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:output[k] for k in ['window','status','report_available','summary','errors']},ensure_ascii=False),flush=True)
    print('SAVED',target,'SHA256',sha(target),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['2022','2024'],required=True);audit(ap.parse_args().window)
