import copy

import common
from Belt import Belt

class Splitter:

    def __init__(self, inputs: list[Belt], outputs: list[Belt]):
        self.inputs = inputs
        self.outputs = outputs

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
        return str(self.node)

    def get_output_demand(self) -> float:
        return sum([x.demand for x in self.get_enabled_outputs()])

    def get_input_demand(self) -> float:
        return sum([x.demand for x in self.get_enabled_outputs()])

    def is_input_proxy(self):
        return len(self.inputs) == 0

    def is_output_proxy(self):
        return len(self.outputs) == 0

    def get_enabled_inputs(self) -> list[Belt]:
        return [x for x in self.inputs if x.enabled]

    def get_enabled_outputs(self) -> list[Belt]:
        return [x for x in self.outputs if x.enabled]

    def update_check_output_balance(self) -> bool:

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        # record old balances for change detection
        old_real_balances = [copy.deepcopy(x.real_balance) for x in enabled_outputs]
        old_desired_balances = [copy.deepcopy(x.desired_balance) for x in enabled_outputs]
        old_demands = [x.demand for x in enabled_inputs]

        common.debug_print(f"------------------------------------------------")
        common.debug_print(f"update_output_balance, Splitter: {self}")
        common.debug_print(f"Inputs:")
        for in_belt in enabled_inputs:
            common.debug_print(f"\tfrom {in_belt.source}:")
            common.debug_print(f"\t\t{in_belt.get_label()}")
            common.debug_print(f"\t\t{in_belt.get_label(True)}")
        common.debug_print(f"Outputs:")
        for out_belt in enabled_outputs:
            common.debug_print(f"\tto {out_belt.dest}:")
            common.debug_print(f"\t\t{out_belt.get_label()}")
            common.debug_print(f"\t\t{out_belt.get_label(True)}")
        common.debug_print(f"------------------------------------------------")

        self.update_output_balance()

        common.debug_print(f"------------------------------------------------")
        common.debug_print(f"Done with update_output_balance, Splitter: {self}")
        common.debug_print(f"Inputs:")
        for in_belt in enabled_inputs:
            common.debug_print(f"\tfrom {in_belt.source}:")
            common.debug_print(f"\t\t{in_belt.get_label()}")
            common.debug_print(f"\t\t{in_belt.get_label(True)}")
        common.debug_print(f"Outputs:")
        for out_belt in enabled_outputs:
            common.debug_print(f"\tto {out_belt.dest}:")
            common.debug_print(f"\t\t{out_belt.get_label()}")
            common.debug_print(f"\t\t{out_belt.get_label(True)}")
        common.debug_print(f"------------------------------------------------")

        # check for any changes in balance
        enabled_outputs = [x for x in enabled_outputs]

        # remove any balance items that are basically 0

        for out_belt in enabled_inputs:
            out_belt.real_balance = {name: frac for name, frac in out_belt.real_balance.items()
                                     if abs(frac) > common.diff_threshold_iter}
            out_belt.desired_balance = {name: frac for name, frac in out_belt.desired_balance.items()
                                     if abs(frac) > common.diff_threshold_iter}

        for out_belt in enabled_outputs:
            out_belt.real_balance = {name: frac for name, frac in out_belt.real_balance.items()
                                     if abs(frac) > common.diff_threshold_iter}
            out_belt.desired_balance = {name: frac for name, frac in out_belt.desired_balance.items()
                                     if abs(frac) > common.diff_threshold_iter}

        new_real_balances = [x.real_balance for x in enabled_outputs]
        new_desired_balances = [x.desired_balance for x in enabled_outputs]

        is_changed = False

        for i in range(len(new_real_balances)):
            new_real_balance = new_real_balances[i]
            new_desired_balance = new_desired_balances[i]
            old_real_balance = old_real_balances[i]
            old_desired_balance = old_desired_balances[i]
            for name, frac in new_real_balance.items():
                if name not in old_real_balance:
                    common.debug_print(f"\tchange: {name} added to {enabled_outputs[i]} (real)")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
                elif abs(old_real_balance[name] - frac) > common.diff_threshold_iter:
                    common.debug_print(f"\tchange: {name} in {enabled_outputs[i]} changed from {old_real_balance[name]} to {frac} (real)")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
            for name, frac in new_desired_balance.items():
                if name not in old_desired_balance:
                    common.debug_print(f"\tchange: {name} added to {enabled_outputs[i]} (desired)")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
                elif abs(old_desired_balance[name] - frac) > common.diff_threshold_iter:
                    common.debug_print(f"\tchange: {name} in {enabled_outputs[i]} changed from {old_desired_balance[name]} to {frac} (desired)")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
            for name in old_real_balance.keys():
                if name not in new_real_balance:
                    common.debug_print(f"\tchange: {name} removed from {enabled_outputs[i]} (real)")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
            for name in old_desired_balance.keys():
                if name not in new_desired_balance:
                    common.debug_print(f"\tchange: {name} removed from {enabled_outputs[i]} (desired)")
                    if common.debug:
                        is_changed = True
                    else:
                        return True

        # check for any changes in demand
        new_demands = [x.demand for x in enabled_inputs]
        for i in range(len(new_demands)):
            new_demand = new_demands[i]
            old_demand = old_demands[i]
            if abs(new_demand - old_demand) > common.diff_threshold_iter:
                common.debug_print(f"\tchange: demand of {enabled_inputs[i]} changed from {old_demand} to {new_demand}")
                if common.debug:
                    is_changed = True
                else:
                    return True

        return is_changed

    # apply input supply to outputs, and apply output demand to inputs based on actual flow rate
    def update_output_balance(self):

        if self.is_input_proxy():
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            self.outputs[0].desired_balance[self.node] = 1
            common.debug_print(f"Input proxy, setting {self.node} to demand ({self.outputs[0].demand})")
            return

        if self.is_output_proxy():
            assert len(self.inputs) == 1
            common.debug_print(f"Output proxy: setting demand of {self.inputs[0]} to 1")
            self.inputs[0].demand = 1
            self.inputs[0].scale_real_to_demand()
            return

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        num_enabled_inputs = len(enabled_inputs)
        num_enabled_outputs = len(enabled_outputs)

        if num_enabled_inputs == 0:
            common.debug_print(f"No enabled inputs, skipping")
            return

        for belt in enabled_inputs:
            assert belt.demand >= 0

        for belt in enabled_outputs:
            assert belt.demand >= 0

        total_desired_supply_balance = self.get_total_desired_supply_balance()

        common.debug_print("Total desired balance:")
        for k, v in total_desired_supply_balance.items():
            common.debug_print(f"\t{k}: {v}")

        total_desired_supply = sum(total_desired_supply_balance.values())
        common.debug_print(f"Total desired supply: {total_desired_supply}")

        min_desired_supply = min([x.get_desired_strength() for x in enabled_inputs])
        min_desired_supply_belt = next(x for x in enabled_inputs if x.get_desired_strength() == min_desired_supply)
        max_desired_supply_belt = next((x for x in enabled_inputs if x.get_desired_strength() > min_desired_supply), None)

        if max_desired_supply_belt is None:
            min_desired_supply_belt = enabled_inputs[0]
            max_desired_supply_belt = enabled_inputs[-1]

        total_demand = sum([x.demand for x in enabled_outputs])

        has_priority_input = any([x.dest_priority for x in enabled_inputs])

        if has_priority_input:
            common.debug_print(f"Has priority input")
            priority_belt = next(x for x in enabled_inputs if x.dest_priority)
            priority_belt.demand = min(total_demand, 1)
            if num_enabled_inputs > 1:
                assert num_enabled_inputs == 2
                non_priority_belt = next(x for x in enabled_inputs if not x.dest_priority)
                non_priority_belt.demand = min(total_demand - priority_belt.get_desired_strength(), 1)
                if non_priority_belt.demand < 0:
                    non_priority_belt.demand = 0
        else:
            common.debug_print(f"No priority input")
            if min_desired_supply * num_enabled_inputs >= total_demand:
                common.debug_print(f"Applying backpressure evenly to inputs")
                for belt in enabled_inputs:
                    belt.demand = total_demand / num_enabled_inputs
            elif total_desired_supply > total_demand:
                common.debug_print(f"Applying backpressure to higher throughput belt to meet demand limit")
                oversupply = total_desired_supply - total_demand
                max_desired_supply_belt.demand = max_desired_supply_belt.get_desired_strength() - oversupply
                min_desired_supply_belt.demand = min_desired_supply_belt.get_desired_strength()
            else:
                common.debug_print(f"Relaxing backpressure")
                # for belt in enabled_inputs:
                #     belt.demand = belt.get_desired_strength()
                # overdemand = total_demand - total_real_supply
                # for belt in enabled_inputs:
                #     belt.demand = min(1, belt.demand + overdemand)
                for belt in enabled_inputs:
                    belt.demand = min(1, total_demand)

        for belt in enabled_inputs:
            belt.scale_real_to_demand()

        common.debug_print(f"After applying backpressure:")
        for in_belt in enabled_inputs:
            common.debug_print(f"\tfrom {in_belt.source}: {in_belt.get_label()}")

        
        total_real_supply_balance = self.get_total_real_supply_balance()

        common.debug_print("Total real balance:")
        for k, v in total_real_supply_balance.items():
            common.debug_print(f"\t{k}: {v}")

        # sum of magnitude of all balances coming into splitter
        total_real_supply = sum(total_real_supply_balance.values())
        common.debug_print(f"Total real supply: {total_real_supply}")

        priority_outputs = [x for x in enabled_outputs if x.source_priority]
        nonpriority_outputs = [x for x in enabled_outputs if not x.source_priority]

        has_priority_output = len(priority_outputs) > 0

        # no more than 1 priority output please
        assert len(priority_outputs) < 2

        if has_priority_output:
            common.debug_print("Has priority output")
            priority_output = priority_outputs[0]

            pri_ratio = 1
            if total_real_supply > 1:
                pri_ratio = 1 / total_real_supply

            # fill priority output with real supply up to strength 1
            priority_output.desired_balance.clear()
            for k, v in total_real_supply_balance.items():
                priority_output.desired_balance[k] = v * pri_ratio

            if len(nonpriority_outputs) > 0:
                nonpri_supply_limit = total_real_supply - priority_output.demand

                if nonpri_supply_limit < 0:
                    nonpri_supply_limit = 0
                if nonpri_supply_limit > 1:
                    nonpri_supply_limit = 1

                nonpriority_output = nonpriority_outputs[0]
                desired_strength = min(nonpri_supply_limit, total_real_supply)

                if desired_strength > 0:
                    nonpri_ratio = desired_strength / total_real_supply
                else:
                    nonpri_ratio = 0
                # fill nonpriority output with real supply up to what is left over
                # after subtracting the demand of the priority output
                nonpriority_output.desired_balance.clear()
                for k, v in total_real_supply_balance.items():
                    nonpriority_output.desired_balance[k] = v * nonpri_ratio
        else:
            common.debug_print("No priority output")
            # fill desired output balances, ignoring demand
            for belt in enabled_outputs:
                belt.desired_balance.clear()
                for k, v in total_real_supply_balance.items():
                    belt.desired_balance[k] = v / num_enabled_outputs

            common.debug_print("After applying real supply evenly:")
            for belt in enabled_outputs:
                common.debug_print(belt.get_label(True))

            # if any output belt has a demand restricting it below its desired balance,
            # add the difference to the desired balance of the others.
            # we keep the restricted belt's balance where it is in case that backpressure reduces in later iterations
            oversupplies = []
            for i in range(len(enabled_outputs)):
                belt = enabled_outputs[i]
                oversupply = max(0, belt.get_desired_strength() - belt.demand)
                oversupplies.append(oversupply)

            assert(len(oversupplies) == len(enabled_outputs))

            for i in range(len(oversupplies)):
                # oversupply of all other outputs
                belt = enabled_outputs[i]
                desired_strength = belt.get_desired_strength()
                if desired_strength <= 0:
                    continue

                oversupply_to_apply = sum(oversupplies[:i]) + sum(oversupplies[i+1:])
                ratio = (oversupply_to_apply + desired_strength) / desired_strength

                common.debug_print(f"\t{belt} will get oversupply of {oversupply_to_apply} from other belts")

                for name in belt.desired_balance.keys():
                    belt.desired_balance[name] = belt.desired_balance[name] * ratio

        common.debug_print(f"After filling output desired balance: ")
        for belt in enabled_outputs:
            common.debug_print(belt.get_label(True))

        return

    def get_total_real_supply_balance(self) -> dict:
        # calculate the sum of the input belt balances as a dict
        real_balance = dict()
        enabled_inputs = self.get_enabled_inputs()

        for belt in enabled_inputs:
            common.debug_print(f"Adding belt {belt.get_label()}")
            real_balance = Belt.merge_balances_eq(real_balance, belt.real_balance)

        return real_balance

    def get_total_desired_supply_balance(self) -> dict:
        # calculate the sum of the input belt balances as a dict
        desired_balance = dict()
        enabled_inputs = self.get_enabled_inputs()

        for belt in enabled_inputs:
            common.debug_print(f"Adding belt {belt.get_label(True)}")
            desired_balance = Belt.merge_balances_eq(desired_balance, belt.desired_balance)

        return desired_balance