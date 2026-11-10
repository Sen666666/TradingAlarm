"""Isolated narrow compound-equity mechanics. No runner or automatic event admission.
Uses existing state/layer objects. Cash functions and trading decisions are not replaced.
Real economic commit is intentionally closed until a separate reviewed binding exists.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, date, time, timezone, timedelta
from decimal import Decimal as D
import copy, hashlib, json

ZERO = D(0)
CN = timezone(timedelta(hours=8))
class Unsupported(ValueError): pass
def require(ok, reason):
    if not ok: raise Unsupported(reason)
def dec(x):
    z=D(str(x)); require(z.is_finite(), "NONFINITE_NUMBER"); return z
def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,default=str,separators=(",",":")).encode()).hexdigest()
def day(x):
    if isinstance(x,datetime): return x.date()
    if isinstance(x,date): return x
    return date.fromisoformat(str(x)[:10])
def cutoff(d, phase):
    return datetime.combine(day(d), time(9,30) if phase=="OPEN" else time(15), CN)
def clock(x):
    z=x if isinstance(x,datetime) else datetime.fromisoformat(str(x))
    require(z.tzinfo is not None and z.utcoffset() is not None, "NAIVE_EVIDENCE_CLOCK")
    return z
def get(layer,k): return layer[k] if isinstance(layer,dict) else getattr(layer,k)
def setq(layer,q):
    if isinstance(layer,dict): layer["qty"]=q
    else: layer.qty=q

@dataclass(frozen=True)
class Event:
    event_id: str
    evidence_version: str
    sid: str
    known_at: str
    record_date: str
    ex_date: str
    pay_date: str
    credit_date: str
    saleable_date: str
    official_cash: str
    source_cash: str
    transfer_per_old: str
    source_split: str
    bonus_per_old: str = "0"
    share_class_equal: bool = True
    listing_explicit: bool = True
    credit_explicit: bool = True
    domain: str = "SYNTHETIC"

@dataclass(frozen=True)
class TaxBinding:
    policy_id: str
    freeze_hash: str
    mode: str
    reserve_per_new_share: str
    integration: str
    # All are deliberately explicit; no zero or 20% default.
    available_cash_policy: str
    nav_policy: str
    profit_gate_policy: str

def validate_event(e, previous_common_day):
    require(bool(e.event_id and e.evidence_version and e.sid), "EVENT_IDENTITY_MISSING")
    require(e.domain in ("SYNTHETIC","HISTORICAL_CONDITIONAL"),"UNKNOWN_DOMAIN")
    require(day(e.record_date)==day(previous_common_day), "RECORD_NOT_PREVIOUS_COMMON_SESSION")
    require(day(e.record_date)<day(e.ex_date), "INVALID_RECORD_EX_CLOCK")
    require(clock(e.known_at)<cutoff(e.record_date,"CLOSE"), "EVENT_NOT_KNOWN_AT_RECORD_CLOSE")
    require(clock(e.known_at)<cutoff(e.ex_date,"OPEN"), "EVENT_NOT_KNOWN_BEFORE_EX_OPEN")
    require(e.listing_explicit and day(e.saleable_date)==day(e.ex_date), "LATER_OR_UNPROVED_LISTING_UNSUPPORTED")
    require(e.credit_explicit and day(e.credit_date)==day(e.ex_date), "CREDIT_CLOCK_UNSUPPORTED")
    require(day(e.pay_date)>=day(e.ex_date), "PAY_BEFORE_EX_UNSUPPORTED")
    require(e.share_class_equal, "DIFFERENT_SHARE_CLASS_UNSUPPORTED")
    require(dec(e.bonus_per_old)==0, "BONUS_SHARES_OUTSIDE_NARROW_SCOPE")
    require(dec(e.transfer_per_old)>0 and dec(e.official_cash)>=0 and dec(e.source_cash)>=0, "INVALID_TERMS")
    require(dec(e.source_split)==1+dec(e.transfer_per_old), "SOURCE_AND_ENTITLEMENT_RATIO_DIFFER")
    return True

def validate_tax(t, e):
    """Explicit mechanical input only, NOT tax-exemption evidence or real-event admission.
    A syntactically valid 64-hex value is not an independent authorization signature.
    EXPLICIT_ZERO means the caller supplied zero, not that any stock tax is legally exempt.
    """
    require(t is not None, "STOCK_TAX_MODE_NOT_FROZEN")
    require(bool(t.policy_id) and len(t.freeze_hash)==64 and all(c in "0123456789abcdef" for c in t.freeze_hash),
            "STOCK_TAX_FREEZE_MISSING")
    require(t.mode in ("EXPLICIT_ZERO","EXPLICIT_RESERVE"), "STOCK_TAX_MODE_NOT_ADMITTED")
    amount=dec(t.reserve_per_new_share)
    require(amount>=0 and (t.mode!="EXPLICIT_ZERO" or amount==0), "INCONSISTENT_TAX_AMOUNT")
    require(all((t.integration,t.available_cash_policy,t.nav_policy,t.profit_gate_policy)),
            "TAX_STATE_INTEGRATION_UNDECIDED")
    if e.domain=="SYNTHETIC":
        require(t.integration=="SYNTHETIC_ONLY", "SYNTHETIC_TAX_INTEGRATION_MISMATCH")
    return amount

def register_layers(e, st, layers, previous_common_day):
    validate_event(e,previous_common_day)
    require(st["sid"]==e.sid and st.get("state")=="HELD", "NO_HELD_REGISTRATION_OWNER")
    rid=st["round_id"]; chosen=[x for x in layers if get(x,"round_id")==rid and int(get(x,"qty"))>0]
    require(len({get(x,"layer_id") for x in chosen})==len(chosen), "DUPLICATE_LAYER")
    rows=[]
    for x in chosen:
        require(get(x,"sid")==e.sid and get(x,"kind") in ("core","add"),"LAYER_OWNER_MISMATCH")
        require(day(get(x,"opened"))<=day(e.record_date),"POST_RECORD_LAYER")
        q=int(get(x,"qty")); require(q==get(x,"qty") and q>0,"INVALID_LAYER_QUANTITY")
        rows.append({k:get(x,k) for k in ("layer_id","round_id","sid","kind","opened","cost","first_fill_id")} | {"record_q":q})
    for kind in ("core","add"):
        require(sum(x["record_q"] for x in rows if x["kind"]==kind)==int(st.get(kind,0)), "RECORD_LAYER_STATE_MISMATCH")
    require(sum(x["record_q"] for x in rows)>0,"ZERO_OWNER_REQUIRES_COORDINATE_ONLY_PATH")
    return {"event_id":e.event_id,"evidence_version":e.evidence_version,"sid":e.sid,
            "owner_round_id":rid,"record_date":e.record_date,"record_q":sum(x["record_q"] for x in rows),
            "core_record_q":sum(x["record_q"] for x in rows if x["kind"]=="core"),"layers":rows}

def cash_claim_projection(e,reg,arm):
    require(reg["event_id"]==e.event_id and reg["evidence_version"]==e.evidence_version,"CLAIM_EVENT_MISMATCH")
    q=reg["record_q"];cq=reg["core_record_q"]
    return {"key":("2022",arm,e.sid,e.event_id),"arm":arm,"sid":e.sid,"economic_event_id":e.event_id,
            "evidence_version":e.evidence_version,"record_date":e.record_date,"inventory_snapshot_day":e.record_date,
            "snapshot_kind":"RECORD_CLOSE","state":"HELD","record_q":q,"core_record_q":cq,
            "owner_round_id":reg["owner_round_id"],"amount":D(q)*dec(e.official_cash)*D(".8"),
            "core_amount":D(cq)*dec(e.official_cash)*D(".8"),"recognized":False,"settled":False,
            "ex_date":e.ex_date,"pay_date":e.pay_date,"d_cash":dec(e.official_cash)}

def source_cash_event_projection(e):
    """Fields accepted by original register/accrue/pay; registration tables remain caller-owned."""
    return {"sid":e.sid,"economic_event_id":e.event_id,"evidence_version":e.evidence_version,
            "record_date":e.record_date,"coordinate_snapshot_day":e.record_date,
            "ex_date":e.ex_date,"pay_date":e.pay_date,"d_cash":dec(e.official_cash),
            "entitlement_verified":True,"event_type":"CASH_PLUS_CAPITALIZATION",
            "stock_permission":"NOT_GRANTED_BY_THIS_CASH_PROJECTION"}

def _state_layer_fingerprint(st,layers):
    rid=st["round_id"]
    return digest({"state":st,"layers":[{k:get(x,k) for k in
                   ("layer_id","round_id","sid","kind","qty","opened","cost","first_fill_id")}
                   for x in layers if get(x,"round_id")==rid]})

def prepare_ex(e,reg,st,layers,obs,tax,previous_common_day,action_index,applied):
    validate_event(e,previous_common_day);reserve=validate_tax(tax,e)
    key=(e.event_id,reg["owner_round_id"])
    require(key not in applied,"DUPLICATE_EQUITY_EVENT")
    require(st.get("state")=="HELD" and st["sid"]==e.sid and st["round_id"]==reg["owner_round_id"],"EX_OWNER_MISMATCH")
    require(reg["event_id"]==e.event_id and reg["evidence_version"]==e.evidence_version,"REGISTRATION_VERSION_MISMATCH")
    require(day(obs["day"])==day(e.ex_date) and day(obs["previous_day"])==day(previous_common_day),"OBSERVATION_DAY_MISMATCH")
    op=dec(obs["raw_open"]);pc=dec(obs["previous_raw_close"])
    fo=dec(obs["previous_factor"]);fn=dec(obs["factor"])
    require(op>0 and pc>dec(e.source_cash) and fo>0 and fn>0,"INVALID_OPEN_OR_FACTOR")
    require(obs["origin"]==obs["previous_origin"]==st["origin"],"SOURCE_CHANGED_AT_EX")
    require(abs(dec(st["fac"])/fo-1)<=D("1e-11"),"STATE_OLD_FACTOR_MISMATCH")
    expected=fo*dec(e.source_split)*pc/(pc-dec(e.source_cash))
    require(abs(expected/fn-1)<=D("1e-11"),"COMPOUND_FACTOR_PATH_UNKNOWN")
    ratio=dec(e.transfer_per_old);updates=[]
    byid={get(x,"layer_id"):x for x in layers if get(x,"round_id")==st["round_id"] and int(get(x,"qty"))>0}
    require(set(byid)=={x["layer_id"] for x in reg["layers"]},"LAYER_SET_CHANGED_SINCE_RECORD")
    for row in reg["layers"]:
        x=byid[row["layer_id"]]
        require(int(get(x,"qty"))==row["record_q"] and all(get(x,k)==row[k] for k in
                ("round_id","sid","kind","opened","cost","first_fill_id")),"REGISTERED_LAYER_CHANGED")
        n=D(row["record_q"])*ratio
        require(n==n.to_integral_value(),"FRACTIONAL_LAYER_ENTITLEMENT_UNSUPPORTED")
        n=int(n);after=row["record_q"]+n;cost=dec(row["cost"])
        old_cost=cost*D(row["record_q"])/D(after);new_cost=cost-old_cost
        require(old_cost+new_cost==cost,"COST_ALLOCATION_MISMATCH")
        updates.append(dict(row,new_q=n,qty_after=after,old_attributed_cost=old_cost,
                            new_attributed_cost=new_cost,reserve_delta=D(n)*reserve))
    for kind in ("core","add"):
        require(sum(x["record_q"] for x in updates if x["kind"]==kind)==int(st.get(kind,0)),"EX_LAYER_STATE_MISMATCH")
    protections={k:dec(st[k])*fo/fn for k in ("addfloor","addpending") if st.get(k) is not None}
    require(isinstance(action_index,int) and action_index>=0,"INVALID_ACTION_SEQUENCE")
    plan={"event":asdict(e),"registration":reg,"tax_binding":asdict(tax),"key":key,"updates":updates,
          "new_factor":fn,"protections":protections,"action_index":action_index,
          "cash_claim":cash_claim_projection(e,reg,st["arm"]),
          "stock_reserve_total":sum((x["reserve_delta"] for x in updates),ZERO),
          "state_layer_fingerprint":_state_layer_fingerprint(st,layers)}
    plan["plan_hash"]=digest(plan)
    return plan

def commit_synthetic(plan,st,layers,ledger,applied):
    """Atomic mechanical fixture only. No real-economic route, cash posting or tax policy inferred."""
    require(plan["event"]["domain"]=="SYNTHETIC","REAL_ECONOMIC_BINDING_NOT_RELEASED")
    require(plan["tax_binding"]["integration"]=="SYNTHETIC_ONLY","TAX_INTEGRATION_NOT_RELEASED")
    check=dict(plan);expected=check.pop("plan_hash");require(digest(check)==expected,"PLAN_TAMPERED")
    key=tuple(plan["key"]);require(key not in applied,"DUPLICATE_EQUITY_EVENT")
    require(_state_layer_fingerprint(st,layers)==plan["state_layer_fingerprint"],"STALE_EX_PLAN")
    byid={get(x,"layer_id"):x for x in layers};before=copy.deepcopy(st)
    oldqty={u["layer_id"]:get(byid[u["layer_id"]],"qty") for u in plan["updates"]}
    oldlen=len(ledger)
    try:
        for u in plan["updates"]:
            setq(byid[u["layer_id"]],u["qty_after"]);st[u["kind"]]+=u["new_q"]
        st["fac"]=plan["new_factor"];st["factor"]=float(plan["new_factor"])
        st.update(plan["protections"])
        allowed={"core","add","fac","factor","addfloor","addpending"}
        require({k:v for k,v in st.items() if k not in allowed}==
                {k:v for k,v in before.items() if k not in allowed},"NON_EQUITY_STATE_MUTATED")
        for u in plan["updates"]:
            ledger.append({"event_id":plan["event"]["event_id"],"evidence_version":plan["event"]["evidence_version"],
                           "round_id":u["round_id"],"layer_id":u["layer_id"],"sid":u["sid"],"kind":u["kind"],
                           "day":plan["event"]["ex_date"],"action_index":plan["action_index"],
                           "old_q":u["record_q"],"new_q":u["new_q"],"qty_after":u["qty_after"],
                           "historical_layer_cost":u["cost"],"old_attributed_cost":u["old_attributed_cost"],
                           "new_attributed_cost":u["new_attributed_cost"],"first_fill_id":u["first_fill_id"],
                           "original_opened":u["opened"],"saleable_from":plan["event"]["saleable_date"],
                           "stock_reserve_delta":u["reserve_delta"],"stock_reserve_is_paid_tax":False,
                           "cash_delta":ZERO,"trade_fee_delta":ZERO})
        applied.add(key)
    except BaseException:
        st.clear();st.update(before)
        for lid,q in oldqty.items():setq(byid[lid],q)
        del ledger[oldlen:];applied.discard(key);raise

def check_requested_exit(quantity,total,quantity_rule):
    require(0<quantity<=total,"INVALID_EXIT_QUANTITY")
    require(quantity_rule.sell_floor(quantity,total)==quantity,"ODD_EXIT_NOT_ALLOWED_BY_ORIGINAL_RULE")
    return True

def replay_quantity(actions,share_ledger):
    """Report-only quantity reconstruction. Share entries never pretend to be trades."""
    rows={};shares_by_index={}
    for x in share_ledger:
        require(isinstance(x["action_index"],int) and 0<=x["action_index"]<=len(actions),"SHARE_ACTION_INDEX_INVALID")
        shares_by_index.setdefault(x["action_index"],[]).append(x)
    def record(rid):return rows.setdefault(rid,{"core":0,"add":0})
    seen=set()
    for index in range(len(actions)+1):
        for x in shares_by_index.get(index,[]):
            identity=(x["event_id"],x["round_id"],x["layer_id"])
            require(identity not in seen,"DUPLICATE_REPORT_SHARE_ENTRY");seen.add(identity)
            row=record(x["round_id"])
            # Current strategy has at most one actual core and one actual ADD layer.
            require(row[x["kind"]]==x["old_q"],"REPORT_PRE_ISSUE_QUANTITY_MISMATCH")
            row[x["kind"]]+=x["new_q"]
            require(row[x["kind"]]==x["qty_after"],"REPORT_POST_ISSUE_QUANTITY_MISMATCH")
        if index==len(actions):break
        x=actions[index];row=record(x["round_id"]);q=int(x["q"]);side=x["side"]
        require(q>0,"INVALID_ACTION_QUANTITY")
        if side in ("buy_core","buy_add"):row["core" if side=="buy_core" else "add"]+=q
        elif side=="sell_add":
            require(row["add"]==q,"REPORT_ADD_SELL_MISMATCH");row["add"]=0
        elif side=="sell_all":
            require(row["core"]+row["add"]==q,"REPORT_FULL_SELL_MISMATCH");row.update(core=0,add=0)
        else:raise Unsupported("UNSUPPORTED_ACTION_SIDE")
    return rows


def allocate_remaining_basis(current_qty, remaining_cost, sold_qty):
    """Report-only basis allocation; current adjusted qty, never historical buy qty.
    Does not post cash, tax, fees or a trade; partial examples do not authorize partial exits.
    """
    require(isinstance(current_qty,int) and isinstance(sold_qty,int) and 0<sold_qty<=current_qty, "INVALID_COST_ALLOCATION_QUANTITY")
    cost=dec(remaining_cost);require(cost>=0,"NEGATIVE_REMAINING_BASIS")
    sold=cost if sold_qty==current_qty else cost*D(sold_qty)/D(current_qty)
    residual=cost-sold
    require(sold+residual==cost,"REMAINING_BASIS_NOT_CONSERVED")
    return {"sold_basis":sold,"remaining_basis":residual,"remaining_qty":current_qty-sold_qty,"unit_basis_before":cost/D(current_qty)}
