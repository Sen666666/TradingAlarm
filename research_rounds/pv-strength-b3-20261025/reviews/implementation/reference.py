"""Independent scalar B3 reference. Never imports the candidate implementation."""
import math
import statistics
import sys
import pandas as pd

NUMERIC = ['sigma','activity','shock','effective_shock','speed_21','speed_63','z_21','z_63',
           'amplitude_21','amplitude_63','return_21','return_63','local','background',
           'normal_grade','grade','freeze_active','freeze_created','freeze_released',
           'freeze_count','freeze_id','freeze_age','freeze_anchor','freeze_low','rapid_up',
           'freeze_anchor_price','freeze_low_price']
TABLE = {(-1,-1):(-1,'local_decline'),(-1,0):(-1,'down_background_pause'),
         (-1,1):(0,'down_background_rebound'),(0,-1):(-1,'local_decline'),
         (0,0):(0,'no_clear_progress'),(0,1):(1,'up_building'),
         (1,-1):(-1,'local_decline'),(1,0):(1,'up_background_pause'),(1,1):(2,'aligned_up')}

def cmp(a,b):
    gap=32*sys.float_info.epsilon*max(1,abs(a),abs(b))
    return 0 if abs(a-b)<=gap else (1 if a>b else -1)

def evidence(z,old):
    if cmp(z,1)>=0: return 1
    if cmp(z,-1)<=0: return -1
    return old if (old==1 and cmp(z,.5)>0) or (old==-1 and cmp(z,-.5)<0) else 0

def valid_reference(frame,joint=True):
    base=float(frame.close.iloc[0]); prices=[math.log(float(c)/base) for c in frame.close]
    volumes=list(map(float,frame.volume));changes=[math.nan]+[prices[i]-prices[i-1] for i in range(1,len(prices))]
    records=[];journal=[];memory={21:0,63:0};book={};counter=0
    for i,p in enumerate(prices):
        row={name:math.nan for name in NUMERIC};row['phase']='unknown'
        if i<64: records.append(row);continue
        sigma=max(math.sqrt(math.fsum(changes[j]**2 for j in range(i-63,i))/63),1e-8)
        activity=volumes[i]/statistics.median(volumes[i-21:i]);q=changes[i]/sigma
        eq=q*math.sqrt(min(4,max(1,activity)) if joint else 1)
        row.update(sigma=sigma,activity=activity,shock=q,effective_shock=eq,rapid_up=float(cmp(eq,2)>=0))
        for horizon in (21,63):
            ys=prices[i-horizon:i+1];center=math.fsum(ys)/(horizon+1)
            offsets=[j-horizon/2 for j in range(horizon+1)]
            slope=math.fsum(x*(y-center) for x,y in zip(offsets,ys))/math.fsum(x*x for x in offsets)
            z=math.sqrt(horizon)*slope/sigma;memory[horizon]=evidence(z,memory[horizon])
            row.update({f'speed_{horizon}':slope,f'z_{horizon}':z,f'amplitude_{horizon}':100*horizon*slope,
                        f'return_{horizon}':100*math.expm1(p-prices[i-horizon])})
        B,L=memory[63],memory[21];grade,phase=TABLE[(B,L)]
        row.update(background=float(B),local=float(L),normal_grade=float(grade),grade=float(grade),phase=phase,
                   freeze_active=0.,freeze_created=0.,freeze_released=0.,freeze_id=0.)
        for eid in list(book):
            e=book[eid];e['low']=min(e['low'],p);age=i-e['birth']
            why=('price_recovered' if cmp(p,e['anchor'])>=0 else 'downtrend_takeover' if L==-1 else
                 'outside_current_scale' if age>=21 else None)
            if why:
                journal.append(dict(observation=i,date=str(frame.index[i].date()),kind=why,event=eid,birth=e['birth'],low=e['low'],
                                    anchor=e['anchor'],close=p,age=age,price_recovered=cmp(p,e['anchor'])>=0))
                row['freeze_released']+=1;del book[eid]
        if cmp(eq,-2)<=0:
            counter+=1;book[counter]={'id':counter,'birth':i,'anchor':prices[i-1],'low':p}
            row['freeze_created']=1.
            journal.append(dict(observation=i,date=str(frame.index[i].date()),kind='freeze_created',event=counter,
                                anchor=prices[i-1],close=p,shock=q,activity=activity,effective_shock=eq))
        row['freeze_count']=float(len(book))
        if book:
            items=list(book.values());anchor=max(e['anchor'] for e in items);low=min(e['low'] for e in items)
            row.update(grade=-2.,phase='acute_damage',freeze_active=1.,freeze_id=float(max(book)),
                       freeze_age=float(i-min(e['birth'] for e in items)),freeze_anchor=anchor,freeze_low=low,
                       freeze_anchor_price=base*math.exp(anchor),freeze_low_price=base*math.exp(low))
        records.append(row)
    result=pd.DataFrame(records,index=frame.index);result.attrs['terminal']=list(book.values())
    return result,journal

def reference(frame,joint=True):
    result=pd.DataFrame(math.nan,index=frame.index,columns=NUMERIC);result['phase']='unknown'
    journal=[];archive=[];last_segment=None
    for segment in frame.segment_id.drop_duplicates():
        part=frame.loc[frame.segment_id.eq(segment)]
        if archive:
            journal.append(dict(segment=str(segment),date=str(part.index[0].date()),observation=None,
                                kind='source_discontinuity',previous_segment=last_segment,unresolved=archive))
        clean=part.loc[part.valid_strength_observation]
        archive=[]
        if len(clean):
            values,events=valid_reference(clean,joint);result.loc[clean.index,values.columns]=values
            journal.extend(dict(segment=str(segment),**event) for event in events);archive=values.attrs['terminal']
        last_segment=str(segment)
    return result,journal
