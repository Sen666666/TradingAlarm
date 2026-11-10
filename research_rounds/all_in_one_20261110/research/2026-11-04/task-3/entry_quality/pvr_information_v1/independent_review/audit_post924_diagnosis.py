"""Thin independent arithmetic/source join of the fixed post924 description."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import json,hashlib
getcontext().prec=65
HERE=Path(__file__).resolve().parent;E=HERE.parents[1];P=HERE.parent/'post924_diagnosis';SRC={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def eq(a,b,k):assert abs(D(str(a))-D(str(b)))<D('1e-6'),(k,str(a),str(b))
def money(rr):return dict(layers=len(rr),positive=sum((max(Z,D(r['net'])) for r in rr),Z),negative=sum((min(Z,D(r['net'])) for r in rr),Z),net=sum((D(r['net']) for r in rr),Z),fees=sum((D(r['buy_fee'])+D(r['sell_fee']) for r in rr),Z))
def check(rr,expected):
 for k,v in money(rr).items():eq(v,expected[k],k)
 return money(rr)
if __name__=='__main__':
 out=HERE/'POST924_DIAGNOSIS_AUDIT.json';assert not out.exists();result=dict(status='RUNNING',new_accounts=0,new_models=0)
 try:
  sm=read(P/'SOURCE_MANIFEST.json')
  for path,h in sm['source_sha256'].items():assert sha(path)==h
  deliverables=read(P/'DELIVERABLE_SHA256.json')
  # Deliverable index may use filenames or absolute paths; validate both.
  for path,h in deliverables.items():
   q=Path(path);q=q if q.is_absolute() else P/q;assert sha(q)==h
  tables=read(P/'CORE_TABLES.json');read(P/'VALIDATION.json');read(P/'THIN_VERIFICATION.json');text=(P/'READOUT.txt').read_text();SRC[str((P/'READOUT.txt').resolve())]=sha(P/'READOUT.txt')
  joined=read(P/'ALL_JOINED_LAYER_ROWS.json');orig={};holding={};requests={};ratchets={}
  for win in ['2022_2024','strong']:
   holding[win]=read(E/'entry_exit_scale/holding_exit'/f'{win}_LAYERS.json');requests[win]={x['layer']:x for x in read(E/'entry_exit_scale/holding_exit'/f'{win}_REQUEST_CLOCK_JOIN.json')};ratchets[win]={x['layer']:x for x in read(E/'entry_exit_scale/mechanism_review'/f'{win}_ACTUAL_CP_REQUEST_RATCHET_JOIN.json')}
   source={x['layer']:x for x in holding[win]};assert len(source)==len(joined[win])
   for r in joined[win]:
    x=source[r['layer']];assert r['sid']==x['sid'] and r['opened']==x['opened'] and r['closed']==x['closed'] and r['role']==x['role']
    for k in ['cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee','held_close_observations']:eq(r[k],x[k],win+' holding '+k)
    assert r['request_clock']==requests[win][r['layer']];assert r['ratchet']==ratchets[win][r['layer']]
  assert sum(len(x) for x in joined.values())==3436
  post=[x for x in holding['2022_2024'] if x['opened'][:10]>'2024-10-08'];assert len(post)==303 and all(x['closed'] is not None for x in post)
  strong=holding['strong'];assert len(strong)==1171;tail=[x for x in strong if D(x['net'])/D(x['cost'])>=D('.30')];posttail=[x for x in post if D(x['net'])/D(x['cost'])>=D('.30')]
  assert len(tail)==123 and len(posttail)==13;check(post,tables['post303']['all']);check(strong,tables['strong_all']['all']);check(tail,tables['strong_tail123']['all']);check([x for x in strong if x not in tail],tables['strong_ordinary1048']['all'])
  short=[x for x in post if x['held_close_observations']<=5];assert len(short)==152;check(short,tables['post303']['predicates']['POSTHOC_held_CLOSE_at_most5']);negative_short=[x for x in short if D(x['net'])<0];assert len(negative_short)==139
  shortcp=[x for x in short if x['actual_exit_class']=='CP1_add_protection'];check(shortcp,tables['post303']['predicates']['POSTHOC_primary_CP_at_most5_held_CLOSE']);negcp=[x for x in shortcp if D(x['net'])<0];assert len(negcp)==82
  unchanged=[x for x in shortcp if ratchets['2022_2024'][x['layer']]['entry_to_primary_CP_ratchet']=='UNCHANGED_ENTRY_LINE'];assert len(unchanged)==61 and all(D(x['net'])<0 for x in unchanged);check(unchanged,tables['post303']['predicates']['POSTHOC_primary_CP_short5_unchanged_entry_line'])
  open_tail=[x for x in tail if x['closed'] is None];assert len(open_tail)==32 and len(tail)-len(open_tail)==91
  closed_tail=[x for x in tail if x['closed'] is not None];open_components={k:sum((D(x[k]) for x in open_tail),Z) for k in ['strict_realized','open_unrealized','recognized_dividend_AR','net']};eq(open_components['net'],tables['strong_tail123']['by_exit']['OPEN_NO_ACTUAL_EXIT']['net'],'open-tail wealth')
  post_controls=read(P/'POST_OWN13_TAIL_CONTROLS.json');tail_controls=read(P/'SYSTEMATIC_TOP10_AND_TAIL_CONTROLS.json')
  # All123 are already validated as a full table; recursively find stored layer IDs.
  def contains_layer(obj,lid,sid):
   if isinstance(obj,dict):
    if obj.get('layer')==lid and obj.get('sid')==sid:return True
    return any(contains_layer(v,lid,sid) for v in obj.values())
   if isinstance(obj,list):return any(contains_layer(v,lid,sid) for v in obj)
   return False
  assert all(contains_layer(post_controls,x['layer'],x['sid']) for x in posttail)
  assert {x['layer'] for x in joined['strong'] if D(x['net'])/D(x['cost'])>=D('.30')}=={x['layer'] for x in tail}
  assert '不能反向门控入场' in text and '不等于真实趋势' in text and 'NO_NEW_ENTRY_MECHANISM_SUPPORTED' in text and '0新规则/账户' in text
  ratio=(-money(unchanged)['negative'])/(-money(negcp)['negative'])
  result.update(status='PASS_THIN_POST924_DESCRIPTIVE_SCOPE',original_rows=3436,post303=money(post),strong1171=money(strong),post13_complete=True,strong123_complete=True,strong123_closed=91,strong123_open=32,strong_open_tail_components=open_components,posthoc_short152=money(short),posthoc_negative_short139=money(negative_short),posthoc_negative_shortCP82=money(negcp),posthoc_unchanged_shortCP61=money(unchanged),unchanged_shortCP_loss_fraction=ratio,source_inputs_rehashed=len(sm['source_sha256']),all_held_and_primary_request_ratchet_joins_exact=True,
   limitations=['Thin source/arithmetic audit of existing already-audited holding/clock/ratchet tables, not a cold model or book replay.',
    'Short holding and entry-line ratchet status are later outcomes. They cannot become decision-time gates or causal avoidable-loss estimates.',
    'Legal original I/CP authorization is not validated future trend efficacy. Descriptive marginal overlap does not prove that no possible predictive interaction exists.',
    'Open32 tail net is marked unrealized contribution plus recognized AR (and any recorded realized component), not paid cash or inventory market value. Original13 post tails and123 strong evaluation tails retained, no winner filter.'])
 except BaseException as ex:result.update(status='FAIL_PRESERVE',error=repr(ex));raise
 finally:
  SRC[str(Path(__file__).resolve())]=sha(__file__);result['source_sha256']=SRC;out.open('x').write(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
 print(result['status'])
