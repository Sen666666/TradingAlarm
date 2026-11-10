"""Deterministic synthetic tests; never reads empirical forward outcomes."""
from pathlib import Path
import ast,json
import pandas as pd,numpy as np
from decimal import Decimal as D
p=Path(__file__).with_name('simulate.py');tree=ast.parse(p.read_text())
keep=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
g=dict(pd=pd,np=np,D=D,Path=Path,RuleUnavailable=type('RuleUnavailable',(Exception,),{}))
exec(compile(ast.Module(body=keep,type_ignores=[]),str(p),'exec'),g)
class QR:
 def buy_floor(self,q):return max(0,(int(q)//100)*100)
g.update(NAV=D(1200000),INIT=D(24000),SLOT=D(48000),RISK=D(3000),SLIP=D('.0005'))
g['getmeta']=lambda sid,d:(QR(),None,D(1))
g['fee']=lambda q,p,fs,side,par:D(0)
g['load']=lambda sid:None
g['checkclose']=lambda r:dict(close_check='PASS',close_q=100,prior20_capacity=10000)
cal=pd.bdate_range('2024-01-01',periods=5);sid='TEST.SZ'
def setup():
 rows={}
 for d in cal:rows[d]=dict(raw_open=100.,raw_close=100.,adjustment_factor=1.,source_kind='X',source_path='X',segment_id=0,observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False)
 ff={d:dict(i_target=True,i_floor=90.) for d in cal};cc={d:dict(receipt=False,candidate=np.nan) for d in cal}
 events=[]
 for d,typ in [(cal[0],'A_SECTOR_BIRTH'),(cal[1],'B_STOCK_BIRTH_DURING_SECTOR'),(cal[2],'A_SECTOR_BIRTH'),(cal[3],'B_STOCK_BIRTH_DURING_SECTOR')]:
  events.append(dict(window='TEST',day=d,sid=sid,name='TEST',sector='SEC',industry='TEST',event_type=typ,event_id=f'{d}|{typ}',PVR_score=50.,I_qualified=True,PVR_known=True,i_floor=90.))
 g.update(cal=cal,END=cal[-1],raw={sid:rows},facts={sid:ff},cp={sid:cc},capacity={sid:{d:10000 for d in cal}},sector={'SEC':{d:1 for d in cal}},ev=pd.DataFrame(events),rounds=[],actions=[],decisions=[],blocks=[],load_count=0,started=0,time=__import__('time'))
 return rows,ff,cc
out=[]
z,f,c=setup();f[cal[1]]['i_target']=False;z[cal[2]]['raw_open']=95.
g['run_window']('TEST',str(cal[0].date()),str(cal[-1].date()),None,'A_UNION_B')
de=pd.DataFrame(g['decisions']);aa=pd.DataFrame(g['actions'])
assert de[de.selected].day.tolist()==[cal[0],cal[2]]
assert de.loc[de.event_type.str.startswith('B'),'decision'].tolist()==['BLOCKED_HELD','BLOCKED_HELD']
assert aa[aa.side.eq('sell_all')].day.tolist()==[str(cal[2].date())]
assert aa[aa.side.eq('buy_core')].day.tolist()==[str(cal[1].date()),str(cal[3].date())]
out.append('held receipt blocked, T+1 close exit, same-day sell then fresh close edge reentry')
z,f,c=setup();f[cal[1]]['i_target']=False;z[cal[2]]['adjustment_factor']=2.
g['run_window']('TEST',str(cal[0].date()),str(cal[-1].date()),None,'A_UNION_B')
de=pd.DataFrame(g['decisions']);assert de.loc[de.day.ge(cal[2]),'decision'].eq('BLOCKED_UNKNOWN').all()
assert len(g['rounds'])==1 and g['rounds'][0]['status']=='FACTOR_PATH_UNKNOWN'
out.append('unknown exit locks stock, never presumed flat')
z,f,c=setup();z[cal[1]]['raw_open']=89.
g['run_window']('TEST',str(cal[0].date()),str(cal[-1].date()),None,'A_UNION_B')
de=pd.DataFrame(g['decisions']);assert de.loc[de.day.eq(cal[1]),'selected'].item()
assert g['rounds'][0]['status']=='NEXT_OPEN_BELOW_PROTECTION_NOFILL'
out.append('explicit nofill returns flat and only fresh later receipt may reenter')
z,f,c=setup();c[cal[1]]=dict(receipt=True,candidate=95.);z[cal[2]]['raw_close']=120.;c[cal[2]]=dict(receipt=True,candidate=110.);z[cal[3]]['raw_open']=90.
g['run_window']('TEST',str(cal[0].date()),str(cal[-1].date()),None,'A_UNION_B')
aa=pd.DataFrame(g['actions']);assert not aa.side.eq('buy_add').any()
assert g['rounds'][0]['negative_CP_blocked']>=1 and g['rounds'][0]['add_profit_floor_rejects']==1
out.append('negative net CP blocked, positive close CP rejected after losing/gap next OPEN')
z,f,c=setup();g['run_window']('TEST',str(cal[0].date()),str(cal[-1].date()),None,'A_ONLY')
assert len(g['decisions'])==2 and len(g['rounds'])==1 and g['rounds'][0]['status']=='OPEN_CENSORED_AT_2026_06_30'
out.append('A-only excludes B; end remains censored with no forced sale')
Path(__file__).with_name('SYNTHETIC_TESTS.json').write_text(json.dumps(dict(passed=out,count=len(out),script_tested=str(p)),indent=2)+'\n')
print('PASS',len(out))
