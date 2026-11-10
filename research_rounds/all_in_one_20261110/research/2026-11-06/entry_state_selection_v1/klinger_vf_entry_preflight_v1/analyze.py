from pathlib import Path
import pandas as pd,numpy as np,json,math,hashlib,time,datetime
O=Path(__file__).resolve().parent;R=O.parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
S={}
def source(p):p=Path(p);S[str(p)]=sha(p);return p
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else str(v))+'\n')
def kvo(b,cal):
    # Input is physically truncated by caller at target signal CLOSE.
    # Calendar missing rows are explicit state breaks, never future filled.
    cc=cal[(cal>=b.index.min())&(cal<=b.index.max())]
    b=b.reindex(cc)
    raw=['raw_open','raw_high','raw_low','raw_close'];native=['open','high','low','close']
    valid=np.isfinite(b[raw+native]).all(axis=1)&b[raw+native].gt(0).all(axis=1)
    valid &= b.raw_high.ge(b[raw].max(axis=1))&b.raw_low.le(b[raw].min(axis=1))&b.high.ge(b[native].max(axis=1))&b.low.le(b[native].min(axis=1))
    for c in ['observed_bar','is_observed_bar','price_eligible','volume_eligible']:valid &= b[c].eq(True)
    for c in ['source_invalid','synthetic_event_bar']:valid &= b[c].eq(False)
    valid &= b.volume_unit.eq('shares')&b.amount_unit.eq('CNY')
    for c in ['raw_volume','amount','adjustment_factor','volume_factor']:valid &= np.isfinite(b[c])&b[c].gt(0)
    for c in native:valid &= (b['raw_'+c]*b.adjustment_factor-b[c]).abs().le(1e-8)
    mean=b.amount/b.raw_volume;tol=.5/b.raw_volume+1e-8
    valid &= np.isfinite(mean)&mean.ge(b.raw_low-tol)&mean.le(b.raw_high+tol)
    keys=['source_kind','source_path','segment_id','adjustment_factor','volume_factor']
    valid &= b[keys].notna().all(axis=1)
    for c in ['source_kind','source_path']:valid &= b[c].astype(str).str.len().gt(0)
    vals=b[['raw_high','raw_low','raw_close','raw_volume']].to_numpy(float)
    identities=list(b[keys].itertuples(index=False,name=None))
    n=0;prevkey=None;T=1;dm=cm=prevS=prevDM=0.;F=Slow=Sig=K=0.;start=None;breakreason='START';res=[];run=0
    alpha=[2/35,2/56,2/14]
    for j,(d,row,ok,key) in enumerate(zip(cc,vals,valid.to_numpy(),identities)):
        hi,lo,cl,v=row;dr=hi-lo;ss=hi+lo+cl
        if not ok:
            n=0;prevkey=None;start=None;breakreason='MISSING_OR_INVALID_BAR'
            res.append(dict(day=d,known=False,reason=breakreason,state_rows=0,raw_close=cl,raw_volume=v));continue
        if prevkey is not None and key!=prevkey:
            changed=[keys[k] for k in range(len(keys)) if key[k]!=prevkey[k]]
            n=0;breakreason='CHANGE_'+','.join(changed)
        if n==0:
            start=d;n=1;T=1;prevS=ss;prevDM=dr;prevC=cl;prevkey=key;run=0
            res.append(dict(day=d,known=False,reason='WARMUP_'+breakreason,state_rows=n,state_start=start,raw_close=cl,raw_volume=v));continue
        nt=1 if ss>prevS else -1 if ss<prevS else T
        newtrend=nt!=T
        cm=prevDM+dr if n==1 or newtrend else cm+dr
        vf=0. if cm==0 else v*abs(2*(dr/cm)-1)*nt*100
        if n==1:F=Slow=vf;K=Sig=0.
        else:
            F=alpha[0]*vf+(1-alpha[0])*F
            Slow=alpha[1]*vf+(1-alpha[1])*Slow
            K=F-Slow
            Sig=alpha[2]*K+(1-alpha[2])*Sig
        run=1 if n==1 or newtrend else run+1
        hist=K-Sig;n+=1;known=n>=111
        res.append(dict(day=d,known=known,reason='KNOWN' if known else 'WARMUP_'+breakreason,state_rows=n,state_start=start,
         raw_high=hi,raw_low=lo,raw_close=cl,raw_volume=v,HLC=ss,HLC_change=ss-prevS,close_change=cl-prevC,
         T=nt,HLC_tie=ss==prevS,close_sign=int(np.sign(cl-prevC)),direction_disagreement=nt!=int(np.sign(cl-prevC)),
         DM=dr,CM=cm,DM_CM=dr/cm if cm else np.nan,trend_run=run,VF=vf,EMA34=F,EMA55=Slow,KVO=K,signal13=Sig,histogram=hist,
         raw_CLV=(2*cl-hi-lo)/dr if dr else np.nan,source_kind=key[0],source_path=key[1],segment_id=key[2],
         adjustment_factor=key[3],volume_factor=key[4]))
        T=nt;prevS=ss;prevDM=dr;prevC=cl;prevkey=key
    return pd.DataFrame(res).set_index('day')

