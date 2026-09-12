import inspect
import logging

import z3

import common
from Balancer import Balancer
from Belt import ColorStrategy


logger = logging.getLogger(__name__)
common.setup_logger(logger)


def debug_proof(balancer: Balancer, z3solver: z3.Solver, check_result: z3.CheckSatResult, condition_name: str):

    if not common.debug:
        z3solver.pop()
        return

    # assumes push was used before the critical condition

    logger.debug("Assertions:")
    for a in z3solver.assertions():
        logger.debug(a)

    if check_result == z3.sat:
        # for a in z3solver.assertions():
        #     balancer.logger.debug(a)

        logger.debug(f"{condition_name} Counterexample:")

        balancer.set_to_model()

        balancer.render_all_methods(f"{condition_name} Counterexample")

        # # calculate balance of this counterexample, locking the supply of inputs and demand of outputs in place.
        # balancer.calc_balance(io_preset=True)
        # balancer.render("Counterexample_rebalanced")
    else:

        # remove critical condition so we can get a model that would violate it
        z3solver.pop()
        z3solver.push()

        # balancer.logger.debug(f"Assertions:")
        # for a in z3solver.assertions():
        #     balancer.logger.debug(a)

        # outputs = balancer.get_outputs()
        # inputs = balancer.get_inputs()
        #
        # for i in range(len(outputs)):
        #     belt = outputs[i]
        #     if i < len(outputs) / 2:
        #         z3solver.assert_and_track(belt.demand_var() == 1, f"{str(belt.dest)}_d_1")
        #     else:
        #         z3solver.assert_and_track(belt.demand_var() == 0, f"{str(belt.dest)}_d_0")
        #
        # for i in range(len(inputs)):
        #     belt = inputs[i]
        #     if i < len(inputs) / 2:
        #         z3solver.assert_and_track(belt.supply_var() == 0, f"{str(belt.source)}_s_0")
        #     else:
        #         z3solver.assert_and_track(belt.supply_var() == 1, f"{str(belt.source)}_s_1")

        # z3solver.assert_and_track(total_throughput_var == exp_full_throughput_rate_var, "can_be_TU")
        sat_check = z3solver.check()

        if sat_check == z3.sat:
            balancer.set_to_model()
            balancer.render(f"{condition_name} Example", color_strat=ColorStrategy.BACKPRESSURE)
        else:
            core = z3solver.unsat_core()
            logger.debug(f"{condition_name} Unsat core:")
            for a in core:
                logger.debug(a)

    z3solver.pop()

# raynquist refers to this as "regular"
def partially_tu_proof(balancer: Balancer) -> bool:
    logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # assuming one of the large sides of the balancer is fully saturated,
    # if theres any scenario in which the total flow rate is less than the min of (input supply, output demand),
    # the balancer is not even partially TU

    # make symbol for if all inputs are saturated (we may or may not care)
    input_all_saturated_expr = True
    for belt in balancer.get_inputs():
        demand_var = belt.demand_var()
        supply_var = belt.supply_var()
        input_all_saturated_expr = z3.And(input_all_saturated_expr, demand_var <= supply_var)

    input_all_saturated_var = z3.Bool("input_all_saturated")
    z3solver.assert_and_track(input_all_saturated_var == input_all_saturated_expr, "input_all_saturated_expr")

    # make symbol for if all outputs are saturated (we may or may not care)
    output_all_saturated_expr = True
    for belt in balancer.get_outputs():
        demand_var = belt.demand_var()
        supply_var = belt.supply_var()
        output_all_saturated_expr = z3.And(output_all_saturated_expr, demand_var <= supply_var)

    output_all_saturated_var = z3.Bool("output_all_saturated")
    z3solver.assert_and_track(output_all_saturated_var == output_all_saturated_expr, "output_all_saturated_expr")

    num_inputs = balancer.get_num_enabled_inputs()
    num_outputs = balancer.get_num_enabled_outputs()
    if num_inputs > num_outputs:
        # input is bigger, we only care about input saturation
        z3solver.assert_and_track(input_all_saturated_var == True, "bigger_input_all_saturated")
    elif num_outputs > num_inputs:
        # output is bigger, we only care about output saturation
        z3solver.assert_and_track(output_all_saturated_var == True, "bigger_output_all_saturated")
    else:
        # NxN balancer, either needs to be true
        z3solver.assert_and_track(z3.Or(input_all_saturated_var, output_all_saturated_var), "one_side_saturated")

    total_input_supply_var = z3.Sum([x.supply_var() for x in balancer.get_inputs()])
    total_output_demand_var = z3.Sum([x.demand_var() for x in balancer.get_outputs()])
    exp_full_throughput_rate_var = common.z3realMin(total_input_supply_var, total_output_demand_var)

    total_throughput_var = balancer.total_throughput_var

    z3solver.push()

    z3solver.assert_and_track(total_throughput_var != exp_full_throughput_rate_var, "non_TU")

    check_result = z3solver.check()

    is_tu = check_result == z3.unsat

    if not is_tu:
        logger.info("Balancer is not even partially Throughput Unlimited")
    else:
        logger.info("Balancer is at least partially Throughput Unlimited")

    debug_proof(balancer, z3solver, check_result, "partially TU")

    z3solver.pop()

    return is_tu

