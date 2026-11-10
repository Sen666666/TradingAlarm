"""Additional fixed-state adapter checks; never advance a complete new strategy phase."""
from pathlib import Path
from decimal import Decimal as D
import copy,json,pickle,types
import compound_bridge_v1 as E
import report_compound_halt_v1 as REPORT
import compound_equity_v1 as M
Layer=E.A.native.base.Layer
ZERO=D(0)
def run(b,saved,out,passed,checkpoint_separate=False):
    sid='000987.SZ';rid='2022|A_UNION_B_SHARED_ENGINEERING_V1|000987.SZ|2'
    day=b.s.pd.Timestamp('2022-06-23')
    def restore():
        b.restore_runtime(saved);return b.states[sid]
    def isolated_report(target=b):
        s=target.s;st=s.archives[rid];proxy=copy.copy(target);source=types.SimpleNamespace(**s.__dict__)
        source.actions=[x for x in s.actions if x['round_id']==rid]
        source.archives={rid:st};source.claims={k:v for k,v in s.claims.items() if v['owner_round_id']==rid}
        proxy.s=source;proxy.share_ledger=copy.deepcopy(target.share_ledger)
        for x in proxy.share_ledger:x['action_index']=sum(a['round_id']==rid for a in s.actions[:x['action_index']])
        return REPORT.reports(proxy,day)
    def add_variant(close_before_record=False):
        st=restore();s=b.s;d=s.pd.Timestamp('2022-06-20');q=200
        px=D(str(s.raw[sid].get(d)['raw_open']))*(1+s.SLIP);_,fs,pa=s.getmeta(sid,d);fee=s.fee(q,px,fs,'buy',pa)
        cost=D(q)*px+fee;uid=rid+'|SYNTHETIC_ADD_FIXTURE'
        a=dict(round_id=rid,window='2022',arm=E.ARM,sid=sid,day='2022-06-20',side='buy_add',q=q,
          price=float(px),fee=float(fee),reason='SYNTHETIC_LAYER_FIXTURE_NOT_HISTORICAL_TRADE',
          execution_action_id=uid,execution_domain='SYNTHETIC_ADAPTER_FIXTURE')
        s.actions.append(a);b.action_ids.add(uid)
        layer=Layer(uid,rid,sid,'add',q,d,cost,next(x.first_fill_id for x in b.layers if x.round_id==rid))
        b.layers.append(layer)
        st['cash']-=cost;st['spent']+=cost;st['fees']+=fee
        st.update(add=q,added=True,added_q=q,add_attempts=1)
        if close_before_record:
            d=s.pd.Timestamp('2022-06-21');px=D(str(s.raw[sid].get(d)['raw_open']))*(1-s.SLIP)
            _,fs,pa=s.getmeta(sid,d);fee=s.fee(q,px,fs,'sell',pa);sell_uid=uid+'|CLOSED'
            s.actions.append(dict(round_id=rid,window='2022',arm=E.ARM,sid=sid,day='2022-06-21',
                side='sell_add',q=q,price=float(px),fee=float(fee),reason='SYNTHETIC_PRE_RECORD_EXIT',
                execution_action_id=sell_uid,execution_domain='SYNTHETIC_ADAPTER_FIXTURE'))
            b.action_ids.add(sell_uid);st['cash']+=D(q)*px-fee;st['fees']+=fee;st['add']=0;layer.qty=0
        key=('2022',E.ARM,sid,E.COMPOUND_ID);qrec=st['core']+st['add']
        for obj in (s.snapshots[key],s.claims[key]):
            obj.update(record_q=qrec,core_record_q=st['core'])
        s.claims[key].update(amount=D(qrec)*D('.2')*D('.8'),core_amount=D(st['core'])*D('.2')*D('.8'))
        b.share_registrations[(E.COMPOUND_ID,rid)]=M.register_layers(b._mechanical_event(),st,b.layers,s.pd.Timestamp('2022-06-22'))
        return st,layer,cost

    theory=(D('9.39')-D('.2'))/D('1.35')
    old_value=D(300)*D('9.39');post=D(405)*theory+D(48)-D(21)
    assert old_value==D(2817) and post==D(2784) and old_value-post==D(33)
    assert D(405)*D('6.7')-D(405)*theory==D('-43.5')
    assert D(405)*D('6.7')+D(48)-D(21)-D('2796.614682786500')==D('-56.114682786500')
    passed('synthetic_theoretical_ex_value_loss_exact_cash_haircut12_plus_stock_haircut21')

    # Active ADD allocation and an invalid partial odd-lot exit, then full allowed exit.
    st,layer,cost=add_variant(False);s=b.s;before=(st['cash'],st['spent'],st['fees'],b.cash())
    b._stage(day,'OPEN');b._compound_open_preamble(day)
    assert (st['core'],st['add'],layer.qty)==(405,270,270)
    assert st['research_stock_tax_total']==35 and b.research_tax_total()==35 and b.cash()==before[3]-35
    assert st['spent']==before[1] and st['fees']==before[2] and layer.cost==cost
    assert sorted((x['kind'],x['research_stock_tax']) for x in b.share_ledger)==[('add',D(14)),('core',D(21))]
    post=b.capture_runtime();st['addexitpending']=True;st['exitpending']=None
    n=len(s.actions);b._callback('source_exit_only')(b.states,sid,st,day,b.last_close)
    assert len(s.actions)==n and b.states[sid]['unknown_reason']=='ODD_ADD_EXIT_PATH_UNKNOWN'
    assert st['core']==405 and st['add']==270 and b.research_tax_total()==35
    b.restore_runtime(post);st=b.states[sid];st['exitpending']='SYNTHETIC_FULL_EXIT_WITH_ADD';n=len(s.actions)
    b._callback('source_exit_only')(b.states,sid,st,day,b.last_close);b._record_new_actions(n,day)
    assert s.actions[-1]['q']==675 and st['core']==st['add']==0
    s.pay_day(E.ARM,day);s.finalize()
    r=isolated_report()
    assert r['rounds'][0]['research_stock_tax_total']==35
    assert {x['layer']:x['research_stock_tax'] for x in r['layers']}=={'core':D(21),'add':D(14)}
    assert sum(x['NET80'] for x in r['layers'])==r['rounds'][0]['whole_round_NET80']
    assert sum(x['exact_whole_order_fee'] for x in r['exact_trade_journal'])==st['fees']
    (out/'SYNTHETIC_CORE_ADD_REPORT.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n')
    passed('real_adapter_synthetic_active_ADD_tax_21_14_partial_odd_reject_full675_exit_fee_once')

    # Already-closed ADD never receives new stock/tax/claim and retains its settled report.
    st,closed_layer,cost=add_variant(True);s=b.s;before_qty=closed_layer.qty;closed_cost=closed_layer.cost
    b._stage(day,'OPEN');b._compound_open_preamble(day)
    assert st['core']==405 and st['add']==0 and closed_layer.qty==before_qty==0 and closed_layer.cost==closed_cost
    assert len(b.share_ledger)==1 and b.share_ledger[0]['kind']=='core' and b.research_tax_total()==21
    assert s.claims[('2022',E.ARM,sid,E.COMPOUND_ID)]['amount']==48
    b.states[sid]=dict(state='UNKNOWN',round_id=rid,unknown_reason='SYNTHETIC_ASSET_UNKNOWN')
    r=isolated_report();add=next(x for x in r['layers'] if x['layer']=='add')
    assert r['rounds'][0]['status']=='ASSET_UNKNOWN' and add['layer_status']=='EXECUTION_AND_SETTLEMENT_CLOSED'
    assert add['research_stock_tax']==0 and add['NET80'] is not None
    add_net=add['NET80'];b.states[sid]=dict(st,state=E.HALT,halt_session=day)
    r=isolated_report();add=next(x for x in r['layers'] if x['layer']=='add')
    assert r['rounds'][0]['status']=='KNOWN_HALT_UNCERTIFIED'
    assert add['layer_status']=='EXECUTION_AND_SETTLEMENT_CLOSED' and add['NET80']==add_net
    passed('real_adapter_closed_ADD_zero_qty_not_issued_taxed_or_poisoned_by_round_UNKNOWN_or_HALT')

    # Deliberately wrong old-round registration must not issue to the new live round.
    st=restore();b._stage(day,'OPEN');reg=b.share_registrations[(E.COMPOUND_ID,rid)]
    reg['owner_round_id']='SYNTHETIC_ALREADY_CLOSED_OLD_ROUND'
    before=(st['core'],st['cash'],len(b.share_ledger),b.research_tax_total())
    try:b._prepare_compound(st,day)
    except M.Unsupported as err:assert str(err)=='EX_OWNER_MISMATCH'
    else:raise AssertionError('Old round identity transferred to new owner')
    assert before==(st['core'],st['cash'],len(b.share_ledger),b.research_tax_total())
    passed('old_registered_round_identity_cannot_transfer_stock_or_tax_to_new_round')

    if checkpoint_separate:
        restore();return

    # Actual pre/post-ex serialization. A fresh adapter reconstructs bound source functions.
    st=restore();prefix_bytes=pickle.dumps(b.capture_runtime(),protocol=5)
    fresh_s=E.bridge.load_original('2022');fresh=E.ExecutionBridge(fresh_s,halt_evidence=E.AnnualHalts())
    prefix=pickle.loads(prefix_bytes)
    # Independent source function/state construction; share only verified immutable market caches
    # to avoid duplicating multiple GiB during a fixture. This is not an independent raw-data reload.
    for field in ('raw','facts','cp','capacity'):
        setattr(fresh_s,field,dict(getattr(b.s,field)))
    assert set(prefix['union']['loaded_sids'])<=set(fresh_s.raw)
    fresh.restore_runtime(prefix)
    assert fresh_s.before_held.__self__ is fresh and fresh_s.coordinate_matches.__self__ is fresh
    assert fresh.states[sid] is fresh_s.archives[rid]
    assert fresh._native_accrue_day.__globals__['claims'] is fresh_s.claims
    assert fresh._native_accrue_day.__globals__['archives'] is fresh_s.archives
    assert fresh._claims_for(rid)[-1] is fresh_s.claims[('2022',E.ARM,sid,E.COMPOUND_ID)]
    assert E.structural_digest(fresh.capture_runtime())==E.structural_digest(prefix)
    fresh._stage(day,'OPEN');fresh._compound_open_preamble(day)
    post=fresh.capture_runtime()
    path=out/'POST_EX_CHECKPOINT.pkl'
    with path.open('xb') as f:pickle.dump(post,f,protocol=5)
    with path.open('rb') as f:post_load=pickle.load(f)
    fresh.restore_runtime(post_load)
    assert fresh.states[sid] is fresh_s.archives[rid]
    assert fresh._native_accrue_day.__globals__['claims'] is fresh_s.claims
    assert fresh._native_accrue_day.__globals__['archives'] is fresh_s.archives
    assert fresh._claims_for(rid)[-1] is fresh_s.claims[('2022',E.ARM,sid,E.COMPOUND_ID)]
    assert fresh_s.before_held.__self__ is fresh and fresh_s.coordinate_matches.__self__ is fresh
    assert E.structural_digest(fresh.capture_runtime())==E.structural_digest(post_load)
    assert fresh.states[sid]['core']==405 and fresh.research_tax_total()==21
    before=E.structural_digest(fresh.capture_runtime())
    try:fresh._prepare_compound(fresh.states[sid],day)
    except M.Unsupported as err:assert str(err)=='DUPLICATE_EQUITY_EVENT'
    else:raise AssertionError('Duplicate ex effect accepted after checkpoint')
    assert E.structural_digest(fresh.capture_runtime())==before
    assert fresh_s.claims[('2022',E.ARM,sid,E.COMPOUND_ID)]['recognized']
    fresh_s.pay_day(E.ARM,day);paid=fresh.cash();fresh_s.pay_day(E.ARM,day)
    assert fresh.cash()==paid and fresh.research_tax_total()==21
    passed('fresh_adapter_pre_and_post_ex_checkpoint_restore_bindings_identity_no_duplicate_stock_tax_or_pay')
    restore()
