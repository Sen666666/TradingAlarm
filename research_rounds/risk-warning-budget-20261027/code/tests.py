from risk_policy import *
import json
s=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=True,episode=0)
x,dd,e=advance(s,D(800000),False,True,True,'ACT20_BREAK');assert e=='pause' and not x['on']
y,dd,e=advance(x,D(810000),False,True,True,'ACT20_BREAK');assert e is None and not y['on']
y,dd,e=advance(x,D(810000),True,True,True,'ACT20_BREAK');assert e=='resume' and y['on'] and y['peak']==D(810000) and y['episode']==1
z,dd,e=advance(y,D(700000),False,True,False,'ACT20_BREAK');assert e is None and z['on'] # Not a hidden lifetime peak rule.
y,dd,e=advance(x,D(810000),True,True,True,'ACT20_FAST');assert e is None and not y['on']
y,dd,e=advance(y,D(810000),True,False,False,'ACT20_FAST');assert e is None
y,dd,e=advance(y,D(810000),True,True,False,'ACT20_FAST');assert e=='resume'
x,dd,e=advance(s,D(900000),False,False,False,'ACT10_BREAK');assert e=='pause'
# Flat NAV by itself cannot recover; new external breakout is required.
y,dd,e=advance(x,D(900000),True,True,False,'ACT10_BREAK');assert e is None and not y['on']
(O/'synthetic-tests.json').write_text(json.dumps({'passed':True,'checks':9},indent=2));print('9 risk state contracts passed')

# Warning is not sufficient alone, loss alone below20 is not sufficient.
for nav,fast,expected in [(D(910000),False,None),(D(900000),False,'pause'),(D(900000),True,None),(D(800000),True,'pause')]:
 x,dd,e=advance(dict(on=True,peak=D(1000000),saw_off=False,previous_fast=True,episode=0),nav,False,fast,False,'ACT20_WARN');assert e==expected
(O/'synthetic-tests.json').write_text(json.dumps({'passed':True,'checks':13},indent=2))
