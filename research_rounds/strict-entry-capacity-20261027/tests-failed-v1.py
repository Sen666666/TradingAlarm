from study import *
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
T=datetime(2025,1,1,15,tzinfo=ZoneInfo('Asia/Shanghai'));clock=E.admission.Clock(T,T+timedelta(days=1),T.date());Fact=E.admission.Fact;Rank=E.admission.Rank
sectors=tuple(E.admission.Sector('s'+str(i),Fact(True,T,T),Rank(90-i,T,T)) for i in range(3));stocks=[]
for i in range(18):
 stocks.append(E.admission.Security(str(i),Fact(str(i),T,T),Fact('s'+str(i//6),T,T),Fact(True,T,T),Fact(True,T,T),Fact(2e10,T,T),Fact(True,T,T),Rank(90-i,T,T)))
args=dict(clock=clock,variant='S0',securities=stocks,sectors=sectors,previous=(),occupied=(),bootstrap=True,completed_exits=())
a=original_decide(**args);b=decide12(**args);assert len(a.selected)==6 and len(b.selected)==12
from collections import Counter
assert sorted(Counter(int(i)//6 for i in a.selected).values())==[2,2,2];assert sorted(Counter(int(i)//6 for i in b.selected).values())==[4,4,4]
# Insufficient candidates are not invented by the larger allocator.
a2=original_decide(**{**args,'securities':stocks[:2]});b2=decide12(**{**args,'securities':stocks[:2]});assert a2==b2
save(O/'tests.json',{'passed':True,'six_selected':list(a.selected),'twelve_selected':list(b.selected),'sector_caps_checked':True,'sparse_candidates_identical':True})
