import importlib.util,pathlib,json,copy,hashlib
p=pathlib.Path("mainline_candidate_v12_winner_funding_competition")
spec=importlib.util.spec_from_file_location("v12_reviewer_extra_fixture",p/"synthetic_tests.py");t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t);e=t.e;D=t.D
checks=[]
def ok(n,v):assert v,n;checks.append(n)
def binding():
 x=t.setup();t.hold(x,qty=110000);x.cash=D(20000);x.d.main_rows[("old",t.dt)]={"M":0,"E":0,"W":True};return x
x,y=binding(),binding()
for s in y.d.ids:
 y.d.prices[(s,t.nxt)]={"raw_open":999.,"raw_high":1000.,"raw_low":998.,"raw_close":999.,"raw_volume":1.,"adjustment_factor":17.}
 y.d.fact_rows[(s,t.nxt)]={"i_target":False,"i_floor":500.}
 y.d.cp_rows[(s,t.nxt)]={"receipt":True,"candidate":900.}
 y.d.main_rows[(s,t.nxt)]={"M":0,"E":800.}
 y.d.stock.at[t.nxt,s]=0
rx,ry=t.planned(x),t.planned(y)
ok("CLOSE_book_invariant_to_next_session_all_quotes_factor_signals",e.digest(x.funding_book)==e.digest(y.funding_book))
x,y=binding(),binding();rx,ry=t.planned(x),t.planned(y)
for s in y.d.ids:
 y.d.prices[(s,t.nxt)]={"raw_high":"POISON","raw_low":"POISON","raw_close":"POISON","raw_volume":"POISON","observed_bar":False,"price_eligible":False,"volume_eligible":False,"source_invalid":True,"synthetic_event_bar":True}
 y.d.fact_rows[(s,t.nxt)]={"i_target":False,"i_floor":500.};y.d.cp_rows[(s,t.nxt)]={"receipt":True,"candidate":900.};y.d.main_rows[(s,t.nxt)]={"M":-1,"E":900.};y.d.stock.at[t.nxt,s]=-1
dx,dy=x.select_open(t.nxt,rx),y.select_open(t.nxt,ry)
ok("OPEN_H_invariant_to_current_full_day_flags_and_signals",dx["H"]==dy["H"])
ok("OPEN_choice_and_quantities_invariant_to_future_fields",dx["selected_index"]==dy["selected_index"] and dx["chosen_projection"]==dy["chosen_projection"])
x=binding();r=t.planned(x);dec=x.select_open(t.nxt,r)
x.d.prices[("a",t.nxt)]={"raw_open":100.}
x.execute_selected(t.nxt,r,dec)
ok("withdrawn_new_SEED_attempt_budget_failure_not_retained","a" not in x.tickets)
ok("original_rejection_saved_not_disguised_WAIT",x.funding_wait_log[-1]["reason"].startswith("MIN_LOT_CAPITAL_REJECT:") and x.funding_wait_log[-1]["status"]=="ORIGINAL_REJECT_NO_TICKET")
x=binding();r=t.planned(x);before=e.digest(x.funding_book);x.select_open(t.nxt,r)
ok("OPEN_selection_does_not_mutate_CLOSED_branch_book",before==e.digest(x.funding_book))
for b in x.funding_book["branches"]:ok("branch_payload_identity_"+str(b["deletion_index"]),e.digest(e.branch_hash_payload(b))==b["branch_id"])
RESULT=dict(result="PASS_INDEPENDENT_INTERFACE_EXTRAS",checks=checks,count=len(checks),engine_sha256=e.sha(p/"engine.py"),history_run=False)
print(json.dumps(RESULT,indent=2))
