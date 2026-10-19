"""Exit contract, one meaning per code.

0  ok
1  findings: the check ran and found problems (claims violations, a refusal)
2  NOT EVALUABLE: cannot run or cannot judge; the message says which and why
3  drift: a topic's derived state disagrees with its log (``learn rebuild``)
64 usage error
"""
OK, FINDINGS, NOT_EVALUABLE, DRIFT, USAGE = 0, 1, 2, 3, 64


class CareerloopError(Exception):
    code = FINDINGS


class Refused(CareerloopError):
    code = FINDINGS


class NotEvaluable(CareerloopError):
    code = NOT_EVALUABLE


class UsageError(CareerloopError):
    code = USAGE


class Drifted(CareerloopError):
    code = DRIFT
