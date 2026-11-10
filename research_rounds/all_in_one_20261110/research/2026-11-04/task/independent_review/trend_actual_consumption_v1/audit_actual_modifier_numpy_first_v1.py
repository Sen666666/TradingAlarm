"""Independent actual-key formula/plan-clock audit; no producer/engine import.

Reads only source observations used by saved modifier keys.  NumPy window
arithmetic and an explicit EMA recursion independently implement the fixed card.
Classification differences are failures, never hidden with a wider tolerance.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import argparse, bisect, gzip, hashlib, json, time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
W=O.parents[1]
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
RULES=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    p=Path(p);SRC[str(p.resolve())]=sha(p)
    return json.loads(p.read_text())
def book(p):
    SRC[str(p.resolve())]=sha(p)
    with gzip.open(p,'rt')as f:return json.load(f)
def rows(p):
    with gzip.open(p,'rt')as f:
        for line in f:yield json.loads(line)
def normat(s):return str(s).replace('T',' ')
def day(s):return str(s)[:10]
def key(at,sid,role):return day(at),sid,role
def trace_key(e):return key(e['at'],e['sid'],e['role'])
def checked(p,h):
    p=Path(p);a=sha(p);assert a==h,('original source changed',str(p),h,a)
    SRC[str(p.resolve())]=a;return p

def independent_features(f,source):
    """Whole original warm clock, without pandas rolling/EWM or NA compression."""
    assert f.index.is_unique and f.index.is_monotonic_increasing
    s=source.reindex(f.index)
    c=f.close.to_numpy(float);raw=f.raw_close.to_numpy(float);fac=f.factor.to_numpy(float)
    seg=f.segment_id.to_numpy();sc=s.close.to_numpy(float);ss=s.segment_id.to_numpy()
    observed=np.ones(len(f),dtype=bool)
    for col,yes in [('price_eligible',True),('observed_bar',True),('synthetic_event_bar',False)]:
        observed &= s[col].eq(yes).fillna(False).to_numpy(bool)
    observed &= np.isfinite(sc)&(sc>0)&pd.notna(ss)
    both=observed&np.isfinite(c)&(c>0)&pd.notna(seg)
    assert np.all(np.abs(c[both]-sc[both])<=1e-10+1e-10*np.abs(sc[both]))
    assert np.array_equal(seg[both],ss[both])
    coord=raw*fac
    valid=(observed&np.isfinite(c)&(c>0)&np.isfinite(raw)&(raw>0)&np.isfinite(fac)&(fac>0)
           &pd.notna(seg)&(np.abs(c-coord)<=1e-10+1e-10*np.abs(coord)))
    n=len(c);ma=np.full(n,np.nan);up=ma.copy();ema=ma.copy();run=np.zeros(n,dtype=int)
    start=0;blocks=0
    while start<n:
        if not valid[start]:start+=1;continue
        end=start+1
        while end<n and valid[end]and seg[end]==seg[start]:end+=1
        a=c[start:end];count=len(a);blocks+=1;run[start:end]=np.arange(1,count+1)
        if count>=60:
            ma[start+59:end]=np.lib.stride_tricks.sliding_window_view(a,60).mean(axis=1)
        if count>=20:
            windows=np.lib.stride_tricks.sliding_window_view(a,20)
            mid=windows.mean(axis=1)
            sd=np.sqrt(np.square(windows-mid[:,None]).sum(axis=1)/20.0)
            up[start+19:end]=mid+2*sd
        z=float(a[0]);ema[start]=z
        for j in range(1,count):
            z=(2.0/11.0)*float(a[j])+(1.0-2.0/11.0)*z
            ema[start+j]=z
        start=end
    ak=run>=65;bk=run>=21
    av=np.zeros(n,bool);bv=av.copy()
    ia=np.flatnonzero(ak);ib=np.flatnonzero(bk)
    av[ia]=(c[ia]>=ma[ia])&(ma[ia]>ma[ia-5])
    bv[ib]=(c[ib]>up[ib])&(c[ib-1]<=up[ib-1])&(ema[ib]>ema[ib-3])
    return dict(index=f.index,c=c,valid=valid,run=run,ak=ak,bk=bk,av=av,bv=bv,ma=ma,up=up,ema=ema,blocks=blocks)

def actual_at(data,d):
    loc=data['index'].get_indexer([pd.Timestamp(d)])[0]
    if loc<0:return dict(A=None,B=None,A_known=False,B_known=False,price_known=False,m_A_ONLY=.5,m_A_OR_B=.5),None
    a=bool(data['av'][loc]);b=bool(data['bv'][loc]);ak=bool(data['ak'][loc]);bk=bool(data['bk'][loc])
    v=dict(A=a if ak else None,B=b if bk else None,A_known=ak,B_known=bk,price_known=bool(data['valid'][loc]),m_A_ONLY=1. if a else .5,m_A_OR_B=1. if a or b else .5)
    return v,loc

def main():
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--end',required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();assert not args.out.exists();args.out.mkdir(parents=True)
    begin=time.monotonic();manifest={r['symbol']:r for r in read(MANIFEST)};rules=read(RULES)
    eventpath=args.run/'pair/confirmation-size-events.jsonl.gz';assert eventpath.exists()
    SRC[str(eventpath.resolve())]=sha(eventpath)
    wanted=defaultdict(set);actual_flags={};seen=set();events_count=Counter();mismatches=[];near_boundaries=[];b_only=[]
    for e in rows(eventpath):
        assert day(e['at'])<=args.end and pd.Timestamp(e['at']).hour==15
        k=(e['account'],)+trace_key(e);assert k not in seen;seen.add(k)
        events_count[e['account']]+=1
        if e['account']=='UNIFORM50':assert e['flags']is None;continue
        sid,d=e['sid'],day(e['at']);f=e['flags'];kk=(sid,d)
        if kk in actual_flags:assert actual_flags[kk]==f
        else:actual_flags[kk]=f;wanted[sid].add(d)
    counts=Counter();expected={};unknown_examples=[];feature_sources=0
    b_info={}
    for sid in sorted(wanted):
        r=manifest.get(sid)
        if r is None or r['status']!='complete':
            for d in wanted[sid]:expected[sid,d]=dict(A=None,B=None,A_known=False,B_known=False,price_known=False,m_A_ONLY=.5,m_A_OR_B=.5)
            counts['missing_complete_source_sids']+=1;continue
        fp=checked(r['refs']['facts'],r['output_sha256'][r['refs']['facts']])
        sp=next(Path(q)for q in r['source_sha256']if q.endswith('/signal.parquet'))
        checked(sp,r['source_sha256'][str(sp)])
        f=pd.read_parquet(fp,columns=['close','segment_id','raw_close','factor']).loc[:args.end]
        s=pd.read_parquet(sp,columns=['close','segment_id','price_eligible','observed_bar','synthetic_event_bar']).loc[:args.end]
        data=independent_features(f,s);feature_sources+=2;counts['original_warm_slots']+=len(f);counts['known_blocks']+=data['blocks']
        for d in sorted(wanted[sid]):
            v,i=actual_at(data,d);expected[sid,d]=v;got=actual_flags[sid,d]
            diff={k:dict(independent=v[k],logged=got[k])for k in v if got[k]!=v[k]}
            if diff:mismatches.append(dict(sid=sid,day=d,differences=diff))
            counts['actual_distinct_sid_date_keys']+=1
            if not v['price_known']or not v['A_known']or not v['B_known']:
                counts['actual_keys_with_any_unknown']+=1
                if len(unknown_examples)<12:unknown_examples.append(dict(sid=sid,day=d,flags=v))
            if i is not None:
                margins={}
                if data['ak'][i]:margins.update(price_minus_MA=float(data['c'][i]-data['ma'][i]),MA_slope5=float(data['ma'][i]-data['ma'][i-5]))
                if data['bk'][i]:margins.update(price_minus_upper=float(data['c'][i]-data['up'][i]),prior_price_minus_upper=float(data['c'][i-1]-data['up'][i-1]),EMA_slope3=float(data['ema'][i]-data['ema'][i-3]))
                close=[k for k,x in margins.items()if abs(x)<=1e-12*max(1.,abs(float(data['c'][i])))]
                if close:near_boundaries.append(dict(sid=sid,day=d,near_zero_fields=close,margins=margins,classification_exact=not diff))
                if v['B']is True and v['A']is not True:
                    h={}
                    for n in (1,3,5):
                        if i+n>=len(f):h[str(n)]=dict(known=False,reason='RIGHT_CENSORED_AT_FIXED_END');continue
                        ii=np.arange(i+1,i+n+1);known=bool(np.all(data['bk'][ii]))
                        h[str(n)]=dict(known=known,reason='NATIVE_SLOTS_NO_COMPRESSION',back_inside_band_within_horizon=bool(np.any(data['c'][ii]<=data['up'][ii]))if known else None,
                            close_return_from_signal=float(data['c'][i+n]/data['c'][i]-1)if known else None)
                    b_info[sid,d]=dict(group='A_KNOWN_FALSE_B_TRUE'if v['A']is False else'A_UNKNOWN_B_TRUE',horizons=h)
        del f,s,data
    # Audit one account book at a time; no financial/NAV reconstruction.
    report={};planproof=Counter();all_cp_checks=0
    for arm in ('B','UNIFORM50','A_ONLY','A_OR_B'):
        b=book(args.run/'pair'/f'{arm}.json.gz');plans={};e_by={}
        for e in rows(eventpath):
            if e['account']!=arm:continue
            k=trace_key(e);assert k not in e_by;e_by[k]=e
            independent_m=D('.5')if arm=='UNIFORM50'else D(str(expected[e['sid'],day(e['at'])]['m_'+arm]))
            m=D(str(e['multiplier']));assert m in(D('.5'),D(1))
            if m!=independent_m:
                mismatches.append(dict(account=arm,sid=e['sid'],day=day(e['at']),role=e['role'],multiplier_logged=str(m),multiplier_independent=str(independent_m)))
            logged_m=D('.5')if arm=='UNIFORM50'else D(1)if e['flags']['A']is True or(arm=='A_OR_B'and e['flags']['B']is True)else D('.5')
            assert m==logged_m
            versions=[x for x in rules['quantity_versions'][e['sid']]if x['from']<=k[0]and(not x['to']or k[0]<x['to'])];assert versions
            q=versions[-1]['rule'];mini,step=q['buy_minimum'],q['buy_step'];maxq=int(D(e['cap_before'])*m)
            cap=0 if maxq<mini else mini+(maxq-mini)//step*step
            assert e['cap_after']==cap and D(e['budget_after'])==D(e['budget_before'])*m
            assert e['cap_before']>=mini and(e['cap_before']-mini)%step==0
            assert e['effective_after']=='NEXT_LEGAL_OPEN_NO_REAPPLICATION'
            if not cap:assert e['result']=='confirmation_half_below_minimum';planproof[arm+'_minimum_zero']+=1
        for d in b['decisions']:
            for i in d['intents']:
                k=key(d['at'],i['sid'],i.get('role',i['kind']));assert k not in plans;plans[k]=i
                if arm=='B':continue
                e=e_by[k];assert e['result']=='kept'
                for field,efield in [('cap','cap_after'),('budget','budget_after'),('rank','priority_rank'),('risk_budget','risk_budget_unchanged'),('CP1_id','CP1_id'),('epoch','signal_epoch')]:
                    assert i.get(field)==e.get(efield),(arm,k,field,i.get(field),e.get(efield))
        if arm!='B':assert set(plans)=={k for k,e in e_by.items()if e['result']=='kept'}
        actual_cp=Counter();reserves={};fills=defaultdict(list);cp_dates=defaultdict(set);stat=Counter()
        jr_by={x['order']:x for x in b['journal']if x['kind']=='real_reserve'}
        for row in b['audit']:
            if row['kind']!='reserve':continue
            at=row['decision_at']
            # Core/mobile may coexist as legal plans; the native budget-order
            # journal supplies the actual chosen role without guessing.
            jr=jr_by[row['order_id']]
            k=key(at,row['sid'],jr['role']);i=plans[k]
            assert row['frozen_max_shares']==i['cap']and D(row['frozen_max_gross'])==D(i['budget'])
            assert row['target_shares']<=i['cap']and D(row['gross_budget_cny'])<=D(i['budget'])
            assert normat(at)==normat(jr['budget_order'].split('|')[1])
            assert pd.Timestamp(row['at'])>pd.Timestamp(at)
            # Original next global venue open, not a later close-dependent retry.
            calendar=rules['calendars']['A'];iso=pd.Timestamp(at).isoformat();idx=bisect.bisect_right(calendar,iso)
            assert idx<len(calendar)and pd.Timestamp(row['at'])==pd.Timestamp(calendar[idx])
            bo=b['budget']['orders'][jr['budget_order']]
            assert bo['expiry_bar']==pd.Timestamp(row['at']).date().toordinal()
            assert jr['receipt']==i.get('CP1_id')
            if jr['receipt']:
                actual_cp[jr['receipt']]+=1;cp_dates[row['sid']].add(day(at))
            reserves[jr['budget_order']]=(row,jr,k);stat['actual_reserves']+=1
        assert all(n==1 for n in actual_cp.values()),('CP1 reserved more than once',arm)
        for sid,ds in cp_dates.items():
            r=manifest[sid];cpfile=checked(r['refs']['CP1'],r['output_sha256'][r['refs']['CP1']])
            cp=pd.read_parquet(cpfile,columns=['receipt'])
            for d in ds:assert pd.Timestamp(d)in cp.index and bool(cp.loc[d,'receipt']);all_cp_checks+=1
        for row in b['journal']:
            if row['kind']!='real_buy_fill':continue
            reserve,jr,k=reserves[row['budget_order']]
            assert normat(row['signal_at'])==normat(reserve['decision_at'])
            assert row['CP1_id']==jr['receipt']
            assert day(row['at'])==day(reserve['at']),('buy expiry extended',arm,row)
            fills[row['budget_order']].append(row)
        for bid,ff in fills.items():
            reserve,jr,k=reserves[bid]
            assert sum(x['shares']for x in ff)<=reserve['target_shares']
            assert sum(D(x['shares'])*D(x['price'])for x in ff)<=D(reserve['gross_budget_cny'])
            stat['actual_buy_orders_filled']+=1;stat['actual_buy_fills']+=len(ff)
            if len(ff)>1:stat['multiple_fill_orders']+=1
            if arm=='A_OR_B'and(k[1],k[0])in b_info:
                info=b_info[k[1],k[0]]
                b_only.append(dict(account=arm,sid=k[1],signal_day=k[0],role=k[2],budget_order=bid,
                    group=info['group'],reserved_shares=reserve['target_shares'],filled_shares=sum(x['shares']for x in ff),
                    actual_buy_gross=str(sum(D(x['shares'])*D(x['price'])for x in ff)),actual_buy_fees=str(sum(D(x['fees'])for x in ff)),
                    signal_to_future_native_slot_diagnostics=info['horizons']))
        stat['kept_legal_plans']=len(plans);stat['modifier_events']=len(e_by)
        report[arm]=dict(stat);del b,plans,e_by,reserves,fills,jr_by
    result=dict(passed=not mismatches,status='PASS_ACTUAL_CONSUMED_FEATURES_AND_SINGLE_CLOSE_PLAN_MODIFIER'if not mismatches else'FAIL_FEATURE_CLASSIFICATION_DIFFERENCES',
        run=str(args.run),fixed_end=args.end,coverage=dict(counts,unique_sids=len(wanted),actual_modifier_events=sum(events_count.values()),independent_price_source_files=feature_sources),
        actual_event_counts=dict(events_count),arms=report,minimum_zero_counts=dict(planproof),classification_mismatches=mismatches,
        diagnostic_near_zero_boundaries=near_boundaries,unknown_examples=unknown_examples,
        original_CP1_current_receipt_dates_checked=all_cp_checks,all_CPs_reserved_at_most_once_per_arm=True,
        actual_order_frozen_cap_gross_next_open_and_same_day_expiry_verified=True,
        actual_plan_and_risk_budget_CP1_epoch_alignment_verified=True,
        source_SHA256=SRC,checker_SHA256=sha(__file__),seconds=time.monotonic()-begin,
        boundaries='No tolerance is used to accept boolean/multiplier classification differences. Near-zero list is diagnostic only.',
        numeric_implementation='Independent numpy direct sliding-window means and sum-of-squared-deviations ddof0; explicit alpha=2/11,beta=1-alpha EMA recursion seeded at first valid original run. No producer compute_flags/import/native replay.',
        limitations=['No financial/NAV or PVR ranking re-audit; those have separate owners.',
            'Original legal plan generation/order callbacks are source-bound; cap_before is own-state pre-modifier logged intent, not the NONE arm future realized fill.',
            'B-only forward native-slot diagnostics are after-the-fact labels and never inputs or a new exit rule.',
            'All actual-used feature keys are checked; unused universe rows do not become a new feature export.'])
    (args.out/'AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with gzip.open(args.out/'B_ONLY_ACTUAL_FILLED_ORDER_DIAGNOSTICS.jsonl.gz','wt')as f:
        for row in b_only:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(json.dumps({k:result[k]for k in ['passed','status','coverage','actual_event_counts','arms','seconds']},indent=2))

if __name__=='__main__':main()
