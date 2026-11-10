"""Five fixed sources only. Observations and cached CP-line expansion, no model."""
from pathlib import Path
import sys,json,hashlib,time
from collections import Counter
import pandas as pd

HERE=Path(__file__).resolve().parent;SHARED=HERE.parent/'channel_atr_fsm_v1'
sys.path.insert(0,str(SHARED))
import engine,runner
import cusum

SIDS=['000620.SZ','002583.SZ','300085.SZ','603061.SH','300623.SZ']
CASE_ANCHORS={'000620.SZ':['2022-01-07'],'002583.SZ':['2024-09-20'],'300085.SZ':['2024-09-12','2024-10-09']}
WINDOWS={'000620.SZ':('2022-01-01','2022-02-08'),'002583.SZ':('2024-09-01','2024-11-29'),'300085.SZ':('2024-09-01','2024-11-29')}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(engine.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def original_CP_line(pair,price,f,native,cp):
    """Cached candidate/Ifloor monotone line only; endpoint must equal saved control.
    No CP formula, E0/I model, new protection rule, fill, or account is calculated.
    """
    n=native.reindex(price.index);c=cp.reindex(price.index);P=float(pair['P0']);rows=[]
    ref=pair['CP'];exit_day=None;exit_line=None
    for t in price.loc[pair['anchor_day']:pair['common_end_day']].index:
        day=str(t.date())
        if day==pair['anchor_day']:continue
        if f.at[t,'source_key']!=f.at[pd.Timestamp(pair['anchor_day']),'source_key'] or not f.at[t,'close_valid'] or engine.bit(n.at[t,'i_target']) is None:break
        C=float(price.at[t,'close']);old=P;proposal=None;reason=None
        if engine.bit(n.at[t,'i_target'])==0:reason='ORIGINAL_I_INVALID';exit_line=P
        elif engine.ge(P,C):reason='EXIT_STORED_LINE';exit_line=P
        elif not f.at[t,'valid_bar'] or not engine.positive(n.at[t,'i_floor']):break
        else:
            proposal=max(P,float(n.at[t,'i_floor']))
            if engine.flag(c.at[t,'receipt']) is True:
                if not engine.positive(c.at[t,'candidate']):break
                proposal=max(proposal,float(c.at[t,'candidate']))
            if engine.ge(proposal,C):reason='EXIT_NEW_CP_OR_I_PROPOSAL';exit_line=proposal
            else:P=proposal
        rows.append(dict(day=day,C=C,raw_C=price.at[t,'raw_close'],P_old=old,I_floor=n.at[t,'i_floor'],
            CP_receipt=engine.flag(c.at[t,'receipt']),CP_candidate=c.at[t,'candidate'],proposal_after_old_line_check=proposal,
            P_next=None if reason else P,exit_reason=reason,held_condition='ORIGINAL_CP_ANCHOR_SHADOW_NOT_ACTUAL_POSITION'))
        if reason:exit_day=day;break
    assert exit_day==ref['exit_day'],(pair['sid'],pair['anchor_day'],exit_day,ref['exit_day'])
    if exit_day:assert exit_line==ref['exit_line']
    return rows

def main():
    out=HERE/'run_v1';out.mkdir(exist_ok=False);start=time.monotonic()
    sources={str(p):sha(p) for p in [HERE/'cusum.py',Path(__file__),SHARED/'engine.py',SHARED/'runner.py',runner.MANIFEST]}
    metas={r['symbol']:r for r in json.loads(runner.MANIFEST.read_text())};summary=[];case_reports=[]
    for sid in SIDS:
        data,bind=runner.read_symbol(metas[sid]);sources.update(bind);p=data['price'];f=engine.features(p)
        daily=cusum.calculate(sid,p,f,data['facts'])
        ev=data['events'].reindex(p.index);cp=data['CP1'].reindex(p.index)
        daily['original_E0_event']=ev.event;daily['original_CP_receipt']=[engine.flag(x) for x in cp.receipt]
        daily['original_CP_candidate']=cp.candidate
        daily.to_parquet(out/(sid.replace('.','_')+'_CUSUM_DAILY.parquet'))
        summary.append(dict(sid=sid,rows=len(daily),status_counts=dict(Counter(daily.D_status)),
            evidenced_cycle_starts=int(daily.cycle_event.eq('I_CYCLE_START_D0').sum()),
            leftcensored_cycles=int(daily.cycle_event.eq('LEFT_CENSORED_I_ON').sum()),
            all_cycle_crosses=int(daily.threshold_cross.sum()),active_crosses=int(daily.active_cross_warning.sum()),
            active_level_days=int(daily.active_level_warning.sum()),scale_guard_rows=int(daily.scale_status.eq('LOW_SCALE_GUARD').sum())))
        if sid in CASE_ANCHORS:
            pairfile=SHARED/'smoke_v1'/sid.replace('.','_')/'CP_ANCHOR_PAIRS.json';sources[str(pairfile)]=sha(pairfile)
            pairs=json.loads(pairfile.read_text());w0,w1=WINDOWS[sid]
            save(out/(sid.replace('.','_')+'_CASE_WINDOW.json'),daily.loc[w0:w1].to_dict('records'))
            for anchor in CASE_ANCHORS[sid]:
                pair=next(x for x in pairs if x['anchor_day']==anchor);lines=original_CP_line(pair,p,f,data['facts'],data['CP1'])
                linemap={x['day']:x for x in lines};cycleid=daily.at[pd.Timestamp(anchor),'cycle_id']
                cycle=daily.loc[daily.cycle_id.eq(cycleid)]
                crossed=cycle.loc[cycle.active_cross_warning]
                first=None if crossed.empty else crossed.iloc[0].to_dict()
                rows=[]
                for row in daily.loc[anchor:w1].to_dict('records'):
                    line=linemap.get(row['day']);rows.append(dict(row,CP_line=line,
                        original_CP_already_exited=bool(pair['CP']['exit_day'] and row['day']>pair['CP']['exit_day'])))
                reports=dict(sid=sid,anchor_day=anchor,anchor_cycle_id=cycleid,original_CP_control=pair['CP'],
                    first_active_cross_same_native_I_cycle=first,
                    E0_down_same_native_I_cycle=cycle.loc[cycle.original_E0_event.eq(-1),'day'].tolist(),
                    original_CP_daily_line_endpoint_matches_saved=True,observations=rows,
                    execution_unknown=True,new_account=False,new_order=False,new_return=False)
                case_reports.append(reports)
    for r in case_reports:save(out/(r['sid'].replace('.','_')+'_'+r['anchor_day']+'_CP_CUSUM.json'),r)
    save(out/'SUMMARY.json',summary)
    assert all(sha(p)==v for p,v in sources.items())
    save(out/'RUN_RECEIPT.json',dict(status='FIXED_FIVE_SOURCE_OBSERVATION_COMPLETE',source_sha256=sources,
        constants=dict(window63=63,MADfactor=1.4826,scale_guard=1e-8,drift=.25,warning_level=3),
        source_clock='same-source strict comparable adjusted CLOSE; missing/invalid row breaks contiguous returns',
        scale_excludes_current_r=True,CP_resets_D=False,I_cycle_start_close_D0=True,
        new_accounts=0,new_orders=0,new_E0_I_CP_model_runs=0,new_protection_FSM_runs=0,
        full_calendar_gap_check='NOT_VERIFIED',elapsed_seconds=time.monotonic()-start))
    for r in case_reports:
        x=r['first_active_cross_same_native_I_cycle'];print(json.dumps(dict(sid=r['sid'],anchor=r['anchor_day'],firstcross=None if x is None else {k:x[k] for k in ['day','C','raw_C','r','s63','D_before','D']},CPexit=r['original_CP_control']['exit_day'],E0down=r['E0_down_same_native_I_cycle']),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
