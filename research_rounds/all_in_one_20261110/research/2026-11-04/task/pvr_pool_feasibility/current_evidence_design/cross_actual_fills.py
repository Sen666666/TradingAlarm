"""One frozen B prior63 actual-fill cross. Saved source readers only; no strategy/account."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import importlib.util,json,hashlib,math,time
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parents[1]
RISK=ROOT/'risk_constraints';INPUT=RISK/'ma63_information_diagnostic_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);SRC={};CACHE={};FRAMES={};IM={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def same(a,b,k):assert abs(D(str(a))-D(str(b)))<D('.00000001'),(k,a,b)
def label(v):return 'UNKNOWN' if v is None else 'PASS' if v else 'FAIL'
def snapshot(sector,day):
    key=(sector,day)
    if key in CACHE:return CACHE[key]
    m=IM[sector];p=Path(m['refs']['CP1_input'])
    if sector not in FRAMES:
        actual=sha(p);assert actual==m['output_sha256'][str(p)];SRC[str(p)]=actual
        f=pd.read_parquet(p,columns=['close','segment_id'])
        assert f.index.is_unique and f.index.is_monotonic_increasing
        FRAMES[sector]=f
    f=FRAMES[sector];dt=pd.Timestamp(day)
    r=dict(sector=sector,decision_day=day,pass_B=None,known=False,reason=None,definition='current>mean(previous63), exclude current')
    if dt not in f.index:r['reason']='no_exact_decision_close';CACHE[key]=r;return r
    prefix=f.loc[:dt];current=prefix.iloc[-1];w=prefix.iloc[-64:-1]
    r.update(current_close=float(current.close),current_segment=str(current.segment_id),current_observed_day=str(prefix.index[-1].date()),prior_count=len(w))
    valid=lambda v:pd.notna(v) and math.isfinite(float(v)) and float(v)>0
    if len(w)!=63:r['reason']='insufficient63_prior_slots'
    elif pd.isna(current.segment_id) or not w.segment_id.eq(current.segment_id).all():r['reason']='not63_same_original_price_source_segment'
    elif not valid(current.close) or not all(valid(v) for v in w.close):r['reason']='missing_or_invalid_current_or_prior_price'
    else:
        mean=float(w.close.mean());c=float(current.close)
        r.update(known=True,pass_B=c>mean,prior63_mean=mean,equal_mean=c==mean,gap_pct=(c/mean-1)*100,
          prior_first=str(w.index[0].date()),prior_last=str(w.index[-1].date()),prior_hash=hashlib.sha256(w.to_csv().encode()).hexdigest())
        assert w.index[-1]<dt and len(w)==63
    CACHE[key]=r;return r
def grouped(ee,cols,M):
    bs=defaultdict(list)
    for x in ee:bs[tuple(x[k] for k in cols)].append(x)
    out=[dict(labels=dict(zip(cols,k)),**M.agg(v)) for k,v in sorted(bs.items())]
    same(sum((D(x['net_lifetime']) for x in out),Z),M.agg(ee)['net_lifetime'],str(cols))
    return out
def periods(ref,ds,M):
    out=M.phase_specs(ref,ds)
    days=sorted({str(r['at'])[:10] for r in ds})
    out=[('FULL',days[0],days[-1])]+out
    for month in sorted({d[:7] for d in days}):
        dd=[d for d in days if d[:7]==month];out.append(('month_'+month,dd[0],dd[-1]))
    return out
def main():
    global IM
    started=time.monotonic();assert not (O/'B_EXACT_RESULTS.json').exists(),'preserve result; do not automatically rerun'
    frozen=read(O/'DESIGN_FREEZE.json')
    for n,h in frozen['files'].items():assert sha(O/n)==h,(n,'design changed')
    IM={m['series']:m for m in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
    oldsource=read(INPUT/'SOURCE_MANIFEST.json')['sources']
    specs=[('2022_2024',ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024',2265),('strong',O.parent/'runs/2025_26',1171)]
    data={ref:read(INPUT/(ref+'_ENTRIES.json')) for ref,_,_ in specs}
    tails={ref:read(INPUT/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json')) for ref,_,_ in specs}
    # Freeze the complete input mother and every relevant industry source before calculating a B value.
    for ref,run,count in specs:
        assert len(data[ref])==count and len({x['layer']for x in data[ref]})==count
        assert len({x['budget_order']for x in data[ref]})==count
        for p in [run/'pair/B.json.gz',run/'pair/daily.jsonl.gz']:
            SRC[str(p)]=sha(p);assert SRC[str(p)]==oldsource[str(p)]
    for sector in sorted({x['sector'] for ee in data.values() for x in ee}|{t['original']['sector'] for tt in tails.values() for t in tt}):
        p=Path(IM[sector]['refs']['CP1_input']);SRC[str(p)]=sha(p)
        assert SRC[str(p)]==IM[sector]['output_sha256'][str(p)]==oldsource[str(p)]
    for p in [RISK/'analyze_ma63_information.py',RISK/'analyze_no60_capital_deployment.py',W/'c1-drawdown-capacity-20261101/analyze_saved.py']:
        SRC[str(p)]=sha(p);assert SRC[str(p)]==oldsource[str(p)]
    SRC[str(Path(__file__))]=sha(__file__)
    save('B_EXACT_INPUT_FREEZE.json',dict(before_any_new_B_label=True,definition=frozen['definition'],source_sha256=dict(SRC),
      rows={k:len(v) for k,v in data.items()},account_events=0,new_strategy_fills=0))
    sp=importlib.util.spec_from_file_location('saved_ma63_helpers_B_exact',RISK/'analyze_ma63_information.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
    # Reuse the original saved-journal accounting function; only its partition key is private here.
    M.gkey=lambda x:(x['B_class'],x['pool_at_fill'],x['action'],x['role'])
    result={};allphases=[]
    for ref,run,count in specs:
        ee=data[ref]
        for x in ee:
            bits=x['budget_order'].split('|');assert len(bits)==4 and bits[2]==x['sid'] and bits[3]==x['role']
            assert pd.Timestamp(bits[1])==pd.Timestamp(x['decision_at'])<pd.Timestamp(x['opened'])
            b=snapshot(x['sector'],x['decision_at'][:10]);old=x['industry_state']
            assert b['current_observed_day']==old['decision_day'] and b['current_close']==old['close']
            x.update(B_exact=b,B_class=label(b['pass_B']),inclusive_industry_class=label(old['above']),
              No60_fixed_layer_tail=bool(D(x['cost'])>0 and D(x['net'])/D(x['cost'])>=D('.3')),
              direct_original_confirmed_request=bool(x['pool_at_fill']=='confirmed'))
        bb=M.book(run/'pair/B.json.gz');ds=M.rows(run/'pair/daily.jsonl.gz')
        assert len([j for j in bb['journal']if j['kind']=='real_buy_fill'])==count
        before={x['layer']:{k:x[k]for k in ['net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee','remaining_basis']} for x in ee}
        M.C.A.SM={x['symbol']:x for x in M.read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
        ee,history,dep=M.ledger(ref,bb,ds,ee)
        for x in ee:
            for k,v in before[x['layer']].items():same(x[k],v,(ref,x['layer'],k))
        original_net=sum((D(x['net']) for x in ee),Z)
        same(original_net,D(bb['ending_NAV'])-D(1000000),'native NAV bridge')
        phaseout=[];entryphase=[]
        for name,lo,hi in periods(ref,ds,M):
            hh=[h for h in history if lo<=h['day']<=hi];nd=len({h['day']for h in hh})
            for bc in ['PASS','FAIL','UNKNOWN']:
                h=[h for h in hh if h['key'][0]==bc]
                phaseout.append(dict(ref=ref,phase=name,lo=lo,hi=hi,B_class=bc,closes=nd,
                  actual_phase_wealth=sum((h['wealth']for h in h),Z),phase_buycash=sum((h['buycash']for h in h),Z),phase_fees=sum((h['fees']for h in h),Z),
                  mean_market_value=sum((h['end_value']for h in h),Z)/nd if nd else Z))
                phaseentries=[x for x in ee if x['B_class']==bc and lo<=x['decision_at'][:10]<=hi]
                entryphase.append(dict(phase=name,lo=lo,hi=hi,B_class=bc,scope='decision cohort whole life to cutoff; NOT phase wealth',**M.agg(phaseentries)))
            native_phase=[d for d in ds if lo<=str(d['at'])[:10]<=hi]
            if native_phase:
                idx=next(i for i,d in enumerate(ds)if str(d['at'])[:10]==str(native_phase[0]['at'])[:10]);anchor=D(ds[idx-1]['nav'])if idx else D(1000000)
                same(sum((p['actual_phase_wealth']for p in phaseout if p['phase']==name),Z),D(native_phase[-1]['nav'])-anchor,(ref,name,'phase NAV'))
        oldtails=[]
        for t in tails[ref]:
            x=t['original'];b=snapshot(x['sector'],x['decision_at'][:10]);ids=t['matched_No60_layers']
            oldtails.append(dict(original=x,B_exact=b,B_class=label(b['pass_B']),old_inclusive_class=t['original_MA63_class'],
              matched_No60_layers=ids,matched_No60_money=M.agg([e for e in ee if e['layer']in ids]),unmatched=not bool(ids)))
        tables={name:grouped(ee,cols,M)for name,cols in {
          'by_B':['B_class'],'B_vs_original_inclusive_industry':['B_class','inclusive_industry_class'],
          'B_vs_original_inclusive_stock_industry':['B_class','MA63_class'],
          'by_B_pool_role':['B_class','pool_at_fill','role'],'by_B_action':['B_class','action'],
          'by_B_fixed_No60_layer_tail':['B_class','No60_fixed_layer_tail']}.items()}
        direct=[x for x in ee if x['direct_original_confirmed_request']]
        changed=[x for x in ee if x['B_class']!=x['inclusive_industry_class']]
        post=[x for x in ee if '2024-10-09'<=x['opened'][:10]<='2024-12-31']if ref=='2022_2024' else []
        if ref=='2022_2024':assert len(post)==303
        result[ref]=dict(overall=M.agg(ee),groups=tables,direct_confirmed_all=M.agg(direct),
          direct_confirmed_by_B=grouped(direct,['B_class'],M),changed_vs_inclusive=M.agg(changed),changed_layers=[x['layer']for x in changed],
          original_fixed_tail_by_B=[dict(B_class=bc,original_members=sum(t['B_class']==bc for t in oldtails),
           matched_No60_members=sum(t['B_class']==bc and not t['unmatched']for t in oldtails),
           matched_money=M.agg([x for x in ee if any(t['B_class']==bc and x['layer']in t['matched_No60_layers']for t in oldtails)]))for bc in ['PASS','FAIL','UNKNOWN']],
          postOct8_303fills=dict(overall=M.agg(post),by_B=grouped(post,['B_class'],M),direct_confirmed_by_B=grouped([x for x in post if x['pool_at_fill']=='confirmed'],['B_class'],M)),
          unknown=sum(x['B_class']=='UNKNOWN'for x in ee),native_NAV=bb['ending_NAV'],closes=len(ds))
        save(ref+'_B_EXACT_ENTRIES.json',ee);save(ref+'_B_EXACT_ACTUAL_PHASE_WEALTH.json',phaseout);save(ref+'_B_EXACT_ENTRY_PHASE_COHORTS.json',entryphase)
        save(ref+'_B_EXACT_ORIGINAL_FIXED_TAIL.json',oldtails)
        allphases.extend(phaseout)
        print('B_EXACT',ref,'fills',len(ee),'net',original_net,'by_B',[(r['labels'],r['fills'],str(r['net_lifetime']))for r in tables['by_B']],flush=True)
    for sid,f in M.C.A.frames.items():
        p=Path(M.C.A.SM[sid]['refs']['facts']);SRC[str(p)]=sha(p);assert SRC[str(p)]==M.C.A.SM[sid]['output_sha256'][str(p)]
    SRC.update(M.SRC)
    for p,h in SRC.items():assert sha(p)==h,(p,'source changed during run')
    save('B_EXACT_RESULTS.json',dict(definition=frozen['definition'],results=result,new_account_events=0,new_strategy_fills=0,
      migrated_probe_coupling_evaluated=False,avoidable_profit_or_loss_estimated=False,seconds=time.monotonic()-started))
    save('B_EXACT_SOURCE_SHA256.json',SRC)
    save('B_EXACT_GATE.json',dict(passed=True,mothers_exact=[2265,1171],postOct8_actual_fills=303,decision_order_close_exact=True,
      original_money_fields_exact_to_1e_8=True,all_periods_to_native_NAV_exact_to_1e_8=True,source_unchanged=True,
      B_feature_source='originalINDUSTRY_MANIFEST CP1_input.close and originalsource segment; no dropna/current excluded',
      exact_B_unique_snapshots=len(CACHE),new_strategy_events=0,old_completed_strategy_replays=0))
if __name__=='__main__':main()
