"""Frozen MA63 information diagnostic; pure saved prices/books, zero accounts."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import importlib.util,json,gzip,hashlib,math
import pandas as pd
import numpy as np

HERE=Path(__file__).resolve().parent;OUT=HERE/'ma63_information_diagnostic_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');OLD=W/'pvr-slot1-native-readiness-20261101'
sp=importlib.util.spec_from_file_location('saved_action_cost_helpers_ma',HERE/'analyze_no60_capital_deployment.py');C=importlib.util.module_from_spec(sp);sp.loader.exec_module(C)
Z=D(0);EPS=D('.000001');SRC={};FRAMES={};STATES={};SNAPS={};MACRO=None
SM={};IM={}
def n(x):return D(str(x))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def book(p):
    SRC[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
    SRC[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def close(x,y,k):assert abs(x-y)<EPS,(k,x,y,x-y)
def day(x):return str(x)[:10]
def valid(x):return pd.notna(x) and math.isfinite(float(x)) and float(x)>0
def decision(j):
    bits=j['budget_order'].split('|');assert len(bits)==4 and bits[2]==j['sid'] and bits[3]==j['role']
    return pd.Timestamp(bits[1]).isoformat(sep=' ')
def frame(sid):
    if sid not in FRAMES:
        m=IM[sid] if sid.startswith('URFI') else SM[sid];p=Path(m['refs']['CP1_input'] if sid.startswith('URFI') else m['refs']['facts'])
        actual=sha(p);assert actual==m['output_sha256'][str(p)];SRC[str(p)]=actual
        cols=['close','segment_id'] if sid.startswith('URFI') else ['close','segment_id','raw_close','factor']
        f=pd.read_parquet(p,columns=cols);assert f.index.is_unique and f.index.is_monotonic_increasing;FRAMES[sid]=f
    return FRAMES[sid]
def snapshot(sid,d):
    key=(sid,d)
    if key in SNAPS:return SNAPS[key]
    f=frame(sid);dt=pd.Timestamp(d);r=dict(series=sid,decision_day=d,above=None,return63_sign='unknown',unknown=None)
    if dt not in f.index:r['unknown']='no_exact_decision_quote';SNAPS[key]=r;return r
    # Physical prefix before window/segment selection; no future holding/trend labels.
    prefix=f.loc[:dt];current=prefix.iloc[-1];segment=current.segment_id
    r['segment_id']=str(segment);r['source_max_used_day']=str(prefix.index[-1].date());assert prefix.index[-1]==dt
    if pd.isna(segment):r['unknown']='unknown_original_price_source_segment';SNAPS[key]=r;return r
    w=prefix.iloc[-63:]
    if len(w)<63:r['unknown']='insufficient_full_warm63'
    elif not w.segment_id.eq(segment).all():r['unknown']='fewer_than63_in_current_comparable_price_source_segment'
    elif not all(valid(x) for x in w.close):r['unknown']='invalid_price_in_original63_observations'
    else:
        if not sid.startswith('URFI'):
            assert all(valid(x) for x in w.factor) and all(valid(x) for x in w.raw_close)
            assert np.allclose(w.close.to_numpy(float),w.raw_close.to_numpy(float)*w.factor.to_numpy(float),rtol=1e-10,atol=1e-10)
        price=float(current.close);ma=float(w.close.mean());r.update(close=price,MA63=ma,above=price>ma,equal_MA63=price==ma,gap_to_MA_pct=(price/ma-1)*100,
            window_first=str(w.index[0].date()),window_last=str(w.index[-1].date()),window_observations=63,
            window_hash=hashlib.sha256(w[['close','segment_id']].to_csv().encode()).hexdigest())
    wr=prefix.iloc[-64:]
    if len(wr)==64 and wr.segment_id.eq(segment).all() and all(valid(x) for x in wr.close):
        ret=float(wr.iloc[-1].close/wr.iloc[0].close-1);r.update(return63=ret,return63_sign='+' if ret>0 else '-' if ret<0 else '0')
    SNAPS[key]=r;return r
def probe(sector,d):
    if sector not in STATES:
        m=IM[sector];p=Path(m['refs']['state']);actual=sha(p);assert actual==m['output_sha256'][str(p)];SRC[str(p)]=actual
        f=pd.read_parquet(p);f['day']=f.day.astype(str).str[:10];assert f.day.is_unique
        STATES[sector]=f.set_index('day',drop=False)
    f=STATES[sector]
    if d not in f.index:return dict(unknown='no_exact_original_industry_state',R=None,R_bin='unknown')
    prefix=f.loc[:d];row=prefix.iloc[-1];aid=row.attempt_id
    if pd.isna(aid):return dict(unknown='no_current_original_attempt',R=None,R_bin='unknown')
    first=prefix[prefix.attempt_id.eq(aid)&prefix.action.eq('probe')]
    if first.empty:return dict(unknown='original_probe_not_in_known_warm_prefix',R=None,R_bin='unknown')
    first=first.iloc[0];line=max(float(first.E0_floor),float(first.candidate_floor));assert abs(line-float(first.mobile_after))<1e-8
    risk=float(first.close)-line
    if not math.isfinite(risk) or risk<=0:return dict(unknown='invalid_original_probe_R',R=None,R_bin='unknown')
    rr=(float(row.close)-float(first.close))/risk
    return dict(unknown=None,probe_day=first.day,probe_close=float(first.close),initial_line=line,fixed_R=risk,R=rr,
        R_bin='<0R' if rr<0 else '0_to_1R' if rr<1 else '1_to_2R' if rr<2 else '>=2R')
def macro_setup():
    global MACRO
    p=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/three-layer-prototype-20261024/inputs/USHJ510300.parquet')
    freeze=read(HERE.parent/'benchmark_2022_2023/INPUT_FREEZE.json');assert sha(p)==freeze['sources'][str(p)];SRC[str(p)]=sha(p)
    f=pd.read_parquet(p);assert f.index.is_unique and f.index.is_monotonic_increasing
    f=f[['close']].rename(columns={'close':'signal_close'});f['MA63']=f.signal_close.rolling(63,min_periods=63).mean();f['on']=f.signal_close.gt(f.MA63)&f.MA63.notna()
    hp=HERE.parent/'benchmark_2022_2023/inputs/510300_history.csv';SRC[str(hp)]=sha(hp);old=pd.read_csv(hp,parse_dates=['date']).set_index('date');x=f.loc[old.index]
    assert np.allclose(x.signal_close,old.signal_close,rtol=0,atol=1e-10)
    ready=old.ma63.notna();assert np.allclose(x.loc[ready,'MA63'],old.loc[ready,'ma63'],rtol=0,atol=1e-10)
    assert np.array_equal(x.loc[ready,'on'].to_numpy(bool),old.loc[ready,'on'].to_numpy(bool))
    MACRO=f
    save(OUT/'MACRO_OVERLAP_GATE.json',dict(passed=True,source=str(p),source_sha256=sha(p),overlap_rows=len(old),ready_MA_rows=int(ready.sum()),
        full_source_bounds=[str(f.index[0].date()),str(f.index[-1].date())],formula='same frozen ETF causal-reinvested close rolling63 arithmeticmean, minperiods63, close>MA; label only',
        not_original_ACT_synthetic_market=True,account_events=0))
def macro(d):
    dt=pd.Timestamp(d)
    if dt not in MACRO.index:return 'unknown'
    r=MACRO.loc[dt]
    if not valid(r.signal_close) or not valid(r.MA63):return 'unknown'
    return 'ETF_above_MA63' if bool(r.on) else 'ETF_not_above_MA63'
def ma_class(stock,industry):
    if stock['above'] is None or industry['above'] is None:return 'unknown_S'+('?' if stock['above'] is None else '+' if stock['above'] else '-')+'I'+('?' if industry['above'] is None else '+' if industry['above'] else '-')
    return 'S'+('+' if stock['above'] else '-')+'I'+('+' if industry['above'] else '-')
def crosskey(row):
    epoch=tuple(row.get('watch_epoch') or []) if row['role']=='core' else ()
    return (row['sid'],row['decision_at'],row['role'],row.get('receipt'),epoch)
def enrich(b,ll):
    jr={x['layer']:x for x in b['journal'] if x['kind']=='real_buy_fill'};tx={t['layer']:t for t in b['trades'] if t['side']=='buy'}
    decisions={pd.Timestamp(d['at']).isoformat(sep=' '):d for d in b['decisions']};actions=C.entry_actions(dict(book=b));enriched=[]
    assert len(jr)==len(tx)==len(ll)
    for row in ll:
        lid=row['layer'];j=jr[lid];t=tx[lid];at=decision(j);d=day(at);assert pd.Timestamp(at)<pd.Timestamp(t['at']) and pd.Timestamp(at).hour==15
        di=decisions.get(at);matched=bool(di and any(x['sid']==row['sid'] and x.get('role',x.get('kind'))==j['role'] and (j['CP1_id'] is None or x.get('CP1_id')==j['CP1_id']) for x in di['intents']))
        if not matched:raise AssertionError(('decision cannot be source-verified',lid,j['budget_order']))
        s=snapshot(row['sid'],d);i=snapshot(row['sector'],d);p=probe(row['sector'],d)
        enriched.append(dict(**row,decision_at=at,budget_order=j['budget_order'],signal_at=j['signal_at'],signal_differs_from_actual_decision=pd.Timestamp(j['signal_at'])!=pd.Timestamp(at),
            action=actions[lid]['action'],quantity_before_actual_buy=actions[lid]['quantity_before'],watch_epoch=t.get('epoch'),
            stock=s,industry_state=i,MA63_class=ma_class(s,i),ETF_macro=macro(d),return63_class='S'+s['return63_sign']+'I'+i['return63_sign'],probe_progress=p))
    return enriched
def agg(entries,dep=None):
    cost=sum((n(x['cost']) for x in entries),Z);net=sum((n(x['net']) for x in entries),Z);flat=[x for x in entries if not x['qty']];neg=[x for x in flat if n(x['net'])<0]
    r=dict(fills=len(entries),stocks=len({x['sid'] for x in entries}),actual_buy_cash=cost,net_lifetime=net,strict_realized=sum((n(x['strict_realized']) for x in entries),Z),
        open_unrealized=sum((n(x['open_unrealized']) for x in entries),Z),recognized_dividend_AR=sum((n(x['recognized_dividend_AR']) for x in entries),Z),
        buy_fees=sum((n(x['buy_fee']) for x in entries),Z),sell_fees=sum((n(x['sell_fee']) for x in entries),Z),
        equity_flat_positive=sum((n(x['net']) for x in flat if n(x['net'])>=0),Z),equity_flat_negative=sum((n(x['net']) for x in neg),Z),negative_flat_own_buy_cash=sum((n(x['cost']) for x in neg),Z),
        open_lifecycle_net=sum((n(x['net']) for x in entries if x['qty']),Z),open_terminal_value=sum((n(x['value']) for x in entries),Z),net_per_buycash_descriptive=net/cost if cost else None)
    close(r['strict_realized']+r['open_unrealized']+r['recognized_dividend_AR'],net,'group real+open+AR')
    if dep:r.update(dep)
    return r
def gkey(row):return (row['MA63_class'],row['ETF_macro'],row['action'],row['role'])
def ledger(ref,b,ds,ee):
    er={x['layer']:x for x in ee};keys=sorted({gkey(x) for x in ee});ev=[]
    for ix,t in enumerate(b['trades']):ev.append((str(t['at']),1,ix,'trade',t))
    for ix,t in enumerate(b['audit']):
        if t['kind']=='split':ev.append((str(t['at']),0,ix,'split',t))
        elif t['kind']=='dividend_accrual':ev.append((str(t['receivable']['ex_at']),2,ix,'dividend',t['receivable']))
    ev.sort(key=lambda x:x[:3]);ls={};ei=0;prior={};history=[];native={x['id']:x for x in b['layers']}
    for r in ds:
        d=day(r['at'])
        while ei<len(ev) and ev[ei][0]<=str(r['at']):
            _,_,_,kind,t=ev[ei];ei+=1
            if kind=='split':
                for l in ls.values():
                    if l['sid']==t['sid'] and l['q']:
                        exact=D(l['q'])*n(t['ratio']);assert exact==int(exact),'nontradefraction must be separate';l['q']=int(exact)
            elif kind=='dividend':
                held=[l for l in ls.values() if l['sid']==t['security_id'] and l['q']];total=sum(l['q'] for l in held);assert total>0
                for l in held:l['div']+=n(t['net_local'])*D(l['q'])/D(total)
            elif t['side']=='buy':
                lid=t['layer'];cost=n(t['gross_cny'])+n(t['fees_cny']);assert lid not in ls
                ls[lid]=dict(sid=t['security_id'],q=t['shares'],basis=cost,cash=-cost,real=Z,div=Z,cost=cost,buyfee=n(t['fees_cny']),sellfee=Z,buys=1,sells=0)
            else:
                proceeds=Z
                for part in t['parts']:
                    l=ls[part['layer']];q=part['shares'];assert q<=l['q'];used=l['basis']*D(q)/D(l['q']);net=n(part['net_cash'])
                    l['basis']-=used;l['q']-=q;l['cash']+=net;l['real']+=net-used;l['sellfee']+=n(t['price'])*D(q)-net;l['sells']+=1;proceeds+=net
                close(proceeds,n(t['gross_cny'])-n(t['fees_cny']),'parts net')
        cur={k:defaultdict(lambda:Z) for k in keys};qstock=defaultdict(int)
        for lid,l in ls.items():
            g=cur[gkey(er[lid])];value=D(l['q'])*C.A.price(l['sid'],d) if l['q'] else Z;qstock[l['sid']]+=l['q']
            for field,v in [('real',l['real']),('unreal',value-l['basis']),('div',l['div']),('cash',l['cash']),('value',value),('basis',l['basis']),('buycash',l['cost']),('fees',l['buyfee']+l['sellfee']),('buycount',l['buys'])]:g[field]+=v
        assert {sid:q for sid,q in qstock.items() if q}=={sid:int(q) for sid,q in r['positions'].items() if q}
        close(sum((g['value'] for g in cur.values()),Z),n(r['inventory']),'raw inventory')
        total=sum((g['real']+g['unreal']+g['div'] for g in cur.values()),Z);close(D(1000000)+total,n(r['nav']),'whole daily NAV')
        close(sum((g['div'] for g in cur.values()),Z),n(r['dividend_receivable']),'daily unpaid AR')
        hh=[]
        for k,g in cur.items():
            p=prior.get(k,defaultdict(lambda:Z));wealth=g['real']-p['real']+g['unreal']-p['unreal']+g['div']-p['div'];close(wealth,g['cash']-p['cash']+g['value']-p['value']+g['div']-p['div'],'group daily wealth')
            hh.append(dict(day=d,key=k,wealth=wealth,real_change=g['real']-p['real'],unreal_change=g['unreal']-p['unreal'],div_change=g['div']-p['div'],buycash=g['buycash']-p['buycash'],fees=g['fees']-p['fees'],
                begin_value=p['value'],end_value=g['value'],held_basis=g['basis'],exposure_pct=g['value']/n(r['nav'])*100))
        history.extend(hh);prior=cur
    assert ei==len(ev)
    for x in ee:
        l=ls[x['layer']];v=D(l['q'])*C.A.price(l['sid'],day(ds[-1]['at'])) if l['q'] else Z
        close(l['div'],n(native[x['layer']]['dividend']),'independent layer dividend allocation')
        close(l['cash'],n(native[x['layer']]['cash']),'native layer cash');close(l['real']+v-l['basis']+l['div'],n(x['net']),'terminal layer wealth')
        x.update(strict_realized=l['real'],open_unrealized=v-l['basis'],recognized_dividend_AR=l['div'],buy_fee=l['buyfee'],sell_fee=l['sellfee'],remaining_basis=l['basis'])
    deployment={}
    for k in keys:
        rr=[r for r in history if tuple(r['key'])==k];deployment[k]=dict(mean_held_basis=sum((r['held_basis'] for r in rr),Z)/len(ds),mean_market_value=sum((r['end_value'] for r in rr),Z)/len(ds),mean_exposure_pct=sum((r['exposure_pct'] for r in rr),Z)/len(ds))
    return ee,history,deployment
def phase_specs(ref,ds):
    days=[day(r['at']) for r in ds];out=[]
    for y in sorted({d[:4] for d in days}):out.append(('year_'+y,y+'-01-01',y+'-12-31'))
    for q in sorted({d[:4]+'Q'+str((int(d[5:7])-1)//3+1) for d in days}):
        dd=[d for d in days if d[:4]+'Q'+str((int(d[5:7])-1)//3+1)==q];out.append(('quarter_'+q,dd[0],dd[-1]))
    if ref=='2022_2024':
        for leg in read(HERE.parent/'pvr_pool_feasibility/market_phase_2022_2023/HS300_ALL_LEGS.json'):out.append(('retrospective_'+leg['id'],leg['first_analysis_day'],leg['last_analysis_day']))
        out += [('pre924','2024-01-01','2024-09-23'),('924_to_Oct8','2024-09-24','2024-10-08'),('postOct8','2024-10-09','2024-12-31')]
    return out
def main():
    global SM,IM
    freeze=read(OUT/'PROTOCOL_FREEZE.json');assert freeze['before_MA_feature_labels_and_results']
    for p,expected in freeze['sources'].items():assert sha(p)==expected,('pre-feature source changed',p)
    assert not (OUT/'RESULTS.json').exists(),'preserve earlier result; do not overwrite'
    SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};IM={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
    specs=[('2022_2024',HERE.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024',HERE/'continuation2024_finance/analysis/2022_2024/PVR_NO_CONFIRMED60/LAYERS.json',HERE.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/original/run-2024',HERE/'continuation2024_finance/analysis/2022_2024/PVR_SLOT1/LAYERS.json'),
        ('strong',HERE.parent/'pvr_pool_feasibility/runs/2025_26',HERE/'pvr_pool_results_2025_26/analysis/2025_26/PVR_NO_CONFIRMED60/LAYERS.json',OLD/'runs/2025_26',HERE/'pvr_pool_results_2025_26/analysis/2025_26/PVR_SLOT1/LAYERS.json')]
    cohorts={};data={}
    # Freeze every original tail member BEFORE any feature query or macro MA calculation.
    for ref,root,lp,oldroot,olp in specs:
        ob=book(oldroot/'pair/B.json.gz');oll=read(olp);oj={j['layer']:j for j in ob['journal'] if j['kind']=='real_buy_fill'};ot={t['layer']:t for t in ob['trades'] if t['side']=='buy'}
        tail=[]
        for x in oll:
            if n(x['cost'])>0 and n(x['net'])/n(x['cost'])>=D('.3'):
                j=oj[x['layer']];tail.append(dict(**x,decision_at=decision(j),budget_order=j['budget_order'],signal_at=j['signal_at'],watch_epoch=ot[x['layer']].get('epoch')))
        cohorts[ref]=tail;data[ref]=(root,lp,ob,oll)
    save(OUT/'ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json',dict(members=cohorts,definition='original PVR layer whole-life net/original actualbuycash>=30%, including originaldiv/openmark; not cashclosedcampaign; latest2024list frozen now not pre2024',source_SHA256=dict(SRC)))
    macro_setup();results={}
    for ref,root,lp,_,_ in specs:
        b=book(root/'pair/B.json.gz');ds=rows(root/'pair/daily.jsonl.gz');ee=enrich(b,read(lp));ee,history,deployment=ledger(ref,b,ds,ee)
        overall=agg(ee);close(overall['net_lifetime'],n(b['ending_NAV'])-D(1000000),'all actual fill mother')
        tables={}
        fields={'by_MA':['MA63_class'],'by_MA_macro':['MA63_class','ETF_macro'],'by_MA_action':['MA63_class','action'],'by_MA_role':['MA63_class','role'],'by_MA_vs_return63':['MA63_class','return63_class']}
        for name,cols in fields.items():
            buckets=defaultdict(list)
            for x in ee:buckets[tuple(x[c] for c in cols)].append(x)
            tables[name]=[dict(labels=dict(zip(cols,k)),**agg(v)) for k,v in sorted(buckets.items())]
            close(sum((n(x['net_lifetime']) for x in tables[name]),Z),overall['net_lifetime'],name)
        rbs=defaultdict(list)
        for x in ee:rbs[(x['MA63_class'],x['probe_progress']['R_bin'])].append(x)
        tables['by_MA_vs_original_probe_R']=[dict(MA63_class=k[0],original_probe_R_bin=k[1],**agg(v)) for k,v in sorted(rbs.items())]
        tables['fully_crossed']=[dict(MA63_class=k[0],ETF_macro=k[1],action=k[2],role=k[3],**agg([x for x in ee if gkey(x)==k],deployment[k])) for k in sorted(deployment)]
        phases=[];entrycohorts=[]
        for label,lo,hi in phase_specs(ref,ds):
            rr=[r for r in history if lo<=r['day']<=hi];keys=sorted({r['key'][0] for r in rr});count=len({r['day'] for r in rr})
            for ma in keys:
                g=[r for r in rr if r['key'][0]==ma];phases.append(dict(phase=label,lo=lo,hi=hi,MA63_class=ma,closes=count,
                    actual_phase_wealth=sum((r['wealth'] for r in g),Z),realized_change=sum((r['real_change'] for r in g),Z),unrealized_change=sum((r['unreal_change'] for r in g),Z),AR_change=sum((r['div_change'] for r in g),Z),actual_phase_buycash=sum((r['buycash'] for r in g),Z),actual_phase_fees=sum((r['fees'] for r in g),Z),
                    mean_actual_held_basis=sum((r['held_basis'] for r in g),Z)/count,mean_actual_market_value=sum((r['end_value'] for r in g),Z)/count,mean_exposure_pct=sum((r['exposure_pct'] for r in g),Z)/count))
                ev=[x for x in ee if x['MA63_class']==ma and lo<=day(x['decision_at'])<=hi];entrycohorts.append(dict(phase=label,MA63_class=ma,scope='entry-decision cohort FULL LIFE through book cutoff; NOT phase wealth',**agg(ev)))
        tailout=[];emap=defaultdict(list)
        for x in ee:emap[crosskey(x)].append(x)
        for old in cohorts[ref]:
            match=emap.get(crosskey(old),[]);d=day(old['decision_at']);s=snapshot(old['sid'],d);i=snapshot(old['sector'],d)
            tailout.append(dict(original=old,original_MA63_class=ma_class(s,i),original_stock=s,original_industry=i,original_macro=macro(d),matched_No60_layers=[x['layer'] for x in match],matched_No60_money=agg(match),
                unmatched=not bool(match),scope='actual original tail entry eligibility/cross-arm correspondence only; not avoidable/missed profit'))
        ret_dis=[x for x in ee if x['stock']['above'] is not None and x['industry_state']['above'] is not None and x['stock']['return63_sign'] in ['+','-','0'] and x['industry_state']['return63_sign'] in ['+','-','0'] and (x['stock']['above']!=(x['stock']['return63_sign']=='+') or x['industry_state']['above']!=(x['industry_state']['return63_sign']=='+'))]
        results[ref]=dict(overall=overall,groups=tables,nonredundant_vs_old63_return=agg(ret_dis),actual_decision_signal_clock_mismatches=sum(x['signal_differs_from_actual_decision'] for x in ee),
            unknown_feature_fills=sum(x['stock']['above'] is None or x['industry_state']['above'] is None for x in ee),fixed_original_tail_members=len(tailout),fixed_original_tail_matched=sum(not x['unmatched'] for x in tailout),
            no_new_account_events=0,source_book_NAV=b['ending_NAV'],closes=len(ds))
        save(OUT/(ref+'_ENTRIES.json'),ee);save(OUT/(ref+'_ACTUAL_PHASE_WEALTH.json'),phases);save(OUT/(ref+'_ENTRY_PHASE_LIFECYCLE_COHORTS.json'),entrycohorts);save(OUT/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'),tailout)
        print('MA63_SAVED_DIAGNOSTIC',ref,len(ee),'unknown',results[ref]['unknown_feature_fills'],'net',overall['net_lifetime'],flush=True)
    save(OUT/'RESULTS.json',results)
    for sid in C.A.frames:
        p=Path(C.A.SM[sid]['refs']['facts']);actual=sha(p);assert actual==C.A.SM[sid]['output_sha256'][str(p)];SRC[str(p)]=actual
    for p in [Path(__file__),HERE/'analyze_no60_capital_deployment.py',W/'c1-drawdown-capacity-20261101/analyze_saved.py']:SRC[str(p)]=sha(p)
    save(OUT/'SOURCE_MANIFEST.json',dict(sources=SRC,account_events=0,protocol_sha256=freeze['protocol_sha256'],no_future_feature_rows=True,
        money='strict sale-basis realized+remainingbasis unrealized+recognizeddiv; perlayer dividendallocation independently reconciled to native layer.dividend and every daily NAV',
        scope='observational information diagnostic. No deleted-group counterfactual. Full actual fill mothers; old tail membership frozen before MA labels. Intraday/HK/OOS/1.2m execution remain unverified.'))
    print('MA63_DIAGNOSTIC_COMPLETE',len(SNAPS),'causal price snapshots',len(SRC),'source hashes',flush=True)
if __name__=='__main__':main()
