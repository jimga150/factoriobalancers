from logging import Logger

import z3

import common
from Belt import Belt

class Splitter:

    def __init__(self, inputs: list[Belt], outputs: list[Belt]):
        self.inputs = inputs
        self.outputs = outputs

        assert len(self.inputs) <= 2, f"Splitter has {len(self.inputs)} inputs"
        assert len(self.outputs) <= 2, f"Splitter has {len(self.outputs)} outputs"

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