def tu_proof(balancer: Balancer) -> bool:
    logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # if there's any scenario in which the total flow rate is less than the min of (input supply, output demand), the balancer is not TU

    total_input_supply_var = z3.Sum([x.supply_var() for x in balancer.get_inputs()])
    total_output_demand_var = z3.Sum([x.demand_var() for x in balancer.get_outputs()])
    exp_full_throughput_rate_expr = common.z3realMin(total_input_supply_var, total_output_demand_var)

    exp_full_throughput_rate_var = z3.Real("exp_full_throughput_rate")
    z3solver.assert_and_track(exp_full_throughput_rate_var == exp_full_throughput_rate_expr, "exp_full_throughput_rate_expr")

    total_throughput_var = balancer.total_throughput_var

    z3solver.push()

    z3solver.assert_and_track(balancer.total_throughput_var != exp_full_throughput_rate_var, "non_TU")

    check_result = z3solver.check()

    is_tu = check_result == z3.unsat

    if not is_tu:
        logger.info("Balancer is not Throughput Unlimited")
    else:
        logger.info("Balancer is Throughput Unlimited")

    debug_proof(balancer, z3solver, check_result, "TU")

    z3solver.pop()

    return is_tu

def partially_input_balanced_proof(balancer: Balancer) -> bool:
    logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # if, assuming all inputs are saturated, the demand of each input is always the same
    # then the balancer is at least partially input balanced

    total_throughput_var = balancer.total_throughput_var
    num_inputs = balancer.get_num_inputs()

    input_unbalanced_var = False

    for belt in balancer.get_inputs():
        demand_var = belt.demand_var()
        supply_var = belt.supply_var()
        z3solver.assert_and_track(demand_var < supply_var, f"{str(belt)}_saturated")
        input_unbalanced_var = z3.Or(
            input_unbalanced_var,
            demand_var != total_throughput_var / num_inputs
        )

    z3solver.push()

    z3solver.assert_and_track(input_unbalanced_var, f"input_unbalanced")

    check_result = z3solver.check()

    is_pi_balanced = check_result == z3.unsat

    debug_proof(balancer, z3solver, check_result, "pi_balanced")

    if not is_pi_balanced:
        logger.info("Balancer is not even partially input balanced")
    else:
        logger.info("Balancer is at least partially input balanced")

    z3solver.pop()

    return is_pi_balanced

def input_balanced_proof(balancer: Balancer) -> bool:
    logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # if theres any scenario in which any two input belts have supply > demand != average demand of blocked inputs
    # then the balancer is not input balanced

    total_blocked_input_expr = 0
    num_blocked_inputs_expr = 0

    for belt in balancer.get_inputs():
        supply_var = belt.supply_var()
        demand_var = belt.demand_var()
        total_blocked_input_expr = z3.If(supply_var > demand_var, total_blocked_input_expr + demand_var,
                                         total_blocked_input_expr)
        num_blocked_inputs_expr = z3.If(supply_var > demand_var, num_blocked_inputs_expr + 1,
                                        num_blocked_inputs_expr)

    num_blocked_inputs_var = z3.Real("num_blocked_inputs")
    z3solver.assert_and_track(num_blocked_inputs_var == num_blocked_inputs_expr, "num_blocked_inputs_assert")

    total_blocked_input_var = z3.Real("total_blocked_input")
    z3solver.assert_and_track(total_blocked_input_var == total_blocked_input_expr, "total_blocked_input_assert")

    input_unbalanced_var = False

    for belt in balancer.get_inputs():
        supply_var = belt.supply_var()
        demand_var = belt.demand_var()
        input_unbalanced_var = z3.Or(
            input_unbalanced_var,
            z3.And(supply_var > demand_var, demand_var != total_blocked_input_var / num_blocked_inputs_var)
        )

    z3solver.assert_and_track(input_unbalanced_var, "input_unbalanced")

    check_result = z3solver.check()

    is_input_balanced = check_result == z3.unsat

    debug_proof(balancer, z3solver, check_result, "input_balanced")

    if not is_input_balanced:
        logger.info("Balancer is not fully input balanced")
    else:
        logger.info("Balancer is fully input balanced")

    return is_input_balanced