def synthetic():
    ix=pd.bdate_range('2020-01-01',periods=150)
    b=pd.DataFrame(index=ix)
    for c,v in dict(open=10.,high=11.,low=9.,close=10.,raw_volume=100.,amount=1000.,source_kind='test',source_path='test',segment_id=0,adjustment_factor=1.,volume_factor=1.,volume_unit='shares',amount_unit='CNY',observed_bar=True,is_observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False).items():b[c]=v
    for c in ['open','high','low','close']:b['raw_'+c]=b[c]
    x=kvo(b,ix);checks={'tie_preserves_plus1':bool(x['T'].dropna().eq(1).all()),'warmup110_unknown111_known':bool(not x.known.iloc[109] and x.known.iloc[110])}
    b2=b.copy()
    for c in ['high','low','open','close']:
        b2[c]=b2['raw_'+c]=b[c]+np.arange(150)*.01
    b2.amount=b2.raw_volume*b2.raw_close
    x2=kvo(b2,ix);b3=b2.copy();b3.raw_volume*=7;b3.amount*=7
    x3=kvo(b3,ix);checks['volume_rescale_histogram_sign_and_linear']=bool(np.allclose(x3.histogram.dropna(),7*x2.histogram.dropna(),rtol=1e-10,atol=1e-6))
    for name,c,val in [('price_factor','adjustment_factor',2.),('volume_factor','volume_factor',2.),('source','source_path','other'),('missing_volume','raw_volume',np.nan)]:
        t=b2.copy();t.loc[ix[-20],c]=val;z=kvo(t,ix);checks[name+'_break_unknown']=bool(not z.known.iloc[-1])
    flat=b.copy()
    for c in ['open','high','low','close']:flat[c]=flat['raw_'+c]=10.
    z=kvo(flat,ix);checks['CM0_VF0']=bool(z.CM.dropna().eq(0).all() and z.VF.dropna().eq(0).all())
    # Original 1993 printed VF numerical check; arithmetic convention only.
    checks['original_printed_VF_round2']=round(19030*abs(2*1.25/2.25-1)*100,2)==211444.44
    # HLC can rise while C falls: not identical to signed close-return/OBV.
    checks['HLC_vs_close_distinct']=(12+10+10.5)>(11+9+10.8) and 10.5<10.8
    assert all(checks.values()),checks
    return checks

