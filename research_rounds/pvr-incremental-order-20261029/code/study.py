"""PVR incremental local reordering under comparable H1; no >50 gate test."""
from pathlib import Path
import sys,json,gzip,time,hashlib,importlib.util,math,collections,datetime
from decimal import Decimal as D
import numpy as np
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/pvr-incremental-order-20261029';E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029';S0=ROOT/'research_rounds/s0-first-margin-20261029';PV=ROOT/'research_rounds/pvr-act-comparison-20261027'
sp=importlib.util.spec_from_file_location('pvr_reuse_s0',S0/'code/study.py');R=importlib.util.module_from_spec(sp);sys.modules[sp.name]=R;sp.loader.exec_module(R);H=R.H;Z=H.Z;B=H.B
def save(p,x):H.save(p,x)
def enc(x):return H.encoded(x)
def digest(x):return hashlib.sha256(x.encode()).hexdigest()
def match(risk):
    used=set();pairs=[];status=[]
    for day,g in risk.groupby('date',sort=True):
        previous=set(used);edges=[];degree=collections.Counter();records=g.to_dict('records')
        for sector,gg in g[g.feature_ready].groupby('sector',sort=True):
            rows=gg.sort_values(['h1','symbol']).to_dict('records')
            for i,a in enumerate(rows):
                for b in rows[i+1:]:
                    hd=b['h1']-a['h1']
                    if hd>1:break
                    ad=abs(a['age']-b['age']);rg=abs(a['runup']-b['runup'])/max(a['scale'],b['scale'])
                    if ad>5 or rg>1:continue
                    known='|'.join(sorted([a['known_id'],b['known_id']]));pid=digest(known);degree[a['known_id']]+=1;degree[b['known_id']]+=1;edges.append((hd,ad,rg,pid,a,b,known))
        chosen=set()
        for hd,ad,rg,pid,a,b,known in sorted(edges,key=lambda x:x[:4]):
            if a['e0_epoch'] in used or b['e0_epoch'] in used:continue
            used.update([a['e0_epoch'],b['e0_epoch']]);chosen.update([a['known_id'],b['known_id']])
            hi=min([a,b],key=lambda z:(-z['h1'],z['symbol']));pr=min([a,b],key=lambda z:(-z['pvr'],z['symbol']))
            tie=a['pvr']==b['pvr'];kind='pvr_tie_no_contrast' if tie else 'same_choice' if pr['symbol']==hi['symbol'] else 'conflict'
            other=b if a['symbol']==hi['symbol'] else a
            p=dict(pair_id=pid,date=str(pd.Timestamp(day).date()),sector=a['sector'],pair_kind=kind,known_id_fields=known,h1_gap=hd,age_gap=ad,runup_gap_scale=rg,h1_exact_tie=a['h1']==b['h1'])
            # H1 and other roles are independent of PVR; matching order never uses score values.
            for role,z in [('h1',hi),('other',other)]:
                for k in ['symbol','e0_epoch','i_epoch','anchor','age','runup','scale','h1','pvr','pvr_raw','grade','known_id']:p[role+'_'+k]=z[k]
            p['pvr_choice_symbol']=hi['symbol'] if tie else pr['symbol'];pairs.append(p)
        for a in records:
            why='feature_missing' if not a['feature_ready'] else 'event_used_earlier_date' if a['e0_epoch'] in previous else 'matched_today' if a['known_id'] in chosen else 'comparable_peer_consumed' if degree[a['known_id']] else 'no_comparable_peer'
            status.append(dict(date=day,symbol=a['symbol'],e0_epoch=a['e0_epoch'],known_id=a['known_id'],reason=why,comparable_edges=degree[a['known_id']]))
    return pd.DataFrame(pairs),pd.DataFrame(status)
