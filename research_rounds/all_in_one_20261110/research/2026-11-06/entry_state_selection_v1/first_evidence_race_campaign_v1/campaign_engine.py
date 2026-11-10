"""Frozen initial-layer local adapter. No economic work at import. No old writes.
Economic execution is exposed to the separately audited driver only.
"""
from pathlib import Path
import importlib.util, hashlib, json, re
from decimal import Decimal as D
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent; R=O.parent; E=R/'m3_stock_birth_during_sector_v1'
END=pd.Timestamp('2026-06-30')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load_engine(window):
    folder='relative_priority_equity_run_2022_v1' if window=='2022' else 'cash_equity_baseline_2024_v1'
    path=E/folder/'engine.py'
    spec=importlib.util.spec_from_file_location('original_'+window,path);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
    # The imported original engine contains definitions and source checks, no driver/output writes.
    # Keep native monetary calculations; omit redundant daily profitability audit logs.
    s.mark=lambda st,px,d:s.native_mark(st,px,d)+st.get('receivable',D(0))
    return s

def market_path(s,sid):
    m=s.manifest[sid];pe=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'));ps=str(Path(pe).with_name('signal.parquet'))
    h=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
    with np.load(h,allow_pickle=False) as z:fullcal=pd.DatetimeIndex(z['dates'])
    fullcal=fullcal[fullcal<=END];s.hashes[str(h)]=sha(h)
    frames=[]
    for p in [m['refs']['facts'],m['refs']['CP1'],pe,ps]:
        expected={**m['source_sha256'],**m['output_sha256']}[p];assert sha(p)==expected,(p,'drift');s.hashes[p]=expected
        frames.append(pd.read_parquet(p).reindex(fullcal))
    f,cp,ev,b=frames;lin=b[['source_kind','source_path','segment_id']]
    same=(lin.notna().all(axis=1)&lin.shift().notna().all(axis=1)&lin.eq(lin.shift()).all(axis=1)).fillna(False)
    ok=(b.observed_bar.eq(True)&b.price_eligible.eq(True)&pd.to_numeric(b.close,errors='coerce').gt(0)&pd.to_numeric(b.raw_close,errors='coerce').gt(0)&pd.to_numeric(f.factor,errors='coerce').gt(0)&lin.notna().all(axis=1)&f.segment_id.eq(b.segment_id)&ev.segment_id.eq(b.segment_id)).fillna(False)
    known=f.i_target.isin([0,1]);roots=[];root=None
    for k,d in enumerate(fullcal):
        if not (known.iloc[k] and ok.iloc[k]) or f.i_target.iloc[k]==0:root=None
        elif k>0 and same.iloc[k] and known.iloc[k-1] and ok.iloc[k-1] and f.i_target.iloc[k-1]==0:root=d
        elif not(k>0 and same.iloc[k] and known.iloc[k-1] and ok.iloc[k-1] and f.i_target.iloc[k-1]==1):root=None
        roots.append(root)
    return dict(f=f,cp=cp,ev=ev,b=b,same=same,ok=ok,known=known,roots=pd.Series(roots,index=fullcal))

def unresolved_date(u):
    z=u.get('row',u) if isinstance(u,dict) else {};v=z.get('1') or z.get('effective_date') or z.get('date')
    if v is None:
        m=re.search(r'\d{4}-\d{2}-\d{2}',str(u));return pd.Timestamp(m.group()) if m else None
    try:return pd.Timestamp(str(v)) if '-' in str(v) else pd.to_datetime(str(v),format='%Y%m%d')
    except Exception:return None

