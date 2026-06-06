import copy

import common
from Belt import Belt

class Splitter:

    def __init__(self, inputs: list[Belt], outputs: list[Belt]):
        self.inputs = inputs
        self.outputs = outputs

        # sources = ", ".join([str(x.source) for x in inputs])
        # dests = ", ".join([str(x.dest) for x in outputs])
        # print(f"{sources=} and {dests=}")

        if len(self.inputs) > 0:
            self.node = self.inputs[0].dest
        else:
            assert len(self.outputs) > 0
            self.node = self.outputs[0].source

        for belt in self.outputs:
            assert belt.source == self.node

        for node in self.inputs:
            assert node.dest == self.node

    def __str__(self):
        sources = ", ".join([str(x.source) for x in self.inputs])
        dests = ", ".join([str(x.dest) for x in self.outputs])
        return f"{sources} --> {dests}"

    def get_output_demand(self) -> float:
        return sum([x.demand for x in self.outputs])

    def get_input_demand(self) -> float:
        return sum([x.demand for x in self.inputs])

    # return True if input demands changed
    def update_input_demand(self) -> bool:

        is_changed = False

        old_demands = [x.demand for x in self.inputs if x.enabled]

        output_demand = self.get_output_demand()
        input_demand = self.get_input_demand()

        if output_demand == 0:
            assert len(self.inputs) == 1
            # print(f"Output splitter: setting belt {self.inputs[0]} to 1")
            self.inputs[0].demand = 1
        elif output_demand < input_demand:
            new_demand = output_demand / len(self.inputs)
            # print(f"{self.node}: output demand ({output_demand}) < input demand ({input_demand}), setting input demands each to {new_demand}")
            for belt in self.inputs:
                belt.demand = new_demand

        new_demands = [x.demand for x in self.inputs if x.enabled]
        for i in range(len(new_demands)):
            new_demand = new_demands[i]
            old_demand = old_demands[i]
            if abs(new_demand - old_demand) > common.diff_threshold_iter:
                is_changed = True

        return is_changed

    def update_output_balance(self) -> bool:
        is_changed = False

        # record old balances for change detection
        old_balances = [copy.deepcopy(x.supply_balance) for x in self.outputs if x.enabled]
        num_enabled_outputs = len(old_balances)

        if num_enabled_outputs == 0:
            return False

        print(f"Splitter: {self}")

        input_balances = [x.supply_balance for x in self.inputs if x.enabled]

        if len(self.inputs) == 0:
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            self.outputs[0].supply_balance[self.node] = self.outputs[0].demand
            print(f"No inputs, setting {self.node} to demand ({self.outputs[0].demand})")
        elif len(input_balances) == 0:
            # no inputs are enabled, just wipe the record and move on
            for belt in self.outputs:
                belt.supply_balance.clear()
            print(f"No inputs enabled, clearing balances")
        else:

            # calculate the sum of the input belt balances as a dict
            total_supply_balance = dict()
            for belt in self.inputs:
                if not belt.enabled:
                    continue
                total_supply_balance = {i: total_supply_balance.get(i, 0) + belt.supply_balance.get(i, 0)
                                        for i in set(total_supply_balance).union(belt.supply_balance)}

            print("Total supply balance:")
            for k, v in total_supply_balance.items():
                print(f"\t{k}: {v}")

            # sum of magnitude of all balances coming into splitter
            total_supply = sum(total_supply_balance.values())
            print(f"Total supply: {total_supply}")

            # minimum of output belt demands--input supply will be split evenly up to this magnitude
            min_demand = min([x.demand if x.enabled else 0 for x in self.outputs])
            print(f"Min demand: {min_demand}")
            if min_demand * num_enabled_outputs > total_supply:
                min_demand_scaling_factor = 1.0 / num_enabled_outputs
                tsb_scale_factor = 0
            else:
                min_demand_scaling_factor = min_demand / total_supply
                new_total_supply = total_supply - (min_demand * num_enabled_outputs)
                tsb_scale_factor = new_total_supply / total_supply

            print(f"Min demand scaling factor: {min_demand_scaling_factor}")
            print(f"Total Supply Balance scaling factor: {tsb_scale_factor}")

            # fill all outputs with equal amount of supply
            for belt in self.outputs:
                if not belt.enabled:
                    continue
                belt.supply_balance = {k: v * min_demand_scaling_factor for k, v in total_supply_balance.items()}

            print(f"After filling belts to min demand: ")
            for belt in self.outputs:
                if not belt.enabled:
                    continue
                print(belt.get_label())

            # scale total supply down to represent what hasn't yet been moved to output belts
            total_supply_balance = {k: v * tsb_scale_factor for k, v in total_supply_balance.items()}
            total_supply *= tsb_scale_factor

            print("After scaling down supply:")
            print("Total supply balance:")
            for k, v in total_supply_balance.items():
                print(f"\t{k}: {v}")

            # sum of magnitude of all balances coming into splitter
            total_supply = sum(total_supply_balance.values())
            print(f"Total supply: {total_supply}")

            # if one belt has greater demand, fill that with more supply
            for belt in self.outputs:

                if not belt.enabled:
                    continue
                if belt.demand <= min_demand:
                    continue

                print(f"Belt {belt} has higher demand: {belt.demand}")
                additional_demand = belt.demand - min_demand
                if total_supply < additional_demand:
                    print(f"total_supply ({total_supply}) < additional_demand ({additional_demand})")
                    as_ratio = 1
                else:
                    print(f"total_supply ({total_supply}) >= additional_demand ({additional_demand})")
                    as_ratio = additional_demand / total_supply

                print(f"as_ratio: {as_ratio}")

                belt.supply_balance = {i: total_supply_balance.get(i, 0)*as_ratio + belt.supply_balance.get(i, 0)
                                        for i in set(total_supply_balance).union(belt.supply_balance)}

                print("Belt supply balance after adding more:")
                for k, v in belt.supply_balance.items():
                    print(f"\t{k}: {v}")

        # check for any changes in balance
        new_balances = [x.supply_balance for x in self.outputs if x.enabled]
        for i in range(len(new_balances)):
            new_balance = new_balances[i]
            old_balance = old_balances[i]
            for name, frac in new_balance.items():
                if name not in old_balance or abs(old_balance[name] - frac) > common.diff_threshold_iter:
                    is_changed = True
            for name in old_balance.keys():
                if name not in new_balance:
                    is_changed = True

        return is_changed