def prepare():
    t=time.monotonic();O.mkdir(exist_ok=False);(O/'code').mkdir()
    protocol=dict(version='v1',frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),question='Incremental PVR score reordering against original H1 within same-date/same-sector comparable legal I opportunities. Not PVR>50 gate, amount-only increment, CP1 or global portfolio.',universe='All32899 original legal I candidate snapshots; not economic-risk subsets filtered PVR>50 or unconfirmed CP1, not chosen among seen193 outcomes. Reuse raw/cache fields only; known development history.',features='Same experiment-two continuous I source epoch, first original Q anchor, age in actual observed valid-price bars after anchor, cumulative causal log price runup; re-created for ALL original I legal candidates. Current causal E0 visible epoch unique. No future end/confirmation date in ID.',calipers=dict(exact=['date','sector'],H1_percentile_gap_max=1,observed_age_gap_max=5,runup_gap_over_max_known_scale_max=1),matching='Within chronological day/sector create all admissible unordered pairs. Sort H1 distance, age difference, normalized runup difference, hash of then-known fields. Greedily consume each E0 event at most once across roles/dates. PVR values and future returns never select pairs. Missing PVR/scale not imputed.',classification='After pairing reveal strict PVR rank rounded12. Agreement means same stock/no change. Exact PVR tie gives no rank contrast and retain H1. Conflict compares higher PVR against original H1 choice, whose ties use original symbol ID. H1 ties separately reported.',weights='Equal frozen conflict pairs primary, same set across costs/fill/closure. Report mean incremental effect across ALL comparable matched pairs as sum conflict deltas/total matched (agreement/tie policy difference0). Unmatched never get zero return or enter this denominator.',execution='Each alternative fresh1m at same decision close, native next-open/daylease/raw gap guard/whole lots/T+1/actual fees; original I/E0 exit, no F/CP/ACT/add/reentry or compounding. Hold cash after exit until commonOct27 2026.',terminal='No-fill/open shares/pending rights all retained. Marks separate from execution, liquidation estimate only memo.',tail='Pair-tail either actual post-decision net_return>=.30, terminal versus realized separate; continuous contribution curve. All failures and fees. Win rate not a pass gate.',coverage_gate='Publish comparable/conflict/tie/agreement/unmatched coverage and H1/age/runup/scale/PVR balance before outcomes. No conflict or insufficient comparable support means unidentified/inconclusive, never relax calipers or pick other dates.',verdict='Positive relative and absolute contribution with cost stability and tail preservation supports only local reordering. Mixed effects tradeoff. Cost reversal/poor coverage/residual imbalance inconclusive. No causal or general score monotonicity claim.',checks='Causal IDs, E0 uniqueness, PVR-neutral pair-selection invariant, three temporal matching prefixes, six chronological conflict-pair samples and native cash/fees/shares/terminal, physical economic prefix, sample/full exact.',budget_seconds=300,additional_arms=False)
    save(O/'PROTOCOL.json',protocol)
    paths=[E1/'market-cache.parquet',E1/'opportunities.parquet',E1/'code/audit.py',S0/'risk-set.parquet',S0/'code/study.py',PV/'code/experiment.py',PV/'score-validation.json',H.SNAP/'h1.npz',ROOT/'research_rounds/rs-h1-execution-20261025/code/sector_account.py',ROOT/'research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py']+sorted((PV/'scores').glob('*.parquet'))
    save(O/'input-identity.json',dict(sha256={str(p):H.sha(p) for p in paths},snapshot=str(H.SNAP),before_features_and_outcomes=True))
    iq=pd.read_parquet(S0/'risk-set.parquet');assert len(iq)==32899;lookup={(x.date,x.symbol):x for x in iq.itertuples()};cache=pd.read_parquet(E1/'market-cache.parquet');ids=set(cache.symbol);_,m,_,_=H.context(ids,False);rows=[]
    for sid,g in cache.groupby('symbol',sort=True):
        g=g.set_index('date').sort_index();raw=m.raw[sid];obs=(raw.observed_bar&raw.valid_price).reindex(g.index,fill_value=False).to_numpy(bool);pv=pd.read_parquet(PV/'scores'/f'{sid}.parquet').reindex(g.index);st=None;e0key=None;prevE=None
        for j,r in enumerate(g.itertuples()):
            day=r.Index;seg=int(r.segment_id) if pd.notna(r.segment_id) else -1;ve=pd.notna(r.e0_target) and bool(r.e0_target) and pd.notna(r.e0_ready) and bool(r.e0_ready)
            if not ve:e0key=None
            elif e0key is None or seg!=prevE:e0key=f'{sid}|source={seg}|visible_E0_start={day.date()}'
            prevE=seg if ve else None
            active=pd.notna(r.i_target) and bool(r.i_target)
            if not active:st=None;continue
            if st is None or seg!=st['seg']:st=dict(seg=seg,start=str(day.date()),counter=0,anchor=None,ac=None,price=None)
            if obs[j]:st['counter']+=1
            if bool(r.Q) and st['anchor'] is None:st.update(anchor=str(day.date()),ac=st['counter'],price=float(r.close))
            if not bool(r.Q):continue
            assert e0key and st['anchor'] is not None
            rr=lookup[(day,sid)];p=pv.iloc[j];known=f"{sid}|source={seg}|I-visible-start={st['start']}|E0={e0key}|anchor={st['anchor']}|decision={day.date()}";good=pd.notna(p.score) and np.isfinite(p.score) and pd.notna(p.scale) and np.isfinite(p.scale) and p.scale>0
            rows.append(dict(date=day,symbol=sid,sector=rr.sector,h1=rr.stock_rank,grade=int(r.g_grade),e0_epoch=e0key,i_epoch=f"{sid}|source={seg}|I-visible-start={st['start']}",anchor=st['anchor'],age=st['counter']-st['ac'],runup=math.log(float(r.close)/st['price']),scale=float(p.scale) if pd.notna(p.scale) else np.nan,pvr=float(np.round(p.score,12)) if pd.notna(p.score) else np.nan,pvr_raw=float(p.score) if pd.notna(p.score) else np.nan,feature_ready=bool(good),known_id=known))
    risk=pd.DataFrame(rows).sort_values(['date','symbol']).reset_index(drop=True);assert len(risk)==32899;p,status=match(risk);assert len(p)>0
    epochs=list(p.h1_e0_epoch)+list(p.other_e0_epoch);assert len(epochs)==len(set(epochs))
    neutral=risk.copy();neutral.loc[neutral.feature_ready,'pvr']=0.;pn,_=match(neutral);cols=['pair_id','date','h1_symbol','other_symbol'];pd.testing.assert_frame_equal(p[cols],pn[cols],check_exact=True)
    prefixes=[]
    for cut in ['2024-12-31','2025-12-31','2026-06-30']:
        small,_=match(risk[risk.date.le(pd.Timestamp(cut))]);ref=p[p.date.le(cut)].reset_index(drop=True);pd.testing.assert_frame_equal(small.reset_index(drop=True),ref,check_exact=True);prefixes.append(dict(cutoff=cut,pairs=len(small)))
    risk.to_parquet(O/'risk-set.parquet',index=False);p.to_parquet(O/'all-comparable-pairs.parquet',index=False);p[p.pair_kind.eq('conflict')].to_parquet(O/'conflict-pairs.parquet',index=False);status.to_csv(O/'snapshot-coverage.csv',index=False)
    all_events=set(risk.e0_epoch);ready_events=set(risk[risk.feature_ready].e0_epoch);matched=set(epochs);unmatched=sorted(all_events-matched);pd.DataFrame([dict(e0_epoch=x,ever_ready=x in ready_events) for x in unmatched]).to_csv(O/'unmatched-events.csv',index=False)
    conflict=p[p.pair_kind.eq('conflict')];balance={}
    for key in ['h1','age','runup','scale','pvr']:
        aa=conflict['other_'+key];bb=conflict['h1_'+key];den=math.sqrt((aa.var(ddof=0)+bb.var(ddof=0))/2) if len(aa) else np.nan
        balance[key]=dict(PVR_choice_mean=float(aa.mean()) if len(aa) else None,H1_choice_mean=float(bb.mean()) if len(bb) else None,mean_difference=float((aa-bb).mean()) if len(aa) else None,mean_abs_difference=float((aa-bb).abs().mean()) if len(aa) else None,SMD=float((aa.mean()-bb.mean())/den) if len(aa) and den>0 else None)
    cov=dict(no_economic_outcomes_read=True,legal_snapshots=len(risk),ready_snapshots=int(risk.feature_ready.sum()),missing_snapshots=int((~risk.feature_ready).sum()),legal_E0_events=len(all_events),ready_E0_events=len(ready_events),matched_E0_events=len(matched),unmatched_E0_events=len(unmatched),pairs=len(p),kinds=p.pair_kind.value_counts().to_dict(),conflict_pairs=len(conflict),conflict_dates=conflict.date.nunique(),conflict_stocks=len(set(conflict.h1_symbol)|set(conflict.other_symbol)),conflict_industries=conflict.sector.nunique(),all_pair_industries=p.sector.nunique(),agreement_fraction=float(p.pair_kind.eq('same_choice').mean()),conflict_fraction=float(p.pair_kind.eq('conflict').mean()),tie_fraction=float(p.pair_kind.eq('pvr_tie_no_contrast').mean()),status=status.reason.value_counts().to_dict(),max_h1_gap=float(p.h1_gap.max()),max_age_gap=int(p.age_gap.max()),max_runup_scale=float(p.runup_gap_scale.max()),conflict_H1_exact_ties=int(conflict.h1_exact_tie.sum()),conflict_both_PVR_below50=int((conflict.h1_pvr.lt(50)&conflict.other_pvr.lt(50)).sum()),conflict_straddles50=int((conflict.h1_pvr.lt(50)^conflict.other_pvr.lt(50)).sum()),balance=balance,prefixes=prefixes,PVR_neutral_pair_selection_exact=True,seconds=time.monotonic()-t)
    save(O/'COVERAGE_BEFORE_RETURNS.json',cov);save(O/'match-freeze.json',dict(before_returns=True,sha256={str(x):H.sha(x) for x in [O/'PROTOCOL.json',O/'risk-set.parquet',O/'all-comparable-pairs.parquet',O/'conflict-pairs.parquet',O/'COVERAGE_BEFORE_RETURNS.json']},pairs=len(p),conflicts=len(conflict),each_event_used_once=True))
    H.progress(stage='coverage_ready',coverage=cov)

