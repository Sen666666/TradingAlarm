"""Select from prior-close signals, reserving slots for actual holdings and pending entries."""
from collections import Counter
import math
class TrendSlots:
    def __init__(self,strength,groups=None,gates=None,slots=9,group_slots=None,entry_events=None):
        self.strength=strength;self.groups=groups;self.gates=gates;self.slots=slots;self.group_slots=group_slots
        self.entry_events=entry_events
        if slots<1 or (group_slots is not None and (groups is None or group_slots<1)):raise ValueError('Invalid slot constraints')
    def __call__(self,date,scores,qty,pending):
        def group(s):return self.groups.get((date,s)) if self.groups is not None else 'all'
        def admissible(s):
            g=group(s)
            return scores[s]>0 and (self.groups is None or g is not None) and (self.gates is None or self.gates.get((date,g),False))
        selected={s:0. for s in scores};held={s for s in scores if qty[s]>0}
        # Exit-intended positions still occupy slots until sale actually fills.
        reserved=set(held);counts=Counter(group(s) for s in held)
        for s in held:selected[s]=scores[s]
        # Pending entries reserve a slot; do not replace yesterday's order with today's ranking.
        for s in sorted(pending):
            if s not in held and pending[s]['target']>0 and admissible(s):
                selected[s]=scores[s];reserved.add(s);counts[group(s)]+=1
        candidates=[]
        for s in scores:
            if s in reserved or not admissible(s):continue
            if self.entry_events is not None and (date,s) not in self.entry_events:continue
            past=self.strength[s].loc[:date]
            if len(past) and math.isfinite(float(past.iloc[-1])):candidates.append((float(past.iloc[-1]),s))
        for _,s in sorted(candidates,key=lambda x:(-x[0],x[1])):
            if len(reserved)>=self.slots:break
            g=group(s)
            if self.group_slots is not None and counts[g]>=self.group_slots:continue
            selected[s]=scores[s];reserved.add(s);counts[g]+=1
        return selected
