import ast, copy, importlib, json, sys, unittest
from pathlib import Path
from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace
import pandas as pd
import compound_equity_v1 as c

ROOT=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
ORIGINAL=ROOT/"m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/engine.py"
sys.path.insert(0,"/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code")
from sector_account import QuantityRule

def fixture(add=0):
    e=c.Event("SYNTH_EVENT","fixture_version","SYNTH","2022-06-16T23:59:59.999999+08:00",
              "2022-06-22","2022-06-23","2022-06-23","2022-06-23","2022-06-23",".2",".2",".35","1.35")
    st=dict(state="HELD",sid="SYNTH",round_id="ROUND",arm="ARM",core=300,add=add,
            fac=D("2"),factor=2.,origin=("source","path","segment"),cash=D("-2796.61"),
            receivable=D(0),dividend_total=D(0),dividend_paid=D(0),spent=D("2796.61"),
            fees=D("5.21"),initial_fee=D("5.21"),added=bool(add),added_q=add,
            add_attempts=int(bool(add)),exitpending=None,addexitpending=False,
            addpending=D("8"),addfloor=D("7"),first_fill_id="FIRST",cp_identity="UNCHANGED")
    layers=[SimpleNamespace(layer_id="CORE",round_id="ROUND",sid="SYNTH",kind="core",qty=300,
              opened=pd.Timestamp("2022-06-17"),cost=D("2796.61"),first_fill_id="FIRST")]
    if add:
        layers.append(SimpleNamespace(layer_id="ADD",round_id="ROUND",sid="SYNTH",kind="add",qty=add,
                     opened=pd.Timestamp("2022-06-20"),cost=D("1000"),first_fill_id="FIRST"))
    obs=dict(day="2022-06-23",previous_day="2022-06-22",raw_open="6.7",
             previous_raw_close="9.39",previous_factor="2",
             factor=D("2")*D("1.35")*D("9.39")/(D("9.39")-D(".2")),
             previous_origin=st["origin"],origin=st["origin"])
    tax=c.TaxBinding("EXPLICIT_SYNTH", "a"*64,"EXPLICIT_RESERVE",".2",
                     "SYNTHETIC_ONLY","EXPLICIT_TEST_NO_POSTING","EXPLICIT_TEST_RESERVE","EXPLICIT_TEST_RESERVE")
    return e,st,layers,obs,tax

def plan(e,st,layers,obs,tax,index=1,applied=None):
    reg=c.register_layers(e,st,layers,"2022-06-22")
    return c.prepare_ex(e,reg,st,layers,obs,tax,"2022-06-22",index,set() if applied is None else applied)

