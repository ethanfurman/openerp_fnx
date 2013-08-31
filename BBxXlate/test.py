#!/usr/bin/python

class Integers:
    def __init__(self, step=None, auto=0):
        self.lb = None   #Lower bound (inclusive)
        self.ub = None   #Upper bound (inclusive)
        self.up = None   #Flag: Are we counting up (a<i<c) or down (a>i>c)?
        self.step = step #Stepping increment
        self.auto = auto #Automatically return an iterator when we have 2
                         # bounds?

    def __gt__(self, n):
        self.lb = n+1
        if self.ub == None: self.up = 1
        if self.auto and self.ub != None and self.lb != None:
            return iter(self)
        else:
            return self

    def __lt__(self, n):
        self.ub = n-1
        if self.lb == None: self.up = 0
        if self.auto and self.ub != None and self.lb != None:
            return iter(self)
        else:
            return self

    def __ge__(self, n):
        self.lb=n
        if self.ub == None: self.up = 1
        if self.auto and self.ub != None and self.lb != None:
            return iter(self)
        else:
            return self

    def __le__(self, n):
        self.ub=n
        if self.lb == None: self.up = 0
        if self.auto and self.ub != None and self.lb != None:
            return iter(self)
        else:
            return self

    def __nonzero__(self):
        return 1

    def __iter__(self):
        if self.step == None:
            self.step = (-1, 1)[self.up]
        else:
            assert self.step != 0 and self.up == (self.step > 0)

        if self.up:
            return iter(xrange(self.lb, self.ub+1, self.step))
        else:
            return iter(xrange(self.ub, self.lb-1, self.step))

ints = Integers(step=1, auto=1)

if __name__=='__main__':

    assert [i for i in 1 <= Integers() <= 10] == range(1,11)
    assert [i for i in 10 >= Integers() >= 1] == range(10,0,-1)

    assert [i for i in 1 < Integers() < 10] == range(2,10)
    assert [i for i in 10 > Integers() > 1] == range(9,1,-1)

    assert [i for i in 1 < Integers() <= 10] == range(2,11)
    assert [i for i in 10 > Integers() >= 1] == range(9,0,-1)

    assert [i for i in 1 <= Integers() < 10] == range(1,10)
    assert [i for i in 10 >= Integers() > 1] == range(10,1,-1)

    assert [i for i in 2 <= Integers(step=2) < 99] == range(2,99,2)

    n = 0
    for i in 1 <= ints <= 10:
        for j in 1 <= ints <= 10:
            n += 1
    assert n == 100

    assert zip(1 <= ints <= 3, 1 <= ints <= 3) == zip((1,2,3), (1,2,3))
