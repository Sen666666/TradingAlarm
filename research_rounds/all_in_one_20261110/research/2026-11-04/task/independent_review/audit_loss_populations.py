"""Saved full-population/receipt/retry/mobile-core audit, no model execution."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import gzip,hashlib,importlib.util,json
HERE=Path(__file__).parent;R=HERE.parent/'loss_correction/absolute_loss_2022_2023'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sp=importlib.util.spec_from_file_location('ro_marks',HERE/'audit_pvr_saved.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
summary=read(R/'STRUCTURE_POPULATION_SUMMARY.json');mobilepub=read(R/'MOBILE_CYCLE_SUMMARY.json')
bindings=[read(R/n)for n in ['SOURCE_BINDING-PHASE1.json','SOURCE_BINDING-PHASE2.json','SOURCE_BINDING-MOBILE-CYCLES.json']]
sources={}
for b in bindings:
    for p,h in b['sources'].items():assert p not in sources or sources[p]==h;sources[p]=h
assert all(sha(p)==h for p,h in sources.items())
manifests={y:{r['sid']:r for r in read(m.W/path)}for y,path in [('2022','2022-normal-reference-20261031/inputs/MANIFEST.json'),('2023','recovery-2023-readiness-20261101/inputs/MANIFEST.json')]}
out={}
for scope,root,end,campfile,campkey in [('2022_2023',HERE.parent/'pvr_pool_feasibility/continuation2023/run-2023','2023-12-29','PVR_2023_INDEPENDENT_AUDIT_CAMPAIGNS.json','PVR_NO_CONFIRMED60'),('strong',HERE.parent/'pvr_pool_feasibility/runs/2025_26','2026-06-30','PVR_2025_26_INDEPENDENT_AUDIT_CAMPAIGNS.json','PVR_NO_CONFIRMED60')]:
    joined=read(R/('PVR_NO60-'+scope+'-JOINED_ENTRIES.json'));jm={r['layer']:r for r in joined}
    b=json.loads(gzip.decompress((root/'pair/B.json.gz').read_bytes()));buy={t['layer']:t for t in b['trades']if t['side']=='buy'}
    assert set(jm)==set(buy)=={l['id']for l in b['layers']}
    native={l['id']:l for l in b['layers']};role={j['layer']:j['role']for j in b['journal']if j['kind']=='real_buy_fill'}
    receipts={};allmobile=0
    for sid in {x['sid']for x in joined}:
        for year in {x['signal_day'][:4]for x in joined if x['sid']==sid and x['receipt']}:
            rr=manifests[year][sid]if year in manifests else None
            p=rr['output_path']if rr else m.SM[sid]['refs']['receipts'];h=rr['output_sha256']if rr else m.SM[sid]['output_sha256'][p]
            assert sha(p)==h;receipts.update({r['receipt_id']:r for r in read(p)})
    for x in joined:
        t=buy[x['layer']];l=native[x['layer']]
        assert x['role']==role[x['layer']]and x['opened']==t['at']and x['signal_at']==l['signal_at']
        assert abs(D(x['cost'])-D(t['gross_cny'])-D(t['fees_cny']))<D('1e-8')
        value=D(l['qty'])*m.price(l['sid'],end)if l['qty']else D(0)
        assert abs(D(x['net'])-(D(l['cash'])+D(l['dividend'])+value))<D('1e-8')
        actual_reasons=sorted({p['reason']for t in b['trades']if t['side']=='sell'for p in t['parts']if p['layer']==x['layer']})
        assert actual_reasons==x['actual_sale_reason_set']
        if x['receipt']:
            allmobile+=1;assert x['canonical_receipt']==receipts[x['receipt']]
            assert x['canonical_receipt']['canonical_series']==x['sid']and x['canonical_receipt']['confirmed_day']==x['signal_day']and not x['canonical_receipt']['trace_unknown']
    assert allmobile==summary[scope]['actual_mobile_layers']==summary[scope]['independent_CP1_ids']
    # Past-only memo checks distinguish genuine new receipts in one CP1 epoch.
    for sid in {x['sid']for x in joined}:
        seen={k:set()for k in ['cached_E0_epoch','cached_I_epoch','financial_stock_industry_attempt','canonical_stock_industry_attempt']};cp={}
        for x in sorted((r for r in joined if r['sid']==sid),key=lambda r:r['opened']):
            for key,flag in [('cached_E0_epoch','reentry_same_cached_E0'),('cached_I_epoch','reentry_same_cached_I'),('financial_stock_industry_attempt','reentry_same_financial_industry_attempt'),('canonical_stock_industry_attempt','reentry_same_canonical_industry_attempt')]:
                assert x[flag]==(x['action']=='fresh_reentry_after_actual_flat'and x[key]is not None and x[key]in seen[key])
                if x[key]is not None:seen[key].add(x[key])
            epoch=x['CP1_original_E0_episode'];assert x['repeat_mobile_same_CP1_E0']==(epoch is not None and epoch in cp)
            if epoch:
                if epoch in cp:
                    first=cp[epoch]
                    assert x['price_above_first_actual_signal_same_CP1_E0']==(D(x['signal_continuous_close'])>D(first['signal_continuous_close']))
                    assert x['CP1_candidate_above_first_actual_signal_same_CP1_E0']==(D(str(x['CP1_candidate']))>D(str(first['CP1_candidate'])))
                else:cp[epoch]=x
    # Independent actual-role share replay. A surviving ID, not ever-core,
    # proves continuous core ownership across a mobile-clearance gap.
    q=defaultdict(int);sids={};lastcore={};mobilecycle=Counter();classes={};groups=defaultdict(list)
    events=[(t['at'],1,k,'trade',t)for k,t in enumerate(b['trades'])]+[(s['at'],0,k,'split',s)for k,s in enumerate(b['audit'])if s['kind']=='split']
    for at,_,_,kind,t in sorted(events,key=lambda z:z[:3]):
        if kind=='split':
            for lid,v in list(q.items()):
                if sids[lid]==t['sid']and v:assert D(v)*D(t['ratio'])==int(D(v)*D(t['ratio']));q[lid]=int(D(v)*D(t['ratio']))
            continue
        sid=t['security_id']
        if t['side']=='buy':
            lid=t['layer'];cores={k for k,v in q.items()if v and sids[k]==sid and role[k]=='core'}
            mobiles=sum(v for k,v in q.items()if sids[k]==sid and role[k]=='mobile')
            assert sum(v for k,v in q.items()if sids[k]==sid)==jm[lid]['quantity_before']
            if role[lid]=='mobile':
                cls='expand_existing_live_mobile_sleeve'if mobiles else'refill_mobile_after_mobile_flat_with_core_surviving'if cores&lastcore.get(sid,set())else'first_mobile_on_existing_core'if cores else'flat_whole_stock_fresh_mobile'
                if not mobiles:mobilecycle[sid]+=1
                classes[lid]=cls;groups[(sid,mobilecycle[sid])].append(lid)
            q[lid]=t['shares'];sids[lid]=sid
        else:
            before=sum(v for k,v in q.items()if sids[k]==sid and role[k]=='mobile')
            for p in t['parts']:q[p['layer']]-=p['shares'];assert q[p['layer']]>=0
            if before and not any(v for k,v in q.items()if sids[k]==sid and role[k]=='mobile'):
                lastcore[sid]={k for k,v in q.items()if v and sids[k]==sid and role[k]=='core'}
    assert all(q[l['id']]==l['qty']for l in b['layers'])
    me=read(R/('PVR_NO60-'+scope+'-MOBILE_CYCLE_ENTRIES.json'))
    assert {x['layer']:x['actual_mobile_entry_class']for x in me}==classes
    refill=[ids for ids in groups.values()if classes[ids[0]]=='refill_mobile_after_mobile_flat_with_core_surviving']
    assert len(refill)==mobilepub[scope]['refill_cycles_while_core_survives']
    net=sum((D(jm[l]['net'])for ids in refill for l in ids),D(0));cost=sum((D(jm[l]['cost'])for ids in refill for l in ids),D(0))
    assert abs(net-D(mobilepub[scope]['refill_cycle_net']))<D('1e-8')and abs(cost-D(mobilepub[scope]['refill_cycle_buy_cash']))<D('1e-8')
    # Match earliest terminal-tail stock controls to independently built whole
    # stock campaigns; active/claim labels cannot be called cash realization.
    cc=read(HERE/campfile)[campkey];tails={}
    for c in cc:
        if D(c['contribution'])/D(c['buy_cost'])>=D('.3')and c['sid']not in tails:tails[c['sid']]=c
    published=read(R/('PVR_NO60-'+scope+'-TAIL_PREDECESSORS.json'))
    assert {x['sid']for x in published}==set(tails)
    for x in published:
        c=tails[x['sid']];status='cashclosed'if c['cash_closed']else'flat_unpaid_claim'if not c['remaining']else'marked_active'
        assert x['tail_status']==status
        prior=[z for z in cc if z['sid']==x['sid']and z['opened']<c['opened']and D(z['contribution'])<0]
        assert len(prior)==x['prior_negative_campaigns']
        assert abs(sum((D(z['contribution'])for z in prior),D(0))-D(x['prior_negative_net']))<D('1e-8')
    out[scope]=dict(passed=True,all_layers=len(joined),actual_canonical_mobile_receipts=allmobile,all_actual_sell_reason_sets_exact=True,
        past_structure_progress_flags_checked=True,strict_same_live_core_ID_mobile_replay_checked=True,refill_cycles=len(refill),refill_cycle_net=net,
        earliest_terminal_tail_unique_stock_controls=len(tails),tail_status_counts=dict(Counter(x['tail_status']for x in published)))
out.update(source_SHA_checks=len(sources),reviewer_account_events=0,reviewer_source_SHA256=sha(__file__),
    scope='Current v2 only; superseded ever-core v1 excluded. Structure/receipt grouping source reviewed; no I/CP1 numeric recomputation or visual-chart judgment. Monetary base and actual role/reason/quantity/continuous-core identities independently checked. Repeated states, higher-price CP1 cohorts, terminal tails and prior failures are descriptive, dependent observations, not avoidable loss or a new gate. Active/AR tails are not cashclosed campaigns.')
(HERE/'PVR_ABSOLUTE_LOSS_POPULATION_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
print(json.dumps(out,indent=2,default=str))