def coverage(s,st,result):
    """Original report interval rules, per actual attempt; no inherited old label."""
    if st.get('entry_status')!='CONDITIONAL_OPEN_PROXY':return ['NO_CONFIRMED_HOLDING']
    a=s.local_actions(st['sid']);reasons=[];unparsed=[]
    if st['window']=='2024_924':
        reasons+=a.get('_source_issues',[])+a.get('_source_coverage_issues',[])
        if not a.get('_source_integrity_ok',False):reasons.append('ACTION_SOURCE_INTEGRITY_UNKNOWN')
    if a.get('raw_response_empty'):reasons.append('ACTION_RAW_RESPONSE_EMPTY')
    if not a.get('coverage_evidence'):reasons.append('NO_RIGHTS_SOURCE')
    for e in a.get('coverage_evidence',[]):
        try:
            raw=s.read(e['path'])
            if sha(e['path'])!=e['sha256']:reasons.append('RIGHTS_HASH_MISMATCH')
            if not raw.get('records'):reasons.append('RIGHTS_EMPTY')
            unparsed+=raw.get('unparsed',[])
        except Exception:reasons.append('RIGHTS_EVIDENCE_UNREADABLE')
    ent=st['entry_day'];end=pd.Timestamp(result.get('exit_day',result.get('status_day',END)));incl=result['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND' or 'CENSORED' in result['status']
    def inside(d):return d is not None and ent<d and (d<=end if incl else d<end)
    for u in unparsed+a.get('unresolved',[]):
        d=unresolved_date(u)
        if d is None:reasons.append('UNPARSED_UNDATED')
        elif inside(d):reasons.append('UNPARSED_IN_HELD_INTERVAL')
    for e in a.get('events',[]):
        d=pd.Timestamp(e['effective_date'])
        if not inside(d):continue
        ee=s.EVENT_AT.get((st['sid'],d));owned=[c for c in s.claims.values() if ee and c['owner_round_id']==st['round_id'] and c['economic_event_id']==ee['economic_event_id'] and c['recognized']]
        if ee is None or not ee['entitlement_verified'] or not owned:reasons.append('UNVERIFIED_HELD_ACTION:'+str(d.date()))
    return sorted(set(reasons))

def run_campaign(s,baseline,initial_event,arm,mp,invites,native_rows=None,canonical_cp=None,ab_knowledge=None):
    """One original permit. Resets rights ownership and all action state per arm/campaign."""
    assert arm in ['A','B','C','D'];s.reset(True,'CORE_REGRESSION')
    native=None
    if arm=='D':
        from native_role_adapter import NativeRoles
        native=NativeRoles(s,canonical_cp or {})
    sid=baseline['sid'];window=baseline['window'];rid=baseline['round_id'];signal=pd.Timestamp(baseline['signal_day']);root=mp['roots'].get(signal)
    root_known=pd.notna(root);campaign=f'{window}|{sid}|{root.date()}' if root_known else rid+'|UNKNOWN'
    original_size=s.size;cash=D(0);initial_cost=None;attempts=[];states={};ledger=[];decisions=[];closed_root=False;root_unknown=not root_known;last_exit=None;consumed=set();native_unknown=False;recovery_unknown=False;initial_epoch_known=True
    holding_days=0;capital_days=D(0);peak=None;maxdd=D(0);maxdd_pct=D(0);mark_unknown=False
    arm_id=arm+'|'+campaign
    # Keep only the same symbol's original admitted actions, without widening evidence.
    maps={name:getattr(s,name) for name in ['BY_RECORD','BY_EX','BY_PAY']}
    for name,old in maps.items():setattr(s,name,{d:[e for e in es if e['sid']==sid] for d,es in old.items() if any(e['sid']==sid for e in es)})
    def bounded_size(symbol,d,price,floor,budget,riskmax,cap):
        return original_size(symbol,d,price,floor,min(budget,cash),riskmax,cap)
    def start(r,check,d,options=None):
        nonlocal states
        r=dict(r);r['window']=window;r['day']=d
        st=s.new_state(r,arm_id,rid+'|'+arm+'|'+str(len(attempts)+1),check)
        st['trial']=True;st['confirmed_day']=None;st['down_day']=None
        if native is not None:
            nr=(native_rows or {}).get(d,{})
            if not attempts:native.initial_epoch(st,nr)
            else:native.recovery(st,nr,options)
        attempts.append(st);states[sid]=st
    check=s.checkclose(initial_event);assert check['close_check']=='PASS',(rid,check)
    start(initial_event,check,signal)
    if arm=='D':
        nr=(native_rows or {}).get(signal,{})
        initial_epoch_known=s.true(nr.get('epoch_lineage_known')) and pd.notna(nr.get('i_epoch'))
        native_unknown=not initial_epoch_known
    try:
        for k,d in enumerate(s.cal):
            if d<signal:continue
            s.accrue_day(arm_id,d)
            st=states.get(sid)
            if d>signal and st and st['state'] in ['BUY_PENDING','HELD']:
                n=len(s.actions)
                if st['state']=='BUY_PENDING':
                    s.size=bounded_size if len(attempts)>1 else original_size
                    s.entry_open(states,sid,st,d);s.size=original_size
                else:
                    st['addpending']=None;s.held_open(states,sid,st,d,s.cal[k-1])
                for act in s.actions[n:]:
                    value=D(act['q'])*D(str(act['price']));fee=D(str(act['fee']))
                    if act['side']=='buy_core':
                        exact=st['spent'] # first and only buy in each initial-layer attempt
                        if initial_cost is None:initial_cost=exact;cash=exact
                        cash-=exact;delta=-exact
                    elif act['side'] in ['sell_all','sell_initial']:
                        # Native Decimal cash plus spent contains exact sale proceeds, no double dividend.
                        delta=st['cash']+st['spent']-st['dividend_paid'];cash+=delta;last_exit=d
                    else:raise AssertionError(('unexpected add action',act))
                    assert cash>=0,(rid,arm,d,cash)
                    ledger.append(dict(day=d,event=act['side'],attempt=st['round_id'],delta=delta,available_cash=cash))
            st=states.get(sid)
            if st and st['state']=='HELD':
                st['addpending']=None;s.held_close(states,sid,st,d);st['addpending']=None
                live=states.get(sid,{}).get('state')=='HELD'
                if live and arm!='A' and st['trial'] and not st['exitpending'] and not st.get('initialexitpending',False):
                    if not root_known or not mp['ok'].loc[d] or not mp['known'].loc[d] or not mp['same'].loc[d] or mp['roots'].loc[d]!=root:
                        s.freeze_unknown(states,sid,st,'RACE_SOURCE_OR_ROOT_UNKNOWN',d)
                    elif pd.isna(mp['ev'].loc[d,'event']) or pd.isna(mp['cp'].loc[d,'ready']) or not bool(mp['cp'].loc[d,'ready']) or pd.isna(mp['cp'].loc[d,'receipt']):
                        s.freeze_unknown(states,sid,st,'RACE_EVENT_OR_CP_UNKNOWN',d)
                    elif float(mp['ev'].loc[d,'event'])==-1:
                        st['exitpending']='TRIAL_DOWN_FIRST';st['down_day']=d
                    elif bool(mp['cp'].loc[d,'receipt']):
                        if arm=='D' and native.g['cp_receipt'](sid,d) is None:s.freeze_unknown(states,sid,st,'CP_CONFIRMATION_IDENTITY_UNKNOWN',d)
                        else:st['trial']=False;st['confirmed_day']=d
            # Environment does not disappear while flat. C cannot reconnect across unknown.
            if d>=signal and not closed_root and root_known:
                if not(mp['ok'].loc[d] and mp['known'].loc[d]) or (d>signal and not mp['same'].loc[d]):root_unknown=True
                elif mp['f'].loc[d,'i_target']==0:closed_root=True
                elif mp['roots'].loc[d]!=root:root_unknown=True
            s.register(states,arm_id,d)
            if arm=='C' and initial_cost is not None and last_exit is not None and d>=last_exit and not closed_root and not root_unknown and sid not in states:
                birth=(ab_knowledge or {}).get(d) if ab_knowledge is not None else True
                if birth is not True and not s.true(birth):
                    recovery_unknown=True
                    decisions.append(dict(day=d,campaign=campaign,arm=arm,reason='AB_BIRTH_OPPORTUNITY_UNKNOWN'))
                r=invites.get(d) if s.true(birth) else None
                if r is not None:
                    assert r['sid']==sid and pd.Timestamp(r['day'])==d
                    assert r['event_type'] in ['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR']
                    assert r['event_id'] not in consumed
                    consumed.add(r['event_id'])
                    dec=dict(day=d,event_id=r['event_id'],campaign=campaign,arm=arm)
                    if not s.true(r['I_qualified']):
                        dec['reason']='I_INELIGIBLE'
                        known_reject=any(s.false(r.get(f)) for f in ['e0_ready','g_ready','i_target']) or (s.finite(r.get('i_floor')) and r['i_floor']<=0)
                        if not known_reject:recovery_unknown=True;dec['reason']='I_QUALIFICATION_UNKNOWN'
                    elif not s.true(r['PVR_known']) or not s.finite(r['PVR_score']):dec['reason']='PVR_UNKNOWN';recovery_unknown=True
                    else:
                        check=s.checkclose(r);dec.update(check)
                        if check['close_check']=='PASS':start(r,check,d);dec['reason']='CONDITIONAL_NEW_AB_PENDING'
                        else:
                            dec['reason']='CLOSE_'+check['close_check']
                            if 'UNKNOWN' in check['close_check']:recovery_unknown=True
                    decisions.append(dec)
            if arm=='D' and initial_cost is not None and last_exit is not None and d>=last_exit and not closed_root and not root_unknown and sid not in states:
                nr=(native_rows or {}).get(d)
                if not initial_epoch_known or nr is None or not s.true(nr.get('epoch_lineage_known')) or pd.isna(nr.get('i_epoch')):
                    native_unknown=True
                    decisions.append(dict(day=d,campaign=campaign,arm=arm,reason='NATIVE_RECOVERY_SOURCE_UNKNOWN'))
                else:
                    nr=dict(nr,sid=sid,day=d,window=window,sector=initial_event['sector'],name=initial_event['name'],industry=initial_event['industry'],event_type='NATIVE_FAST_RECOVERY',event_id='D|'+sid+'|'+str(d.date()))
                    unused=(arm_id,sid,str(nr['i_epoch'])) not in native.g['core_consumed']
                    uncertain=(unused and pd.isna(nr.get('event_Q'))) or (pd.isna(nr.get('cp_fresh')) and not s.false(nr.get('continuing_Q')))
                    if s.true(nr.get('cp_fresh')) and not s.false(nr.get('continuing_Q')):
                        uncertain=uncertain or pd.isna(nr.get('continuing_Q')) or not s.true(nr.get('cp_trace_known')) or pd.isna(nr.get('cp_id'))
                    if str(nr['i_epoch'])!=str(attempts[0].get('i_epoch')):uncertain=True
                    if uncertain:
                        native_unknown=True
                        decisions.append(dict(day=d,campaign=campaign,arm=arm,event_id=nr['event_id'],reason='NATIVE_RECOVERY_OPPORTUNITY_UNKNOWN'))
                    else:
                        options,checks,reason=native.prepare(nr,arm_id)
                        decisions.append(dict(day=d,campaign=campaign,arm=arm,event_id=nr['event_id'],reason=reason,role_checks=json.dumps(checks,default=str)))
                        if 'UNKNOWN' in reason:native_unknown=True
                        if options and (not s.true(nr.get('PVR_known')) or not s.finite(nr.get('PVR_score'))):
                            native_unknown=True;decisions[-1]['reason']='PVR_UNKNOWN_OR_UNREADABLE_NO_ROUTE';options=[]
                        if options:
                            assert nr['event_id'] not in consumed;consumed.add(nr['event_id'])
                            nr['i_floor_original']=nr['i_floor'];nr['i_floor']=options[0]['floor']
                            start(nr,options[0]['check'],d,options)
            before=sum((st.get('dividend_paid',D(0)) for st in attempts),D(0));s.pay_day(arm_id,d)
            paid=sum((st.get('dividend_paid',D(0)) for st in attempts),D(0))-before
            if paid:cash+=paid;ledger.append(dict(day=d,event='PAY_CLOSE',delta=paid,available_cash=cash,available_from=s.cal[k+1] if k+1<len(s.cal) else None))
            current=states.get(sid);recv=sum((x.get('receivable',D(0)) for x in attempts),D(0))
            if initial_cost is not None:
                equity=cash+recv
                if current and current['state']=='HELD':
                    holding_days+=1;capital_days+=current['spent']
                    if current.get('last_known_mark_day')==d:
                        px=D(str(current['last_raw_close']))*(1-s.SLIP);_,fs,pa=s.getmeta(sid,d)
                        equity+=D(current['core'])*px-s.fee(current['core'],px,fs,'sell',pa)
                    else:mark_unknown=True
                elif current and current['state']=='UNKNOWN':mark_unknown=True
                if not mark_unknown:
                    peak=max(initial_cost if peak is None else peak,equity);maxdd=max(maxdd,peak-equity)
                    if peak>0:maxdd_pct=max(maxdd_pct,(peak-equity)/peak)
            # Registered claims exist before EX and prevent early termination until PAY.
            active=states.get(sid,{}).get('state') in ['BUY_PENDING','HELD']
            settled=all(c['settled'] for c in s.claims.values())
            if not active and settled and (arm not in ['C','D'] or closed_root or root_unknown or initial_cost is None):break
        for st in attempts:
            if '_output_index' not in st:
                s.record(st,'OPEN_CENSORED_AT_2026_06_30' if st['state']=='HELD' else 'BUY_PENDING_CENSORED_AT_DATA_END',END)
        s.finalize(attempts)
        reports=[]
        for st in attempts:
            rr=dict(s.rounds[st['_output_index']]);rr.update(campaign_key=campaign,policy_arm=arm,baseline_round_id=rid,trial=st['trial'],down_day=st['down_day'],confirmed_day=st['confirmed_day']);reasons=coverage(s,st,rr);rr['coverage_reasons']=';'.join(reasons)
            rr['evidence_usable_closed']=rr['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND' and not reasons;reports.append(rr)
        filled=[r for r in reports if r['entry_status']=='CONDITIONAL_OPEN_PROXY'];execution_closed=bool(filled) and all(r['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND' or 'NOFILL' in r['status'] for r in reports)
        coverage_known=all(not r['coverage_reasons'] for r in filled)
        receivable=sum((st.get('receivable',D(0)) for st in attempts),D(0));net=sum((st.get('cash',D(0))+st.get('receivable',D(0)) for st in attempts),D(0))
        complete=execution_closed and coverage_known and root_known and (arm not in ['C','D'] or (closed_root and not root_unknown and not native_unknown and not recovery_unknown))
        out=dict(baseline_round_id=rid,window=window,sid=sid,arm=arm,campaign_key=campaign,root_known=root_known,root_unknown=root_unknown,root_closed=closed_root,native_unknown=native_unknown,recovery_opportunity_unknown=recovery_unknown or native_unknown,holding_close_days=holding_days,capital_close_days=float(capital_days),max_drawdown_known_prefix=float(maxdd),max_drawdown_fraction_known_prefix=float(maxdd_pct),mark_path_unknown=mark_unknown,permits=1,attempts=len(attempts),filled_attempts=len(filled),initial_cost=float(initial_cost) if initial_cost is not None else None,cash=float(cash),receivable=float(receivable),receivable_pending=receivable>0,cash_settled=execution_closed and receivable==0,net_basis='ACCRUAL_NET80',net=float(net) if execution_closed else None,evidence_usable_closed=complete,execution_closed=execution_closed,coverage_known=coverage_known,total_fees=sum(r.get('all_fees',0) for r in reports),baseline_usable=baseline['evidence_usable_closed'],baseline_status=baseline['status'])
        if execution_closed and initial_cost is not None:assert abs(float(cash+receivable-initial_cost-net))<1e-7,(rid,arm,'campaign cash reconciliation')
        return dict(campaign=out,attempts=reports,actions=list(s.actions),native_consumptions=list(native.g['consumptions']) if native is not None else [],native_role_attempts=list(native.g['role_attempts']) if native is not None else [],claims=list(s.claims.values()),cash_ledger=[dict(x,campaign_key=campaign,policy_arm=arm,baseline_round_id=rid) for x in ledger],invitation_decisions=decisions)
    finally:
        if native is not None:native.restore()
        s.size=original_size
        for name,old in maps.items():setattr(s,name,old)