def compute(sample=False):
    t=time.monotonic();ident=H.read(O/'input-identity.json')['sha256'];fr=H.read(O/'match-freeze.json');assert all(H.sha(p)==h for p,h in {**ident,**fr['sha256']}.items());p=pd.read_parquet(O/'conflict-pairs.parquet');p=p.head(6) if sample else p;assert len(p)>0
    ids=set(p.h1_symbol)|set(p.other_symbol);_,m,_,_=H.context(ids,False);cache=pd.read_parquet(E1/'market-cache.parquet');gs={s:g.set_index('date').sort_index() for s,g in cache[cache.symbol.isin(ids)].groupby('symbol')};ep=pd.read_parquet(E1/'opportunities.parquet');dest=O/('sample' if sample else 'results');dest.mkdir(exist_ok=False);units=[];prefix=[]
    save(dest/'execution-freeze.json',dict(code_sha256=H.sha(Path(__file__)),pairs=len(p),units=len(p)*4,before_run=True))
    with gzip.open(dest/'audit.jsonl.gz','wt') as af:
        for n,pair in enumerate(p.to_dict('records')):
            day=pd.Timestamp(pair['date'])
            for role,key in [('pvr','other'),('h1','h1')]:
                s=pair[key+'_symbol'];g=gs[s].copy();assert g.loc[day,'Q'];g['Q']=False;g.loc[day,'Q']=True;ee=ep[ep.symbol.eq(s)&ep.start.le(pair['date'])&(ep.end_signal.isna()|ep.end_signal.gt(pair['date']))];assert len(ee)==1;e=ee.iloc[0].to_dict();original=e['event_id'];e.update(event_id=pair['pair_id']+'|'+role,start=pair['date'],carry_in=False)
                if pd.isna(e['end_signal']):e['end_signal']=None
                for cost in [1,2]:
                    u,a=H.run_event(e,g,m,'I',cost);res=abs(R.cashcheck(a)-u['available']);assert res<=u['precision_bound'];u.update(pair_id=pair['pair_id'],role=role,decision_day=pair['date'],original_event_id=original,cash_residual=res,**R.occupancy(a,g,day));units.append(u);a.update(pair_id=pair['pair_id'],role=role,decision_day=pair['date']);af.write(json.dumps(enc(a),ensure_ascii=False)+'\n');assert u['first_signal'] is None or str(u['first_signal'].date())==pair['date']
                    if sample and cost==1:
                        j=g.index.get_loc(day);cut=g.index[min(j+21,len(g)-1)];ex=dict(e)
                        if ex['end_signal'] and pd.Timestamp(ex['end_signal'])>cut:ex['end_signal']=None
                        _,pa=H.run_event(ex,g.loc[:cut],m,'I',cost,cutoff=cut)
                        def tm(x):return x['receipt'].at if x['kind']=='fill' else x['receivable'].ex_at if x['kind']=='dividend_accrual' else x['at']
                        for field in ['audit','attempts']:
                            expected=[x for x in a[field] if (tm(x) if field=='audit' else x['signal_at'])<=H.at(cut,datetime.time(15,10))];assert enc(expected)==enc(pa[field])
                        prefix.append(dict(pair_id=pair['pair_id'],role=role,cutoff=str(cut.date())))
            if sample or (n+1)%50==0:H.progress(stage='conflict_capital',sample=sample,pairs=n+1,seconds=time.monotonic()-t)
            if not sample and time.monotonic()-t>300:raise TimeoutError('300-second frozen conflict compute budget')
    pd.DataFrame(enc(units)).to_parquet(dest/'units.parquet',index=False)
    if not sample:
        a=pd.read_parquet(O/'sample/units.parquet');b=pd.read_parquet(dest/'units.parquet');b=b[b.pair_id.isin(a.pair_id)];keys=['pair_id','role','cost'];a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True)
        for k in ['net_pnl','buy_gross','buy_fees','sell_gross','sell_fees','shares','market_value','nav','available','dividend_receivable','held_close_sessions','invested_cost_sessions']:assert a[k].tolist()==b[k].tolist(),('sample/full',k)
    save(dest/'verification.json',dict(passed=True,pairs=len(p),units=len(units),independent_fees_raw_open_shares_cash_terminal_claims=True,max_cash_residual=max(x['cash_residual'] for x in units),max_nav_residual=max(x['independent_nav_residual'] for x in units),single_decision_day=True,economic_prefixes=prefix,sample_full_exact=not sample,seconds=time.monotonic()-t))
    H.progress(stage='finished',sample=sample,pairs=len(p),seconds=time.monotonic()-t)
if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='sample':compute(True)
    elif sys.argv[1]=='full':compute(False)
