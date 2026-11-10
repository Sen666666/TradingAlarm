"""Independent read-only posterior audit. No historical consumer execution."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import argparse,csv,hashlib,json,math,os,sys
import numpy as np,pandas as pd
O=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent
sys.dont_write_bytecode=True;sys.path.insert(0,str(O));import runtime
S=runtime.SOURCE
sys.path.insert(0,str(S))
from baseline_regression import load_engine
from report_adapter import financial_coverage,KNOWN_NO_ENTRY
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def day(v):return str(v)[:10]
def num(v,default=0.):return default if v is None or v=='' else float(v)
def truth(v):return v is True or v=='True'
def close(a,b,label,tol=1e-6):
    assert math.isfinite(float(a)) and math.isfinite(float(b)) and abs(float(a)-float(b))<=tol,(label,a,b)
def groups(xs,key):
    out=defaultdict(list)
    for x in xs:out[key(x)].append(x)
    return out
def canonical(x):
    if isinstance(x,dict):return {k:canonical(v) for k,v in x.items() if v is not None and v!=''}
    if isinstance(x,list):return [canonical(v) for v in x]
    return x
def write(p,v):
    tmp=Path(str(p)+'.tmp')
    with tmp.open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False,default=str);f.flush();os.fsync(f.fileno())
    os.link(tmp,p);tmp.unlink()
def integrity(w):
    dest=O/('dmi_'+w);report=O/('report_'+w)
    au=read(O/'ROOT_DMI_AUTHORIZATION.json');audit=read(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json')
    expected='c9f554957b0e3c83cf6274ab7c26d03111613d0a9be853f03ac11e20291cc16c'
    assert sha(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json')==expected==au['implementation_audit_sha256']
    assert au['explicit_root_authorized'] and au['scope']=='ONE_FIXED_PRICE_DMI_PRIORITY_2022_2024_DYNAMIC_STOCK_COMPARISON'
    assert au['windows']==['2022','2024'] and au['authorization_evidence']
    assert au['code_sha256']==audit['reviewed_code_sha256'] and au['input_sha256']==audit['reviewed_input_sha256']
    for p,h in au['code_sha256'].items():assert sha(O/p)==h,('CODE_DRIFT',p)
    for p,h in au['input_sha256'].items():assert sha(p)==h,('INPUT_DRIFT',p)
    for k in ['STARTED.json','COMPLETE_SAVED_SNAPSHOT.json']:
        z=read(dest/k);assert z['authorization_sha256']==sha(O/'ROOT_DMI_AUTHORIZATION.json')
        assert z['protocol_sha256']==sha(O/'DYNAMIC_PROTOCOL.json')
    lock=read(O/('DMI_RUN_ONCE_'+w+'.json'));assert lock['window']==w and lock['authorization_sha256']==sha(O/'ROOT_DMI_AUTHORIZATION.json') and lock['retry'] is False
    complete=read(dest/'COMPLETE_SAVED_SNAPSHOT.json')
    assert complete['implementation_audit_sha256']==expected and complete['raw_ledger_and_rank_audit_saved']
    assert complete['output_seal_sha256']==sha(dest/'OUTPUT_SEAL.json')
    seal=read(dest/'OUTPUT_SEAL.json')
    for p,h in seal.items():assert sha(dest/p)==h,('SNAPSHOT_DRIFT',p)
    required={'DMI_RANK_AUDIT.json','PRICE_AUDIT.json','OFFER_AUDIT.json','AB_DECISION_AUDIT.json','FROZEN_RESPONSIBILITIES.json','EXECUTION_BOOKS.json','LOOP_QA.json','joint/ROUNDS.csv','joint/ACTIONS.csv','joint/CLAIMS.json','joint/CLAIM_LEDGER.csv','joint/OUTPUT_HASHES.json'}
    assert required<=set(seal)
    for p,h in read(dest/'joint/OUTPUT_HASHES.json').items():assert sha(dest/'joint'/p)==h
    for p,h in read(report/'OUTPUT_SHA256.json').items():assert sha(report/p)==h,('REPORT_DRIFT',p)
    assert read(report/'REPORT_QA.json')['report_code_sha256']==sha(O/'report_saved.py')
    assert not (dest/'FAILED_NO_RETRY.json').exists(),'FAILED_RUN_REQUIRES_EXPLICIT_REVIEW'
    return dict(root_authorization_sha256=sha(O/'ROOT_DMI_AUTHORIZATION.json'),once_lock_sha256=sha(O/('DMI_RUN_ONCE_'+w+'.json')),snapshot_sha256=sha(dest/'COMPLETE_SAVED_SNAPSHOT.json'),output_seal_sha256=sha(dest/'OUTPUT_SEAL.json'),report_seal_sha256=sha(report/'OUTPUT_SHA256.json')),dest,report
def rank_check(w,dest):
    actual=rows(dest/'joint/RANKING_AUDIT.csv')
    audit=read(dest/'DMI_RANK_AUDIT.json')
    f=pd.read_parquet(O/'features/ALL_PRICE_RECEIPT_FEATURES.parquet')
    window='2022' if w=='2022' else '2024_924';f=f[f.window.eq(window)]
    feat={(r.sid,day(r.day)):r.d for r in f.itertuples()}
    ix={(day(r['day']),r['sector'],r['sid']):r for r in audit}
    assert len(ix)==len(audit)==len(actual)
    def key(r):
        known=truth(r['PVR_known']) and r['PVR_score']!='' and math.isfinite(float(r['PVR_score']))
        assert known or r['owner_lane']=='PRICE'
        return (0,-float(r['PVR_score']),r['sid']) if known else (1,0.,r['sid'])
    changed=mutable=0;oldstatic=0
    for ds,qs in groups(actual,lambda r:(r['day'],r['sector'])).items():
        assert len({r['sid'] for r in qs})==len(qs)
        orig=sorted(qs,key=key);expected=list(orig);slots=[]
        for i,r in enumerate(orig):
            assert r['stock_state_before']=='FLAT' and r['close_check']=='PASS'
            if r['owner_lane']=='PRICE':
                assert (r['sid'],r['day']) in feat
                dd=feat[r['sid'],r['day']]
                if key(r)[0]==0 and math.isfinite(dd):slots.append(i)
        ordered=sorted([orig[i] for i in slots],key=lambda r:(-feat[r['sid'],r['day']],-float(r['PVR_score']),r['sid']))
        for i,r in zip(slots,ordered):expected[i]=r
        prior={r['sid']:i+1 for i,r in enumerate(orig)}
        assert sum(truth(r['selected']) for r in qs)==min(2,len(qs))
        assert sum(r['owner_lane']=='PRICE' for r in orig[:2])==sum(r['owner_lane']=='PRICE' for r in expected[:2])
        for i,r in enumerate(expected,1):
            z=ix[r['day'],r['sector'],r['sid']];mut=prior[r['sid']]-1 in slots
            assert int(r['joint_feasible_rank'])==i and truth(r['selected'])==(i<=2)
            assert int(z['original_numeric_rank'])==prior[r['sid']] and int(z['dmi_numeric_rank'])==i
            assert z['mutable']==mut and z['dmi_selected']==(i<=2)
            assert z['rank_changed']==(i!=prior[r['sid']])
            if not mut:assert i==prior[r['sid']]
            if r['owner_lane']=='PRICE':close(z['d'],feat[r['sid'],r['day']],('DMI_FEATURE',r['sid'],r['day']),0.)
            changed+=i!=prior[r['sid']];mutable+=mut
    offers=read(dest/'OFFER_AUDIT.json')
    apps=[(r['sid'],day(r['day'])) for r in offers if r['owner_lane']=='PRICE' and r['result']=='APPLICATION']
    assert len(apps)==len(set(apps))==len(feat) and set(apps)==set(feat)
    choices={(r['sid'],r['day']):r for r in actual};assert len(choices)==len(actual)
    ab=read(dest/'AB_DECISION_AUDIT.json');abpass=0
    offerix=groups(offers,lambda r:(r['sid'],day(r['day']),r['owner_lane']))
    for r in ab:
        if r['decision_before_joint']=='PASS_TO_JOINT_QUEUE':
            k=(r['sid'],day(r['day']));assert choices[k]['owner_lane']=='AB';abpass+=1
            if k in feat:assert any(x['result']=='SUPPRESSED_BY_AB_VALID_CLOSE' for x in offerix[k+('PRICE',)])
    static=pd.read_parquet(O.parent/'price_dmi_priority_preflight_v1/SEALED_RANKS.parquet')
    static=static[static.year.eq(int(w))]
    oldkeys={(r.sid,day(r.day)) for r in static.itertuples() if r.owner_lane=='PRICE'}
    newly_feasible=sum(r['owner_lane']=='PRICE' and (r['sid'],r['day']) not in oldkeys for r in actual)
    return dict(rows=len(actual),queues=len(groups(actual,lambda r:(r['day'],r['sector']))),mutable=mutable,moved=changed,ab_legal_precedence_checks=abpass,complete_price_applications=len(apps),new_price_feasible_keys_vs_static=newly_feasible,ab_unknown_slots_exact=True,selected_count_and_price_budget_exact=True)
def fee(s,sid,date,q,price,side):
    _,fs,par=s.getmeta(sid,pd.Timestamp(date))
    return s.fee(int(q),D(str(price)),fs,side,par)
def ledger_check(directory,evidence,arm):
    rr=rows(directory/'joint/ROUNDS.csv');aa=rows(directory/'joint/ACTIONS.csv')
    cc=read(directory/'joint/CLAIMS.json');cl=rows(directory/'joint/CLAIM_LEDGER.csv');books=read(directory/'EXECUTION_BOOKS.json')
    ri={r['round_id']:r for r in rr};assert len(ri)==len(rr)
    acts=groups(aa,lambda r:r['round_id']);claims=groups(cc,lambda r:r['owner_round_id'])
    led=groups(cl,lambda r:(r['round_id'],r['economic_event_id']))
    assert len({json.dumps(c['key']) for c in cc})==len(cc)
    for c in cc:
        assert c['recognized'] is True
        close(D(str(c['amount'])),D(str(c['record_q']))*D(str(c['d_cash']))*D('.8'),('NET80',c['key']))
        close(D(str(c['core_amount'])),D(str(c['core_record_q']))*D(str(c['d_cash']))*D('.8'),('CORE_NET80',c['key']))
        z=led[c['owner_round_id'],c['economic_event_id']]
        accr=[x for x in z if x['event']=='ACCRUE_NET80'];pay=[x for x in z if x['event']=='PAY_CLOSE_TRANSFER']
        assert len(accr)==1 and day(accr[0]['day'])==day(c['ex_date'])
        close(accr[0]['cash_delta'],0,('ACCRUAL_CASH',c['key']))
        close(accr[0]['receivable_delta'],c['amount'],('ACCRUAL_REC',c['key']))
        assert len(pay)==int(c['settled'])
        if pay:
            assert day(pay[0]['day'])==day(c['pay_date'])
            close(pay[0]['cash_delta'],c['amount'],('PAY_CASH',c['key']))
            close(pay[0]['receivable_delta'],-D(str(c['amount'])),('PAY_REC',c['key']))
    result=[];fees_checked=0;lot_sales=0
    cal=[day(d) for d in evidence.cal];next_common=dict(zip(cal,cal[1:]))
    for rid,r in ri.items():
        seq=acts[rid];assert [x['day'] for x in seq]==sorted(x['day'] for x in seq)
        q=core=add=0;cash=spent=fees=probe=D(0);bought=defaultdict(int);positions={}
        for x in seq:
            n=int(x['q']);price=D(x['price']);f=D(x['fee']);dt=x['day'];side=x['side']
            close(f,fee(evidence,r['sid'],dt,n,price,'buy' if side.startswith('buy') else 'sell'),('DATED_FEE',rid,dt,side))
            fees_checked+=1
            if side.startswith('buy'):
                q+=n;bought[dt]+=n;cash-=D(n)*price+f;spent+=D(n)*price+f
                if side=='buy_core':
                    assert dt==next_common[day(r['signal_day'])],('SIGNAL_TO_NEXT_COMMON_OPEN',rid)
                    core+=n;probe-=D(n)*price+fee(evidence,r['sid'],dt,n,price,'buy')
                elif side=='buy_add':add+=n
                else:raise AssertionError(('UNKNOWN_BUY_SIDE',side))
            else:
                assert n<=q-bought[dt],('T_PLUS_ONE',rid,dt);q-=n;cash+=D(n)*price-f
                if side=='sell_all':
                    assert n==core+add
                    if core:probe+=D(core)*price-fee(evidence,r['sid'],dt,core,price,'sell')
                    core=add=0
                elif side=='sell_add':assert n<=add;add-=n
                else:raise AssertionError(('UNKNOWN_SELL_SIDE',side))
            fees+=f;assert q==core+add and q>=0;positions[dt]=(q,core)
        for c in claims[rid]:
            held=[date for date in positions if date<=day(c['inventory_snapshot_day'])]
            inv=positions[max(held)] if held else (0,0)
            assert inv==(int(c['record_q']),int(c['core_record_q'])),('RECORD_INVENTORY',rid,c['economic_event_id'],inv)
        income=sum((D(str(c['amount'])) for c in claims[rid] if c['recognized']),D(0))
        paid=sum((D(str(c['amount'])) for c in claims[rid] if c['settled']),D(0));recv=income-paid
        close(r['cash_after_payouts'],cash+paid,('CASH',rid))
        close(r['receivable_after_payouts'],recv,('RECEIVABLE',rid))
        close(r['dividend_net80_total'],income,('INCOME_ONCE',rid));close(r['dividend_net80_paid'],paid,('PAID',rid))
        if seq:
            close(r['all_fees'],fees,('FEES',rid));close(r['total_buy_cash'],spent,('BUY_CASH',rid))
            assert q==num(r['core_qty'])+num(r['add_qty'])
        else:assert q==0 and fees==spent==0 # Empty saved fee/inventory fields stay missing, not a known total.
        book=books.get(rid);responsibility=book['responsibility'] if book else {}
        bu=bool(responsibility and (responsibility['unknown'] or responsibility['live_leaves'] or responsibility['exit_pending'] or not responsibility['all_orders_reconciled']))
        unknown='UNKNOWN' in r['status'] or 'PENDING' in r['status'] or bu
        entered=any(x['side'].startswith('buy') for x in seq)
        full=cash+income if r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND' and entered else None
        if full is not None:assert q==0;close(r['net_pnl'],full,('CLOSED_NET',rid))
        probe+=sum((D(str(c['core_amount'])) for c in claims[rid] if c['recognized']),D(0))
        coreclosed=entered and core==0 and 'UNKNOWN' not in r['status']
        probeclosed=probe if coreclosed else None
        zero=r['status'] in KNOWN_NO_ENTRY and not seq and not claims[rid] and q==0 and recv==0
        cv=dict(financial_covered=True,reason='KNOWN_ZERO_TERMINATED_NO_ENTRY') if zero else financial_coverage(evidence,{k:v for k,v in r.items() if v!=''},claims[rid])
        total=None
        if not unknown:
            if q==0:total=cash+income
            elif 'CENSORED' in r['status'] and day(r['last_known_mark_day'])=='2026-06-30':
                mark=D(r['last_raw_close'])*(1-D('.0005'))
                total=cash+income+D(q)*mark-fee(evidence,r['sid'],'2026-06-30',q,mark,'sell')
        result.append(dict(sid=r['sid'],arm=arm,owner_lane=r['owner_lane'],round_id=rid,status=r['status'],entered=entered,unknown=unknown,known_zero_no_responsibility=zero,book_unresolved=bu,financial_covered=cv['financial_covered'],coverage_reason=cv['reason'],full_closed_net=None if full is None else float(full),probe_closed_net=None if probeclosed is None else float(probeclosed),known_total=None if total is None else float(total)))
        if book:
            assert responsibility['evidence_domain']=='PROXY' and responsibility['held_qty']==q
            assert sum(int(x['remaining']) for x in book['lots'].values())==q
            for order in book['orders'].values():
                assert order['evidence_domain']=='PROXY'
                if order['side']=='SELL':
                    assert sum(int(qty) for lot,qty in order['allocations'])==order['quantity']
                    for lot,qty in order['allocations']:assert day(order['decision_open'])>day(book['lots'][lot]['buy_day']);lot_sales+=1
            for parent in book['parents'].values():
                t=parent['target'];assert next_common[day(t['signal_receipt_id'][1])]==day(t['decision_open'])
                assert t['budget']<=24000
            if r['owner_lane']=='PRICE':assert book['responsibility']['root_id']==list(__import__('ast').literal_eval(r['price_root']))
    return result,dict(rounds=len(rr),actions=len(aa),dated_fees_checked=fees_checked,claims_net80=len(cc),t_plus_one_lot_allocations=lot_sales,inventory_cash_receivable_fees_exact=True),dict(rounds=rr,actions=aa,claims=cc,books=books)
def retained_ab(old,new):
    b={r['event_id']:r for r in old['rounds'] if r['owner_lane']=='AB'};j={r['event_id']:r for r in new['rounds'] if r['owner_lane']=='AB'}
    assert len(b)==sum(r['owner_lane']=='AB' for r in old['rounds']) and len(j)==sum(r['owner_lane']=='AB' for r in new['rounds'])
    ba=groups(old['actions'],lambda r:r['round_id']);ja=groups(new['actions'],lambda r:r['round_id'])
    bc=groups(old['claims'],lambda r:r['owner_round_id']);jc=groups(new['claims'],lambda r:r['owner_round_id'])
    fields=['sid','economic_event_id','evidence_version','record_date','inventory_snapshot_day','snapshot_kind','state','record_q','core_record_q','exitpending','amount','core_amount','recognized','settled','ex_date','pay_date','d_cash']
    for event in set(b)&set(j):
        x,y=b[event],j[event]
        pa=lambda xs:[canonical({k:v for k,v in a.items() if k not in ['round_id','arm']}) for a in xs]
        assert pa(ba[x['round_id']])==pa(ja[y['round_id']]),('RETAINED_AB_ACTION',event)
        pc=lambda xs:[canonical({k:a.get(k) for k in fields}) for a in xs]
        assert pc(bc[x['round_id']])==pc(jc[y['round_id']]),('RETAINED_AB_CLAIM',event)
        assert [x.get(k) for k in ['status','exit_day','exit_price','exit_reason']]==[y.get(k) for k in ['status','exit_day','exit_price','exit_reason']],('RETAINED_AB_EXIT',event)
    return dict(retained=len(set(b)&set(j)),old_only=len(set(b)-set(j)),new_only=len(set(j)-set(b)),actions_claims_exit_exact=True)
def dist(values):
    v=np.asarray(values,dtype=float);win=v[v>0];loss=v[v<0]
    return dict(known_count=len(v),wins=len(win),losses=len(loss),zeros=int((v==0).sum()),win_rate=len(win)/len(v) if len(v) else None,net=float(v.sum()),net_per_known_unit=float(v.mean()) if len(v) else None,mean_win=float(win.mean()) if len(win) else None,mean_loss=float(loss.mean()) if len(loss) else None,payoff_mean_win_over_abs_mean_loss=float(win.mean()/abs(loss.mean())) if len(win) and len(loss) else None)
def compare_dist(actual,expected,label):
    for k,v in expected.items():
        if v is None:assert actual[k] is None,(label,k)
        else:close(actual[k],v,(label,k),1e-5 if k=='net' else 1e-6)
def metrics_check(reportdir,rounds,w):
    report=read(reportdir/'COMPARISON_REPORT.json');summary=read(reportdir/'SUMMARY.json')
    stockix={(r['arm'],r['sid']):r for r in report['stock_rows']}
    roster=set(r['sid'] for r in report['stock_rows']);assert len(roster)==1709 and len(stockix)==3418
    grouped=groups(rounds,lambda r:(r['arm'],r['sid']))
    cov={(r['arm'],r['round_id']):r for r in report['round_coverage']}
    for r in rounds:
        c=cov[r['arm'],r['round_id']];assert c['financial_covered']==r['financial_covered'] and c['reason']==r['coverage_reason'],('ROUND_COVERAGE',r['round_id'])
    for key,s in stockix.items():
        rs=grouped[key];unk=any(r['unknown'] for r in rs)
        assert s['unknown_liability']==unk,(key,'UNKNOWN_LIABILITY')
        assert s['never_entered']==all(r['known_zero_no_responsibility'] for r in rs),(key,'NEVER_ENTERED_RESPONSIBILITY')
        assert s['financial_covered']==all(r['financial_covered'] for r in rs),(key,'FINANCIAL_COVERAGE')
        total=None if any(r['known_total'] is None for r in rs) else sum(r['known_total'] for r in rs)
        if total is None:assert s['known_total_pnl'] is None,(key,'UNKNOWN_NOT_ZERO')
        else:close(s['known_total_pnl'],total,(key,'STOCK_TOTAL'),1e-5)
        assert s['comparable']==(s['financial_covered'] and total is not None)
    common={sid for sid in roster if all(stockix[arm,sid]['comparable'] for arm in ['baseline','joint'])}
    assert all(set(x['common_covered_sids'])==common for x in report['summary'])
    assert summary['common_comparable_stocks']==len(common)
    old=sum(stockix['baseline',sid]['known_total_pnl'] for sid in common);new=sum(stockix['joint',sid]['known_total_pnl'] for sid in common)
    close(summary['old_net_common'],old,'OLD_COMMON',1e-5);close(summary['new_net_common'],new,'NEW_COMMON',1e-5);close(summary['common_delta'],new-old,'DELTA',1e-5)
    assert summary['unknown']['old']==sum(s['unknown_liability'] for (arm,sid),s in stockix.items() if arm=='baseline')
    assert summary['unknown']['new']==sum(s['unknown_liability'] for (arm,sid),s in stockix.items() if arm=='joint')
    assert not any(summary['unknown_round_stock_mismatch'].values())
    published=read(reportdir/'ROUND_METRICS.json');recomputed=[]
    for m in published:
        rs=[r for r in rounds if r['arm']==m['arm'] and r['entered'] and (m['lane']=='ALL' or r['owner_lane']==m['lane']) and (m['cohort']=='ALL_FIXED_1709' or r['sid'] in common)]
        col='full_closed_net' if m['role']=='FULL_ROUND' else 'probe_closed_net'
        usable=[r for r in rs if r[col] is not None and not r['unknown'] and (m['coverage_filter']=='ALL_CONDITIONAL_CLOSED' or r['financial_covered'])]
        d=dist([r[col] for r in usable]);compare_dist(m,d,(m['cohort'],m['arm'],m['lane'],m['role'],m['coverage_filter']))
        assert m['entered_rounds']==len(rs) and m['closed_net_denominator']==len(usable)
        recomputed.append(dict({k:m[k] for k in ['cohort','arm','lane','role','coverage_filter']},**d))
    for m in read(reportdir/'STOCK_METRICS.json'):
        cohort=[s for (arm,sid),s in stockix.items() if arm==m['arm'] and (m['cohort']=='ALL_FIXED_1709' or sid in common)]
        ent=[s for s in cohort if any(r['entered'] for r in grouped[m['arm'],s['sid']])]
        known=[s for s in ent if s['known_total_pnl'] is not None]
        compare_dist(m['known_participant_distribution'],dist([s['known_total_pnl'] for s in known]),('STOCK',m['cohort'],m['arm']))
        assert m['entered_stocks']==len(ent)
        ordered=sorted(known,key=lambda s:s['known_total_pnl'])
        assert [r['sid'] for r in m['bottom20']]==[r['sid'] for r in ordered[:20]]
        assert [r['sid'] for r in m['top20']]==[r['sid'] for r in ordered[-20:][::-1]]
    target=[m for m in recomputed if m['cohort']=='ALL_FIXED_1709' and m['lane']=='ALL' and m['role']=='FIRST_PROBE_INDEPENDENT_DATED_FEES' and m['coverage_filter']=='FINANCIALLY_COVERED_CLOSED']
    assert len(target)==2
    oldm=next(m for m in target if m['arm']=='baseline')
    expected=(.2889,-371.) if w=='2022' else (.4643,1480.)
    assert abs(oldm['win_rate']-expected[0])<.0001 and abs(oldm['net_per_known_unit']-expected[1])<1.5,('USER_PRIOR_METRIC_SCOPE_MISMATCH',oldm)
    return dict(common_comparable=len(common),common_old_net=old,common_new_net=new,common_delta=new-old,user_prior_comparable_scope=target,all_round_metric_cells_reconciled=len(published),unknown_common_stock_totals_and_tails_reconciled=True,adapter_blockers=report['adapter_blockers']),recomputed
def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True);w=p.parse_args().window
    integ,dest,report=integrity(w);rank=rank_check(w,dest)
    protected={str(x):sha(x) for folder in [dest,report,S/('economic_'+w)] for x in folder.rglob('*') if x.is_file()}
    evidence=load_engine(w);assert not evidence.actions and not evidence.rounds and not evidence.claims
    old,oq,oraw=ledger_check(S/('economic_'+w),evidence,'baseline')
    new,nq,nraw=ledger_check(dest,evidence,'joint')
    ab=retained_ab(oraw,nraw);met,allmet=metrics_check(report,old+new,w)
    assert not evidence.actions and not evidence.rounds and not evidence.claims,'AUDIT_EXECUTED_CONSUMER'
    assert not met['adapter_blockers'],('POSTERIOR_REPORT_BLOCKERS',met['adapter_blockers'])
    for p,h in protected.items():assert sha(p)==h,('SAVED_FILE_CHANGED',p)
    out=dict(status='PASS_INDEPENDENT_POST_ECONOMIC_AUDIT',window=w,integrity=integ,rank=rank,old_ledger=oq,new_ledger=nq,retained_ab=ab,metrics=met,protected_files=len(protected),audit_code_sha256=sha(__file__),historical_economic_runs_by_auditor=0,limitations=['Conditional full-fill per-stock proxy only.','Development data previously seen; no OOS claim.','UNKNOWN and financial-uncovered responsibility excluded only from explicitly named comparable denominators.'])
    write(A/('POSTERIOR_'+w+'.json'),out);write(A/('POSTERIOR_METRICS_'+w+'.json'),allmet)
    print(json.dumps(out,indent=2,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
