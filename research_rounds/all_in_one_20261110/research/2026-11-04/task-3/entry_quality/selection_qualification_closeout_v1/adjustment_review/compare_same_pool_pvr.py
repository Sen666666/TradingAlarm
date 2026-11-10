"""Saved input-coordinate comparison only. No indicator/account/forward execution."""
from pathlib import Path
import csv,json,math,hashlib
from collections import Counter

BASE=Path(__file__).resolve().parents[2]/'local_observable_selection_v1'
OUT=Path(__file__).resolve().parent
SOURCE=BASE/'cache_comparison/ALL_EXACT_OLD_SYMBOL_DATE_COMPARISONS.csv'
TARGETS=['000620.SZ','300666.SZ','300085.SZ','002583.SZ','603061.SH','301611.SZ','300604.SZ','301308.SZ','002371.SZ','688012.SH','688498.SH']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def finite(s):
    try:return math.isfinite(float(s))
    except (TypeError,ValueError):return False
def write_csv(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    prior=load(BASE/'independent_review/FINAL_OUTPUT_AUDIT.json')
    assert prior['status']=='PASS_ALL_SAVED_RANKS_AND_COUNTS_WITH_SOURCE_LIMITS'
    completion=load(BASE/'cache_comparison/COMPLETION.json')
    assert sha(SOURCE)==completion['outputs'][SOURCE.name]
    with SOURCE.open()as f: rows=list(csv.DictReader(f))
    assert len(rows)==11767 and len({(r['sid'],r['day'])for r in rows})==11767
    dates=sorted({r['day']for r in rows}); assert len(dates)==7
    targets=[]; summary=[]; allranks=[]; topdiff=[]
    for day in dates:
        original={r['sid']:r for r in rows if r['day']==day}; assert len(original)==1681
        common={sid:r for sid,r in original.items() if finite(r['score_old'])and finite(r['score_new'])}
        orders={v:sorted(common,key=lambda sid:(-float(common[sid]['score_'+v]),sid))for v in ['old','new']}
        ranks={v:{sid:i+1 for i,sid in enumerate(orders[v])}for v in orders}
        tops={v:set(orders[v][:20])for v in orders}
        for sid,r in sorted(common.items()):
            allranks.append(dict(day=day,sid=sid,common_pool_N=len(common),score_old=float(r['score_old']),score_new=float(r['score_new']),rank_old=ranks['old'][sid],rank_new=ranks['new'][sid],rank_new_minus_old=ranks['new'][sid]-ranks['old'][sid]))
        for sid in sorted(tops['old']|tops['new']):
            topdiff.append(dict(day=day,sid=sid,common_pool_N=len(common),rank_old=ranks['old'][sid],rank_new=ranks['new'][sid],top20_status='BOTH'if sid in tops['old']&tops['new']else('NEW_ONLY'if sid in tops['new']else'OLD_ONLY'),score_old=float(common[sid]['score_old']),score_new=float(common[sid]['score_new'])))
        summary.append(dict(day=day,exact_intersection_rows=len(original),common_finite_PVR_pool_N=len(common),top20_intersection=len(tops['old']&tops['new']),top20_new_only=len(tops['new']-tops['old']),top20_old_only=len(tops['old']-tops['new']),all_common_rank_changed=sum(ranks['new'][s]!=ranks['old'][s]for s in common),max_abs_rank_change=max(abs(ranks['new'][s]-ranks['old'][s])for s in common),old_score_tie_excess=sum(v-1 for v in Counter(float(common[s]['score_old'])for s in common).values()),new_score_tie_excess=sum(v-1 for v in Counter(float(common[s]['score_new'])for s in common).values())))
        for sid in TARGETS:
            r=original.get(sid); known_old=bool(r and finite(r['score_old']));known_new=bool(r and finite(r['score_new']))
            eligible=known_old and known_new
            reason='COMMON_FINITE'if eligible else('OUTSIDE_EXACT_SYMBOL_INTERSECTION'if r is None else('BOTH_UNKNOWN'if not known_old and not known_new else('OLD_UNKNOWN'if not known_old else'NEW_UNKNOWN')))
            targets.append(dict(day=day,sid=sid,status=reason,common_pool_N=len(common),old_known=known_old,new_known=known_new,score_old=float(r['score_old'])if known_old else None,score_new=float(r['score_new'])if known_new else None,rank_old=ranks['old'].get(sid),rank_new=ranks['new'].get(sid),rank_new_minus_old=ranks['new'][sid]-ranks['old'][sid]if eligible else None,old_top20=sid in tops['old']if eligible else None,new_top20=sid in tops['new']if eligible else None))
    assert len(targets)==77
    write_csv('TARGET_77_SAME_POOL_PVR_RANKS.csv',targets)
    write_csv('SAME_POOL_PVR_DATE_SUMMARY.csv',summary)
    write_csv('ALL_COMMON_FINITE_PVR_RANKS.csv',allranks)
    write_csv('TOP20_INTERSECTION_AND_CHANGES.csv',topdiff)
    result=dict(status='PASS_SAVED_SAME_POOL_PVR_COORDINATE_CONTRAST_WITH_LIMITS',prior_completed_audit={'path':str((BASE/'independent_review/FINAL_OUTPUT_AUDIT.json').resolve()),'sha256':sha(BASE/'independent_review/FINAL_OUTPUT_AUDIT.json'),'status':prior['status']},definitions={'pool':'Exact old1709/canonical symbol intersection1681 per date; only both finite old/new PVR, identical frozen membership for the two rankings.','sorting':'Descending raw unrounded PVR score; ties ascending exact symbol on both sides. Not original pending/native H1 rank.','rank_delta':'new_rank - old_rank; positive means new-source rank lower.','qualification':'No E0/I/CP/industryQ/pending/role/cash/order legality filter. Stock-score cohort only.','CONT_extent':'Not recalculated. Existing old dual cache is pending-derived only; cannot infer old-source CONT for full5517 from it.','causal_scope':'Input-coordinate contrast, not isolated corporate-action intervention. Three previously audited maximum-difference cases match raw prices and explain local differences by varying factors; remaining table differences not individually attributed to CA.'},summary=summary,target_rows=77,common_rank_rows=len(allranks),target_common_finite_rows=sum(r['status']=='COMMON_FINITE'for r in targets),changed_targets=[r for r in targets if r['rank_new_minus_old'] not in (None,0)],source_sha256={str(SOURCE.resolve()):sha(SOURCE),str((BASE/'cache_comparison/COMPLETION.json').resolve()):sha(BASE/'cache_comparison/COMPLETION.json'),str(Path(__file__).resolve()):sha(Path(__file__)),str((BASE/'independent_review/THREE_MAX_DIFFERENCE_AUDIT.json').resolve()):sha(BASE/'independent_review/THREE_MAX_DIFFERENCE_AUDIT.json')},output_sha256={p.name:sha(p)for p in OUT.glob('*.csv')},limits=['Old-source CA-adjusted full5517 is not available or reconstructed here.','Common finite pool excludes one-sided unknowns before ranking; excludes full-local population/readiness effects.','Same-symbol saved data may differ in adjustment history, effective-observation clocks, units/masks or other upstream details; no whole-table factor-causation claim.','Nominal15:00 index is not historical publication/availability. Snapshot factors and current metadata are not PIT.','No model, account, forward labels, source refresh, parameter selection, price-path or financial replay.'],remaining_blocks=[])
    p=OUT/'SAME_POOL_PVR_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=result['status'],sha256=sha(p),summary=summary,changed_targets=result['changed_targets'],not_common=[r for r in targets if r['status']!='COMMON_FINITE']),ensure_ascii=False))
if __name__=='__main__':main()
