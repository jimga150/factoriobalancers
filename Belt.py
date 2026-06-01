from common import *


class Belt:

    def __init__(self, source, dest):
        self.source = source
        self.dest = dest

        self.balance = dict()
        self.processed = False

        self.enabled = True

    def get_label(self):

        if len(self.balance.keys()) > 1:
            first_frac = list(self.balance.values())[0]
            is_equal = True
            for name, frac in self.balance.items():
                if frac != first_frac:
                    is_equal = False
                    break

            if is_equal and abs(1/first_frac - len(self.balance.values())) < diff_threshold_verif:
                return "|".join(list(self.balance.keys()))

        return " + ".join([f"{frac:.{decimals_verif}f}*{name}" if frac != 1 else str(name) for name, frac in self.balance.items()])

    def is_balanced(self):
        return len(self.balance.keys()) == 1 or "|" in self.get_label()

    def is_input(self):
        return type(self.source) == str

    def is_output(self):
        return type(self.dest) == str

    def __str__(self):
        return f"{self.source}->{self.dest}"