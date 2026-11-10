"""Research-only port: route reserve/fill through the existing RB1 sizing branch.

The account's I/ACT policy mode is restored before returning. No market,
admission, risk clock, candidate memory, or exit implementation is replaced.
"""
from contextlib import contextmanager

def account_class(Parent):
    class RB1SizingAccount(Parent):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.rb1_sizing=False

        @contextmanager
        def original_sizing_branch(self):
            old=self.mode
            assert old in ('I','ACT'), f'unexpected native policy {old}'
            self.mode='RB1'
            try:
                yield
            finally:
                self.mode=old

        def reserve_budget(self,**kwargs):
            if not self.rb1_sizing:
                return super().reserve_budget(**kwargs)
            with self.original_sizing_branch():
                return super().reserve_budget(**kwargs)

        def fill_buy(self,sid,window):
            if not self.rb1_sizing:
                return super().fill_buy(sid,window)
            with self.original_sizing_branch():
                return super().fill_buy(sid,window)
    return RB1SizingAccount
