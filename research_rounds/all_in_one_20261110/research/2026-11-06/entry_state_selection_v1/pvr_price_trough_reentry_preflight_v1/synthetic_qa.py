from pathlib import Path
import ast,json
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
tree=ast.parse((O/"preflight.py").read_text())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="simulate")
ns=dict(pd=pd,np=np);exec(compile(ast.Module(body=[fn],type_ignores=[]),"<isolated_state_function>","exec"),ns)
sim=ns["simulate"]
d=pd.date_range("2020-01-01",periods=13,freq="B")
q=pd.DataFrame(index=d)
q["PVR"]=[71,68,60,50,55,65,58,45,50,56,58,59,60]
q["close"]=[100,102,101,100,102,105,104,103,104,105,106,107,108]
q["valid"]=True;q["identity"]="same";q["i_target"]=[0]+[1]*12;q["e0_target"]=q.i_target
q["i_buy"]=False;q["CP"]=False;q["CP_ready"]=True;q["g_grade"]=2.;q["g_ready"]=True;q["i_floor"]=90.
checks=[]
def check(name,truth):assert truth,name;checks.append(name)
a=sim(q)
check("b_confirmed_only_next_day",not a.iloc[7].trough_confirmed and bool(a.iloc[8].trough_confirmed))
check("price_break_needs_actual_new_close",not a.iloc[8].issued and bool(a.iloc[9].issued))
check("one_issue_no_repeat",a.issued.sum()==1)
check("a_b_and_known_clocks",a.iloc[9].a_day==d[3] and a.iloc[9].b_day==d[7] and a.iloc[9].known_day==d[8])
for n in range(3,len(q)+1):
 pd.testing.assert_frame_equal(sim(q.iloc[:n]),a.iloc[:n],check_exact=True)
check("all_prefixes",True)
z=q.copy();z.loc[d[4],"PVR"]=50
check("exact_plateau_no_first_trough",sim(z).issued.sum()==0)
z=q.copy();z.loc[d[6],"valid"]=False
check("unknown_clears_no_cross_gap_root",sim(z).issued.sum()==0 and not sim(z).loc[d[7]:,"root_known"].any())
z=q.copy();z.loc[d[6]:,"identity"]="new"
check("source_change_clears",sim(z).issued.sum()==0)
z=q.copy();z.loc[d[7],"close"]=100
check("equality_of_price_anchor_does_not_pass",sim(z).issued.sum()==0)
z=q.copy();z.loc[d[6],"close"]=99
check("intermediate_anchor_break_does_not_pass",sim(z).issued.sum()==0)
z=q.copy();z.loc[d[9],"g_grade"]=1
b=sim(z)
check("wait_for_G_no_arbitrary_expiry",not b.iloc[9].issued and bool(b.iloc[10].issued))
z=q.copy();z.loc[d[8],"i_target"]=0;z.loc[d[8],"e0_target"]=0
check("I_off_clears",sim(z).issued.sum()==0)
z=q.copy();z.loc[d[10]:,"PVR"]=[1,99,1]
pd.testing.assert_frame_equal(sim(z).iloc[:10],a.iloc[:10],check_exact=True)
check("future_poison_no_change",True)
# Monotone score transform keeps exact order absent floating collisions.
z=q.copy();z["PVR"]=z.PVR/100
b=sim(z);pd.testing.assert_frame_equal(a[["trough_confirmed","pair_condition","issued"]],b[["trough_confirmed","pair_condition","issued"]],check_exact=True)
check("positive_affine_PVR_order_invariance",True)
(O/"SYNTHETIC_QA.json").write_text(json.dumps(dict(passed=checks,count=len(checks)),indent=2))
print(json.dumps(dict(passed=len(checks),names=checks)))
