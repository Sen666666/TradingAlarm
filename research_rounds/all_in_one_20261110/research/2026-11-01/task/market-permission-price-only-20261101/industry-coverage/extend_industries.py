"""All-node input inventory and one additive F1 pass; no account dependencies."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
B = O.parent
RUN = O / 'run-v1'
F = B / 'v2-frozen'
IP = B / 'input-preparation/prepared-v2'
OLD = B / 'historical-shadow/run-v1'
R = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
CORE = '962275bd41b5c7bbc062a1191780a6b6a9c616f8d3097ea669b602eabbc9ac59'
CONTRACT = 'c3914aed1896563253961ea40d6065614a115cef21e13a93e1e74ad71779c54a'
CUTS = ['2023-01-19', '2024-09-23', '2026-05-07']
WINDOWS = {
    'year2022': ['2022-01-01', '2022-12-31'],
    'year2023': ['2023-01-01', '2023-12-31'],
    'after_global_end_2023': ['2023-03-15', '2023-12-31'],
    'themes2026': ['2026-04-30', '2026-06-30'],
    'old924': ['2024-09-24', '2024-12-31'],
}
REUSE = {'URFI881121': 'NATIVE1709_semiconductor', 'URFI881172': 'NATIVE1709_electronic_chemicals'}
FOCUS = ['URFI881129','URFI881162','URFI881164','URFI881275','URFI881274','URFI881130','URFI881272','URFI881271']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def clean(x):
    if isinstance(x, dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)): return [clean(v) for v in x]
    if isinstance(x, pd.Timestamp): return str(x.date())
    if isinstance(x, (float, np.floating)): return float(x) if math.isfinite(x) else None
    if hasattr(x,'item'): return clean(x.item())
    return x


def save(name,x):
    p=RUN/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def number(x):
    return float(x) if pd.notna(x) and math.isfinite(x) else None


def snapshot(path):
    return {str(p.relative_to(path)):sha(p) for p in path.rglob('*') if p.is_file()}


def frame_prefix_gate(z, source, primary, coverage, sector):
    raw=pd.read_parquet(source)
    f=pd.read_parquet(primary,columns=['close','segment_id']) if primary else raw[['close','segment_id']]
    records=[]
    for cut in CUTS:
        r=raw.loc[:cut].copy();p=f.loc[:cut].copy()
        mask=(r.price_eligible&r.observed_bar&~r.synthetic_event_bar).reindex(p.index).fillna(False)
        price=pd.DataFrame(dict(price_input=p.close.where(mask),price_observed=mask,
                                 price_source_segment_id=p.segment_id),index=p.index)
        c=coverage.xs(sector,level='sector').loc[:cut]
        short=price.join(c,how='outer').sort_index()
        short['price_observed']=short.price_observed.fillna(False).astype(bool)
        cols=['price_input','price_observed','price_source_segment_id','breadth','ready_m','positive_m','unknown_m']
        pd.testing.assert_frame_equal(short[cols],z.loc[:cut,cols],check_exact=True)
        records.append(dict(cutoff=cut,exact=True,observations=len(short)))
    return records


def run_node(core,node,z):
    state=core.State(scope=node['scope'])
    daily=[];segment=0;last_permit=False
    for day,row in z.iterrows():
        if pd.notna(row.price_source_segment_id):segment=int(row.price_source_segment_id)
        source=core.Source(node['domain']+'-fixed-research-roster','index-'+node['sector'],
                           'original-signed-m21/research-industry-min5','original-source-segment-'+str(segment))
        close=number(row.price_input);breadth=number(row.breadth)
        state,d=core.step(state,core.Observation(str(day.date()),source,close,breadth))
        change=('permission_granted' if d.permit_next_open else 'permission_revoked') if d.permit_next_open!=last_permit else None
        daily.append(dict(day=str(day.date()),stream=node['scope'],close=close,breadth=breadth,
                          mode=d.mode,effective_status=d.effective_status,permit_next_open=d.permit_next_open,
                          permission_change=change,original_break=d.original_break,line_used=d.line_used,next_line=d.next_line,
                          prior_scale=d.scale_before_close,anchor=state.anchor,frontier=state.frontier,credit=state.credit,
                          frozen_segment_scale=state.scale,starts=state.starts,repairs=state.repairs,failures=state.failures,
                          events=list(d.events),unknown=list(d.unknown),ready_m=number(row.ready_m),positive_m=number(row.positive_m),
                          source_segment=segment,pending_failure_at=state.pending_price_failure.at if state.pending_price_failure else None))
        last_permit=d.permit_next_open
    df=pd.DataFrame(daily).set_index('day')
    (RUN/'checkpoints'/ (node['node_id']+'.json')).write_text(core.dumps(state)+'\n')
    return df


def attempts(node,df):
    result=[];current=None
    for i,(day,r) in enumerate(df.iterrows()):
        events=list(r.events)
        start=next((e for e in ['break_started','repair_restored'] if e in events),None)
        if start:
            assert current is None
            current=dict(node_id=node['node_id'],domain=node['domain'],sector=node['sector'],name=node['name'],
                         start_day=day,start_reason=start,start_close=number(r.close),start_breadth=number(r.breadth),
                         start_observation=i,price_advance_count=0)
        if current is not None:
            current['price_advance_count']+=int('price_advance' in events)
            fail=next((e for e in events if e.startswith('price_failure_')),None)
            if fail or 'source_changed_context_ended' in events:
                current.update(end_day=day,end_reason=fail or 'source_boundary',failure_close=number(r.close),
                               failure_breadth=number(r.breadth),observations=i-current['start_observation']+1,
                               no_advance_failure=bool(fail and current['price_advance_count']==0),
                               end_price_not_above_start=bool(fail and r.close<=current['start_close']),censored=False)
                result.append(current);current=None
    if current is not None:
        current.update(end_day=None,end_reason='OPEN_AT_CUTOFF',failure_close=None,failure_breadth=None,
                       observations=len(df)-current['start_observation'],no_advance_failure=False,
                       end_price_not_above_start=None,censored=True)
        result.append(current)
    return result


def metric(node,df,window,a):
    begin,end=WINDOWS[window];w=df.loc[begin:end]
    if w.empty:
        return dict(node_id=node['node_id'],domain=node['domain'],sector=node['sector'],name=node['name'],window=window,status='UNKNOWN_NO_WINDOW_ROWS')
    joint=w.close.notna()&w.breadth.notna()&w.prior_scale.notna()
    positive=joint&w.breadth.gt(.6)
    permits=w.index[w.permit_next_open]
    refs=w.index[positive]
    ref=refs[0] if len(refs) else None
    after=[d for d in permits if ref is not None and d>=ref]
    lag=int(w.index.get_loc(after[0])-w.index.get_loc(ref)) if after else None
    before=df.loc[df.index<begin]
    ev=[e for x in w.events for e in list(x)]
    closed=[x for x in a if x['end_day'] is not None and begin<=x['end_day']<=end]
    status='READY' if int(joint.sum())==len(w) else 'PARTIAL_UNKNOWN'
    if not w.breadth.notna().any():status='UNKNOWN_BREADTH_MIN5'
    if not w.close.notna().any():status='UNKNOWN_PRICE'
    return dict(node_id=node['node_id'],domain=node['domain'],sector=node['sector'],name=node['name'],window=window,
                begin=begin,end=end,status=status,observations=len(w),joint_ready_observations=int(joint.sum()),
                price_unknown=int(w.close.isna().sum()),breadth_unknown=int(w.breadth.isna().sum()),
                prior_scale_unknown=int(w.prior_scale.isna().sum()),permitted_observations=int(w.permit_next_open.sum()),
                permit_over_all=float(w.permit_next_open.mean()),permit_over_joint=float(w.loc[joint,'permit_next_open'].mean()) if joint.any() else None,
                first_permit=permits[0] if len(permits) else None,delay_from_window_first_observation=int(w.index.get_loc(permits[0])) if len(permits) else None,
                first_joint_positive_breadth=ref,first_permit_after_positive_reference=after[0] if after else None,
                positive_reference_delay_observations=lag,positive_reference_status='NO_REFERENCE' if ref is None else ('NOT_PERMITTED_IN_WINDOW' if not after else 'OBSERVED'),
                carried_status=before.iloc[-1].effective_status if len(before) else 'NO_PRIOR_OBSERVATION',
                carried_permit=bool(before.iloc[-1].permit_next_open) if len(before) else False,
                BREAK_starts=ev.count('break_started'),repairs=ev.count('repair_restored'),
                price_failures=sum(e.startswith('price_failure_') for e in ev),
                ENDED_events=sum(e in ['price_failure_ended','repair_breadth_failure_ended','pending_failure_classified_ended','source_changed_context_ended'] for e in ev),
                permission_grants=int(w.permission_change.eq('permission_granted').sum()),
                permission_withdrawals=int(w.permission_change.eq('permission_revoked').sum()),
                no_advance_failures=sum(x['no_advance_failure'] for x in closed),
                index_price_observations_before_window=int(before.close.notna().sum()),
                dates_BREAK=[d for d,r in w.iterrows() if 'break_started' in r.events],
                dates_repair=[d for d,r in w.iterrows() if 'repair_restored' in r.events],
                dates_failure=[d for d,r in w.iterrows() if any(e.startswith('price_failure_') for e in r.events)])


def main():
    RUN.mkdir(exist_ok=False)
    for d in ['inputs','daily','checkpoints']:(RUN/d).mkdir()
    frozen=snapshot(F);original=snapshot(OLD);inputs=snapshot(IP)
    assert sha(F/'signal_core.py')==CORE and sha(F/'CONTRACT.md')==CONTRACT
    for root in [F,OLD,IP]:
        man=json.loads((root/'ARTIFACT_SHA256.json').read_text())
        assert all(sha(root/p)==h for p,h in man.items())
    m=json.loads((W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json').read_text())
    meta=json.loads((R/'a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text())
    names={v['sector_id']:v['industry'] for v in meta.values() if v.get('sector_id')}
    old_roster=pd.read_csv(R/'tech-compound-design-20261026/proposed-pool.csv')
    helper=load_module('bounded_original_input_helper',B/'input-preparation/prepare_inputs.py')
    helper.RUN=RUN/'inputs';helper.TARGETS=names
    covs={d:pd.read_parquet(IP/d/'all_industry_coverage.parquet') for d in ['NATIVE1709','OLD407']}
    old_snapshot=Path(json.loads((R/'pvr-act-comparison-20261027/input.json').read_text())['snapshot']['path'])
    nodes=[];prefix_records=[]
    for domain,entries in [('NATIVE1709',sorted(m,key=lambda x:x['series'])),
                           ('OLD407',[dict(series=s) for s in sorted(old_roster.sector_id.unique())])]:
        for entry in entries:
            sector=entry['series'];node=dict(node_id=domain+'_'+sector,domain=domain,sector=sector,name=names[sector],
                scope=REUSE.get(sector) if domain=='NATIVE1709' and sector in REUSE else domain+'_industry_'+sector,
                reuse=domain=='NATIVE1709' and sector in REUSE)
            try:
                if domain=='NATIVE1709':
                    source=next(Path(p) for p in entry['source_sha256'] if p.endswith('/signal.parquet'))
                    primary=Path(entry['refs']['CP1_input'])
                    z,report=helper.industry_output(domain,sector,covs[domain],source,
                       (primary,entry['output_sha256'][str(primary)]),entry['source_sha256'][str(source)])
                else:
                    source=old_snapshot/'signals'/(sector+'.parquet');primary=None
                    z,report=helper.industry_output(domain,sector,covs[domain],source)
                    baseline=helper.remember(R/f'tech-finite-compound-20261026/prepared-v2/signals/{sector}.parquet')
                    pd.testing.assert_frame_equal(pd.read_parquet(source).loc[:'2026-10-26',['close','segment_id']],
                                                  pd.read_parquet(baseline).loc[:'2026-10-26',['close','segment_id']],check_exact=True)
                node.update(status='INPUT_READY',price_source=str(source),primary_price_source=str(primary) if primary else str(source),
                            price_first=report['price_first'],price_last=report['price_last'],price_rows=report['price_rows'],
                            fixed_identities=report['original_fixed_identities'],source_roster=report['source_roster'],
                            price_segments=report['price_segments'],breadth_first=report['breadth_first'],
                            input_file=str(RUN/'inputs'/domain/('industry_'+sector+'.parquet')))
                prefix_records.append(dict(node_id=node['node_id'],checks=frame_prefix_gate(z,source,primary,covs[domain],sector)))
                if node['reuse']:
                    prior=pd.read_parquet(IP/domain/('industry_'+sector+'.parquet'))
                    pd.testing.assert_frame_equal(z[['price_input','breadth','ready_m','positive_m']],
                                                   prior[['price_input','breadth','ready_m','positive_m']],check_exact=True)
                node['warmup_before_2023_observed_prices']=int(z.loc[:'2022-12-31'].price_input.notna().sum())
                node['joint_known_days_2023']=int((z.loc['2023'].price_input.notna()&z.loc['2023'].breadth.notna()).sum())
            except Exception as exc:
                node.update(status='UNKNOWN_INPUT',reason=repr(exc),traceback=traceback.format_exc())
            nodes.append(node)
    assert len(nodes)==101
    save('ALL_NODES.json',nodes)
    save('INPUT_GATE.json',dict(passed=True,nodes=len(nodes),ready=sum(n['status']=='INPUT_READY' for n in nodes),
                              unknown=[n for n in nodes if n['status']!='INPUT_READY'],physical_price_input_prefixes=prefix_records,
                              breadth_counts_source='previous original-input gate verified all90/all11 daily counts at three physical raw cutoffs',
                              source_sha256=helper.SOURCES,index_price_not_full_index_breadth=True))
    save('SHADOW_FREEZE.json',dict(core_sha256=CORE,contract_sha256=CONTRACT,protocol_sha256=sha(O/'PROTOCOL.md'),runner_sha256=sha(Path(__file__)),
                                  windows=WINDOWS,focus_2023=FOCUS,all_native_nodes=90,all_old_nodes=11,
                                  reused_native_streams=REUSE,scope='99 additive streams maximum; original four unchanged',
                                  initial_state='WAIT at complete source start; no case reset',pilot_nodes=3,pilot_projected_budget_seconds=120))
    core=load_module('frozen_F1_all_industries',F/'signal_core.py')
    metrics=[];all_attempts=[];runtime=[];new_count=0;pilot_start=time.monotonic()
    global2023=pd.read_parquet(OLD/'NATIVE1709_global_daily.parquet')
    local_global=[]
    for index,node in enumerate(nodes):
        if node['status']!='INPUT_READY':
            for window in (['old924'] if node['domain']=='OLD407' else [k for k in WINDOWS if k!='old924']):
                metrics.append(dict(node_id=node['node_id'],domain=node['domain'],sector=node['sector'],name=node['name'],window=window,status='UNKNOWN_INPUT',reason=node['reason']))
            continue
        t=time.monotonic()
        if node['reuse']:
            df=pd.read_parquet(OLD/(node['scope']+'_daily.parquet')).copy()
        else:
            end='2024-12-31' if node['domain']=='OLD407' else '2026-06-30'
            z=pd.read_parquet(node['input_file']).loc[:end]
            df=run_node(core,node,z);new_count+=1
        df['node_id']=node['node_id'];df['sector_name']=node['name']
        df.to_parquet(RUN/'daily'/(node['node_id']+'.parquet'))
        a=attempts(node,df);all_attempts.extend(a)
        for window in (['old924'] if node['domain']=='OLD407' else [k for k in WINDOWS if k!='old924']):
            metrics.append(metric(node,df,window,a))
        if node['domain']=='NATIVE1709':
            for day,r in df.loc['2023-03-15':'2023-12-31'].iterrows():
                g=global2023.loc[day]
                local_global.append(dict(node_id=node['node_id'],day=day,industry_permit=bool(r.permit_next_open),
                                          global_permit=bool(g.permit_next_open),local_while_global_withheld=bool(r.permit_next_open and not g.permit_next_open),
                                          joint_known=bool(pd.notna(r.close) and pd.notna(r.breadth) and pd.notna(r.prior_scale))))
        runtime.append(dict(node_id=node['node_id'],reused=node['reuse'],seconds=time.monotonic()-t,observations=len(df)))
        if new_count==3:
            projected=(time.monotonic()-pilot_start)/3*99
            save('RUNTIME_PILOT.json',dict(new_nodes=3,elapsed=time.monotonic()-pilot_start,projected_seconds=projected,budget_seconds=120))
            if projected>120:raise RuntimeError('additive all-industry pilot exceeded fixed120-second budget')
        if (index+1)%10==0:print('INDUSTRY_PROGRESS',index+1,'of',len(nodes),'new',new_count,flush=True)
    save('WINDOW_METRICS.json',metrics)
    simple=pd.DataFrame([{k:v for k,v in x.items() if not isinstance(v,list)} for x in metrics]);simple.to_csv(RUN/'WINDOW_METRICS.csv',index=False)
    save('ATTEMPTS.json',all_attempts)
    pd.DataFrame(all_attempts).to_csv(RUN/'ATTEMPTS.csv',index=False)
    neg=[x for x in all_attempts if x['no_advance_failure'] and
         ((x['domain']=='NATIVE1709' and '2022-01-01'<=x['end_day']<='2023-12-31') or
          (x['domain']=='OLD407' and '2024-09-24'<=x['end_day']<='2024-12-31'))]
    save('NEGATIVE_NO_ADVANCE_FAILURES.json',sorted(neg,key=lambda x:(x['end_day'],x['node_id'])))
    pd.DataFrame(local_global).to_parquet(RUN/'LOCAL_VS_GLOBAL_2023.parquet',index=False)
    save('RUNTIME.json',runtime)
    assert frozen==snapshot(F) and original==snapshot(OLD) and inputs==snapshot(IP)
    assert all(sha(p)==h for p,h in helper.SOURCES.items())
    save('COMPLETION.json',dict(passed=True,all_nodes=len(nodes),native=90,old=11,new_F1_streams=new_count,
                                reused_F1_streams=2,original_four_unchanged=True,frozen_core_contract_unchanged=True,
                                previous_input_package_unchanged=True,unknown_nodes=[n['node_id'] for n in nodes if n['status']!='INPUT_READY'],
                                observations=sum(x['observations'] for x in runtime),new_stream_observations=sum(x['observations'] for x in runtime if not x['reused']),
                                window_rows=len(metrics),attempts=len(all_attempts),negative_no_advance_failures=len(neg),
                                account_runs=0,new_downloads=0,parameter_changes=0,orders=0,
                                result_independent_review='pending'))
    save('ARTIFACT_SHA256.json',{str(p.relative_to(RUN)):sha(p) for p in sorted(RUN.rglob('*')) if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
    print('ALL_INDUSTRIES_COMPLETE',new_count,'new streams',len(metrics),'metric rows',flush=True)


if __name__=='__main__':
    try:main()
    except BaseException as e:
        if RUN.exists():save('ERROR.json',dict(reason=repr(e),traceback=traceback.format_exc()))
        raise
