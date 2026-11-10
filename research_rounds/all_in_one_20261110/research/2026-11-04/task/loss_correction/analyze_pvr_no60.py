"""Thin saved-PVR contribution/campaign wrapper; no runner import or event API.
Reuse original account(), contribution(), participation(), entry/exit readers.
Do not call pool_and_waits: its original hard-coded60 capacity is not NO60.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import importlib.util,inspect,json,gzip,hashlib,argparse,time
ROOT=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=ROOT/'pvr-slot1-native-readiness-20261101'
SPEC=importlib.util.spec_from_file_location('NO60_existing_saved_layer_tools',OLD/'analyze_results.py')
B=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(B)
A,M,META=B.A,B.M,B.META;Z=D(0)
src=inspect.getsource(B.entry_actions);assert src.count("if x['kind']=='split'")==1
src=src.replace("if x['kind']=='split'","if x['kind'] in ('split','split_fraction_floor_proxy')")
env=dict(B.__dict__);exec(compile(src,__file__+'::existing_two_kind_entry_reader','exec'),env)
entry_actions=env['entry_actions']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def claims(a):
    div=sum((D(str(l['dividend'])) for l in a['book']['layers']),Z);ar=D(str(a['daily'][-1]['dividend_receivable']))
    paid=[x for x in a['book']['audit'] if x['kind']=='dividend_payment']
    return dict(recognized=div,AR=ar,paid=div-ar,all_unpaid=not paid and div==ar,all_paid=ar==0)
def campaign_rows(a,actions):
    by={z['layer']:z for z in a['layers']};raw={z['id']:z for z in a['book']['layers']};cl=claims(a);groups=defaultdict(list);count=Counter()
    for z in actions:
        sid=z['sid']
        if z['action']!='add_to_existing_stock':count[sid]+=1
        assert count[sid]>0;groups[(sid,count[sid])].append(by[z['layer']])
    out=[]
    for (sid,num),ll in sorted(groups.items()):
        c=M.contribution(ll);position_closed=not any(z['qty'] for z in ll)
        div=sum((D(str(raw[z['layer']]['dividend'])) for z in ll),Z)
        claim='none' if div==0 or cl['all_paid'] else 'unpaid' if cl['all_unpaid'] else 'unknown_allocation'
        cashclosed=position_closed and claim=='none';cost=c['buy_cash'];ret=c['net']/cost if cost else None
        out.append(dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],campaign_number=num,position_closed=position_closed,cash_closed=cashclosed,claim_status=claim,recognized_dividend=div,opened=min(z['opened'] for z in ll),closed=max((z['closed'] for z in ll if z['closed']),default=None) if position_closed else None,layer_ids=[z['layer'] for z in ll],return_on_actual_buy_cost=ret,cash_closed_tail30=bool(cashclosed and ret is not None and ret>=D('.3')),**c))
    assert abs(sum((c['net'] for c in out),Z)-(D(str(a['book']['ending_NAV']))-D(1000000)))<D('.00000001')
    return out
def campaign_summary(cc):
    buckets={k:[] for k in ['cash_closed_tail','cash_closed_ordinary','position_flat_claim','active_position']}
    for c in cc:
        k='cash_closed_tail' if c['cash_closed_tail30'] else 'cash_closed_ordinary' if c['cash_closed'] else 'position_flat_claim' if c['position_closed'] else 'active_position'
        buckets[k].append(c)
    return {k:dict(campaigns=len(v),net=sum((x['net'] for x in v),Z),buy_cash=sum((x['buy_cash'] for x in v),Z)) for k,v in buckets.items()}
def path(a,sid,actions,exits):return B.path(a,sid,actions,exits)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['2022','2025_26'],required=True);ap.add_argument('--new-root',required=True);ap.add_argument('--out',required=True);args=ap.parse_args();started=time.monotonic()
    out=Path(args.out);assert not out.exists();out.mkdir(parents=True);A.O=M.O=B.O=out
    roots={'PVR_BASELINE':OLD/'runs'/args.window,'PVR_NO60':Path(args.new_root)}
    assert json.loads((roots['PVR_NO60']/'DONE.json').read_text())['completed']
    data={name:A.account(args.window,name,root) for name,root in roots.items()}
    sets={name:M.participation(a) for name,a in data.items()};summ={};ccs={};allactions={};allexits={}
    for name,a in data.items():
        actions=entry_actions(a);exits=B.exit_chain(a);cc=campaign_rows(a,actions);ccs[name]=cc;allactions[name]=actions;allexits[name]=exits
        summ[name]=dict(contributions=M.contribution(a['layers']),campaigns=campaign_summary(cc),claims=claims(a),actual_funded_stocks=len(sets[name]['all_stocks']),actual_stock_attempts=len(sets[name]['stock_attempts']),entry_actions={k:M.contribution([z for z in a['layers'] if z['layer'] in {x['layer'] for x in actions if x['action']==k}]) for k in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']})
        save(out/(name+'-CAMPAIGNS.json'),cc);save(out/(name+'-ENTRY_ACTIONS.json'),actions);save(out/(name+'-EXIT_CHAIN.json'),exits);save(out/(name+'-SUMMARY.json'),summ[name])
    before,after=data['PVR_BASELINE'],data['PVR_NO60'];deltas=[]
    for sid in sorted(sets['PVR_BASELINE']['all_stocks']|sets['PVR_NO60']['all_stocks']):
        ls={name:[l for l in a['layers'] if l['sid']==sid] for name,a in data.items()};v={name:M.contribution(l) for name,l in ls.items()}
        deltas.append(dict(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],baseline=v['PVR_BASELINE'],NO60=v['PVR_NO60'],delta=v['PVR_NO60']['net']-v['PVR_BASELINE']['net'],category='new_stock' if not ls['PVR_BASELINE'] else 'lost_stock' if not ls['PVR_NO60'] else 'common_stock'))
    deltaNAV=D(str(after['book']['ending_NAV']))-D(str(before['book']['ending_NAV']));assert abs(sum((x['delta'] for x in deltas),Z)-deltaNAV)<D('.00000001')
    changes={k:dict(baseline=len(sets['PVR_BASELINE'][k]),NO60=len(sets['PVR_NO60'][k]),gained=sorted(sets['PVR_NO60'][k]-sets['PVR_BASELINE'][k]),lost=sorted(sets['PVR_BASELINE'][k]-sets['PVR_NO60'][k])) for k in sets['PVR_BASELINE']}
    ranked=sorted(before['stock'],key=before['stock'].get,reverse=True);chosen=list(dict.fromkeys(ranked[:10]+ranked[-3:]+[x['sid'] for x in sorted(deltas,key=lambda x:-x['delta'])[:5]]+[x['sid'] for x in sorted(deltas,key=lambda x:x['delta'])[:5]]+['601869.SH','301511.SZ','300308.SZ','300502.SZ']))
    for name,a in data.items():save(out/(name+'-FIXED_AND_DELTA_PATHS.json'),[path(a,s,allactions[name],allexits[name]) for s in chosen])
    save(out/'STOCK_DELTA.json',sorted(deltas,key=lambda x:-x['delta']));save(out/'FUNDED_CHANGES.json',changes)
    save(out/'COMPARISON.json',dict(window=args.window,NAV_difference=deltaNAV,baseline=summ['PVR_BASELINE'],NO60=summ['PVR_NO60'],stock_delta_parts={k:sum((x['delta'] for x in deltas if x['category']==k),Z) for k in ['new_stock','lost_stock','common_stock']},first_ten_original_winners=[next(z for z in deltas if z['sid']==s) for s in ranked[:10]],source_scope='current-survivor/current-classification developer data; complete original periods, not OOS or live',account_runs_by_analysis=0,hardcoded_old60_wait_capacity_not_called=True))
    save(out/'SOURCE_BINDING.json',dict(sources={str(root/'pair/B.json.gz'):sha(root/'pair/B.json.gz') for root in roots.values()},readers={str(OLD/'analyze_results.py'):sha(OLD/'analyze_results.py'),str(ROOT/'migration-admission-singlepass-economics-20261101/analyze.py'):sha(ROOT/'migration-admission-singlepass-economics-20261101/analyze.py'),str(ROOT/'c1-drawdown-capacity-20261101/analyze_saved.py'):sha(ROOT/'c1-drawdown-capacity-20261101/analyze_saved.py'),str(Path(__file__)):sha(__file__)},zero_account_imports=True,zero_economic_events=True,seconds=time.monotonic()-started))
    print(json.dumps(dict(window=args.window,NAV_difference=deltaNAV,summary=summ),ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
