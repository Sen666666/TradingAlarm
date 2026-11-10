"""One saved-JSON cross join; no state/price/account computation."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import json,gzip,hashlib,ast,datetime
getcontext().prec=50
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');O=Path(__file__).resolve().parent
M=B/'loss_correction/macro_new_risk_association_v1';L=B/'ar6_native_feasibility/sector_local_price_permission'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,default=str)+'\n')
assert read(L/'RESULTS.json')['passed']
# Reuse only the two reviewed pure original-money group functions; no top-level old join execution.
tree=ast.parse((M/'join_saved.py').read_text());nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ['total','agg']]
assert len(nodes)==2
env={'D':D};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(M/'join_saved.py'),'exec'),env);old_agg=env['agg']
with gzip.open(L/'DAILY.jsonl.gz','rt') as f:local_rows=[json.loads(line) for line in f]
local={(r['sector'],r['decision_close']):r for r in local_rows};assert len(local)==len(local_rows)==364796
states=['ON','OFF','UNESTABLISHED','UNKNOWN','UNAVAILABLE'];macros=['D','P','C','UNKNOWN']
source=[M/'2022_2024_ROWS.json',M/'strong_ROWS.json',M/'FIXED_ORIGINAL_TAILS.json',M/'SUMMARY.json',M/'join_saved.py',L/'DAILY.jsonl.gz',L/'SCHEMA.json',L/'RESULTS.json',L/'SERIES_INDEX.json',O/'PROTOCOL.txt',Path(__file__)]
save('INPUT_FREEZE.json',dict(before_join=True,time_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256={str(p):sha(p) for p in source},new_models=0,new_accounts=0,local_rule='one frozen prior20 high/low only, no grid'))
def join(x):
    x=dict(x);at=x['budget_order'].split('|')[1].replace('T',' ');assert at==x['decision_at']
    r=local.get((x['sector'],at));status='UNAVAILABLE' if r is None else r['local_permission_status']
    cls={'KNOWN_ON':'ON','KNOWN_OFF':'OFF','KNOWN_UNESTABLISHED':'UNESTABLISHED','UNKNOWN_NO_NEW_PERMISSION':'UNKNOWN','UNAVAILABLE':'UNAVAILABLE'}[status]
    if r is not None:
        assert r['decision_close']==at and r['sector']==x['sector']
        assert r['local_new_risk_permission']==(cls=='ON')
    x.update(local_class=cls,local_permission_status=status,local_new_risk_permission=False if r is None else r['local_new_risk_permission'],local_known=None if r is None else r['known'],local_source_segment=None if r is None else r['source_segment'],local_source_SHA256=None if r is None else r['source_SHA256'],local_event=None if r is None else r['event'])
    return x
def agg(z):
    q=old_agg(z);q['macro_known']=q.pop('known');q['macro_NA']=q.pop('NA')
    q.update(local_ON=sum(x['local_class']=='ON' for x in z),local_OFF=sum(x['local_class']=='OFF' for x in z),local_UNESTABLISHED=sum(x['local_class']=='UNESTABLISHED' for x in z),local_UNKNOWN=sum(x['local_class']=='UNKNOWN' for x in z),local_UNAVAILABLE=sum(x['local_class']=='UNAVAILABLE' for x in z))
    q['original_gross_buy_notional']=None if q['buy_fee'] is None else D(q['cost'])-D(q['buy_fee'])
    q['original_cash_flow_contribution_ex_mark_AR']=None if q['recognized_dividend_AR'] is None or any('value' not in x for x in z) else D(q['net'])-sum((D(x['value']) for x in z),D(0))-D(q['recognized_dividend_AR'])
    return q
def cross(z):return {m:{s:agg([x for x in z if x['macrostate_asof']==m and x['local_class']==s]) for s in states} for m in macros}
rows={w:[join(x) for x in read(M/(w+'_ROWS.json'))] for w in ['2022_2024','strong']}
tails={w:[join(x) for x in z['full_original_members']] for w,z in read(M/'FIXED_ORIGINAL_TAILS.json').items()}
summary={};oldsummary=read(M/'SUMMARY.json');examples={}
for w,rs in rows.items():
    save(w+'_ROWS.json',rs);summary[w]={}
    for label,old in oldsummary[w].items():
        if label=='strict303_newfills':q=[x for x in rs if '2024-10-08'<x['opened'][:10]<='2024-12-31'];f=q
        else:
            lo,hi=old['lo'],old['hi'];q=[x for x in rs if lo<=x['decision_at'][:10]<=hi];f=[x for x in rs if lo<=x['opened'][:10]<=hi]
        summary[w][label]={'all':agg(q),'cross':cross(q),'actual_fill_cohort_all':agg(f),'actual_fill_cross':cross(f),'role_cross':{r:cross([x for x in q if x['role']==r]) for r in ['core','mobile']},'action_cross':{a:cross([x for x in q if x['action']==a]) for a in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']},'pool_cross':{p:cross([x for x in q if x['pool_at_fill']==p]) for p in ['probe','confirmed']},'money_scope':'original lifecycle to common book cutoff, not phase wealth','period_newlayer_wealth_reused_only_if_strict303':label=='strict303_newfills'}
    examples[w]={}
    for name,m,s in [('macroC_localOFF','C','OFF'),('macroD_localON','D','ON')]:
        z=[x for x in rs if x['macrostate_asof']==m and x['local_class']==s];examples[w][name]={'all':agg(z),'posthoc_original_top_positive':sorted([x for x in z if D(x['net'])>0],key=lambda x:D(x['net']),reverse=True)[:3],'posthoc_original_top_negative':sorted([x for x in z if D(x['net'])<0],key=lambda x:D(x['net']))[:3]}
fixed={w:{'all':agg(z),'cross':cross(z),'role_cross':{r:cross([x for x in z if x['role']==r]) for r in ['core','mobile']},'full_original_members':z} for w,z in tails.items()}
save('SUMMARY.json',summary);save('FIXED_ORIGINAL_TAILS.json',fixed);save('SAME_CELL_EXAMPLES.json',examples)
for w,scopes in summary.items():
    for name,q in scopes.items():
        cells=[x for m in q['cross'].values() for x in m.values()]
        assert sum(x['layers'] for x in cells)==q['all']['layers']
        assert abs(sum((D(x['net']) for x in cells),D(0))-D(q['all']['net']))<D('1e-20')
assert [len(rows[w]) for w in ['2022_2024','strong']]==[2265,1171]
assert [len(tails[w]) for w in ['2022_2024','strong']]==[83,94]
assert all(sha(Path(p))==h for p,h in read(O/'INPUT_FREEZE.json')['source_sha256'].items())
save('COMPLETED.json',dict(status='PASS_SAVED_CROSS_ASSOCIATION_ONLY',new_models=0,new_accounts=0,all_source_post_exact=True,original_layers=3436,fixed_original_tails=177,no_deleted_PnL_NAV=True))
print(json.dumps({'main':{w:{k:summary[w][k]['cross'] for k in ['ALL']+(['2022L03','2023Q2_AI','strict303_newfills'] if w=='2022_2024' else [])} for w in rows},'fixed':{w:z['cross'] for w,z in fixed.items()},'output':str(O)},ensure_ascii=False,default=str,indent=2))