class CompoundMechanics(unittest.TestCase):
    def test_explicit_300_to_405_and_cost_identity(self):
        e,st,ls,obs,tax=fixture();before=copy.deepcopy(st);p=plan(e,st,ls,obs,tax)
        self.assertEqual(p["stock_reserve_total"],D(21))
        self.assertEqual(p["cash_claim"]["amount"],D(48))
        self.assertEqual(p["updates"][0]["old_attributed_cost"]+p["updates"][0]["new_attributed_cost"],ls[0].cost)
        ledger=[];applied=set();c.commit_synthetic(p,st,ls,ledger,applied)
        self.assertEqual((st["core"],ls[0].qty),(405,405))
        for k in ("cash","receivable","spent","fees","initial_fee","added","added_q","add_attempts","first_fill_id","cp_identity"):
            self.assertEqual(st[k],before[k])
        self.assertEqual(ls[0].opened,pd.Timestamp("2022-06-17"))
        self.assertEqual(ls[0].cost,D("2796.61"))
        self.assertEqual(st["addfloor"],before["addfloor"]*D(2)/obs["factor"])
        self.assertEqual(sum(x["cash_delta"] for x in ledger),0)
    def test_core_and_add_owner_allocation(self):
        e,st,ls,obs,tax=fixture(200);p=plan(e,st,ls,obs,tax)
        self.assertEqual([x["new_q"] for x in p["updates"]],[105,70])
        self.assertEqual(p["cash_claim"]["core_amount"],D(48))
        self.assertEqual(p["cash_claim"]["amount"],D(80))
        c.commit_synthetic(p,st,ls,[],set());self.assertEqual((st["core"],st["add"]),(405,270))
    def test_tax_pending_fails_without_mutation(self):
        e,st,ls,obs,tax=fixture();before=copy.deepcopy(st)
        with self.assertRaisesRegex(c.Unsupported,"STOCK_TAX_MODE_NOT_FROZEN"):plan(e,st,ls,obs,None)
        self.assertEqual(st,before);self.assertEqual(ls[0].qty,300)
    def test_tax_amount_and_integration_explicit(self):
        e,st,ls,obs,tax=fixture()
        for bad in (replace(tax,mode="PENDING"),replace(tax,freeze_hash=""),replace(tax,available_cash_policy=""),
                    replace(tax,mode="EXPLICIT_ZERO",reserve_per_new_share=".2")):
            with self.assertRaises(c.Unsupported):plan(e,st,ls,obs,bad)
        p=plan(e,st,ls,obs,replace(tax,mode="EXPLICIT_ZERO",reserve_per_new_share="0"))
        self.assertEqual(p["stock_reserve_total"],0)
    def test_strict_known_clock_and_timezone(self):
        e,*_=fixture()
        for bad in (replace(e,known_at="2022-06-22T15:00:00+08:00"),
                    replace(e,known_at="2022-06-23T09:30:00+08:00"),
                    replace(e,known_at="2022-06-16T12:00:00")):
            with self.assertRaises(c.Unsupported):c.validate_event(bad,"2022-06-22")
    def test_later_listing_credit_and_record_rejected(self):
        e,*_=fixture()
        for bad in (replace(e,saleable_date="2022-06-24"),replace(e,listing_explicit=False),
                    replace(e,credit_date="2022-06-24"),replace(e,record_date="2022-06-21"),
                    replace(e,pay_date="2022-06-22")):
            with self.assertRaises(c.Unsupported):c.validate_event(bad,"2022-06-22")
    def test_bonus_and_different_share_class_rejected(self):
        e,*_=fixture()
        for bad in (replace(e,bonus_per_old=".1"),replace(e,share_class_equal=False)):
            with self.assertRaises(c.Unsupported):c.validate_event(bad,"2022-06-22")
    def test_fractional_layer_no_floor(self):
        e,st,ls,obs,tax=fixture();st["core"]=301;ls[0].qty=301
        with self.assertRaisesRegex(c.Unsupported,"FRACTIONAL"):plan(e,st,ls,obs,tax)
        self.assertEqual(ls[0].qty,301)
    def test_source_cash_official_cash_separate(self):
        e,st,ls,obs,tax=fixture();e=replace(e,official_cash=".18168",source_cash=".1817")
        obs["factor"]=D(2)*D("1.35")*D("9.39")/(D("9.39")-D(".1817"))
        p=plan(e,st,ls,obs,tax);self.assertEqual(p["cash_claim"]["amount"],D(300)*D(".18168")*D(".8"))
        with self.assertRaisesRegex(c.Unsupported,"FACTOR_PATH_UNKNOWN"):
            plan(replace(e,source_cash=".18168"),st,ls,obs,tax)
    def test_factor_source_and_missing_open_fail_closed(self):
        e,st,ls,obs,tax=fixture()
        for bad in (dict(obs,factor=D(3)),dict(obs,raw_open="NaN"),dict(obs,origin=("bad","path","segment"))):
            with self.assertRaises(c.Unsupported):plan(e,st,ls,bad,tax)
    def test_wrong_ratio_rejected(self):
        e,st,ls,obs,tax=fixture()
        with self.assertRaisesRegex(c.Unsupported,"RATIO_DIFFER"):plan(replace(e,source_split="1.4"),st,ls,obs,tax)
    def test_registration_owner_and_state_mismatch(self):
        e,st,ls,obs,tax=fixture();ls[0].qty=299
        with self.assertRaisesRegex(c.Unsupported,"MISMATCH"):plan(e,st,ls,obs,tax)
    def test_closed_historical_layer_does_not_receive_shares(self):
        e,st,ls,obs,tax=fixture()
        ls.append(SimpleNamespace(layer_id="OLD_ADD",round_id="ROUND",sid="SYNTH",kind="add",qty=0,
                  opened=pd.Timestamp("2022-06-18"),cost=D(1000),first_fill_id="FIRST"))
        p=plan(e,st,ls,obs,tax);c.commit_synthetic(p,st,ls,[],set())
        self.assertEqual([x.qty for x in ls],[405,0])
    def test_stale_plan_and_tamper_atomicity(self):
        e,st,ls,obs,tax=fixture();p=plan(e,st,ls,obs,tax);ls[0].qty=299
        with self.assertRaisesRegex(c.Unsupported,"STALE"):c.commit_synthetic(p,st,ls,[],set())
        self.assertEqual(st["core"],300);self.assertEqual(ls[0].qty,299)
        ls[0].qty=300;p["updates"][0]["new_q"]=999
        with self.assertRaisesRegex(c.Unsupported,"TAMPERED"):c.commit_synthetic(p,st,ls,[],set())
        self.assertEqual(ls[0].qty,300)
    def test_idempotence(self):
        e,st,ls,obs,tax=fixture();p=plan(e,st,ls,obs,tax);ledger=[];applied=set()
        c.commit_synthetic(p,st,ls,ledger,applied)
        with self.assertRaisesRegex(c.Unsupported,"DUPLICATE"):c.commit_synthetic(p,st,ls,ledger,applied)
        self.assertEqual(len(ledger),1);self.assertEqual(ls[0].qty,405)
    def test_real_domain_cannot_commit(self):
        e,st,ls,obs,tax=fixture();e=replace(e,domain="HISTORICAL_CONDITIONAL");p=plan(e,st,ls,obs,tax)
        with self.assertRaisesRegex(c.Unsupported,"REAL_ECONOMIC_BINDING_NOT_RELEASED"):c.commit_synthetic(p,st,ls,[],set())
        self.assertEqual(ls[0].qty,300)
    def test_original_quantity_rule_full_odd_vs_partial_odd(self):
        qr=QuantityRule("ORIGINAL_DATED_FIXTURE",100,100,100,True,1)
        self.assertTrue(c.check_requested_exit(405,405,qr))
        with self.assertRaisesRegex(c.Unsupported,"ODD_EXIT"):c.check_requested_exit(105,405,qr)
        self.assertTrue(c.check_requested_exit(100,405,qr))
    def test_report_share_sequence_then_actual_sell(self):
        e,st,ls,obs,tax=fixture();p=plan(e,st,ls,obs,tax);ledger=[];c.commit_synthetic(p,st,ls,ledger,set())
        actions=[dict(round_id="ROUND",side="buy_core",q=300),dict(round_id="ROUND",side="sell_all",q=405)]
        self.assertEqual(c.replay_quantity(actions,ledger),{"ROUND":{"core":0,"add":0}})
        self.assertEqual(c.replay_quantity(actions[:1],ledger),{"ROUND":{"core":405,"add":0}})
        with self.assertRaisesRegex(c.Unsupported,"DUPLICATE"):c.replay_quantity(actions,ledger+ledger)
    def test_original_cash_functions_compatibility(self):
        e,st,ls,obs,tax=fixture(200);reg=c.register_layers(e,st,ls,"2022-06-22")
        projected=c.cash_claim_projection(e,reg,"ARM");ev=c.source_cash_event_projection(e)
        for k in ("record_date","coordinate_snapshot_day","ex_date","pay_date"):ev[k]=pd.Timestamp(ev[k])
        ctx=dict(D=D,NET=D(".8"),enabled=lambda x:True,
                 BY_RECORD={pd.Timestamp(e.record_date):[ev]},BY_EX={pd.Timestamp(e.ex_date):[ev]},
                 BY_PAY={pd.Timestamp(e.pay_date):[ev]},snapshots={},registrations=[],claims={},
                 archives={"ROUND":st},claim_ledger=[],cal=pd.DatetimeIndex(["2022-06-22","2022-06-23","2022-06-24"]))
        src=ORIGINAL.read_text();tree=ast.parse(src)
        for name in ("claim_key","register","accrue_day","pay_day"):
            node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            exec(compile(ast.get_source_segment(src,node),str(ORIGINAL)+":"+name,"exec"),ctx)
        ctx["register"]({"SYNTH":st},"ARM",pd.Timestamp(e.record_date))
        claim=next(iter(ctx["claims"].values()))
        for k in ("record_q","core_record_q","owner_round_id","amount","core_amount"):
            self.assertEqual(claim[k],projected[k])
        before=st["cash"];ctx["accrue_day"]("ARM",pd.Timestamp(e.ex_date))
        self.assertEqual(st["cash"],before);self.assertEqual(st["receivable"],D(80))
        ctx["accrue_day"]("ARM",pd.Timestamp(e.ex_date));self.assertEqual(st["receivable"],D(80))
        ctx["pay_day"]("ARM",pd.Timestamp(e.pay_date))
        self.assertEqual(st["cash"],before+D(80));self.assertEqual(st["receivable"],0)
        self.assertEqual(ctx["claim_ledger"][-1]["available_from"],pd.Timestamp("2022-06-24"))
        ctx["pay_day"]("ARM",pd.Timestamp(e.pay_date));self.assertEqual(st["cash"],before+D(80))
        self.assertEqual(st["core"],300) # Original cash functions do not issue shares.
    def test_input_restriction_no_current_close_required(self):
        e,st,ls,obs,tax=fixture();self.assertNotIn("raw_close",obs)
        self.assertEqual(plan(e,st,ls,obs,tax)["updates"][0]["new_q"],105)


    def test_adjusted_cost_basis_partial_and_full_no_phantom_cost(self):
        historical_qty=300;cost=D("2796.6146827865");current_qty=405
        partial=c.allocate_remaining_basis(current_qty,cost,300)
        self.assertEqual(partial["remaining_qty"],105)
        self.assertEqual(partial["sold_basis"]+partial["remaining_basis"],cost)
        self.assertEqual(partial["unit_basis_before"],cost/D(405))
        self.assertNotEqual(partial["unit_basis_before"],cost/D(historical_qty))
        final=c.allocate_remaining_basis(105,partial["remaining_basis"],105)
        self.assertEqual(partial["sold_basis"]+final["sold_basis"],cost)
        self.assertEqual(final["remaining_basis"],0)
        all_at_once=c.allocate_remaining_basis(405,cost,405)
        self.assertEqual(all_at_once["sold_basis"],cost)
    def test_core_add_cost_and_one_time_fees_separate(self):
        core=D("2796.6146827865");add=D("12005");buy_fees=D("5.2146827865")+D(5)
        c1=c.allocate_remaining_basis(405,core,405)
        a1=c.allocate_remaining_basis(270,add,100);a2=c.allocate_remaining_basis(170,a1["remaining_basis"],170)
        self.assertEqual(c1["sold_basis"]+a1["sold_basis"]+a2["sold_basis"],core+add)
        # Basis already contains original buy fees; issuance adds zero cash and no fees.
        self.assertGreater(buy_fees,0)
        e,st,ls,obs,tax=fixture(200);p=plan(e,st,ls,obs,tax,index=2);led=[]
        before=(st["cash"],st["fees"]);c.commit_synthetic(p,st,ls,led,set())
        self.assertEqual((st["cash"],st["fees"]),before)
        self.assertEqual(sum(x["trade_fee_delta"] for x in led),0)
        actions=[dict(round_id="ROUND",side="buy_core",q=300),dict(round_id="ROUND",side="buy_add",q=200),
                 dict(round_id="ROUND",side="sell_add",q=270),dict(round_id="ROUND",side="sell_all",q=405)]
        self.assertEqual(c.replay_quantity(actions,led)["ROUND"],dict(core=0,add=0))
        self.assertEqual(p["cash_claim"]["amount"],D(500)*D(".2")*D(".8")) # Not 675 dividend shares.
    def test_saved_no_share_prefix_quantity_equivalence_and_no_mutation(self):
        p=ROOT/"m3_ab_shared_probe_v1/annual_2022_marked_nav_v1/economic_run_2022_annual_once"
        actions=json.loads((p/"ACTIONS.json").read_text());layers=json.loads((p/"LAYERS.json").read_text())
        signature=c.digest(actions);actual=c.replay_quantity(actions,[])
        expected={}
        for x in layers:
            row=expected.setdefault(x["round_id"],dict(core=0,add=0));row[x["kind"]]+=int(x["qty"])
        self.assertEqual(actual,expected);self.assertEqual(len(actual),113)
        self.assertEqual(len(actions),254);self.assertEqual(c.digest(actions),signature)
    def test_original_native_mark_uses_current_qty_and_actual_cash(self):
        e,st,ls,obs,tax=fixture();p=plan(e,st,ls,obs,tax);c.commit_synthetic(p,st,ls,[],set())
        src=(ROOT/"m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py").read_text()
        node=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=="mark")
        fees=[];ctx={"D":D,"getmeta":lambda *a:(None,None,None),
                    "fee":lambda q,px,*a:(fees.append((q,px)) or D(5))}
        exec(compile(ast.get_source_segment(src,node),"original_native_mark","exec"),ctx)
        val=ctx["mark"](st,D("6.7"),pd.Timestamp("2022-06-23"))
        self.assertEqual(val,st["cash"]+D(405)*D("6.7")-D(5))
        self.assertEqual(fees,[(405,D("6.7"))])
        st["spent"]=D("999999");self.assertEqual(ctx["mark"](st,D("6.7"),pd.Timestamp("2022-06-23")),val)
        # spent is a historical denominator, not unit cost multiplied by adjusted shares.
    def test_original_native_full_exit_after_share_issue(self):
        import numpy as np
        e,st,ls,obs,tax=fixture();p=plan(e,st,ls,obs,tax);c.commit_synthetic(p,st,ls,[],set())
        st["exitpending"]="I_STRUCTURE_EXIT";st["entry_day"]=pd.Timestamp("2022-06-17")
        sid=st["sid"];d=pd.Timestamp("2022-06-23");before_cash=st["cash"];before_fee=st["fees"];before_spent=st["spent"]
        c.check_requested_exit(405,405,QuantityRule("ORIGINAL",100,100,100,True,1))
        actions=[];records=[];fee_calls=[]
        bar={"raw_open":D("6.7"),"adjustment_factor":st["factor"],"origin":st["origin"]}
        class Frame:
            def get(self,*a):return bar
        ctx={"D":D,"np":np,"SLIP":D(".0005"),"raw":{sid:Frame()},"finite":lambda x:bool(np.isfinite(float(x))),
             "lineage":lambda z:z["origin"],"getmeta":lambda *a:(None,None,None),"RuleUnavailable":RuntimeError,
             "fee":lambda q,px,*a:(fee_calls.append(q) or D(5)),
             "act":lambda st,d,side,q,px,ff,reason,**kw:actions.append(dict(side=side,q=q,price=px,fee=ff)),
             "record":lambda *a,**kw:records.append((a,kw)),
             "freeze_unknown":lambda *a:(_ for _ in ()).throw(AssertionError("unexpected unknown"))}
        src=(ROOT/"m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py").read_text()
        node=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=="held_open")
        exec(compile(ast.get_source_segment(src,node),"original_native_held_open","exec"),ctx)
        states={sid:st};ctx["held_open"](states,sid,st,d,pd.Timestamp("2022-06-22"))
        self.assertEqual(actions,[dict(side="sell_all",q=405,price=D("6.7")*(1-D(".0005")),fee=D(5))])
        self.assertEqual(st["cash"],before_cash+D(405)*D("6.7")*(1-D(".0005"))-D(5))
        self.assertEqual(st["fees"],before_fee+D(5));self.assertEqual(st["spent"],before_spent)
        self.assertEqual(fee_calls,[405]);self.assertEqual(st["core"],0);self.assertNotIn(sid,states)

if __name__=="__main__":unittest.main(verbosity=2)
