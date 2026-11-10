"""Read-only ETA complete-account audit. Reuse audited ledger/fee kernels.

No native model, Account, Runner, indicator or provider import/initialization.
Only the data path/metadata alias of the prior BASELINE ledger audit changes;
new independent priority and original receipt/role-clock checks are below.
"""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,getcontext
import ast,bisect,gzip,hashlib,json,math,sys
import numpy as np
import pandas as pd
getcontext().prec=65
O=Path(__file__).resolve().parent;S=O.parent;P=S/'pvr_eta_v1';T=S.parent/'trend_exit_controls_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
CORE=T/'independent_review/audit_completed_accounts.py'
FEES=S.parent/'dec2022_authorization_v1/followup_robustness_v1/independent_review/audit_completed_robust_accounts.py'
SM={r['symbol']:r for r in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
FACT={};FSHA={};Z=D(0);provider=None
calendar=sorted(pd.read_csv(W/'mainline-absolute-Q4-20261031/recovery.csv',index_col=0).index.tolist());calindex={x:i for i,x in enumerate(calendar)}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    p=Path(p)
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:
        return [json.loads(l) for l in f] if '.jsonl' in p.name else json.load(f)
def extract(path,names,replace=None):
    src=Path(path).read_text();tree=ast.parse(src)
    for name in names:
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        code=ast.get_source_segment(src,node)
        for a,b in (replace or {}).get(name,[]):
            assert code.count(a)==1,(name,a,code.count(a));code=code.replace(a,b)
        exec(compile(code,str(path)+':auditor_readonly_reuse','exec'),globals())

replacements={'audit':[
    ("out=P/'runs'/arm/window","out=P/'runs'/window"),
    ("assert done['completed'];meta=", "assert done['completed'] and read(out/'TIMING.json')['completed'];meta="),
    ("meta['arm']==arm", "meta['policy']=='PVR_ETA_ORIGINAL_E21_MASS_SHARE_SLOT_ONLY_V1'"),
    ("baseline=read(P/'runs/BASELINE'/window/'RUN_METADATA.json')", "baseline=read(T/'runs/BASELINE'/window/'RUN_METADATA.json')"),
    ("meta['input_identity']", "meta['original_shared_input_identity']"),
    ("near(fees,d['fees_cny'],'all_daily_fees',C)","near(fees,d['fees_cny'],'all_daily_fees',C);near(n(1000000)+tradecash+divs-n(d['dividend_receivable']),d['available'],'all_available_cash_recognized_AR_bridge',C)")
]}
extract(CORE,['row','n','near','audit'],replacements);ledger_audit=audit
RULEFILE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');RULES=read(RULEFILE)
extract(FEES,['rule_at','fee_parts','independent_cost_check'])
RECEIPTS={};RECEIPT_PATHS={}
extract(FEES,['receipt_at'])


def priority(rows,values):
    base=sorted(rows,key=lambda r:r['original_H1_rank']);assert len({r['sid'] for r in base})==len(base)
    assert len({r['original_H1_rank'] for r in base})==len(base)
    ready=[r for r in base if values[r['sid']] is not None]
    ready.sort(key=lambda r:(-round(values[r['sid']],12),r['original_H1_rank']))
    it=iter(ready);new=[r if values[r['sid']] is None else next(it) for r in base]
    return {r['sid']:(k,base[k]['original_H1_rank']) for k,r in enumerate(new)}


def audit_eta(window):
    out=P/'runs'/window;done=read(out/'DONE.json');timing=read(out/'TIMING.json');assert done['completed'] and timing['completed']
    meta=read(out/'RUN_METADATA.json');manifest=Path(meta['selected_eta_manifest']);assert sha(manifest)==meta['selected_eta_manifest_sha256']
    assert meta['rank_log_PVR_field_semantics'].startswith('Raw eta')
    result=ledger_audit('BASELINE',window)
    book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');C=Counter(result['checks'])
    independent_cost_check(book,dict(cost_multiplier=1),C)
    decisions={d['at']:d for d in book['decisions']};byday=defaultdict(list)
    for x in read(out/'pair/rank-policy.jsonl.gz'):byday[x['day']].append(x)
    cache={};score_sources={};manifest_rows={r['symbol']:r for r in read(manifest)['entries']}
    def eta(sid,day):
        if sid not in cache:
            p=manifest.parent/'scores'/(sid+'.parquet');h=sha(p);assert h==manifest_rows[sid]['output_sha256'];score_sources[str(p)]=h
            q=pd.read_parquet(p,columns=['score']);cache[sid]={str(t.date()):float(v) for t,v in q.score.items()}
        v=cache[sid].get(day);return v if v is not None and math.isfinite(v) else None
    intents={};role_lists={};query_count=0;unknown=0
    for at,d in decisions.items():
        day=at[:10];rs=byday.pop(day,[]);symbols={i['sid'] for i in d['intents']}
        assert len(rs)==len({r['sid'] for r in rs}) and symbols=={r['sid'] for r in rs}
        vals={r['sid']:eta(r['sid'],day) for r in rs};order=priority(rs,vals);rmap={r['sid']:r for r in rs}
        for r in rs:
            sid=r['sid'];slot,key=order[sid]
            assert r['PVR']==vals[sid] and r['PVR_ready']==(vals[sid] is not None)
            assert (r['final_slot'],r['priority_rank'])==(slot,key)
            if vals[sid] is None:assert r['final_slot']==r['original_slot'];unknown+=1
            roles=[i['role'] for i in sorted(d['intents'],key=lambda i:(i['original_H1_rank'],i['role']!='core')) if i['sid']==sid]
            assert roles==r['roles'] and len(roles)==len(set(roles));query_count+=1
        for i in d['intents']:
            sid=i['sid'];r=rmap[sid]
            assert i['original_H1_rank']==r['original_H1_rank'] and i['rank']==i['priority_rank']==order[sid][1]
            assert i['PVR_score']==vals[sid] and i['PVR_ready']==(vals[sid] is not None)
            k=(at,sid,i['role']);assert k not in intents;intents[k]=i
            role_lists.setdefault((day,sid),[]).append(i['role']);C['all_frozen_intent_raw_eta_and_slot']+=1
        # H1 numeric slot ordering remains independent of eta and role count.
        hs=sorted({(i['original_H1_rank'],i['sid'],i['score']) for i in d['intents']})
        assert [x[1] for x in hs]==[x[1] for x in sorted(hs,key=lambda x:(-x[2],x[1]))]
    assert not byday
    C['all_unique_stock_rank_queries']=query_count;C['all_eta_UNKNOWN_fixed_H1_slots']=unknown
    prev={calendar[j]:calendar[j-1] for j in range(1,len(calendar))}
    funds=read(out/'pair/funding.jsonl.gz');groups=defaultdict(list);canonical={};reserved={}
    for f in funds:
        if f['at'][11:19]!='09:30:00' or f['result']=='no_execution_window_after_reservation':continue
        signal=prev[f['at'][:10]]+' 15:10:00+08:00';key=(signal,f['sid'],f['role']);assert key in intents,(window,key,f)
        i=intents[key];groups[f['at']].append((i['rank'],i['role']!='core',f,i))
    for at,rr in groups.items():
        assert [(x[0],x[1]) for x in rr]==sorted((x[0],x[1]) for x in rr)
        seen=set()
        for rank,rolekey,f,i in rr:
            sid=f['sid'];key=(at,sid)
            assert key not in seen,'An earlier successful reservation must suppress later same-stock roles'
            if f['result']!='reserved':continue
            seen.add(key);assert key not in reserved;reserved[key]=f
            assert f['shares']>0 and f['pool'] in ['probe','confirmed']
            if f['role']=='core':assert f['pool']=='probe'
            else:
                signal=prev[at[:10]]+' 15:10:00+08:00'
                if 'core' in role_lists.get((signal[:10],sid),[]):
                    assert any(z[2]['sid']==sid and z[2]['role']=='core' and z[2]['result']!='reserved' for z in rr[:rr.index((rank,rolekey,f,i))])
                    C['core_attempt_before_mobile_reservation']+=1
                cp=receipt_at(window,sid,signal[:10],dict(input_identity=meta['original_shared_input_identity']))
                assert cp and cp['receipt_id']==i['CP1_id']==f['CP1_id']
                assert cp['confirmed_day']==signal[:10] and cp['receipt_id'] not in canonical
                canonical[cp['receipt_id']]=key;C['canonical_CP_consumed_once_at_reservation']+=1
        C['all_OPEN_funding_batches_in_frozen_stock_role_order']+=1
    filled_core=set()
    for t in book['trades']:
        if t['side']!='buy':continue
        lid=t['layer'];role=book['metadata'][str(lid)]['role'];k=(t['signal_at'],t['security_id'],role);i=intents[k]
        assert n(t['pvr'])==n(i['score']),'trade.pvr is original H1, not eta'
        assert t['signal_at']<t['at'] and (t['at'],t['security_id']) in reserved
        assert t['shares']<=reserved[t['at'],t['security_id']]['shares']
        C['actual_buy_trade_pvr_original_H1_alias']+=1
        if role=='core':
            epoch=(t['security_id'],tuple(t['epoch']));assert epoch not in filled_core;filled_core.add(epoch);C['actual_CORE_once_per_original_epoch']+=1
    assert set(result['actual_exit_part_reasons'])<={'ACT_pause','I_structure_exit','CP1_add_protection'}
    assert n(timing['ending_NAV'])==n(book['ending_NAV'])==n(daily[-1]['nav'])
    result.update(arm='ETA',label='ETA',checks=dict(C),auditor_script_sha256=sha(__file__),
                  total_rank_queries=query_count,canonical_mobile_reserved_receipts=len(canonical),
                  selected_eta_manifest_sha256=sha(manifest),trade_pvr_semantics='Original H1 score; verified against original intent.score on every actual buy. Raw eta is intent.PVR_score/ranklog.PVR only.',
                  code_reuse='AST extraction of previously audited BASELINE ledger function with exact path/metadata-only replacements; no overlay/provider initialization or account replay.',
                  financial_kernel_sha256={str(CORE):sha(CORE),str(FEES):sha(FEES)},
                  source_sha256={**result['source_sha256'],**{str(out/f):sha(out/f) for f in ['TIMING.json','pair/rank-policy.jsonl.gz','pair/funding.jsonl.gz']},str(manifest):sha(manifest)},
                  priority_score_source_sha256=score_sources,raw_price_source_sha256=FSHA.copy(),
                  limits=['All daily cold raw-facts NAV, share/FIFO T+1/split/fractional proxy units, fee-inclusive lifecycle/basis, realized/unrealized/recognized dividend AR replay; no new strategy or Account initialized.','All actual reserve/fill fees independently recomputed from original dated venue/component/minimum/cap/partial-paid schedules; original5bps rawOPEN prices checked.','All ranklog stock slots/NA/ties and frozen intent aliases independently checked on this candidate path, all OPEN funding attempts follow frozen ranks and original CORE role precedence; all mobile reserved canonical CP unique and original same-day.','Original native code/provenance and source-only execution gate bind unchanged admission, protection/holding and ACT methods. No claim that every route function invocation was separately profiled in the full run.','Settled available/recognized AR bridge and wealth verified; AR/realized profit are not assumed spendable settled cash. Source execution, missing quotes, rights/payment proxies and non-PIT/development limitations persist.','Complete policy path difference is not independently additive per-stock/entry causal savings. No old realized layer label used in new priority.'],new_accounts=0)
    return result


def main():
    index={}
    for window in ['2022_2024','strong']:
        d=P/'runs'/window;dst=O/('PVR_ETA_'+window+'_ACCOUNT_AUDIT.json')
        if not all((d/n).exists() for n in ['DONE.json','TIMING.json']):continue
        if not (read(d/'DONE.json')['completed'] and read(d/'TIMING.json')['completed']):continue
        if dst.exists():
            result=read(dst)
            for p,h in result['source_sha256'].items():assert sha(p)==h
        else:
            print('AUDITING_COMPLETE_ETA',window,flush=True);result=audit_eta(window)
            dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            print('ETA_ACCOUNT_AUDIT_PASS',window,result['ending_NAV'],flush=True)
        index[window]=dict(receipt=str(dst),sha256=sha(dst),status=result['status'],ending_NAV=result['ending_NAV'])
    (O/'PVR_ETA_COMPLETED_ACCOUNT_AUDIT_INDEX.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    print('ETA_ROLLING_AUDIT_COMPLETE',len(index),flush=True)
if __name__=='__main__':main()
