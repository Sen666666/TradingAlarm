"""Three fixed 2024 phases of two frozen books; zero account events.

Reuses original saved-report price reader and exact original entry-actions
reader. This is descriptive native-money attribution, not a second engine.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import ast, collections, csv, gzip, hashlib, importlib.util, json

O=Path(__file__).resolve().parent; T=O.parent; Z=D(0); EPS=D('.000001')
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def n(x): return D(str(x))
def day(x): return str(x)[:10]
def save(name,x):
    p=O/name
    with p.open('x') as f: json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def gz(p):
    with gzip.open(p,'rt') as f: return json.load(f)
def rows(p):
    with gzip.open(p,'rt') as f: return [json.loads(x) for x in f]
def near(a,b,label): assert abs(a-b)<EPS,(label,a,b,a-b)

PRICE_READER=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/c1-drawdown-capacity-20261101/analyze_saved.py')
sp=importlib.util.spec_from_file_location('frozen_saved_price_reader',PRICE_READER)
A=importlib.util.module_from_spec(sp);sp.loader.exec_module(A)
ENTRY_READER=PRICE_READER.parent.parent/'pvr-slot1-native-readiness-20261101/analyze_results.py'
src=ENTRY_READER.read_text();tree=ast.parse(src)
entry_src=ast.get_source_segment(src,next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='entry_actions'))
entry_src=entry_src.replace("if x['kind']=='split'","if x['kind'] in ('split','split_fraction_floor_proxy')")
env=dict(collections=collections,D=D,n=n);exec(compile(entry_src,str(ENTRY_READER)+'::original_entry_actions_two_split_kinds','exec'),env)
entry_actions=env['entry_actions']
PHASES=[('pre924','2023-12-29','2024-09-23'),('924_six_closes','2024-09-23','2024-10-08'),('post_oct8','2024-10-08','2024-12-31'),('year2024','2023-12-29','2024-12-31')]
binding=read(T/'market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json')['long']
for p,h in binding['source_sha256'].items(): assert sha(p)==h
sources={};result={};mark_sources={}

def agg(rr):
    return dict(layers=len(rr),stocks=len({x['sid'] for x in rr}),wealth=sum((x['wealth'] for x in rr),Z),positive=sum((max(Z,x['wealth']) for x in rr),Z),negative=sum((min(Z,x['wealth']) for x in rr),Z),positive_layers=sum(x['wealth']>0 for x in rr),negative_layers=sum(x['wealth']<0 for x in rr),zero_layers=sum(x['wealth']==0 for x in rr),new_fill_buy_cash=sum((x['buy_cash_in_phase'] for x in rr),Z))

for arm,root,bookname,derived in [
    ('No60',T/'capacity_cost_guard_v1/runs/long-v1/arms/B','B',T/'capacity_cost_guard_analysis_v1/full_long_v1/analysis/long/B/LAYERS.json'),
    ('D_GROSS10',T/'market_gross_admission_native_v1/full-long-v1','D_GROSS10',T/'market_gross_admission_outcome_analysis_v1/full_long_v1/analysis/long/D_GROSS10/LAYERS.json')]:
    bp=root/'pair'/f'{bookname}.json.gz';dp=root/'pair/daily.jsonl.gz'
    b=gz(bp);ds=rows(dp);by={day(r['at']):r for r in ds};ls=read(derived);lm={x['layer']:x for x in ls};raw={x['id']:x for x in b['layers']}
    actions=entry_actions(dict(book=b,layers=ls));am={x['layer']:x for x in actions};assert len(actions)==len(ls)==sum(t['side']=='buy' for t in b['trades'])
    buy_by={t['layer']:t for t in b['trades'] if t['side']=='buy'}
    # Native original split events affect quantities in the original action reader.
    save(arm+'_ALL_HISTORICAL_ENTRY_ACTIONS.json',actions)
    bounds={};invbounds={}
    for d in sorted({p[i] for p in PHASES for i in (1,2)}):
        live={x['id']:x for x in by[d]['layers']};ww={};iv=defaultdict(lambda:Z)
        for lid,l in lm.items():
            if day(l['opened'])>d: v=Z
            elif lid in live:
                x=live[lid];vmark=D(x['qty'])*A.price(l['sid'],d);iv[l['sid']]+=vmark
                v=n(x['cash'])+n(x['dividend'])+vmark
                fp=A.SM[l['sid']]['refs']['facts'];mark_sources[str(fp)]=sha(fp)
            else:
                x=raw[lid];assert not x['qty'] and x['closed'] and day(x['closed'])<=d
                v=n(x['cash'])+n(x['dividend'])
            ww[lid]=v
        near(sum(ww.values(),Z),n(by[d]['nav'])-D(1000000),(arm,d,'layer_boundary_NAV'))
        near(sum(iv.values(),Z),n(by[d]['inventory']),(arm,d,'native_inventory_raw_marks'))
        bounds[d]=(ww,live);invbounds[d]=iv
    ar={}
    for phase,start,end in PHASES:
        w0,live0=bounds[start];w1,live1=bounds[end];rr=[];flows=defaultdict(lambda:defaultdict(lambda:Z))
        for t in b['trades']:
            if not start<day(t['at'])<=end: continue
            f=flows[t['security_id']];g=n(t['gross_cny']);fee=n(t['fees_cny']);f['fees']+=fee
            if t['side']=='buy':f['buy_cash']+=g+fee;f['buy_fills']+=1
            else:f['sell_net']+=g-fee;f['sell_fills']+=1
        for x in b['audit']:
            if x['kind']=='dividend_accrual':
                dv=x['receivable']
                if start<day(dv['ex_at'])<=end: flows[dv['security_id']]['dividend_accrued']+=n(dv['net_local'])
        for lid,l in lm.items():
            new=start<day(l['opened'])<=end
            if lid not in live0 and not new and w1[lid]==w0[lid]: continue
            t=buy_by[lid];rr.append(dict(arm=arm,phase=phase,layer=lid,sid=l['sid'],name=l['name'],industry=l['industry'],sector=l['sector'],role=l['role'],pool_at_fill=l['pool_at_fill'],action=am[lid]['action'],opened=l['opened'],closed=l['closed'],signal_day=l['signal_day'],group='new_actual_fill_in_phase' if new else 'held_at_start_CLOSE',boundary_wealth=w0[lid],ending_wealth=w1[lid],wealth=w1[lid]-w0[lid],buy_cash_in_phase=n(t['gross_cny'])+n(t['fees_cny']) if new else Z,qty_begin=live0.get(lid,{}).get('qty',0),qty_end=live1.get(lid,{}).get('qty',0),receipt=l['receipt'],attempt=l['attempt'],lifecycle_net_to_final2024=n(l['net']),final_exit_reason=raw[lid]['reason']))
        change=n(by[end]['nav'])-n(by[start]['nav']);near(sum((r['wealth'] for r in rr),Z),change,(arm,phase,'layer_phase_NAV'))
        grouped={k:agg([r for r in rr if r['group']==k]) for k in ['held_at_start_CLOSE','new_actual_fill_in_phase']}
        stockrows=[]
        for sid in sorted({x['sid'] for x in ls}):
            ss=[r for r in rr if r['sid']==sid];f=flows[sid];money=invbounds[end].get(sid,Z)-invbounds[start].get(sid,Z)+f['sell_net']-f['buy_cash']+f['dividend_accrued'];near(sum((r['wealth'] for r in ss),Z),money,(arm,phase,sid,'native_money_vs_boundary_layers'))
            stockrows.append(dict(sid=sid,name=A.META[sid]['name'],industry=A.META[sid]['industry'],wealth=money,held_at_start_wealth=sum((r['wealth'] for r in ss if r['group']=='held_at_start_CLOSE'),Z),newfill_wealth=sum((r['wealth'] for r in ss if r['group']=='new_actual_fill_in_phase'),Z),inventory_begin=invbounds[start].get(sid,Z),inventory_end=invbounds[end].get(sid,Z),buy_cash=f['buy_cash'],sell_net=f['sell_net'],fees=f['fees'],recognized_dividend=f['dividend_accrued'],buy_fills=int(f['buy_fills']),sell_fills=int(f['sell_fills']),layer_ids=[x['layer'] for x in ss]))
        near(sum((r['wealth'] for r in stockrows),Z),change,(arm,phase,'whole_stock_money_NAV'))
        inds=[]
        for industry in sorted({x['industry'] for x in stockrows}):
            ss=[x for x in stockrows if x['industry']==industry]
            inds.append(dict(industry=industry,wealth=sum((x['wealth'] for x in ss),Z),held_at_start_wealth=sum((x['held_at_start_wealth'] for x in ss),Z),newfill_wealth=sum((x['newfill_wealth'] for x in ss),Z),positive_stock_wealth=sum((max(Z,x['wealth']) for x in ss),Z),negative_stock_wealth=sum((min(Z,x['wealth']) for x in ss),Z),buy_cash=sum((x['buy_cash'] for x in ss),Z),fees=sum((x['fees'] for x in ss),Z),active_stocks=sum(bool(x['layer_ids']) for x in ss),all_funded_stock_population=len(ss)))
        actionsums={k:agg([r for r in rr if r['group']=='new_actual_fill_in_phase' and r['action']==k]) for k in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']}
        roles={k:agg([r for r in rr if r['group']=='new_actual_fill_in_phase' and r['role']==k]) for k in ['core','mobile']}
        save(arm+'_'+phase+'_ALL_LAYERS.json',rr);save(arm+'_'+phase+'_ALL_STOCKS.json',sorted(stockrows,key=lambda x:x['wealth']));save(arm+'_'+phase+'_ALL_INDUSTRIES.json',sorted(inds,key=lambda x:x['wealth']))
        ar[phase]=dict(start_CLOSE=start,end_CLOSE=end,start_NAV=by[start]['nav'],end_NAV=by[end]['nav'],NAV_change=change,layer_groups=grouped,newfill_actions=actionsums,newfill_roles=roles,trade_fees=sum((x['fees'] for x in stockrows),Z),recognized_dividend=sum((x['recognized_dividend'] for x in stockrows),Z),full_stock_population=len(stockrows),active_phase_stocks=sum(bool(x['layer_ids']) for x in stockrows),negative_stock_count=sum(x['wealth']<0 for x in stockrows),positive_stock_count=sum(x['wealth']>0 for x in stockrows),top5_loss_industries=sorted(inds,key=lambda x:x['wealth'])[:5],top5_gain_industries=sorted(inds,key=lambda x:-x['wealth'])[:5],top10_loss_stocks=sorted(stockrows,key=lambda x:x['wealth'])[:10],top10_gain_stocks=sorted(stockrows,key=lambda x:-x['wealth'])[:10])
        print(arm,phase,'change',change,'actions',[(k,str(v['wealth']),v['layers']) for k,v in actionsums.items()],flush=True)
    # All actual 2024 trades, original quantities/prices/exits, not only worst cases.
    save(arm+'_ALL_2024_TRADES.json',[x for x in b['trades'] if day(x['at']).startswith('2024')])
    save(arm+'_ALL_2024_EXIT_REQUESTS_AND_CA.json',[x for x in b['audit'] if day(x.get('at','')).startswith('2024') and x['kind'] in ('pilot_layer_exit','exit_request','split','split_fraction_floor_proxy','dividend_accrual','dividend_payment','targeted_non_pro_rata_issuance')])
    near(sum((ar[p]['NAV_change'] for p in ['pre924','924_six_closes','post_oct8']),Z),ar['year2024']['NAV_change'],(arm,'three_phases_telescope'))
    result[arm]=ar;sources.update({str(p):sha(p) for p in [bp,dp,derived]})
save('SUMMARY.json',result)
save('SOURCE_BINDING.json',dict(status='NATIVE_SAVED_MONEY_AND_LAYER_ATTRIBUTION_ASSERTIONS_PASS_INDEPENDENT_REVIEW_PENDING',source_sha256=sources,original_price_reader=str(PRICE_READER),original_price_reader_sha256=sha(PRICE_READER),original_entry_reader=str(ENTRY_READER),original_entry_reader_sha256=sha(ENTRY_READER),script_sha256=sha(__file__),marks_facts_sha256=mark_sources,new_account_events=0,new_prices=0,scope='Existing saved reader money reused; no new financial model or basis. Complete positive/negative/zero stock population saved. First/add/reentry replay actual since2022, original split qty handling. Boundary marks native raw price reader. Not independent financial recomputation, not counterfactual deletion savings.',review='Pending independent new derivation review; original ledger reviews apply only original sources.'))
print('DONE',sha(O/'SUMMARY.json'),flush=True)
