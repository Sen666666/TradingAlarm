"""CP1 receipt increment under already-warm/PVR>50 eligibility; no pooled portfolio."""
from pathlib import Path
import importlib.util,sys,json,hashlib,time,gzip,csv,collections,math,datetime
from decimal import Decimal as D,getcontext
from dataclasses import replace
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029'
O=ROOT/'research_rounds/cp1-incremental-mechanism-20261029'
spec=importlib.util.spec_from_file_location('exp1_reused',E1/'code/audit.py');H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)
CP=ROOT/'research_rounds/continuous-protection-lines-20261028/signals';PV=ROOT/'research_rounds/pvr-act-comparison-20261027/scores'
Z=D(0);B=D('1000000')
def enc(x):return H.encoded(x)
def save(p,x):
    with Path(p).open('x') as f:json.dump(enc(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def read(p):return json.loads(Path(p).read_text())
def outputcsv(p,rows):
    if not rows:return
    with Path(p).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows([enc(x) for x in rows])
def progress(**x):print(json.dumps(enc(x),ensure_ascii=False),flush=True)
def smd(a,b):
    a=np.array(a,float);b=np.array(b,float);den=math.sqrt((a.var()+b.var())/2)
    return float((a.mean()-b.mean())/den) if den else 0.

def matching(risks):
    used=set();pairs=[];cases=[]
    for day,g in risks.groupby('date',sort=True):
        cand=g[g.case].to_dict('records');controls=g[~g.receipt].to_dict('records')
        for c in sorted(cand,key=lambda x:x['decision_id']):
            exact=[n for n in controls if (n['sector'],n['grade'],n['age_bin'])==(c['sector'],c['grade'],c['age_bin'])]
            free=[n for n in exact if n['epoch_id'] not in used]
            close=[n for n in free if abs(c['runup']-n['runup'])<=max(c['scale'],n['scale'])]
            why='matched' if close else 'no_exact_stratum' if not exact else 'control_epoch_already_used' if not free else 'runup_caliper'
            cases.append(dict(**c,match_status=why))
            if not close:continue
            n=min(close,key=lambda x:(abs(c['runup']-x['runup']),x['decision_id']))
            used.add(n['epoch_id'])
            pairs.append(dict(pair_id=c['decision_id'],date=day,case_epoch=c['epoch_id'],control_epoch=n['epoch_id'],case_symbol=c['symbol'],control_symbol=n['symbol'],sector=c['sector'],grade=c['grade'],age_bin=c['age_bin'],case_age=c['age'],control_age=n['age'],case_anchor=c['anchor'],control_anchor=n['anchor'],case_runup=c['runup'],control_runup=n['runup'],case_scale=c['scale'],control_scale=n['scale'],case_pvr=c['pvr'],control_pvr=n['pvr'],runup_gap=abs(c['runup']-n['runup']),gap_scale_units=abs(c['runup']-n['runup'])/max(c['scale'],n['scale'])))
    return pd.DataFrame(cases),pd.DataFrame(pairs)

def prepare():
    t=time.monotonic();ids={r['symbol'] for r in H.roster()};meta={r['symbol']:r for r in H.roster()}
    cache=pd.read_parquet(E1/'market-cache.parquet');b,m,_,dates=H.context(ids,True)
    grids={s:g.set_index('date').copy() for s,g in cache.groupby('symbol')};source={};risks=[];continuous=[];states={};epochs={}
    for s,g in grids.items():
        cp=pd.read_parquet(CP/f'{s}.parquet');pv=pd.read_parquet(PV/f'{s}.parquet')
        g['receipt']=cp.receipt.reindex(g.index).fillna(False).astype(bool);g['cp_ready']=cp.ready.reindex(g.index).fillna(False).astype(bool)
        g['pvr']=pv.score.reindex(g.index);g['scale']=pv.scale.reindex(g.index)
        for p in [CP/f'{s}.parquet',PV/f'{s}.parquet']:source[str(p)]=H.sha(p)
    for num,day in enumerate(dates):
        cl=H.at(day,datetime.time(15,10));opens=m.sessions['A'];clock=H.A.Clock(cl,opens[__import__('bisect').bisect_right(opens,cl)],cl.date())
        buyable=m.market_buyable(cl);inp=b.at_decision(clock,market_buyable=buyable);sectors={x.sector_id:x for x in inp.sectors}
        for line,h in zip(inp.lines,inp.historical):
            s=line.security_id;r=grids[s].loc[day];active=pd.notna(r.i_target) and bool(r.i_target);seg=int(r.segment_id) if pd.notna(r.segment_id) else -1
            st=states.get(s)
            if not active:states.pop(s,None);continue
            if st is None or st['seg']!=seg:
                eid=f'{s}|source={seg}|I-visible-start={day.date()}'
                st=dict(seg=seg,epoch_id=eid,start=str(day.date()),counter=0,anchor=None,anchor_counter=None,anchor_price=None,confirmed=False)
                states[s]=st;epochs[eid]=dict(epoch_id=eid,symbol=s,sector=meta[s]['sector_id'],visible_start=str(day.date()),anchor=None,first_confirmation=None)
            raw=m.raw[s];observed=day in raw.index and bool(raw.loc[day,'observed_bar']) and bool(raw.loc[day,'valid_price'])
            if observed:st['counter']+=1
            if bool(r.Q) and st['anchor'] is None:
                st.update(anchor=str(day.date()),anchor_counter=st['counter'],anchor_price=float(r.close));epochs[st['epoch_id']]['anchor']=st['anchor']
            if h.trend_up.read(clock) is not None:h=replace(h,trend_up=replace(h.trend_up,value=True))
            sec=H.pool.build_security(line,h,inp.evidence);sec=replace(sec,buy_allowed=buyable[s])
            q=H.A.eligibility(sec,sectors,clock,'S0').q is True
            continuous.append(dict(date=day,symbol=s,Q_cont=q))
            warm=pd.notna(r.g_ready) and bool(r.g_ready) and r.g_grade>=2
            good=st['anchor'] is not None and q and warm and bool(r.cp_ready) and pd.notna(r.pvr) and r.pvr>50 and pd.notna(r.scale) and r.scale>0
            if not good or st['confirmed']:continue
            age=st['counter']-st['anchor_counter'];agebin='0-20' if age<21 else '21-62' if age<63 else '63+'
            known=f"{s}|source={seg}|I-visible-start={st['start']}|anchor={st['anchor']}|decision={day.date()}"
            receipt=bool(r.receipt);did=hashlib.sha256(known.encode()).hexdigest()
            risks.append(dict(date=str(day.date()),symbol=s,sector=line.sector_id,grade=int(r.g_grade),age=age,age_bin=agebin,epoch_id=st['epoch_id'],anchor=st['anchor'],anchor_same_day=st['anchor']==str(day.date()),runup=math.log(float(r.close)/st['anchor_price']),scale=float(r.scale),pvr=float(r.pvr),receipt=receipt,case=receipt,decision_id=did,id_known_fields=known))
            if receipt:st['confirmed']=True;epochs[st['epoch_id']]['first_confirmation']=str(day.date())
        if (num+1)%100==0:progress(stage='risk_set',days=num+1,seconds=time.monotonic()-t)
    risks=pd.DataFrame(risks);cases,pairs=matching(risks);risks.to_parquet(O/'risk-set.parquet',index=False);pd.DataFrame(continuous).to_parquet(O/'continuous-eligibility.parquet',index=False);pd.DataFrame(epochs.values()).to_parquet(O/'observation-epochs.parquet',index=False)
    cases.to_parquet(O/'all-confirmations.parquet',index=False);pairs.to_parquet(O/'pairs.parquet',index=False)
    outputcsv(O/'unmatched.csv',cases[cases.match_status.ne('matched')].to_dict('records'))
    prefix=[]
    for end in ['2024-12-31','2025-12-31','2026-06-30']:
        c,p=matching(risks[risks.date.le(end)]);ref=pairs[pairs.date.le(end)].reset_index(drop=True);pd.testing.assert_frame_equal(p.reset_index(drop=True),ref,check_exact=True);prefix.append(dict(cutoff=end,pairs=len(p)))
    assert cases.epoch_id.is_unique and pairs.control_epoch.is_unique
    known_c=set(cases[cases.match_status.eq('matched')].decision_id);assert set(pairs.pair_id)==known_c
    balance={}
    for name in ['age','runup','scale','pvr']:
        a=pairs['case_'+name];z=pairs['control_'+name]
        balance[name]=dict(case_mean=float(a.mean()),control_mean=float(z.mean()),case_median=float(a.median()),control_median=float(z.median()),mean_paired_difference=float((a-z).mean()),median_abs_paired_difference=float((a-z).abs().median()),smd=smd(a,z))
    counts=cases.groupby('sector').size().to_dict();matched=pairs.groupby('sector').size().to_dict();both=set(pairs.case_epoch)&set(pairs.control_epoch)
    cov=dict(no_economic_results_read=True,all_confirmations=len(cases),matched=len(pairs),unmatched=len(cases)-len(pairs),matching_rate=len(pairs)/len(cases),unmatched_reasons=cases[cases.match_status.ne('matched')].match_status.value_counts().to_dict(),case_stocks=int(cases.symbol.nunique()),matched_case_stocks=int(pairs.case_symbol.nunique()),matched_control_stocks=int(pairs.control_symbol.nunique()),case_dates=int(cases.date.nunique()),matched_dates=int(pairs.date.nunique()),case_sectors=len(counts),matched_sectors=len(matched),sector_coverage={s:dict(cases=int(n),matched=int(matched.get(s,0))) for s,n in counts.items()},age_bins=pairs.age_bin.value_counts().to_dict(),same_anchor_day_cases=int(cases.anchor_same_day.sum()),balance=balance,max_caliper_scale_gap=float(pairs.gap_scale_units.max()),control_epochs_later_used_as_cases=len(both),prefix_exact=prefix,seconds=time.monotonic()-t)
    save(O/'MATCH_COVERAGE.json',cov)
    for p in [E1/'market-cache.parquet',E1/'code/audit.py',O/'PROTOCOL.json',Path(__file__),O/'risk-set.parquet',O/'pairs.parquet',O/'all-confirmations.parquet',O/'observation-epochs.parquet',O/'MATCH_COVERAGE.json']:
        source[str(p)]=H.sha(p)
    save(O/'match-freeze.json',dict(before_economic_outcomes=True,sha256=source,pairs=len(pairs),main_weight_per_pair=1,case_stock_pair_counts=pairs.case_symbol.value_counts().to_dict(),role_reuse='one case and at most one control per I epoch',prefix_exact=True))
    progress(stage='matching_ready',coverage=cov)

def economic(sample=False):
    t=time.monotonic();freeze=read(O/'match-freeze.json');assert H.sha(O/'pairs.parquet')==freeze['sha256'][str(O/'pairs.parquet')]
    pairs=pd.read_parquet(O/'pairs.parquet');allpairs=pairs
    if sample:
        # Deterministic matching metadata only, no P&L selection.
        take=list(pairs.groupby('sector',sort=True).head(1).index)+list(pairs.groupby('age_bin',sort=True).head(1).index)
        pairs=pairs.loc[sorted(set(take))]
    ids=set(pairs.case_symbol)|set(pairs.control_symbol);_,m,_,_=H.context(ids,False)
    cache=pd.read_parquet(E1/'market-cache.parquet');grids={s:g.set_index('date').sort_index() for s,g in cache[cache.symbol.isin(ids)].groupby('symbol')}
    epochs=pd.read_parquet(E1/'opportunities.parquet');dest=O/('sample' if sample else 'results');dest.mkdir(exist_ok=False);units=[]
    f=gzip.open(dest/'audit.jsonl.gz','wt')
    try:
        for n,p in enumerate(pairs.to_dict('records')):
            day=pd.Timestamp(p['date'])
            for leg in ['case','control']:
                s=p[leg+'_symbol'];g=grids[s].copy();g['Q']=False;g.loc[day,'Q']=True
                choices=epochs[epochs.symbol.eq(s)&epochs.start.le(p['date'])&(epochs.end_signal.isna()|epochs.end_signal.gt(p['date']))]
                assert len(choices)==1,(s,p['date'],'unique original E0 event');e=choices.iloc[0].to_dict();e['original_event_id']=e['event_id'];e['event_id']=p['pair_id']+'|'+leg;e['start']=p['date'];e['carry_in']=False
                if pd.isna(e['end_signal']):e['end_signal']=None
                for cost in [1,2]:
                    u,a=H.run_event(e,g,m,'I',cost);u.update(pair_id=p['pair_id'],leg=leg,decision_day=p['date'],observation_epoch=p[leg+'_epoch'],original_event_id=e['original_event_id']);units.append(u)
                    # Independent available-cash transfer reconstruction, same tested experiment-one contract.
                    cash=B;reserved={}
                    for x in a['audit']:
                        k=x['kind']
                        if k=='reserve':cash-=x['gross_budget_cny']+x['fee_reserved_cny'];reserved[x['order_id']]=x['fee_reserved_cny']
                        elif k=='release_buy':cash+=x['gross_released']+x['fee_released'];reserved.pop(x['order_id'],None)
                        elif k=='fill' and x['receipt'].side=='buy':
                            fee=x['receipt'].fees_cny;cash-=max(Z,fee-reserved[x['order_id']]);reserved[x['order_id']]=max(Z,reserved[x['order_id']]-fee)
                        elif k=='settle' and not x['settlement'].debit:cash+=x['settlement'].cny_amount
                        elif k=='dividend_payment':cash+=x['entitlement'].net_local
                    assert abs(cash-u['available'])<=u['precision_bound']
                    assert u['first_signal'] is None or str(u['first_signal'].date())==p['date']
                    a.update(pair_id=p['pair_id'],leg=leg,decision_day=p['date']);f.write(json.dumps(enc(a),ensure_ascii=False)+'\n')
            if sample or (n+1)%100==0:progress(stage='paired_capital',sample=sample,pairs=n+1,total=len(pairs),seconds=time.monotonic()-t)
            if not sample and time.monotonic()-t>300:raise TimeoutError('300-second compute budget')
        f.close();pd.DataFrame(enc(units)).to_parquet(dest/'units.parquet',index=False)
        save(dest/'verification.json',dict(passed=True,pairs=len(pairs),units=len(units),post_confirmation_only=True,single_decision_day_exact=True,independent_fees_shares_cash_terminal=True,max_nav_residual=max(u['independent_nav_residual'] for u in units),all_terminal_holdings_claims_included=True))
        save(dest/'timings.json',dict(seconds=time.monotonic()-t,budget_seconds=300));progress(stage='economic_verified',sample=sample,pairs=len(pairs),seconds=time.monotonic()-t)
    except BaseException as ex:
        f.close();pd.DataFrame(enc(units)).to_parquet(dest/'partial-units.parquet',index=False);save(dest/'FAILURE.json',dict(error=repr(ex),seconds=time.monotonic()-t));raise

if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='match':prepare()
    elif cmd=='sample':economic(True)
    elif cmd=='full':economic(False)
    else:raise ValueError(cmd)
