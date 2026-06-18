import copy

import common

class Balance:

    def __init__(self):
        self.balance = dict()

    def __str__(self):
        if len(self.balance.keys()) == 0:
            return ""

        first_frac = list(self.balance.values())[0]
        is_equal = True
        for name, frac in self.balance.items():
            if abs(frac - first_frac) > common.diff_threshold_verif:
                is_equal = False
                break

        if first_frac < common.diff_threshold_verif and is_equal:
            return ""

        if is_equal and abs(1 / first_frac - len(self.balance.values())) < common.diff_threshold_verif:
            balance_node_names = [str(x) for x in self.balance.keys()]
            return "|".join(balance_node_names)

        balance_terms = [common.term_str(name, frac) for name, frac in self.balance.items()]
        balance_terms = [x for x in balance_terms if x != ""]
        return " + ".join(balance_terms)

    def __iter__(self):
        return iter(self.balance)

    def items(self):
        return self.balance.items()

    def keys(self):
        return self.balance.keys()

    def values(self):
        return self.balance.values()

    def __getitem__(self, item):
        return self.balance[item]

    def __setitem__(self, key, value):
        self.balance[key] = value

    def __add__(self, other: Balance):
        assert isinstance(other, Balance)
        ans = copy.deepcopy(self)
        ans.balance = {i: ans.balance.get(i, 0) + other.balance.get(i, 0)
                for i in set(ans.balance).union(other.balance)}
        ans.purge_null_balances()
        return ans

    def __radd__(self, other: Balance):
        return self + other

    def __mul__(self, other: float):
        assert isinstance(other, float) or isinstance(other, int)
        ans = copy.deepcopy(self)
        for k in ans.balance.keys():
            ans.balance[k] *= other
        ans.purge_null_balances()
        return ans

    def __rmul__(self, other: float):
        return self * other

    def __truediv__(self, other: float):
        assert isinstance(other, float) or isinstance(other, int)
        ans = copy.deepcopy(self)
        for k in self.balance.keys():
            ans.balance[k] /= other
        ans.purge_null_balances()
        return ans

    def __rtruediv__(self, other: float):
        return self / other

    def purge_null_balances(self):
        to_purge = []
        for name in self.balance.keys():
            if self.balance[name] < common.diff_threshold_verif:
                to_purge.append(name)

        for name in to_purge:
            del self.balance[name]

    def is_balanced(self) -> bool:
        return len(self.balance.keys()) == 1 or "|" in str(self)

    def magnitude(self):
        return sum(self.balance.values())