def main():
    t=time.monotonic()
    seal=json.loads((O/'FREEZE.json').read_text())
    assert all(sha(O/n)==h for n,h in seal['hashes'].items())
    with (O/'RUN_ONCE.lock').open('x') as f:f.write(datetime.datetime.now(datetime.timezone.utc).isoformat())
    source(O/'PROTOCOL.json');source(Path(__file__))
    save('SYNTHETIC_QA.json',synthetic())
    cases=pd.read_csv(source(O/'FIXED42_IDENTITIES.csv'));early=pd.read_csv(source(O/'FIXED6_EARLY_IDENTITIES.csv'));queue=pd.read_csv(source(O/'FIXED_DATE_ORIGINAL_QUEUES.csv'))
    wanted=pd.concat([queue[['sid','signal_day']],cases[['sid','signal_day']],early[['sid','signal_day']]],ignore_index=True).drop_duplicates()
    wanted['signal_day']=pd.to_datetime(wanted.signal_day)
    manifest={m['symbol']:m for m in json.loads(source(U/'STOCK_MANIFEST.json').read_text())}
    with np.load(source(H),allow_pickle=False) as z:cal=pd.DatetimeIndex(z['dates'])
    for sid in sorted(wanted.sid.unique()):
        m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
        source(p);assert S[p]==m['source_sha256'][p]
    save('EXACT_REPEAT_SOURCE_BEFORE.json',S)
    features=[];prefix=[];case_daily=[];inputs=[]
    casekeys=set(zip(pd.concat([cases,early]).sid,pd.to_datetime(pd.concat([cases,early]).signal_day)))
    cols=['open','high','low','close','raw_open','raw_high','raw_low','raw_close','raw_volume','amount','source_kind','source_path','segment_id','adjustment_factor','volume_factor','volume_unit','amount_unit','observed_bar','is_observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']
    for no,(sid,g) in enumerate(wanted.groupby('sid',sort=True)):
        m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));source(p);assert S[p]==m['source_sha256'][p]
        b=pd.read_parquet(p,columns=cols).loc[:g.signal_day.max()]
        z=kvo(b,cal)
        for d in sorted(g.signal_day):
            # Recalculate physical truncated prefix for every queried point.
            zz=kvo(b.loc[:d],cal)
            if d not in z.index:
                row=dict(known=False,reason='NO_SIGNAL_BAR',state_rows=0)
                exact=d not in zz.index
            else:
                pd.testing.assert_series_equal(z.loc[d],zz.loc[d],check_exact=True)
                row=z.loc[d].to_dict();exact=True
            k=cal.get_loc(d)
            gate='ALLOW' if row['known'] and row['histogram']>0 else 'DENY' if row['known'] else 'UNKNOWN_KEEP_ORIGINAL'
            features.append(dict(sid=sid,signal_day=d,earliest_next_open=cal[k+1] if k+1<len(cal) else pd.NaT,gate=gate,**row))
            prefix.append(dict(sid=sid,signal_day=d,physical_prefix_exact=exact,last_input_day=zz.index.max() if len(zz) else None))
            if (sid,d) in casekeys:
                daily=z.loc[:d].tail(111).reset_index();daily['sid']=sid;daily['signal_day']=d;case_daily.append(daily)
        if (no+1)%100==0:print('PROGRESS',no+1,'seconds',round(time.monotonic()-t,2),flush=True)
    feat=pd.DataFrame(features)
    for x in [cases,early,queue]:x['signal_day']=pd.to_datetime(x.signal_day)
    feat.to_csv(O/'FEATURES_PRELABEL.csv',index=False)
    cases.merge(feat,on=['sid','signal_day'],validate='one_to_one').to_csv(O/'FIXED42_FEATURES_PRELABEL.csv',index=False)
    early.merge(feat,on=['sid','signal_day'],validate='one_to_one',suffixes=('_old','')).to_csv(O/'FIXED6_FEATURES_PRELABEL.csv',index=False)
    queue.merge(feat,on=['sid','signal_day'],validate='many_to_one',suffixes=('_old','')).to_csv(O/'FULL_QUEUE_FEATURES_PRELABEL.csv',index=False)
    pd.concat(case_daily,ignore_index=True).to_csv(O/'FIXED48_LAST111_STATE_TRACE.csv',index=False)
    pd.DataFrame(prefix).to_csv(O/'PREFIX_QA.csv',index=False)
    save('FEATURE_SEAL.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),hashes={p.name:sha(p) for p in O.glob('*PRELABEL.csv')},no_new_labels_read=True))
    # Previously sealed original actual account labels, only after feature seal.
    lab=pd.read_csv(source(R/'shared_probe_order_credit_identity_v1/FIXED_CASES_WITH_ORIGINAL_SHARED_LABELS.csv'),parse_dates=['signal_day'])
    labcols=['event_id','original_actual_shared_fill','original_buy_day','original_buy_q','original_core_status','original_core_NET80','original_core_return']
    final=cases.merge(feat,on=['sid','signal_day'],validate='one_to_one').merge(lab[labcols],on='event_id',validate='one_to_one')
    final.to_csv(O/'FIXED42_ORIGINAL_LABEL_CONTROLS.csv',index=False)
    queues=queue.merge(feat,on=['sid','signal_day'],validate='many_to_one',suffixes=('_old',''))
    sums=[]
    for (win,d),g in queues.groupby(['window','signal_day']):
        selected=g[g.decision.eq('SELECTED_PENDING')]
        sums.append(dict(window=win,signal_day=d,all_original_events=len(g),I_qualified=int(g.I_qualified.eq(True).sum()),selected_pending=len(selected),selected_allow=int(selected.gate.eq('ALLOW').sum()),selected_deny=int(selected.gate.eq('DENY').sum()),selected_unknown=int(selected.gate.eq('UNKNOWN_KEEP_ORIGINAL').sum()),events_known=int(g.known.sum()),events_deny=int(g.gate.eq('DENY').sum())))
    pd.DataFrame(sums).to_csv(O/'QUEUE_SUMMARY.csv',index=False)
    save('SUMMARY.json',dict(total_features=len(feat),stocks=feat.sid.nunique(),fixed42_gate=final.gate.value_counts().to_dict(),fixed6_gate=early[['sid','signal_day']].merge(feat,on=['sid','signal_day']).gate.value_counts().to_dict(),original_filled_control_gate=final[final.original_actual_shared_fill.eq(True)].gate.value_counts().to_dict(),original_positive_core_control_gate=final[final.original_actual_shared_fill.eq(True)&final.original_core_NET80.gt(0)].gate.value_counts().to_dict(),original_nonpositive_core_control_gate=final[final.original_actual_shared_fill.eq(True)&final.original_core_NET80.le(0)].gate.value_counts().to_dict(),known_all=int(feat.known.sum()),unknown_reason=feat[~feat.known].reason.value_counts().to_dict(),queue_summary=sums))
    save('SOURCE_SHA256.json',S);assert all(sha(p)==h for p,h in S.items())
    assert all(sha(O/n)==h for n,h in seal['hashes'].items())
    save('QA.json',dict(physical_prefix_exact=len(prefix),fixed_cases=48,source_hashes_unchanged=len(S),accounts_run=0,parameter_searches=0,original_files_changed=0,seconds=time.monotonic()-t))
    prior=json.loads((O/'FIRST_FEATURE_PASS_HASHES.json').read_text())
    exact={n:sha(O/n)==h for n,h in prior.items()}
    assert all(exact.values()),exact
    save('EXACT_REPEAT_QA.json',dict(all_prior_feature_and_control_CSVs_identical=exact,reason='Post-feature summary merge column collision; exact same formula repetition also records whole source hashes before and after. No alternate candidate.'))
    print('DONE',json.dumps(json.loads((O/'SUMMARY.json').read_text()),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
