"""Read saved CUSUM outputs and original source samples, no sequence/model imports."""
from pathlib import Path
import hashlib,json,math
from collections import Counter
from statistics import median
import pandas as pd

P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;D=P/'run_v1'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(x):return x is not None and not pd.isna(x) and math.isfinite(float(x))
def eq(a,b):return a==b or finite(a) and finite(b) and abs(a-b)<=1e-12*max(1,abs(a),abs(b))
r=load(D/'RUN_RECEIPT.json');facts=load(D/'FIRST_CROSS_CASE_FACTS.json');summary={x['sid']:x for x in load(D/'SUMMARY.json')}
bindings={};sources=r['source_sha256']
for path,h in sources.items():assert sha(path)==h,path
case_source={};records=[];totals=Counter()
for path in sorted(D.glob('*_CUSUM_DAILY.parquet')):
    d=pd.read_parquet(path);sid=d.sid.iloc[0];s=summary[sid]
    assert len(d)==s['rows'] and d.D_status.value_counts().to_dict()==s['status_counts']
    # Locate the native file by symbol, then its matching price path from the frozen manifest.
    sm=load('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    m=next(x for x in sm if x['symbol']==sid)
    pp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
    fp=m['refs']['facts'];assert pp in sources and fp in sources
    price=pd.read_parquet(pp).loc[d.index];native=pd.read_parquet(fp).reindex(d.index)
    rawI=pd.to_numeric(d.original_native_i_target,errors='coerce');nativeI=pd.to_numeric(native.i_target,errors='coerce')
    assert (rawI.eq(nativeI)|(rawI.isna()&nativeI.isna())).all()
    for j,(_,x) in enumerate(d.iterrows()):
        if finite(x.D):
            if x.cycle_event=='I_CYCLE_START_D0':
                assert x.D==0 and x.native_i_target==1 and j>0 and d.iloc[j-1].native_i_target==0
            else:
                assert finite(x.D_before) and finite(x.r) and finite(x.s63) and x.s63>1e-8
                expected=max(0.,float(x.D_before)-float(x.r)/float(x.s63)-.25)
                assert eq(expected,x.D)
            assert bool(x.level_ge3)==(x.D>=3)
            assert bool(x.active_level_warning)==(x.native_i_target==1 and x.D>=3)
        if x.native_i_target!=1:assert not x.active_level_warning and not x.active_cross_warning
        if x.cycle_event=='I_CYCLE_END_CLOSE_INCLUDED':assert x.native_i_target==0 and pd.notna(x.cycle_id)
    for _,g in d.dropna(subset=['cycle_id']).groupby('cycle_id',sort=False):
        missing=g.D_status.eq('UNKNOWN')
        if missing.any():assert g.loc[missing.idxmax():,'D'].isna().all()
    vals={'sid':sid,'rows':len(d),'known':int(d.D_status.eq('KNOWN').sum()),'unknown':int(d.D_status.eq('UNKNOWN').sum()),
       'source_changed':int(d.source_changed.sum()),'source_start':int(d.start_reason.eq('NEW_SOURCE_CONFIRMED_I_ON').sum()),
       'left_censored_cycles':int(d.cycle_event.eq('LEFT_CENSORED_I_ON').sum()),
       'low_scale_rows':int(d.scale_status.eq('LOW_SCALE_GUARD').sum())}
    records.append(vals);totals.update({k:vals[k] for k in ['rows','known','unknown','source_changed','source_start','left_censored_cycles','low_scale_rows']})
    bindings[str(path)]=sha(path)
    case_source[sid]=(price,d,pp,fp)

checks=[]
for item in facts:
    sid=item['sid'];day=item['first_active_cross'];price,d,pp,fp=case_source[sid]
    t=pd.Timestamp(day);i=price.index.get_loc(t);past=price.close.iloc[i-64:i].astype(float).tolist()
    assert len(past)==64 and d.iloc[i-64:i].close_valid.all()
    prior_abs=[abs(math.log(b/a)) for a,b in zip(past[:-1],past[1:])]
    sigma=1.4826*median(prior_abs);ret=math.log(float(price.close.iloc[i])/float(price.close.iloc[i-1]))
    x=d.loc[t];assert eq(ret,x.r) and eq(sigma,x.s63)
    prev=d.iloc[i-1];assert prev.cycle_id==x.cycle_id and eq(prev.D,x.D_before)
    step=-ret/sigma-.25;now=max(0.,float(prev.D)+step)
    assert eq(now,x.D) and eq(now,item['D']) and x.active_cross_warning
    assert price.close.iloc[i]==item['C'] and price.raw_close.iloc[i]==item['raw_C']
    checks.append({'sid':sid,'anchor':item['anchor'],'first_cross':day,'r_original_price':ret,'prior63_s_original_price':sigma,
       'D_before':float(prev.D),'D':now,'current_step':step,'single_bar_without_memory':max(0.,step),
       'memory_required_for_this_cross':step<3,'old_CP_P':item['CP_oldP'],'C':item['C'],
       'already_at_or_below_old_CP':item['C']<=item['CP_oldP'],
       'old_CP_exit':item['oldCP_exit'],'warning_not_order_or_quote_realizability':True})

runtime_sources={
 'J':'/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py',
 'N':'/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py',
 'Facts':'/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py',
 'Iproject':'/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py'}
out={'status':'PASS_FIXED_FIVE_SOURCE_CUSUM_OBSERVATION_WITH_LIMITS_BROAD_SOURCE_GUARD_PENDING',
 'scope':'Full helper/driver static read; all saved five-source known-step/poison/active-warning invariants, source-native-I identity, three original-price r/s first-cross checks (four CP anchors). No candidate calculate/CP/E0/account execution.',
 'five_sources':records,'totals':dict(totals),'first_cross_checks':checks,
 'runtime_lineage':{'source_sha256':{p:sha(p) for p in runtime_sources.values()},
   'J_lines216_218':'Watch key is (bool(row.i_target), int(row.segment_id)); changes on both I transitions and source changes.',
   'N_lines116_118':'Calls J.Runner.planning before priority reordering.',
   'Facts_lines24_26':'As-of <=day row, not guaranteed fresh daily evidence.',
   'warning':'CUSUM uses strict exact known native-I transitions; do not copy bool(NaN), CP epochs, stock_structure or funded core consumption as reset.'},
 'source_sha256_verified':sources,'saved_output_bindings':bindings,
 'source_guard_issue':'v1 special pending source start can reset a newly left-censored UNKNOWN cycle on following valid I1; fixed five sources have zero source changes, so existing results unaffected. Await v2 static guard for broad source gate.',
 'limits':['No economic, order, fill, ACK or return evidence','Low-scale, source-change and initial-left-censored branches have zero real occurrences in these five sources',
   'Full market-session gaps unverified; actual clock is observed comparable source rows','All known-step audit uses saved previous D; no independent entire CUSUM recursion',
   'CP-line values are saved conditional original-CP shadows, not actual No60 layer exits'],
 'new_cusum_sequence_runs_by_reviewer':0,'new_accounts':0,'parameter_searches':0}
(O/'FIVE_SOURCE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':out['status'],'totals':dict(totals),'first_cross_checks':checks},ensure_ascii=False))
