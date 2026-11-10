"""Pure helpers for the root-frozen v3 evaluation; no I/O/model/ranking at import."""
import numpy as np
import pandas as pd

PATH_VALUES=[f'{kind}{h}_{tag}_log' for h in (5,20) for tag in ('abs','rel') for kind in ('final','mfe','mae')]
TAIL_TARGETS={'REL_MFE20_PRIMARY':'mfe20_rel_log','ABS_MFE20_DIAGNOSTIC':'mfe20_abs_log','REL_FINAL20_DIAGNOSTIC':'final20_rel_log'}

def study_window(date):
    return '2022_2023' if date[:4]<='2023' else '2024' if date[:4]=='2024' else '2025_2026H1'

def nullable_bool(s):
    return s.astype('boolean')

def future_tail_columns(frame, reference_column='C_t_member'):
    """Evaluation only: same T-reference and positive 90-midpercentile, preserve ties."""
    out=frame[['date','sector_id_static']].copy()
    reference=frame[reference_column].eq(True)
    for name,value in TAIL_TARGETS.items():
        known=reference & frame.label_valid20.eq(True) & np.isfinite(frame[value])
        pct=pd.Series(np.nan,index=frame.index,dtype=float)
        for _,g in frame[known].groupby('date',sort=False):
            pct.loc[g.index]=(g[value].rank(method='average')-.5)/len(g)
        out[name+'_reference_known']=known
        out[name+'_midpercentile']=pct
        out[name+'_tail']=known & pct.ge(.90) & frame[value].gt(0)
    return out

def distribution(values):
    v=pd.Series(values,dtype=float).dropna()
    return {'known':len(v),'mean':float(v.mean()) if len(v) else np.nan,
            'median':float(v.median()) if len(v) else np.nan,
            'p10':float(v.quantile(.1)) if len(v) else np.nan,
            'p90':float(v.quantile(.9)) if len(v) else np.nan}

def list_pair(previous,current):
    """Actual snapshot turnover; unknown lists never become empty sets."""
    if previous is None or current is None:
        return dict(pair_known=False,N_old=None,N_new=None,entered=None,left=None,
                    intersection=None,union=None,symmetric_turnover=np.nan,jaccard=np.nan)
    a,b=set(previous),set(current);inter=len(a&b);union=len(a|b);total=len(a)+len(b)
    return dict(pair_known=True,N_old=len(a),N_new=len(b),entered=len(b-a),left=len(a-b),
                intersection=inter,union=union,
                symmetric_turnover=len(a^b)/total if total else np.nan,
                jaccard=inter/union if union else np.nan)

def true_weekends(calendar):
    """Use the full CSI calendar, never the administration-window's last Tuesday."""
    dates=pd.DatetimeIndex(calendar);iso=dates.isocalendar()
    t=pd.DataFrame({'date':dates,'ISO_year':iso.year.to_numpy(),'ISO_week':iso.week.to_numpy()})
    return t.groupby(['ISO_year','ISO_week'],as_index=False).date.max()

def observed_true_runs(frame,state_column,window_column='study_window'):
    """True runs by industry/window; unknown is a censoring stop, not an exit."""
    rows=[]
    for (sector,win),g in frame.groupby(['sector_id_static',window_column],sort=True):
        g=g.sort_values('date');dates=g.date.to_numpy();st=g[state_column].astype('Float64').to_numpy(dtype=float,na_value=np.nan)
        begin=None;left=None;reason=None
        def emit(end,exitdate,right,stop):
            rows.append(dict(sector_id_static=sector,study_window=win,start=dates[begin],end_last_true=dates[end],
                             exit_date_known_false=exitdate,length=int(end-begin+1),left_censored=bool(left),
                             right_censored=bool(right),start_reason=reason,stop_reason=stop,
                             complete_uncensored=bool(not left and not right)))
        for j,v in enumerate(st):
            if v==1:
                if begin is None:
                    begin=j;left=j==0 or np.isnan(st[j-1]);reason='WINDOW_HEAD_TRUE' if j==0 else 'AFTER_UNKNOWN' if np.isnan(st[j-1]) else 'KNOWN_FALSE_TO_TRUE'
            elif begin is not None:
                if v==0:emit(j-1,dates[j],False,'KNOWN_TRUE_TO_FALSE')
                else:emit(j-1,None,True,'INPUT_UNKNOWN_NOT_ECONOMIC_EXIT')
                begin=None
        if begin is not None:emit(len(st)-1,None,True,'WINDOW_END_TRUE')
    return pd.DataFrame(rows)

def daily_tail_rows(frame,methods,tail_frame):
    rows=[]
    z=frame.join(tail_frame.drop(columns=['date','sector_id_static']))
    for date,g in z.groupby('date',sort=True):
        for method,col in methods.items():
            selected=g[col].eq(True);known_list=g[col].notna().any()
            for target,value in TAIL_TARGETS.items():
                tail=g[target+'_tail'];tailN=int(tail.sum());hits=int((selected&tail).sum())
                selected_label=selected & g.label_valid20.eq(True) & np.isfinite(g[value])
                denominator=int(selected_label.sum())
                rows.append(dict(date=date,method=method,target=target,selection_day_known=bool(known_list),
                                 selected=int(selected.sum()),selected_label_known=denominator,
                                 tail_reference_label_known=int(g[target+'_reference_known'].sum()),tailN=tailN,tail_empty=tailN==0,hits=hits,
                                 coverage=hits/tailN if tailN and known_list else np.nan,
                                 precision=hits/denominator if denominator and known_list else np.nan))
    return pd.DataFrame(rows)
