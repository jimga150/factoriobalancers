from enum import Enum

import z3

import common
from Balance import Balance
from Node import Node
from UniqueIDObj import UniqueIDObj


class ColorStrategy(Enum):
    PRIORITY = 0
    BACKPRESSURE = 1
    FLOW = 2

class Belt(UniqueIDObj):
    max_belt_val = common.ext_var_quant_denom if common.use_quant_ext_vars else 1

    def __init__(self, source: Node, dest: Node, source_priority: bool = False, dest_priority: bool = False):

        super().__init__()

        self.source = source
        self.dest = dest

        # is the source node prioritizing this output
        self.source_priority = source_priority

        # is the destination node prioritizing this input
        self.dest_priority = dest_priority

        self.enabled = True

        # PyCharm gets mad if I don't put these here
        self.supply = None
        self.demand = None
        self.pushing = None
        self.balance = Balance()
        self.reset()

    def reset(self):
        # keys are input nodes
        # values are ratio of that input's items (where 1 = this belt is full capacity with this input belt)
        self.balance = Balance()

        self.demand = 1
        self.supply = 0
        self.pushing = 0

    def __str__(self):
        return f"{self.source}->{self.dest} ({self.id})"

    def varname(self):
        return f"{self.source}_to_{self.dest}_{str(hash(self))[-4:]}"

    def supply_var(self):
        # as a fraction of the belts total capacity
        # the rate of items being fed to the belt (or trying to be fed to the belt)
        return z3.Real(self.varname() + "_s")

    def demand_var(self):
        # as a fraction of the belts total capacity
        # the rate of items being voided to the belt (or trying to be voided from the belt)
        return z3.Real(self.varname() + "_d")

    def pushing_var(self):
        # true when supply = demand and the input splitter wants to push more flow through this belt
        return z3.Bool(self.varname() + "_p")

    def flow_var(self):
        # as a fraction of the belts total capacity
        # the actual rate of items moving across the belt
        return common.z3realMin(self.supply_var(), self.demand_var())

    def virtual_supply_var(self):
        # add a smidge extra if "pushing" to cause demand to raise if it can
        return z3.If(self.pushing_var(), self.supply_var() + common.diff_threshold_iter, self.supply_var())

    def flow(self) -> float:
        return min(self.demand, self.supply)

    def virtual_supply(self) -> float:
        return self.supply + common.diff_threshold_iter if self.pushing else self.supply

    def get_label(self) -> str:
        if not self.enabled:
            return ""
        p = "+" if self.pushing else ""
        return f"{str(self.balance)} (S: {common.frac_str(self.supply)}{p}, D: {common.frac_str(self.demand)})"

    def get_color(self, strat: ColorStrategy = ColorStrategy.PRIORITY) -> str:
        if not self.enabled:
            return "white"

        if strat == ColorStrategy.BACKPRESSURE:
            if self.demand > self.virtual_supply():
                return "green"
            if self.demand < self.virtual_supply():
                return "red"

        if strat == ColorStrategy.FLOW:
            flow = self.flow()
            hue = 0.5 - 0.5*flow/Belt.max_belt_val # start at 0.5 (cyan) for 0 flow, move towards 0 (red) as flow increases
            return f"{hue} 0.75 0.75"

        if strat == ColorStrategy.PRIORITY:
            if self.source_priority and self.dest_priority:
                return "green"
            if self.source_priority:
                return "red"
            if self.dest_priority:
                return "blue"

        return "black"

    def is_balanced(self) -> bool:
        return self.balance.is_balanced()
