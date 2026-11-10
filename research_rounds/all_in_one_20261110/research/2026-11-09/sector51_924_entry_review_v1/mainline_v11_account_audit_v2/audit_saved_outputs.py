"""Independent V11 saved-output audit. Standard library and reviewed output helper only.
Never imports a strategy, instantiates Data, opens a network connection, or reruns history.
"""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from collections import defaultdict, Counter
import argparse, ast, csv, hashlib, importlib.util, json, sys
sys.dont_write_bytecode = True
O=Path(__file__).resolve().parent; R=O.parent; Z=D(0); INITIAL=D(1200000); TOL=D('1e-16')
BASE=R/'mainline_m7_cash_batch_design_v6/once_20260630'
TAIL=R/'mainline_tail_capture_baseline_v1'
HELPER=R/'mainline_candidate_v8_false_mainline_retirement_run_v1/evaluate_independent.py'
RULES=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json')
PROTOCOL=RULES.parent/'economic-protocol.json'
read=lambda p:json.loads(Path(p).read_text())
CACHE={}
def sha(p):
    p=Path(p); st=p.stat(); key=(str(p),st.st_size,st.st_mtime_ns)
    if key not in CACHE:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
        CACHE[key]=h.hexdigest()
    return CACHE[key]
def save(n,v):
    (O/(n+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
    if isinstance(v,list) and v:
        with (O/(n+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in v for k in r)));w.writeheader()
            w.writerows({k:json.dumps(x,ensure_ascii=False,default=str) if isinstance(x,(list,dict)) else x for k,x in r.items()} for r in v)
def near(a,b,label):assert abs(D(a)-D(b))<TOL,(label,str(a),str(b))
def sm(rs,k):return sum((D(r.get(k,0) or 0) for r in rs),Z)
def bykey(rows,key):
    out=defaultdict(list)
    for row in rows:out[row[key]].append(row)
    return out
def verify_hashes(path):
    path=Path(path); h=read(path/'OUTPUT_HASHES.json')
    actual={p.name for p in path.iterdir() if p.is_file()}-{'OUTPUT_HASHES.json'}
    assert set(h)==actual,('output_inventory',str(path),actual-set(h),set(h)-actual)
    for n,v in h.items():assert sha(path/n)==v,('output_hash',str(path/n))
    sources=read(path/'SOURCE_HASHES.json')
    for p,v in sources.items():assert sha(p)==v,('source_hash',p)
    return dict(output_files=len(h),source_files=len(sources),output_manifest_sha256=sha(path/'OUTPUT_HASHES.json'),source_manifest_sha256=sha(path/'SOURCE_HASHES.json'))
def version(rows,day,proxies):
    selected=[r for r in rows if r['from']<=day and (not r.get('to') or day<r['to'])]
    assert len(selected)==1,('dated_rule',day)
    r=selected[0]
    assert r['basis']=='official_rule' and r.get('verification_status')=='verified' or r['basis']=='explicit_research_proxy' and r.get('proxy_id') in proxies
    return r
def fee_calc(rules,proxies,sid,day,qty,price,side):
    venue=version(rules['venue_versions'][sid],day,proxies)['venue']
    schedule=version(rules['fee_versions'][venue],day,proxies)['schedule']; n=qty*price; fee=Z
    for c in schedule['components']:
        if c.get('side','both') not in ('both',side):continue
        basis=c.get('amount_basis','notional')
        amount=n if basis=='notional' else D(qty) if basis=='shares' else D(qty)*D(rules['security_metadata'][sid]['par_value'])
        f=max(D(c.get('minimum_local','0')),amount*D(c['rate']))
        if c.get('maximum_local') is not None:f=min(f,D(c['maximum_local']))
        if c.get('rounding_unit'):
            u=D(c['rounding_unit']);f=(f/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*u
        fee+=f
    return fee

def cash_event_terms(path):
    found=defaultdict(list)
    def visit(x):
        if isinstance(x,dict):
            if all(k in x for k in ('sid','ex_date','record_date','pay_date','d_cash')):found[(x['sid'],x['ex_date'])].append(x)
            for y in x.values():
                if isinstance(y,(dict,list)):visit(y)
        elif isinstance(x,list):
            for y in x:visit(y)
    for p in read(path/'SOURCE_HASHES.json'):
        q=Path(p)
        if q.suffix=='.json' and any(x in q.name.upper() for x in ('EVENT','ADDITIONAL','EXTRA','EXACT_CASH','MANIFEST')):
            visit(read(q))
    result={}
    for key,values in found.items():
        terms={(v['record_date'],v['pay_date'],str(D(v['d_cash']))) for v in values}
        assert len(terms)==1,('conflicting_cash_terms',key,terms)
        result[key]=values[0]
    return result

def round_rows(path,end,orders,holdings,equity):
    attempts={a['id']:a for a in read(path/'ATTEMPTS.json')}
    groups=bykey(orders,'round_id'); final=bykey([h for h in holdings if h['day']==end],'round_id'); eq=bykey([e for e in equity if e.get('round_id')],'round_id'); out=[]
    for rid,os in groups.items():
        seeds=[x for x in os if x['side']=='BUY_SEED'];assert len(seeds)==1,('round_seed',rid)
        s=seeds[0]; a=attempts[rid];hs=final[rid];qty=sum(x['qty'] for x in hs)
        assert s['signal_day']==a['signal_day'] and s['day']==a['seed_day'] and s['signal_day']<s['day']
        cashflow=sm(os,'cash_delta');div=sum((D(x.get('receivable_delta','0')) for x in eq[rid] if D(x.get('receivable_delta','0'))>0),Z);mv=sm(hs,'market_value');pnl=cashflow+div+mv
        fees=sm(os,'fee'); adds=[x for x in os if x['side']=='BUY_ADD']; sells=[x for x in os if x['side'].startswith('SELL')]
        firstholds=[h for h in holdings if h['day']==s['day'] and h['lot_id']==s['lot_id']];assert len(firstholds)==1
        factor=D(firstholds[0]['factor']);adjfill=D(s['price'])*factor
        if end==read(path/'DAY_LEDGER.json')[-1]['day']:
            near(pnl,a['marked_net_pnl'],('round_pnl',rid));near(fees,a['fees'],('round_fees',rid));assert qty==a['final_qty'] and len(adds)==a['add_count']
        slip=sum((abs(D(x['price'])-D(x['price'])/(D('1.0005') if x['side'].startswith('BUY') else D('.9995')))*x['qty'] for x in os),Z)
        out.append(dict(opportunity_key=s['sid']+'|'+s['signal_day'],round_id=rid,sid=s['sid'],name=s['name'],sector51=s['sector51'],original_signal_date=s['signal_day'],birth_type=a['birth_type'],actual_seed_OPEN=s['day'],seed_phase=s.get('allocation_phase'),seed_capital_role=s['capital_role'],seed_qty=s['qty'],seed_all_in=-D(s['cash_delta']),seed_price=s['price'],seed_factor=factor,seed_adjusted_fill=adjfill,add_count=len(adds),add_days=[x['day'] for x in adds],exit_day=max((x['day'] for x in sells),default=None) if not qty else None,exit_reasons=dict(Counter(x['reason'] for x in sells)),open_at_cutoff=bool(qty),final_qty=qty,marked_net_pnl=pnl,fees=fees,model_slippage=slip,trade_cashflow=cashflow,dividend_entitlement=div,market_value=mv,actual_orders=[x['order_seq'] for x in os]))
    assert len({x['opportunity_key'] for x in out})==len(out), 'duplicate_opportunity_key'
    return out

def account(path,end,helper):
    path=Path(path); full=read(path/'DAY_LEDGER.json');last=full[-1]['day']
    assert full[0]['day']=='2024-09-02' and [x['day'] for x in full]==sorted(set(x['day'] for x in full))
    families=['DAY_LEDGER','ORDERS','HOLDINGS','EQUITY_EVENTS','CAPITAL_LOTS','SECTOR_DAILY']
    allrows={n:read(path/(n+'.json')) for n in families}
    # Validate the full saved frontier even when comparing a shorter shared prefix.
    excluded={'EVENT_ADMISSION','ALL_TARGETS_BLOCKER_SCAN','UNCERTIFIED_DAY','BLOCKERS'}
    no_future_counts={}
    for p in path.glob('*.json'):
        if p.stem in excluded:continue
        value=read(p)
        if isinstance(value,list):
            dated=[x for x in value if isinstance(x,dict) and isinstance(x.get('day'),str)]
            assert all(x['day']<=last for x in dated),('uncertified_committed_day',p.name)
            no_future_counts[p.name]=len(dated)
    unc=read(path/'UNCERTIFIED_DAY.json') if (path/'UNCERTIFIED_DAY.json').exists() else None
    if unc:assert unc['day']>last and not unc.get('partial_orders'),('partial_day_commit',unc)
    rows={n:[x for x in v if x['day']<=end] for n,v in allrows.items()}; led=rows['DAY_LEDGER'];orders=rows['ORDERS'];holds=rows['HOLDINGS'];eq=rows['EQUITY_EVENTS'];caps=rows['CAPITAL_LOTS'];assert led[-1]['day']==end
    summary=helper.evaluate(path,end)
    summary.pop('retirement',None);summary.pop('retirement_rebuy',None)
    rules=read(RULES);proxies=read(PROTOCOL)['approved_proxy_ids'];lots={}; bought={};counts=Counter();fees_by_component_source=Counter()
    hb=bykey(holds,'day');cb=bykey(caps,'day');ob=bykey(orders,'day')
    assert [x['order_seq'] for x in orders]==list(range(1,len(orders)+1))
    for row in led:
        d=row['day']
        for o in ob[d]:
            sid=o['sid'];q=o['qty'];p=D(o['price']);buy=o['side'].startswith('BUY');side='buy' if buy else 'sell';assert isinstance(q,int) and q>0
            near(fee_calc(rules,proxies,sid,d,q,p,side),o['fee'],('dated_fee',o['order_seq']))
            qr=version(rules['quantity_versions'][sid],d,proxies)['rule'];total=sum(v['qty'] for v in lots.values() if v['sid']==sid)
            if buy:
                assert q>=qr['buy_minimum'] and (q-qr['buy_minimum'])%qr['buy_step']==0,('buy_lot_rule',o['order_seq'])
                assert o['lot_id'] not in bought
                bought[o['lot_id']]=o;lots[o['lot_id']]=dict(qty=q,sid=sid,day=d,round_id=o['round_id'])
                assert o['signal_day']<d and o.get('plan_day',o['signal_day'])<d,('buy_time',o['order_seq'])
            else:
                assert q%qr['sell_step']==0 or qr['allow_full_exit_odd'] and q==total,('sell_lot_rule',o['order_seq'],q,total)
                alloc=o.get('lot_quantities') or {lid:lots[lid]['qty'] for lid in o['lots']};assert sum(alloc.values())==q
                for lid,take in alloc.items():
                    lot=lots[lid];assert 0<take<=lot['qty'] and lot['day']<d and lot['sid']==sid and lot['round_id']==o['round_id'],('sell_inventory_T1',o['order_seq'],lid)
                    lot['qty']-=take
                lots={k:v for k,v in lots.items() if v['qty']}
            counts['fees_and_dated_quantity_orders']+=1
        hh=hb[d];cc=cb[d]
        assert {h['lot_id']:h['qty'] for h in hh}=={k:v['qty'] for k,v in lots.items()}
        assert len({c['lot_id'] for c in cc})==len(cc) and {c['lot_id'] for c in cc}=={h['lot_id'] for h in hh}
        cmap={c['lot_id']:c for c in cc}
        for h in hh:
            near(D(h['raw_mark'])*h['qty'],h['market_value'],('raw_mark',d,h['lot_id']))
            c=cmap[h['lot_id']];assert c['qty']==h['qty'] and c['bought']==h['bought'] and c['round_id']==h['round_id']
            near(c['market_value'],h['market_value'],('capital_lot_mv',d,h['lot_id']))
            assert c['frozen_qty']+c['mobile_qty']==c['qty'] and 0<=c['core_qty']<=c['frozen_qty']
            for stem in ('core','frozen','mobile'):near(D(h['raw_mark'])*c[stem+'_qty'],c[stem+'_value'],('capital_partition',d,h['lot_id'],stem))
            counts['holdings_and_capital_lots']+=1
        assert row['stocks']==len({h['sid'] for h in hh}) and row['shares']==sum(h['qty'] for h in hh)
        near(100*D(row['market_value'])/D(row['NAV']),row['weight_pct'],('weight',d))
        # Exported liquidation convention is checked independently per actual stock, not per lot.
        stock=bykey(hh,'sid');cost=Z
        for sid,hh2 in stock.items():
            q=sum(h['qty'] for h in hh2);raw=D(hh2[0]['raw_mark']);assert all(D(h['raw_mark'])==raw for h in hh2)
            cost+=raw*q-raw*D('.9995')*q+fee_calc(rules,proxies,sid,d,q,raw*D('.9995'),'sell')
        near(D(row['NAV'])-cost,row['net_liquidation_NAV'],('net_liquidation_NAV',d))
    terms=cash_event_terms(path);eqcheck=[]
    for ev in eq:
        if ev['event']!='ACCRUE_NET80':continue
        key=(ev['sid'],ev['day']);assert key in terms,('missing_cash_terms',key)
        term=terms[key];h=[x for x in holds if x['day']==term['record_date'] and x['round_id']==ev['round_id']];q=sum(x['qty'] for x in h)
        assert q==ev['record_qty'];amount=D(q)*D(term['d_cash'])*D('.8');near(amount,ev['receivable_delta'],('net80_entitlement',key))
        pays=[x for x in eq if x.get('round_id')==ev['round_id'] and x['event']=='PAY_CLOSE_NET80' and x['day']==term['pay_date']]
        if term['pay_date']<=end:near(sm(pays,'cash_delta'),amount,('net80_paid',key))
        eqcheck.append(dict(sid=ev['sid'],record_date=term['record_date'],ex_date=ev['day'],record_qty=q,net80=amount))
    rounds=round_rows(path,end,orders,holds,eq);near(sm(rounds,'marked_net_pnl'),summary['NAV']-INITIAL,'all_round_reconcile')
    summary['exposure_stats']=dict(mean_close_weight_pct=sm(led,'weight_pct')/len(led),max_close_weight_pct=max(D(x['weight_pct']) for x in led),mean_stocks=D(sum(x['stocks'] for x in led))/len(led),max_stocks=max(x['stocks'] for x in led),mean_market_value=sm(led,'market_value')/len(led),max_market_value=max(D(x['market_value']) for x in led))
    summary['rounds']=dict(total=len(rounds),closed=sum(not x['open_at_cutoff'] for x in rounds),open=sum(x['open_at_cutoff'] for x in rounds),actual_add_orders=sum(x['add_count'] for x in rounds),closed_net=sm([x for x in rounds if not x['open_at_cutoff']],'marked_net_pnl'),open_marked_net=sm([x for x in rounds if x['open_at_cutoff']],'marked_net_pnl'))
    summary['extra_checks']=dict(counts=dict(counts),no_future_log_counts=no_future_counts,uncertified_day=unc,dividends=eqcheck,fee_scope='Frozen dated research-proxy schedule, not external tariff certification',strategy_imported=False,history_executed=False)
    return summary,rounds

def entry_audit(path,end):
    decisions=read(path/'ENTRY_GATE_DECISIONS.json');events=read(path/'ENTRY_CP_EVENTS.json'); orders=[x for x in read(path/'ORDERS.json') if x['day']<=end];by=defaultdict(list);evby=defaultdict(list)
    for x in decisions:
        if x['day']<=end and x.get('original_signal_day'):by[x['sid']+'|'+x['original_signal_day']].append(x)
        if x.get('G') is not None and x['phase']=='CLOSE' and x['allocation_phase']=='MATURE':
            expect=1 if 1 in (x['F'],x['CP_state']) else -1 if -1 in (x['F'],x['CP_state']) else 0
            assert x['G']==expect,('three_state_gate',x)
    for x in events:
        if x['day']<=end:evby[x['sid']+'|'+x['original_signal_day']].append(x)
    checked=[]
    for o in orders:
        if o['side']!='BUY_SEED':continue
        key=o['sid']+'|'+o['signal_day'];plans=[x for x in by[key] if x['phase']=='CLOSE' and x['day']==o['plan_day'] and x.get('G') is not None];assert len(plans)==1,('missing_entry_plan',o['order_seq'])
        plan=plans[0];assert plan['allocation_phase']==o['allocation_phase']
        if o['allocation_phase']=='MATURE':assert plan['G']==1
        evidence=o.get('entry_evidence_id')
        if plan['F']!=1 and o['allocation_phase']=='MATURE':
            assert evidence and evidence==plan['entry_evidence_id']
            creates=[x for x in evby[key] if x['event']=='CREATED' and x['entry_evidence_id']==evidence];assert len(creates)==1
            assert o['signal_day']<=creates[0]['day']<=o['plan_day']<o['day']
            bad=[x for x in evby[key] if x.get('entry_evidence_id')==evidence and x['event'] in ('INVALIDATED','UNKNOWN_GAP') and (x['day']<o['day'] or x['day']==o['day'] and x['phase']=='OPEN')]
            assert not bad,('invalid_entry_evidence_at_fill',o['order_seq'],bad)
        checked.append(dict(order_seq=o['order_seq'],opportunity_key=key,day=o['day'],phase=o['allocation_phase'],F=plan['F'],CP_state=plan['CP_state'],entry_evidence_id=evidence))
    for h in read(path/'HOLDINGS.json'):
        assert not str(h.get('cp_id','')).startswith('ENTRY_CP:'),'entry_evidence_leaked_to_active_CP'
    states={}
    for key in set(by)|set(evby):
        ds=by[key];es=evby[key];terminal=[e for e in es if e['event'] in ('CANCELLED','CONSUMED')];state=terminal[-1]['event'] if terminal else (ds[-1]['result'] if ds else 'LIVE_NO_DECISION')
        states[key]=dict(status=state,last_decision=ds[-1] if ds else None,terminal=terminal[-1] if terminal else None,first_ready_CLOSE=next((x['day'] for x in ds if x.get('G')==1),None),structure_wait_days=len({x['day'] for x in ds if x['result'] in ('STRUCTURE_WAIT','STRUCTURE_PAUSED_UNKNOWN')}))
    return dict(actual_seed_checks=len(checked),mature_seed_checks=sum(x['phase']=='MATURE' for x in checked),decision_counts=dict(Counter(x['result'] for x in decisions)),actual_seed_rows=checked),states

def compare(base_rounds,candidate_rounds,end,states):
    sealed=read(TAIL/'ALL_OPPORTUNITIES.json');membership=read(TAIL/'COHORT_OPPORTUNITY_MEMBERSHIP.json');ranked=read(TAIL/'CLOSED_POSITIVE_RANKING.json');assert len(sealed)==1677
    b={x['opportunity_key']:x for x in base_rounds};c={x['opportunity_key']:x for x in candidate_rounds};cal=[x['day'] for x in read(BASE/'DAY_LEDGER.json')];idx={d:i for i,d in enumerate(cal)}
    rows=[]
    for old in sealed:
        key=old['opportunity_key'];a=b.get(key);new=c.get(key);eligible=a is not None
        row=dict(opportunity_key=key,name=old['name'],sid=old['sid'],sector51=old['sector51'],baseline_original_signal=old['original_signal_date'],baseline_seed_OPEN=old['actual_seed_OPEN'],baseline_sealed_final_pnl=old['marked_net_pnl'],baseline_within_common_frontier=eligible,candidate_captured=new is not None,candidate_seed_OPEN=new['actual_seed_OPEN'] if new else None,candidate_status='FILLED' if new else states.get(key,{}).get('status','NO_CANDIDATE_OPPORTUNITY_EVIDENCE'),candidate_path_state=states.get(key),baseline_common_pnl=a['marked_net_pnl'] if a else None,candidate_actual_pnl=new['marked_net_pnl'] if new else Z,baseline_open_at_common_end=a['open_at_cutoff'] if a else None,candidate_open_at_common_end=new['open_at_cutoff'] if new else None,candidate_add_count=new['add_count'] if new else 0,baseline_add_count=a['add_count'] if a else None,baseline_add_days=a['add_days'] if a else None,candidate_add_days=new['add_days'] if new else [],candidate_exit_day=new['exit_day'] if new else None,baseline_exit_day=a['exit_day'] if a else None)
        if a and new:
            row.update(delay_trading_sessions=idx[new['actual_seed_OPEN']]-idx[a['actual_seed_OPEN']],actual_adjusted_fill_spread_pct=100*(new['seed_adjusted_fill']/a['seed_adjusted_fill']-1),actual_pnl_delta=new['marked_net_pnl']-a['marked_net_pnl'],baseline_seed_qty=a['seed_qty'],candidate_seed_qty=new['seed_qty'],candidate_actual_orders=new['actual_orders'],candidate_exit_reasons=new['exit_reasons'])
        rows.append(row)
    rb={r['opportunity_key']:r for r in rows}; summaries=[]
    cutoffs={'SEPT_STARTUP_SEED_OPEN_0923_0930':'2024-09-30','PV_SEED_OPEN_1023_1029':'2024-10-29'}
    for name,members in bykey(membership,'cohort').items():
        rs=[rb[x['opportunity_key']] for x in members];eligible=[x for x in rs if x['baseline_within_common_frontier']];capt=[x for x in eligible if x['candidate_captured']];miss=[x for x in eligible if not x['candidate_captured']];deadline=min(end,cutoffs.get(name,end));delays=[x['delay_trading_sessions'] for x in capt];win=[x for x in eligible if x['baseline_open_at_common_end'] is False and D(x['baseline_common_pnl'])>0];loss=[x for x in eligible if x['baseline_open_at_common_end'] is False and D(x['baseline_common_pnl'])<0]
        fixedtop=[x for x in ranked if x['cohort']==name and x['in_top10pct_positive']];topkeys={x['opportunity_key'] for x in fixedtop};toprs=[x for x in eligible if x['opportunity_key'] in topkeys]
        summaries.append(dict(cohort=name,fixed_sealed_count=len(rs),baseline_common_frontier_count=len(eligible),baseline_not_yet_reached=len(rs)-len(eligible),captured=len(capt),capture_pct=100*D(len(capt))/len(eligible) if eligible else None,captured_by_original_window_end=sum(x['candidate_seed_OPEN']<=deadline for x in capt),original_window_end=deadline,delayed=sum(x>0 for x in delays),same_day=sum(x==0 for x in delays),earlier=sum(x<0 for x in delays),max_delay_sessions=max(delays,default=None),mean_delay_sessions=D(sum(delays))/len(delays) if delays else None,miss_status=dict(Counter(x['candidate_status'] for x in miss)),baseline_pnl=sm(eligible,'baseline_common_pnl'),candidate_actual_pnl_on_fixed_keys=sm(eligible,'candidate_actual_pnl'),captured_baseline_winner_pnl=sm([x for x in win if x['candidate_captured']],'baseline_common_pnl'),baseline_winner_pnl=sm(win,'baseline_common_pnl'),fixed_top_positive_count=len(fixedtop),fixed_top_captured=sum(x['candidate_captured'] for x in toprs),fixed_top_baseline_pnl=sm(toprs,'baseline_common_pnl'),fixed_top_candidate_actual_pnl=sm(toprs,'candidate_actual_pnl'),baseline_negative_closed_count=len(loss),negative_closed_captured=sum(x['candidate_captured'] for x in loss),negative_closed_baseline_pnl=sm(loss,'baseline_common_pnl'),negative_closed_candidate_actual_pnl=sm(loss,'candidate_actual_pnl'),missed_baseline_pnl_reference_only=sm(miss,'baseline_common_pnl'),candidate_open_on_fixed_keys=sum(x['candidate_open_at_common_end'] is True for x in eligible)))
    new=[x for x in candidate_rounds if x['opportunity_key'] not in {z['opportunity_key'] for z in sealed}]
    # Reconcile all actual candidate cash effects. No rejected-baseline PnL is counted as earned cash.
    fixed_actual=sm([x for x in rows if x['candidate_captured']],'candidate_actual_pnl');near(fixed_actual+sm(new,'marked_net_pnl'),sm(candidate_rounds,'marked_net_pnl'),'fixed_plus_candidate_new')
    winner_rows=[dict(cohort=x['cohort'],fixed_positive_rank=x['positive_rank'],fixed_in_top_decile=x['in_top10pct_positive'],**rb[x['opportunity_key']]) for x in ranked]
    return rows,summaries,new,winner_rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path);ap.add_argument('--status',type=Path);ap.add_argument('--baseline-check',action='store_true');args=ap.parse_args()
    assert args.baseline_check or args.candidate,'Select baseline preparation or an explicit completed output directory'
    sources_before={str(p):sha(p) for p in [HELPER,RULES,PROTOCOL,TAIL/'ALL_OPPORTUNITIES.json',TAIL/'CLOSED_POSITIVE_RANKING.json',TAIL/'COHORT_OPPORTUNITY_MEMBERSHIP.json',R/'mainline_structural_maturity_design_v1/DESIGN.md']}
    tree=ast.parse(HELPER.read_text());assert not any(isinstance(n,(ast.Import,ast.ImportFrom)) and ('engine' in ast.unparse(n) or 'Data' in ast.unparse(n)) for n in ast.walk(tree))
    sp=importlib.util.spec_from_file_location('reviewed_saved_accounting_helper',HELPER);helper=importlib.util.module_from_spec(sp);sp.loader.exec_module(helper)
    hashes={'M7':verify_hashes(BASE)}
    for n,v in read(TAIL/'OUTPUT_SEAL.json').items():assert sha(TAIL/n)==v,('tail_seal',n)
    for p,v in read(TAIL/'SOURCE_HASHES.json').items():assert sha(p)==v,('tail_source',p)
    if args.baseline_check:
        summary,rounds=account(BASE,'2025-01-20',helper);assert summary['days']==93 and summary['trading']['orders']==3596;near(summary['NAV'],'1275326.0427500672225','known_baseline_nav')
        sealed={x['opportunity_key']:x for x in read(TAIL/'ALL_OPPORTUNITIES.json')};assert len(rounds)==1677
        for x in rounds:near(x['marked_net_pnl'],sealed[x['opportunity_key']]['marked_net_pnl'],('fixed_baseline_round',x['opportunity_key']))
        save('PREPARATION_BASELINE_CHECK',dict(verdict='PASS',hashes=hashes,summary=summary,helper_sha256=sha(HELPER),audit_sha256=sha(__file__),fixed_counts={x['cohort']:x['total_rounds'] for x in read(TAIL/'BASELINE_SUMMARY.json')},sources=sources_before,history_executed=False));print('PREPARATION_PASS: baseline accounting, fee rules, lots, dividends and fixed opportunity identities verified; waiting for candidate saved outputs.');return
    path=args.candidate.resolve();assert path!=BASE and path.exists();hashes['V11']=verify_hashes(path)
    cend=read(path/'DAY_LEDGER.json')[-1]['day'];bend=read(BASE/'DAY_LEDGER.json')[-1]['day'];end=min(cend,bend);assert cend<='2025-01-20'
    status=read(args.status) if args.status else None
    if status:
        assert status['last']==read(path/'DAY_LEDGER.json')[-1] and status['days']==len(read(path/'DAY_LEDGER.json')) and status['orders']==len(read(path/'ORDERS.json'))
    a,ar=account(path,end,helper);b,br=account(BASE,end,helper);entry,states=entry_audit(path,end);rows,cohorts,new,winners=compare(br,ar,end,states)
    delta={k:a[k]-b[k] for k in ['NAV','profit','return_pct','cash','market_value','max_close_drawdown_pct']}
    save('M7_COMMON_ROUNDS',br);save('V11_ACTUAL_ROUNDS',ar);save('FIXED_OPPORTUNITY_COMPARISON',rows);save('FIXED_COHORT_SUMMARY',cohorts);save('CANDIDATE_NEW_OPPORTUNITIES',new);save('FIXED_WINNER_COMPARISON',winners);save('CANDIDATE_OPEN_ROUNDS',[x for x in ar if x['open_at_cutoff']]);save('ENTRY_EVIDENCE_AUDIT',entry)
    result=dict(verdict='PASS_SAVED_OUTPUT_ACCOUNTING',common_end=end,full_target_completed=cend=='2025-01-20',candidate_output=str(path),run_status=status,hashes=hashes,V11=a,M7=b,delta=delta,cohorts=cohorts,new_opportunities=dict(count=len(new),actual_net=sm(new,'marked_net_pnl')),sources=sources_before,limits=['Observed development window, not OOS, PIT or production proof.','Fixed baseline winners and losing rounds are evaluation labels, never signals.','Missed baseline net PnL is an opportunity reference, not earned candidate cash. Actual NAV includes funded entry, ADD, exit and redistribution effects.','Gate diagnostic waiting-price spreads are not fills; this report uses actual saved orders and holding factors for actual fill-price comparisons.','Open rounds remain marked, not invented terminal sales. Fee schedules retain original approved research-proxy limits.'])
    save('INDEPENDENT_V11_VS_M7',result)
    save('AUDIT_SEAL',dict(audit_sha256=sha(__file__),helper_sha256=sha(HELPER),inputs=sources_before,outputs={p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='AUDIT_SEAL.json'}))
    print(json.dumps(dict(common_end=end,delta=delta,V11_orders=a['trading']['orders'],M7_orders=b['trading']['orders'],cohorts=cohorts),ensure_ascii=False,default=str))
if __name__=='__main__':main()