def partially_output_balanced_proof(balancer: Balancer) -> bool:
    logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # if, assuming all outputs are unblocked, the supply of each output is always the same
    # then the balancer is at least partially output balanced

    total_throughput_var = balancer.total_throughput_var
    num_outputs = balancer.get_num_outputs()

    output_unbalanced_var = False

    for belt in balancer.get_outputs():
        demand_var = belt.demand_var()
        supply_var = belt.supply_var()
        z3solver.assert_and_track(demand_var > supply_var, f"{str(belt)}_unblocked")
        output_unbalanced_var = z3.Or(
            output_unbalanced_var,
            supply_var != total_throughput_var / num_outputs
        )

    z3solver.push()

    z3solver.assert_and_track(output_unbalanced_var, f"output_unbalanced")

    check_result = z3solver.check()

    is_po_balanced = check_result == z3.unsat

    debug_proof(balancer, z3solver, check_result, "po_balanced")

    if not is_po_balanced:
        logger.info("Balancer is not even partially output balanced")
    else:
        logger.info("Balancer is at least partially output balanced")

    z3solver.pop()

    return is_po_balanced

def output_balanced_proof(balancer: Balancer) -> bool:
    logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # if in any scenario, an output has demand > supply != average supply of unblocked outputs
    # then the balancer is not output balanced

    total_unblocked_output_var = 0
    num_unblocked_outputs_var = 0

    for belt in balancer.get_outputs():
        supply_var = belt.supply_var()
        demand_var = belt.demand_var()
        total_unblocked_output_var = z3.If(supply_var < demand_var, total_unblocked_output_var + supply_var,
                                               total_unblocked_output_var)
        num_unblocked_outputs_var = z3.If(supply_var < demand_var, num_unblocked_outputs_var + 1,
                                         num_unblocked_outputs_var)

    output_unbalanced_var = False

    for belt in balancer.get_outputs():
        supply_var = belt.supply_var()
        demand_var = belt.demand_var()
        output_unbalanced_var = z3.Or(
            output_unbalanced_var,
            z3.And(supply_var < demand_var, supply_var != total_unblocked_output_var / num_unblocked_outputs_var)
        )

    z3solver.assert_and_track(output_unbalanced_var, "output_unbalanced")

    check_result = z3solver.check()

    is_output_balanced = check_result == z3.unsat

    debug_proof(balancer, z3solver, check_result, "output_balanced")

    if not is_output_balanced:
        logger.info("Balancer is not fully output balanced")
    else:
        logger.info("Balancer is fully output balanced")

    return is_output_balanced

def test_total_balance_z3(balancer: Balancer) -> bool:
    is_partially_tu = partially_tu_proof(balancer)

    is_tu = False
    if is_partially_tu:
        is_tu = tu_proof(balancer)

    is_pi_balanced = partially_input_balanced_proof(balancer)

    is_input_balanced = False
    if is_pi_balanced:
        is_input_balanced = input_balanced_proof(balancer)

    is_po_balanced = partially_output_balanced_proof(balancer)

    is_output_balanced = False
    if is_po_balanced:
        is_output_balanced = output_balanced_proof(balancer)

    return is_tu and is_input_balanced and is_output_balanced

all_z3_tests = [
    partially_tu_proof,
    tu_proof,
    partially_input_balanced_proof,
    partially_output_balanced_proof,
    input_balanced_proof,
    output_balanced_proof
]
