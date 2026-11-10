"""Chronological displacement cancellation, a diagnostic representation only.

Opposite motion cancels the most recent retained displacement first (LIFO).
All retained fragments keep their original activity and observation identity.
No future observations, account holdings, or transaction returns are used.
"""
import numpy as np


def cancel(moves, weights=None):
    moves=np.asarray(moves,dtype=float)
    weights=np.ones(len(moves)) if weights is None else np.asarray(weights,dtype=float)
    if moves.shape!=weights.shape or not np.isfinite(moves).all() or not np.isfinite(weights).all() or (weights<=0).any():
        raise ValueError('finite equally shaped moves, positive weights required')
    stack=[]
    for i,(move,weight) in enumerate(zip(moves,weights)):
        remaining=float(move)
        while stack and remaining*stack[-1][0]<0:
            last=stack[-1][0]
            if abs(remaining)>=abs(last):
                remaining+=last;stack.pop()
            else:
                stack[-1][0]+=remaining;remaining=0.
        if remaining!=0:stack.append([remaining,float(weight),i])
    net=sum(x[0] for x in stack)
    weighted=sum(x[0]*x[1] for x in stack)
    return dict(net=net,weighted=weighted,retained_absolute=sum(abs(x[0]) for x in stack),fragments=stack)
