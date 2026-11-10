"""Frozen v4 five-state reference: ranking/state arithmetic only, standard library.

No score calculation, market data, future labels, portfolio or account imports.
P_order is exact one-based order in P-known industries. None/NaN is missing.
"""
import math
from numbers import Real

STATES=('I0','I1','A0','A1','A2')
ALL_INITIAL=frozenset(STATES)
ORDER={s:i for i,s in enumerate(STATES)}


def ordered_states(states):
 states=frozenset(states)
 if not states or not states.issubset(ALL_INITIAL):raise ValueError('Nonempty subset of five frozen states required')
 return tuple(sorted(states,key=ORDER.__getitem__))


def normalize_rank(rank):
 if rank is None:return None
 if isinstance(rank,bool) or not isinstance(rank,Real):raise TypeError('P_order must be one-based numeric integer or None/NaN')
 if not math.isfinite(rank):return None
 if rank<1 or int(rank)!=rank:raise ValueError('P_order is one-based integer; never pass old rank0')
 return int(rank)


def transition_one(state,p_order):
 """Return state AFTER this common-session CLOSE; no date-dependent reset."""
 if state not in ALL_INITIAL:raise ValueError('Unknown state')
 rank=normalize_rank(p_order)
 if rank is None:return 'I0' if state.startswith('I') else 'A0'
 if rank<=5:return 'I1' if state=='I0' else 'A0'
 if rank<=10:return 'I0' if state.startswith('I') else 'A0'
 return {'I0':'I0','I1':'I0','A0':'A1','A1':'A2','A2':'I0'}[state]


def transition_set(states,p_order):
 return frozenset(transition_one(s,p_order) for s in ordered_states(states))


def public_mature(states,p_order_known):
 """Unknown P forces published unknown even when internal phase is determined."""
 ordered_states(states)
 if not p_order_known:return None
 active={s.startswith('A') for s in states}
 return next(iter(active)) if len(active)==1 else None


def kleene_or(a,b):
 for v in (a,b):
  if v is not True and v is not False and v is not None:raise TypeError('Tri-state bool must be True/False/None')
 if a is True or b is True:return True
 if a is None or b is None:return None
 return False


def step(states,p_order,t_selected=False):
 rank=normalize_rank(p_order)
 after=transition_set(states,rank)
 mature=public_mature(after,rank is not None)
 return {'states_after':ordered_states(after),'internal_state_identified':len(after)==1,
         'public_mature':mature,'union':kleene_or(mature,t_selected),
         'public_P_unknown_reason':'P_INPUT_UNKNOWN' if rank is None else 'INITIAL_PHASE_UNRESOLVED' if mature is None else None}


def run_path(p_orders,initial=ALL_INITIAL,t_selected=None,session_labels=None):
 """Each supplied row is an adjacent common session. Never drop missing ranks."""
 initial=frozenset(initial);ordered_states(initial)
 if t_selected is None:t_selected=[False]*len(p_orders)
 if session_labels is None:session_labels=list(range(len(p_orders)))
 if len(p_orders)!=len(t_selected) or len(p_orders)!=len(session_labels):raise ValueError('Input path lengths differ')
 states=initial;out=[]
 for n,(rank,t,sess) in enumerate(zip(p_orders,t_selected,session_labels)):
  before=ordered_states(states);r=step(states,rank,t);states=frozenset(r['states_after'])
  out.append(dict(session_index=n,session_label=sess,P_order=normalize_rank(rank),T_selected=t,states_before=before,**r))
 return out
