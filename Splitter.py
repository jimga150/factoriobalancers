import copy
from logging import Logger

import z3

import common
from Balance import Balance
from Belt import Belt

class Splitter:

    def __init__(self, inputs: list[Belt], outputs: list[Belt]):
        self.inputs = inputs
        self.outputs = outputs

        assert len(self.inputs) <= 2
        assert len(self.outputs) <= 2

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
    
    def populate_solver(self, solver: z3.Solver, logger: Logger):
        if self.is_input_proxy() or self.is_output_proxy():
            logger.debug(f"Proxy, skipping...")
            return

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        num_enabled_inputs = len(enabled_inputs)
        num_enabled_outputs = len(enabled_outputs)

        input_demand_vars = [belt.demand_var() for belt in enabled_inputs]
        output_demand_vars = [belt.demand_var() for belt in enabled_outputs]
        total_output_demand_var = z3.Sum(output_demand_vars)
        solver.assert_and_track(
            z3.Sum(input_demand_vars) == common.z3realMin(total_output_demand_var,
                                                          num_enabled_inputs * Belt.max_belt_val),
            f"{str(self)}_d_io_eq"
        )

        input_supply_vars = [belt.supply_var() for belt in enabled_inputs]
        output_supply_vars = [belt.supply_var() for belt in enabled_outputs]
        total_input_supply_var = z3.Sum(input_supply_vars)
        # removed because supply will now be created to force backpressure
        solver.assert_and_track(
            common.z3realMin(total_input_supply_var, num_enabled_outputs * Belt.max_belt_val) == z3.Sum(
                output_supply_vars),
            f"{str(self)}_s_io_eq"
        )

        output_pushing_vars = [belt.pushing_var() for belt in enabled_outputs]
        input_virtual_supply_vars = [belt.virtual_supply_var() for belt in enabled_inputs]
        total_input_virtual_supply_var = z3.Sum(input_virtual_supply_vars)

        # input_flow_vars = [belt.flow_var() for belt in enabled_inputs]
        # total_input_flow_var = z3.Sum(input_flow_vars)
        # output_flow_vars = [belt.flow_var() for belt in enabled_outputs]
        # total_output_flow_var = z3.Sum(output_flow_vars)
        # solver.assert_and_track(
        #     common.z3realMin(total_input_flow_var, num_enabled_outputs*Belt.max_belt_val) == total_output_flow_var,
        #     f"{str(self)}_f_io_eq"
        # )

        # -------------------------------------------------------------
        # Handle demand of inputs
        # -------------------------------------------------------------

        has_priority_input = any([x.dest_priority for x in enabled_inputs])

        no_backpressure = z3.And(
            z3.If(input_supply_vars[0] == Belt.max_belt_val, input_demand_vars[0] == Belt.max_belt_val,
                  input_demand_vars[0] > input_virtual_supply_vars[0]),
            z3.If(input_supply_vars[-1] == Belt.max_belt_val, input_demand_vars[-1] == Belt.max_belt_val,
                  input_demand_vars[-1] > input_virtual_supply_vars[-1])
        )

        if has_priority_input:
            logger.debug(f"Has priority input")

            # overall equation:
            # if total_demand > total_virtual_supply:
            #   both demands > their supply
            # else
            #   priority input demand = min(total demand, pri supply)
            #   (demand of other input derivable from self _d_io_eq rule)

            priority_belt = next(x for x in enabled_inputs if x.dest_priority)
            priority_belt_demand_var = priority_belt.demand_var()
            priority_belt_supply_var = priority_belt.supply_var()

            solver.assert_and_track(z3.If(
                total_output_demand_var > total_input_virtual_supply_var,
                no_backpressure,
                priority_belt_demand_var == common.z3realMin(total_output_demand_var, priority_belt_supply_var)
            ), f"{str(self)}_pri_i")

        else:
            logger.debug(f"No priority input")

            # overall equation:
            # if min_virtual_supply * num_enabled_inputs >= total_demand:
            #   apply backpressure evenly
            # elif total_supply > total_demand:
            #   (uneven backpressure):
            #   (belt with min input)'s demand = its supply
            #   other belt demand = total demand - former's demand
            # else (no backpressure)
            #   both demands > their supply

            min_virtual_input_supply_var = common.z3realMin(input_virtual_supply_vars[0], input_virtual_supply_vars[-1])

            uneven_backpressure = z3.And(
                input_demand_vars[0] <= input_virtual_supply_vars[0],
                input_demand_vars[-1] <= input_virtual_supply_vars[-1],
                input_demand_vars[0] >= min_virtual_input_supply_var,
                input_demand_vars[-1] >= min_virtual_input_supply_var
            )

            uneven_backpressure_cond = z3.If(
                total_input_supply_var >= total_output_demand_var,
                uneven_backpressure,
                # input_demand_vars[0] - input_virtual_supply_vars[0] == input_demand_vars[-1] - input_virtual_supply_vars[-1]
                no_backpressure
            )

            to_add = z3.If(
                min_virtual_input_supply_var * num_enabled_inputs >= total_output_demand_var,
                input_demand_vars[0] == input_demand_vars[-1],
                uneven_backpressure_cond
            )

            logger.debug(f"to_add: {str(to_add)}")

            solver.assert_and_track(to_add, f"{str(self)}_nonpri_i")

        # -------------------------------------------------------------
        # Handle supply of outputs
        # -------------------------------------------------------------

        has_priority_output = any(x.source_priority for x in enabled_outputs)

        # both supply > their demands
        both_backpressure = z3.And(

            # oversupply on both outputs
            z3.If(output_demand_vars[0] == Belt.max_belt_val, output_supply_vars[0] == Belt.max_belt_val,
                  z3.And(output_supply_vars[0] > output_demand_vars[0], output_pushing_vars[0] == False)),
            z3.If(output_demand_vars[-1] == Belt.max_belt_val, output_supply_vars[-1] == Belt.max_belt_val,
                  z3.And(output_supply_vars[-1] > output_demand_vars[-1], output_pushing_vars[-1] == False))
            # ,
            # # enforce supply in/out equality for this since we don't have to oversupply artificially
            # z3.Sum(output_supply_vars) == total_input_supply_var
        )

        if has_priority_output:
            logger.debug("Has priority output")

            # overall equation:
            # if total_supply > total_demand:
            #   both supply > their demands
            # if priority demand < total flow (nonpriority output overflow):
            #   pressure on priority belt (oversupply)
            #   rest to nonpriority belt (by flow equality rule)
            # else (only priority output flowing)
            #   priority output supply = total flow

            priority_belt = next(x for x in enabled_outputs if x.source_priority)
            priority_belt_supply_var = priority_belt.supply_var()
            priority_belt_demand_var = priority_belt.demand_var()
            priority_belt_pushing_var = priority_belt.pushing_var()

            one_or_no_backpressure = z3.If(
                priority_belt_demand_var < total_input_supply_var,
                z3.And(priority_belt_supply_var == priority_belt_demand_var, priority_belt_pushing_var == True),
                z3.And(priority_belt_supply_var == total_input_supply_var, priority_belt_pushing_var == False)
            )

            solver.assert_and_track(z3.If(
                total_input_supply_var > total_output_demand_var,
                both_backpressure,
                one_or_no_backpressure
            ), f"{str(self)}_pri_o")

        else:
            logger.debug("No priority output")

            # overall equation:
            # if min_demand * num_enabled_outputs >= total_supply (no backpressure on either):
            #   apply supply evenly
            # elif total_supply < total_demand (backpressure on one):
            #   (belt with min demand)'s supply > its demand
            #   other belt supply = total flow - former's demand
            # else (backpressure necessary from both outputs)
            #   both supply > their demands

            min_output_demand_var = common.z3realMin(output_demand_vars[0], output_demand_vars[-1])
            max_output_demand_var = common.z3realMax(output_demand_vars[0], output_demand_vars[-1])

            uneven_supply = z3.And(
                output_supply_vars[0] <= output_demand_vars[0],
                output_supply_vars[-1] <= output_demand_vars[-1],
                output_supply_vars[0] >= min_output_demand_var,
                output_supply_vars[-1] >= min_output_demand_var,
                # # set in/out supply equality to account for oversupply amount to lower demand output belt
                # z3.Sum(output_supply_vars) == total_input_supply_var + Balancer.oversupply_amt
                output_pushing_vars[0] == (output_demand_vars[0] == min_output_demand_var),
                output_pushing_vars[-1] == (output_demand_vars[-1] == min_output_demand_var),
            )

            uneven_supply_cond = z3.If(
                total_input_supply_var <= total_output_demand_var,
                uneven_supply,
                both_backpressure
            )

            solver.assert_and_track(z3.If(
                min_output_demand_var * num_enabled_outputs >= total_input_supply_var,
                z3.And(output_supply_vars[0] == output_supply_vars[-1], output_pushing_vars[0] == False,
                       output_pushing_vars[-1] == False),
                uneven_supply_cond),
                f"{str(self)}_nonpri_o"
            )

    def update_check_flow_rate(self, logger: Logger, io_preset: bool = False):

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        old_demands = copy.deepcopy([x.demand for x in enabled_inputs])
        old_supplies = copy.deepcopy([x.supply for x in enabled_outputs])

        logger.debug(f"------------------------------------------------")
        logger.debug(f"update_check_flow_rate, Splitter: {self}")
        logger.debug(f"Inputs:")
        for in_belt in enabled_inputs:
            logger.debug(f"\tfrom {in_belt.source}:")
            logger.debug(f"\t\t{in_belt.get_label()}")
        logger.debug(f"Outputs:")
        for out_belt in enabled_outputs:
            logger.debug(f"\tto {out_belt.dest}:")
            logger.debug(f"\t\t{out_belt.get_label()}")
        logger.debug(f"------------------------------------------------")

        self.update_flow_rate(logger, io_preset=io_preset)

        logger.debug(f"------------------------------------------------")
        logger.debug(f"Done with update_check_flow_rate, Splitter: {self}")
        logger.debug(f"Inputs:")
        for in_belt in enabled_inputs:
            logger.debug(f"\tfrom {in_belt.source}:")
            logger.debug(f"\t\t{in_belt.get_label()}")
        logger.debug(f"Outputs:")
        for out_belt in enabled_outputs:
            logger.debug(f"\tto {out_belt.dest}:")
            logger.debug(f"\t\t{out_belt.get_label()}")
        logger.debug(f"------------------------------------------------")

        new_demands = [x.demand for x in enabled_inputs]
        new_supplies = [x.supply for x in enabled_outputs]

        is_changed = False

        for i in range(len(new_demands)):
            new_demand = new_demands[i]
            old_demand = old_demands[i]
            if abs(new_demand - old_demand) > common.diff_threshold_iter:
                logger.debug(f"\tchange: demand of {enabled_inputs[i]} changed from {old_demand} to {new_demand}")
                if common.debug:
                    is_changed = True
                else:
                    return True

        for i in range(len(new_supplies)):
            new_supply = new_supplies[i]
            old_supply = old_supplies[i]
            if abs(new_supply - old_supply) > common.diff_threshold_iter:
                logger.debug(f"\tchange: supply of {enabled_outputs[i]} changed from {old_supply} to {new_supply}")
                if common.debug:
                    is_changed = True
                else:
                    return True

        return is_changed

    def update_flow_rate(self, logger: Logger, io_preset: bool = False):

        # -------------------------------------------------------------
        # Weeding out base cases
        # -------------------------------------------------------------

        if self.is_input_proxy():
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            if not io_preset:
                self.outputs[0].supply = 1
                logger.debug(f"Input proxy, setting {self.node} to supply ({self.outputs[0].supply})")
            return

        if self.is_output_proxy():
            assert len(self.inputs) == 1
            if not io_preset:
                logger.debug(f"Output proxy: setting demand of {self.inputs[0]} to 1")
                self.inputs[0].demand = 1
            return

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        num_enabled_inputs = len(enabled_inputs)
        num_enabled_outputs = len(enabled_outputs)

        if num_enabled_inputs == 0:
            logger.debug(f"No enabled inputs, skipping")
            return

        for belt in enabled_inputs:
            assert belt.demand >= 0

        for belt in enabled_outputs:
            assert belt.demand >= 0

        # -------------------------------------------------------------
        # Calculate demand of inputs
        # -------------------------------------------------------------

        total_demand = sum([x.demand for x in enabled_outputs])

        supplies = [x.supply for x in enabled_inputs]

        min_supply = min(supplies)
        total_supply = sum(supplies)

        has_priority_input = any([x.dest_priority for x in enabled_inputs])

        if has_priority_input:
            logger.debug(f"Has priority input")
            priority_belt = next(x for x in enabled_inputs if x.dest_priority)
            priority_belt.demand = min(total_demand, 1)
            if num_enabled_inputs > 1:
                assert num_enabled_inputs == 2
                non_priority_belt = next(x for x in enabled_inputs if not x.dest_priority)
                non_priority_belt.demand = min(total_demand - priority_belt.supply, 1)
                if non_priority_belt.demand < 0:
                    non_priority_belt.demand = 0
        else:
            logger.debug(f"No priority input")
            if min_supply * num_enabled_inputs >= total_demand:
                logger.debug(f"Applying backpressure evenly to inputs")
                for belt in enabled_inputs:
                    belt.demand = total_demand / num_enabled_inputs
            elif total_supply > total_demand:
                assert num_enabled_inputs == 2
                logger.debug(f"Applying backpressure to higher throughput belt to meet demand limit")
                min_supply_belt = next(x for x in enabled_inputs if x.supply == min_supply)
                max_supply_belt = next(x for x in enabled_inputs if x != min_supply_belt)
                oversupply = total_supply - total_demand
                max_supply_belt.demand = max_supply_belt.supply - oversupply
                min_supply_belt.demand = min_supply_belt.supply
            else:
                logger.debug(f"Relaxing backpressure")

                demand_slack = total_demand - total_supply

                # apply demand evenly, letting out slack for
                for belt in enabled_inputs:
                    belt.demand = belt.supply

                logger.debug(f"Step 1:")
                for in_belt in enabled_inputs:
                    logger.debug(f"\tfrom {in_belt.source}: {in_belt.get_label()}")

                # attempt to add slack evenly to inputs, capping demand at 1
                remaining_demand_slack = 0
                for belt in enabled_inputs:
                    to_add = demand_slack / num_enabled_inputs
                    belt.demand += to_add
                    if belt.demand > 1:
                        remaining_demand_slack += belt.demand - 1
                        belt.demand = 1

                # take slack that wasn't added to capped inputs and apply it to other input as available
                # this only works because there's at most 2 inputs,
                # so 2 iterations of this process is all that is necessary
                assert num_enabled_inputs <= 2
                for belt in enabled_inputs:
                    if belt.demand < 1:
                        belt.demand = min(1, belt.demand + remaining_demand_slack)
                        break

        logger.debug(f"After applying backpressure:")
        for in_belt in enabled_inputs:
            logger.debug(f"\tfrom {in_belt.source}: {in_belt.get_label()}")

        # -------------------------------------------------------------
        # Calculate supply of outputs
        # -------------------------------------------------------------

        priority_outputs = [x for x in enabled_outputs if x.source_priority]
        nonpriority_outputs = [x for x in enabled_outputs if not x.source_priority]

        has_priority_output = len(priority_outputs) > 0

        # no more than 1 priority output please
        assert len(priority_outputs) < 2

        if has_priority_output:
            logger.debug("Has priority output")
            priority_output = priority_outputs[0]
            priority_output.supply = min(1, total_supply)
            if len(nonpriority_outputs) > 0:
                nonpriority_output = nonpriority_outputs[0]
                nonpriority_output.supply = total_supply - priority_output.flow()
        else:
            logger.debug("No priority output")
            oversupplies = dict()
            for belt in enabled_outputs:
                belt.supply = min(1, total_supply / num_enabled_outputs)
                oversupplies[belt] = max(0, belt.supply - belt.demand)

            for belt in enabled_outputs:
                other_oversupplies = sum(v for k, v in oversupplies.items() if k != belt)
                belt.supply = min(1, belt.supply + other_oversupplies)

        logger.debug(f"After filling output supplies: ")
        for belt in enabled_outputs:
            logger.debug(belt.get_label())

        return

    def update_check_output_balance(self, logger) -> bool:

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        # record old balances for change detection
        old_balances = [copy.deepcopy(x.balance) for x in enabled_outputs]

        logger.debug(f"------------------------------------------------")
        logger.debug(f"update_output_balance, Splitter: {self}")
        logger.debug(f"Inputs:")
        for in_belt in enabled_inputs:
            logger.debug(f"\tfrom {in_belt.source}:")
            logger.debug(f"\t\t{in_belt.get_label()}")
        logger.debug(f"Outputs:")
        for out_belt in enabled_outputs:
            logger.debug(f"\tto {out_belt.dest}:")
            logger.debug(f"\t\t{out_belt.get_label()}")
        logger.debug(f"------------------------------------------------")

        self.update_output_balance(logger)

        logger.debug(f"------------------------------------------------")
        logger.debug(f"Done with update_output_balance, Splitter: {self}")
        logger.debug(f"Inputs:")
        for in_belt in enabled_inputs:
            logger.debug(f"\tfrom {in_belt.source}:")
            logger.debug(f"\t\t{in_belt.get_label()}")
        logger.debug(f"Outputs:")
        for out_belt in enabled_outputs:
            logger.debug(f"\tto {out_belt.dest}:")
            logger.debug(f"\t\t{out_belt.get_label()}")
        logger.debug(f"------------------------------------------------")

        # check for any changes in balance

        new_balances = [x.balance for x in enabled_outputs]

        is_changed = False

        for i in range(len(new_balances)):
            new_balance = new_balances[i]
            old_balance = old_balances[i]
            for name, frac in new_balance.items():
                if name not in old_balance:
                    logger.debug(f"\tchange: {name} added to {enabled_outputs[i]}")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
                elif abs(old_balance[name] - frac) > common.diff_threshold_iter:
                    logger.debug(f"\tchange: {name} in {enabled_outputs[i]} changed from {old_balance[name]} to {frac}")
                    if common.debug:
                        is_changed = True
                    else:
                        return True
            for name in old_balance.keys():
                if name not in new_balance:
                    logger.debug(f"\tchange: {name} removed from {enabled_outputs[i]}")
                    if common.debug:
                        is_changed = True
                    else:
                        return True

        return is_changed

    # apply input supply to outputs, and apply output demand to inputs based on actual flow rate
    def update_output_balance(self, logger: Logger):

        if self.is_input_proxy():
            # represents an input, just set it to itself
            assert len(self.outputs) == 1
            self.outputs[0].balance[str(self.node)] = self.outputs[0].flow()
            logger.debug(f"Input proxy, setting {self.node} to demand ({self.outputs[0].demand})")
            return

        if self.is_output_proxy():
            assert len(self.inputs) == 1
            logger.debug(f"Output proxy, skipping")
            return

        enabled_inputs = self.get_enabled_inputs()
        enabled_outputs = self.get_enabled_outputs()

        if len(enabled_inputs) == 0:
            logger.debug(f"No enabled inputs, skipping")
            return

        total_supply_balance = self.get_total_supply_balance(logger)
        tsb_flow = total_supply_balance.magnitude()

        logger.debug(f"Total supply balance: {total_supply_balance} ({tsb_flow})")

        if tsb_flow == 0:
            logger.debug(f"Supply balance is 0, skipping")
            return

        for belt in enabled_outputs:
            ratio = belt.flow() / tsb_flow
            belt.balance = total_supply_balance * ratio

        logger.debug(f"after applying input balance to outputs:")
        for belt in enabled_outputs:
            logger.debug(f"\tto {belt.dest}: {belt.get_label()}")

        return

    def get_total_supply_balance(self, logger: Logger) -> Balance:

        # calculate the sum of the input belt balances as a dict
        balance = Balance()

        for belt in self.get_enabled_inputs():
            logger.debug(f"Adding belt {belt.get_label()}")
            balance += belt.balance

        return balance
