import copy
import itertools
import logging
import os.path
import shutil
from concurrent.futures.process import ProcessPoolExecutor
import inspect

from tabulate import tabulate
import z3

import common
from Balance import Balance
from Balancer import Balancer
from Belt import Belt, ColorStrategy
from Node import Node
from ProgressPrinter import ProgressPrinter

def debug_proof(balancer: Balancer, z3solver: z3.Solver, check_result: z3.CheckSatResult, condition_name: str):

    if not common.debug:
        z3solver.pop()
        return

    # assumes push was used before the critical condition

    balancer.logger.debug("Assertions:")
    for a in z3solver.assertions():
        balancer.logger.debug(a)

    if check_result == z3.sat:
        z3model = z3solver.model()

        balancer.logger.debug("Full model:")
        balancer.logger.debug(z3model)
        # for a in z3solver.assertions():
        #     balancer.logger.debug(a)

        balancer.logger.debug(f"{condition_name} Counterexample:")

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
            z3model = z3solver.model()
            balancer.logger.debug(f"{condition_name} Example:")
            for belt in balancer.belts:
                belt.supply = float(z3model[belt.supply_var()].as_fraction())
                belt.demand = float(z3model[belt.demand_var()].as_fraction())
                # print(type(z3model[belt].supply_var().as_fraction()))
            balancer.render(f"{condition_name} Example", color_strat=ColorStrategy.BACKPRESSURE)
        else:
            core = z3solver.unsat_core()
            balancer.logger.debug(f"{condition_name} Unsat core:")
            for a in core:
                balancer.logger.debug(a)

    z3solver.pop()

# raynquist refers to this as "regular"
def test_partial_tu_z3(balancer: Balancer) -> bool:
    balancer.logger.debug(f"{inspect.stack()[0][3]} called")

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
        input_all_saturated_expr = z3.And(input_all_saturated_expr, demand_var < supply_var)

    input_all_saturated_var = z3.Bool("input_all_saturated")
    z3solver.assert_and_track(input_all_saturated_var == input_all_saturated_expr, "input_all_saturated_expr")

    # make symbol for if all outputs are saturated (we may or may not care)
    output_all_saturated_expr = True
    for belt in balancer.get_outputs():
        demand_var = belt.demand_var()
        supply_var = belt.supply_var()
        output_all_saturated_expr = z3.And(output_all_saturated_expr, demand_var < supply_var)

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
        balancer.logger.info("Balancer is not even partially TU")

    debug_proof(balancer, z3solver, check_result, "partially TU")

    z3solver.pop()

    return is_tu

def test_tu_z3(balancer: Balancer) -> bool:
    balancer.logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # if theres any scenario in which the total flow rate is less than the min of (input supply, output demand), the balancer is not TU

    total_input_supply_var = z3.Sum([x.supply_var() for x in balancer.get_inputs()])
    total_output_demand_var = z3.Sum([x.demand_var() for x in balancer.get_outputs()])
    exp_full_throughput_rate_var = common.z3realMin(total_input_supply_var, total_output_demand_var)

    total_throughput_var = balancer.total_throughput_var

    z3solver.push()

    z3solver.assert_and_track(total_throughput_var != exp_full_throughput_rate_var, "non_TU")

    check_result = z3solver.check()

    is_tu = check_result == z3.unsat

    if not is_tu:
        balancer.logger.info("Balancer is not TU")

    debug_proof(balancer, z3solver, check_result, "TU")

    z3solver.pop()

    return is_tu

def test_partial_input_balanced_z3(balancer: Balancer) -> bool:
    balancer.logger.debug(f"{inspect.stack()[0][3]} called")

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
        balancer.logger.info("Balancer is not even partially input balanced")

    z3solver.pop()

    return is_pi_balanced

def test_input_balanced_z3(balancer: Balancer) -> bool:
    balancer.logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # if theres any scenario in which any two input belts have supply > demand != average demand of blocked inputs
    # then the balancer is not input balanced

    total_throughput_var = balancer.total_throughput_var
    total_blocked_input_expr = total_throughput_var
    num_blocked_inputs_expr = 0

    for belt in balancer.get_inputs():
        supply_var = belt.supply_var()
        demand_var = belt.demand_var()
        total_blocked_input_expr = z3.If(supply_var <= demand_var, total_blocked_input_expr - supply_var,
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
        balancer.logger.info("Balancer is not fully input balanced")

    return is_input_balanced

def test_partial_output_balanced_z3(balancer: Balancer) -> bool:
    balancer.logger.debug(f"{inspect.stack()[0][3]} called")

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
        balancer.logger.info("Balancer is not even partially output balanced")

    z3solver.pop()

    return is_po_balanced


def test_output_balanced_z3(balancer: Balancer) -> bool:
    balancer.logger.debug(f"{inspect.stack()[0][3]} called")

    z3solver = balancer.get_solver()
    z3solver.push()

    # if in any scenario, an output has demand > supply != average supply of unblocked outputs
    # then the balancer is not output balanced

    total_throughput_var = balancer.total_throughput_var
    total_unblocked_output_var = total_throughput_var
    num_unblocked_outputs_var = 0

    for belt in balancer.get_outputs():
        supply_var = belt.supply_var()
        demand_var = belt.demand_var()
        total_unblocked_output_var = z3.If(supply_var >= demand_var, total_unblocked_output_var - demand_var,
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
        balancer.logger.info("Balancer is not fully output balanced")

    return is_output_balanced

def test_total_balance_z3(balancer: Balancer) -> bool:
    is_tu = test_tu_z3(balancer)
    is_input_balanced = test_input_balanced_z3(balancer)
    is_output_balanced = test_output_balanced_z3(balancer)
    return is_tu and is_input_balanced and is_output_balanced

# return true if balancer passes test
def test_balance(
        balancer: Balancer,
        exit_on_fail: bool = True,
        test_input_blocking: bool = True,
        test_output_blocking: bool = True,
        max_threads: int | None = None,
) -> bool:

    # balancer is input balanced (meaning it draws evenly from all inputs no matter what)
    is_input_balanced = True

    # balancer is output balanced (meaning it supplies evenly to all outputs no matter what)
    is_output_balanced = True

    # balancer is throughput unlimited (meaning it always provides the maximum throughput possible no matter what)
    is_tu = True

    output_folder_path = os.path.abspath("test")

    # clear test folder output
    try:
        print("cleaning test folder...")
        shutil.rmtree(output_folder_path)
        print("done")
    except FileNotFoundError:
        pass

    os.makedirs(output_folder_path)

    outputs = balancer.get_outputs()
    inputs = balancer.get_inputs()

    num_outputs = len(outputs)
    num_inputs = len(inputs)

    output_sets_to_block = []
    if test_output_blocking:
        for i in range(num_outputs):
            output_sets_to_block.extend(list(itertools.combinations(outputs, i)))
    else:
        output_sets_to_block.append([])

    input_sets_to_block = []
    if test_input_blocking:
        for i in range(num_inputs):
            input_sets_to_block.extend(list(itertools.combinations(inputs, i)))
    else:
        input_sets_to_block.append([])

    balancer.logger.debug("Output sets:")
    for output_set_to_block in output_sets_to_block:
        balancer.logger.debug(", ".join([str(x.dest) for x in output_set_to_block]))

    balancer.logger.debug("Input sets:")
    for input_set_to_block in input_sets_to_block:
        balancer.logger.debug(", ".join([str(x.source) for x in input_set_to_block]))

    num_balancer_combos = len(output_sets_to_block)*len(input_sets_to_block)
    balancer_combos_tested = 0

    pp = ProgressPrinter()

    threads = []
    combo_names = []

    with ProcessPoolExecutor(max_threads) as executor:

        # launch all threads
        print(f"Launching {num_balancer_combos} test threads...")
        thread_idx = 0
        for output_set_to_block in output_sets_to_block:

            blocked_output_names = [str(x.dest) for x in output_set_to_block]

            for input_set_to_block in input_sets_to_block:

                blocked_input_names = [str(x.source) for x in input_set_to_block]

                threads.append(executor.submit(calc_balance_on_copy, balancer, blocked_input_names, blocked_output_names, output_folder_path))
                combo_names.append(io_test_name(blocked_input_names, blocked_output_names))

                thread_idx += 1

        print("Resolving threads...")

        combos_w_issues = []

        # process them as they come
        for thread_idx in range(len(threads)):

            # wait until this thread completes
            iter_is_input_balanced, iter_is_output_balanced, iter_is_tu = threads[thread_idx].result()
            is_input_balanced &= iter_is_input_balanced
            is_output_balanced &= iter_is_output_balanced
            is_tu &= iter_is_tu

            issue_this_iter = not (iter_is_input_balanced and iter_is_output_balanced and iter_is_tu)

            if issue_this_iter:
                combos_w_issues.append([combo_names[thread_idx], is_input_balanced, is_output_balanced, is_tu])

            balancer_combos_tested += 1
            completion = float(balancer_combos_tested) / num_balancer_combos
            pp.print_progress(completion)

            if exit_on_fail and issue_this_iter:
                executor.shutdown(wait=True, cancel_futures=True)
                break

    if len(combos_w_issues) > 0:
        print("Balancer has issues:")
        print(tabulate(combos_w_issues, headers=["Name", "Input Balanced", "Output Balanced", "TU"]))

    if not is_input_balanced:
        print("Balancer is not input balanced")

    if not is_output_balanced:
        print("Balancer is not output balanced")

    if not is_tu:
        print("Balancer is not TU")

    if exit_on_fail and len(combos_w_issues) > 0:
        print("Note: exit_on_fail set to True, so this test may be incomplete.")

    print(f"Tested {balancer_combos_tested}/{num_balancer_combos} combinations")

    return is_input_balanced and is_output_balanced and is_tu

def calc_balance_on_copy(
        balancer: Balancer,
        in_belt_names_to_block: list[str],
        out_belt_names_to_block: list[str],
        output_folder_path: str
) -> tuple[bool, bool, bool]:

    bal_copy = copy.deepcopy(balancer)

    result_filename = io_test_name(in_belt_names_to_block, out_belt_names_to_block)
    result_filepath = os.path.join(output_folder_path, result_filename)

    # completely replace the objects logger with one with no parents so it only will go to the one file handler
    thread_logger = logging.getLogger(result_filename)
    bal_copy.logger = thread_logger

    log_filepath = f"{result_filepath}.log"

    # if not os.path.exists(log_filepath):
    #     with open(log_filepath, 'w'): pass

    # set this balancer to log to filepath.log
    fh = logging.FileHandler(log_filepath, mode='w+')
    fh.setLevel(logging.DEBUG)

    bal_copy.logger.addHandler(fh)

    if common.debug:
        bal_copy.logger.setLevel(logging.DEBUG)
    else:
        bal_copy.logger.setLevel(logging.INFO)

    bal_copy.logger.debug(f"calc_and_render({bal_copy}, {output_folder_path})")
    bal_copy.logger.debug(f"logger at {id(bal_copy.logger)}")

    bal_copy.logger.debug("Blocking outputs:")
    bal_copy.logger.debug(", ".join(out_belt_names_to_block))
    bal_copy.logger.debug("Blocking inputs:")
    bal_copy.logger.debug(", ".join(in_belt_names_to_block))

    inputs = bal_copy.get_inputs()
    outputs = bal_copy.get_outputs()

    for in_belt_name in in_belt_names_to_block:
        in_belt = next((x for x in inputs if x.source.name == in_belt_name), None)
        if in_belt is None:
            bal_copy.logger.error(f"Error: {in_belt_name} is not an input")
            continue
        in_belt.enabled = False

    for out_belt_name in out_belt_names_to_block:
        out_belt = next((x for x in outputs if x.dest.name == out_belt_name), None)
        if out_belt is None:
            bal_copy.logger.error(f"Error: {out_belt_name} is not an output")
            continue
        out_belt.enabled = False

    bal_copy.calc_balance()

    num_enabled_outputs = bal_copy.get_num_enabled_outputs()
    num_enabled_inputs = bal_copy.get_num_enabled_inputs()

    exp_throughput = min(num_enabled_inputs, num_enabled_outputs)
    exp_input_flow = exp_throughput / num_enabled_inputs
    exp_output_flow = exp_throughput / num_enabled_outputs

    exp_output_balance = Balance()
    for in_belt in bal_copy.get_inputs():
        if not in_belt.enabled:
            continue
        exp_output_balance[in_belt.source] = exp_input_flow / num_enabled_outputs

    issue_this_iter = False

    # balancer is input balanced (meaning it draws evenly from all inputs no matter what)
    is_input_balanced = True

    # balancer is output balanced (meaning it supplies evenly to all outputs no matter what)
    is_output_balanced = True

    # balancer is throughput unlimited (meaning it always provides the maximum throughput possible no matter what)
    is_tu = True

    total_throughput = sum([x.flow() for x in bal_copy.get_outputs()])
    if abs(total_throughput - exp_throughput) > common.diff_threshold_verif:
        bal_copy.logger.error(f"Error: expected throughput to be "
                              f"{exp_throughput:.{common.decimals_iter}f}, "
                              f"got {total_throughput:.{common.decimals_iter}f} "
                              f"(diff > {common.diff_threshold_verif})")
        is_tu = False
        issue_this_iter = True

    for out_belt in bal_copy.get_outputs():
        if not out_belt.enabled:
            continue
        flow = out_belt.flow()
        if abs(flow - exp_output_flow) > common.diff_threshold_verif:
            bal_copy.logger.error(f"Error on {out_belt.dest}: expected flow to be "
                                  f"{exp_output_flow:.{common.decimals_iter}f}, "
                                  f"got {flow:.{common.decimals_iter}f} "
                                  f"(diff > {common.diff_threshold_verif})")
            is_output_balanced = False
            issue_this_iter = True

        # upon consideration, i realized the balance ratios of each output don't matter.
        # these metrics would matter if either:
        # 1. they indicated input balance
        #       (they dont, and we're checking that anyways by stress testing), or
        # 2. they indicated item mixing ratios
        #       (balancers do not mix different input items well--you need circuitry for that)
        #
        # we already check the throughput of each input and output. where, in theory, each input goes in the
        # balancer is of no object to the performance of the balancer.

        # if not out_belt.is_balanced():
        #     bal_copy.logger.error(f"Error on {out_belt.dest}: expected output to be balanced (balance: {out_belt.balance})")
        #     is_output_balanced = False
        #     issue_this_iter = True
        #
        # if out_belt.balance != exp_output_balance:
        #     bal_copy.logger.error(f"Error on {out_belt.dest}: expected balance to be "
        #           f"{exp_output_balance}, "
        #           f"got {out_belt.balance} "
        #           f"(diff > {common.diff_threshold_verif})")
        #     is_output_balanced = False
        #     issue_this_iter = True

    for in_belt in bal_copy.get_inputs():
        if not in_belt.enabled:
            continue
        flow = in_belt.flow()
        if abs(flow - exp_input_flow) > common.diff_threshold_verif:
            bal_copy.logger.error(f"Error on {in_belt.source}: expected flow to be "
                                  f"{exp_input_flow:.{common.decimals_iter}f}, "
                                  f"got {flow:.{common.decimals_iter}f} "
                                  f"(diff > {common.diff_threshold_verif})")
            is_input_balanced = False
            issue_this_iter = True

    if issue_this_iter:
        bal_copy.logger.error("While blocking outputs:")
        bal_copy.logger.error(", ".join(out_belt_names_to_block))
        bal_copy.logger.error("And blocking inputs:")
        bal_copy.logger.error(", ".join(out_belt_names_to_block))

    bal_copy.render(result_filepath)

    bal_copy.logger.info(f"Done")

    return is_input_balanced, is_output_balanced, is_tu

def io_test_name(in_belt_names_to_block: list[str], out_belt_names_to_block: list[str]) -> str:
    result_filename = "Sans_" + "_".join(out_belt_names_to_block)
    if len(in_belt_names_to_block) > 0:
        result_filename += "_"
    result_filename += "_".join(in_belt_names_to_block)
    return result_filename

def makeNxN(num_inputs: int, num_outputs: int):
    pass

def make3x3() -> Balancer:
    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_c = Node()
    node_1 = Node()
    node_2 = Node()
    node_3 = Node()
    node_4 = Node()
    node_5 = Node()
    node_6 = Node()
    node_o1 = Node()
    node_o2 = Node()
    node_o3 = Node()

    ans.belts.append(Belt(node_a, node_1))
    ans.belts.append(Belt(node_b, node_1))
    ans.belts.append(Belt(node_c, node_2))
    ans.belts.append(Belt(node_1, node_2))
    ans.belts.append(Belt(node_2, node_3))
    ans.belts.append(Belt(node_1, node_3))
    ans.belts.append(Belt(node_2, node_4))
    ans.belts.append(Belt(node_3, node_5))
    ans.belts.append(Belt(node_4, node_5))
    ans.belts.append(Belt(node_3, node_6))
    ans.belts.append(Belt(node_4, node_6))
    ans.belts.append(Belt(node_5, node_4))
    ans.belts.append(Belt(node_5, node_o1))
    ans.belts.append(Belt(node_6, node_o2))
    ans.belts.append(Belt(node_6, node_o3))

    ## make BAD 3->1
    # node_7 = Node()
    # node_o = Node()
    # self.belts.append(Belt(node_6, node_7))
    # self.belts.append(Belt(node_7, node_o))

    ans.postprocess_nodes()
    return ans

def make2x4_tl() -> Balancer:
    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_1 = Node()
    node_2 = Node()
    node_3 = Node()
    node_o1 = Node()
    node_o2 = Node()
    node_o3 = Node()
    node_o4 = Node()

    ans.belts.append(Belt(node_a, node_1))
    ans.belts.append(Belt(node_b, node_1))
    ans.belts.append(Belt(node_1, node_2))
    ans.belts.append(Belt(node_1, node_3))
    ans.belts.append(Belt(node_2, node_o1))
    ans.belts.append(Belt(node_2, node_o2))
    ans.belts.append(Belt(node_3, node_o3))
    ans.belts.append(Belt(node_3, node_o4))

    ans.postprocess_nodes()
    return ans

def make4x4() -> Balancer:
    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_c = Node()
    node_d = Node()
    node_1 = Node()
    node_2 = Node()
    node_3 = Node()
    node_4 = Node()
    node_o1 = Node()
    node_o2 = Node()
    node_o3 = Node()
    node_o4 = Node()

    ans.belts.append(Belt(node_a, node_1))
    ans.belts.append(Belt(node_b, node_1))
    ans.belts.append(Belt(node_c, node_2))
    ans.belts.append(Belt(node_d, node_2))
    ans.belts.append(Belt(node_1, node_3))
    ans.belts.append(Belt(node_1, node_4))
    ans.belts.append(Belt(node_2, node_3))
    ans.belts.append(Belt(node_2, node_4))
    ans.belts.append(Belt(node_3, node_o1))
    ans.belts.append(Belt(node_3, node_o2))
    ans.belts.append(Belt(node_4, node_o3))
    ans.belts.append(Belt(node_4, node_o4))

    ans.postprocess_nodes()
    return ans

def make4x4TU() -> Balancer:
    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_c = Node()
    node_d = Node()
    node_1 = Node()
    node_2 = Node()
    node_3 = Node()
    node_4 = Node()
    node_5 = Node()
    node_6 = Node()
    node_o1 = Node()
    node_o2 = Node()
    node_o3 = Node()
    node_o4 = Node()

    ans.belts.append(Belt(node_a, node_1))
    ans.belts.append(Belt(node_b, node_1))
    ans.belts.append(Belt(node_c, node_2))
    ans.belts.append(Belt(node_d, node_2))
    ans.belts.append(Belt(node_1, node_3))
    ans.belts.append(Belt(node_1, node_4))
    ans.belts.append(Belt(node_2, node_3))
    ans.belts.append(Belt(node_2, node_4))
    ans.belts.append(Belt(node_3, node_5))
    ans.belts.append(Belt(node_3, node_6))
    ans.belts.append(Belt(node_4, node_5))
    ans.belts.append(Belt(node_4, node_6))
    ans.belts.append(Belt(node_5, node_o1))
    ans.belts.append(Belt(node_5, node_o2))
    ans.belts.append(Belt(node_6, node_o3))
    ans.belts.append(Belt(node_6, node_o4))

    ans.postprocess_nodes()
    return ans

def make_3x1() -> Balancer:
    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_c = Node()
    node_1 = Node()
    node_2 = Node()
    node_3 = Node()
    node_o = Node()

    ans.belts.append(Belt(node_a, node_1))
    ans.belts.append(Belt(node_b, node_2))
    ans.belts.append(Belt(node_c, node_2))
    ans.belts.append(Belt(node_1, node_3))
    ans.belts.append(Belt(node_2, node_3))
    ans.belts.append(Belt(node_3, node_1))
    ans.belts.append(Belt(node_3, node_o, True))

    ans.postprocess_nodes()
    return ans

def make_3x1_bigloop() -> Balancer:
    ans = Balancer()

    loop_size = 8

    node_a = Node()
    node_b = Node()
    node_c = Node()
    int_nodes = [Node() for _ in range(loop_size+1)]
    node_o = Node()

    ans.belts.append(Belt(node_a, int_nodes[1]))
    ans.belts.append(Belt(node_b, int_nodes[0]))
    ans.belts.append(Belt(node_c, int_nodes[0]))

    for i in range(1, loop_size):
        ans.belts.append(Belt(int_nodes[i], int_nodes[i + 1]))

    node_d = Node()
    ans.belts.append(Belt(node_d, int_nodes[4]))

    ans.belts.append(Belt(int_nodes[0], int_nodes[loop_size]))
    ans.belts.append(Belt(int_nodes[loop_size], int_nodes[1]))
    ans.belts.append(Belt(int_nodes[loop_size], node_o, True))

    ans.postprocess_nodes()
    return ans

def make_2x2() -> Balancer:

    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_1 = Node()
    node_o1 = Node()
    node_o2 = Node()

    ans.belts.append(Belt(node_a, node_1))
    ans.belts.append(Belt(node_b, node_1))
    ans.belts.append(Belt(node_1, node_o1))
    ans.belts.append(Belt(node_1, node_o2))

    ans.postprocess_nodes()
    return ans

def make_2x2_pri_out() -> Balancer:

    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_1 = Node()
    node_o1 = Node()
    node_o2 = Node()

    ans.belts.append(Belt(node_a, node_1))
    ans.belts.append(Belt(node_b, node_1))
    ans.belts.append(Belt(node_1, node_o1, True))
    ans.belts.append(Belt(node_1, node_o2))

    ans.postprocess_nodes()
    return ans

def make_2x1_pri_in() -> Balancer:

    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_1 = Node()
    node_o1 = Node()

    ans.belts.append(Belt(node_a, node_1, False, True))
    ans.belts.append(Belt(node_b, node_1))
    ans.belts.append(Belt(node_1, node_o1))

    ans.postprocess_nodes()
    return ans

def make_4x3() -> Balancer:

    ans = Balancer()

    input_nodes = [Node() for _ in range(4)]
    output_nodes = [Node() for _ in range(3)]
    int_nodes = [Node() for _ in range(7)]

    ans.belts.append(Belt(input_nodes[0], int_nodes[0]))
    ans.belts.append(Belt(input_nodes[1], int_nodes[0]))
    ans.belts.append(Belt(input_nodes[2], int_nodes[1]))
    ans.belts.append(Belt(input_nodes[3], int_nodes[1]))
    ans.belts.append(Belt(int_nodes[0], int_nodes[2]))
    ans.belts.append(Belt(int_nodes[0], int_nodes[4], True))
    ans.belts.append(Belt(int_nodes[1], int_nodes[4], True))
    ans.belts.append(Belt(int_nodes[1], int_nodes[2]))
    ans.belts.append(Belt(int_nodes[2], int_nodes[3], False, True))
    ans.belts.append(Belt(int_nodes[3], int_nodes[5], False, True))
    ans.belts.append(Belt(int_nodes[3], int_nodes[6], False, True))
    ans.belts.append(Belt(int_nodes[4], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[3]))
    ans.belts.append(Belt(int_nodes[5], output_nodes[0]))
    ans.belts.append(Belt(int_nodes[6], output_nodes[1]))
    ans.belts.append(Belt(int_nodes[6], output_nodes[2]))

    ans.postprocess_nodes()
    return ans

def make_3x1_subbalancer() -> Balancer:

    # this is the subtree of the 4 - 4 universal balancer that takes leftover output, balances it,
    # and then loops it back to each input
    # I'm cutting out I/Os to force it to act as a 3 - 1 as it does in the 3 - 1 case for the universal balancer

    ans = Balancer()

    input_nodes = [Node() for _ in range(3)]
    output_nodes = [Node() for _ in range(1)]
    int_nodes = [Node() for _ in range(18)]

    ans.belts.append(Belt(input_nodes[0], int_nodes[0]))
    ans.belts.append(Belt(input_nodes[1], int_nodes[0]))
    ans.belts.append(Belt(input_nodes[2], int_nodes[1]))
    ans.belts.append(Belt(int_nodes[0], int_nodes[2]))
    ans.belts.append(Belt(int_nodes[1], int_nodes[2]))
    ans.belts.append(Belt(int_nodes[0], int_nodes[3]))
    ans.belts.append(Belt(int_nodes[1], int_nodes[3]))
    # ans.belts.append(Belt(int_nodes[2], int_nodes[4]))
    # ans.belts.append(Belt(int_nodes[3], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[2], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[3], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[5], output_nodes[0]))
    # ans.belts.append(Belt(int_nodes[9], output_nodes[1], True))
    # ans.belts.append(Belt(int_nodes[10], output_nodes[2], True))
    # ans.belts.append(Belt(int_nodes[11], output_nodes[3], True))

    ans.postprocess_nodes()
    return ans

def make_real_3x1() -> Balancer:

    ans = Balancer()

    input_nodes = [Node() for _ in range(4)]
    output_nodes = [Node() for _ in range(4)]
    int_nodes = [Node() for _ in range(18)]

    ans.belts.append(Belt(input_nodes[0], int_nodes[0], False, True))
    ans.belts.append(Belt(input_nodes[1], int_nodes[1], False, True))
    ans.belts.append(Belt(input_nodes[2], int_nodes[2], False, True))
    # ans.belts.append(Belt(input_nodes[3], int_nodes[3], False, True))
    ans.belts.append(Belt(int_nodes[0], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[1], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[2], int_nodes[5]))
    # ans.belts.append(Belt(int_nodes[3], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[7]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[7]))
    ans.belts.append(Belt(int_nodes[6], int_nodes[8]))
    ans.belts.append(Belt(int_nodes[6], int_nodes[12]))
    ans.belts.append(Belt(int_nodes[7], int_nodes[12]))
    ans.belts.append(Belt(int_nodes[7], int_nodes[13]))
    ans.belts.append(Belt(int_nodes[8], int_nodes[13]))
    # ans.belts.append(Belt(int_nodes[9], int_nodes[12]))
    # ans.belts.append(Belt(int_nodes[10], int_nodes[12]))
    # ans.belts.append(Belt(int_nodes[11], int_nodes[13]))
    ans.belts.append(Belt(int_nodes[12], int_nodes[14]))
    ans.belts.append(Belt(int_nodes[12], int_nodes[15]))
    ans.belts.append(Belt(int_nodes[13], int_nodes[14]))
    ans.belts.append(Belt(int_nodes[13], int_nodes[15]))
    ans.belts.append(Belt(int_nodes[14], int_nodes[16]))
    ans.belts.append(Belt(int_nodes[15], int_nodes[16]))
    ans.belts.append(Belt(int_nodes[14], int_nodes[17]))
    ans.belts.append(Belt(int_nodes[15], int_nodes[17]))
    ans.belts.append(Belt(int_nodes[16], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[16], int_nodes[1]))
    ans.belts.append(Belt(int_nodes[17], int_nodes[0]))
    ans.belts.append(Belt(int_nodes[17], int_nodes[2]))
    ans.belts.append(Belt(int_nodes[8], output_nodes[0], True))
    # ans.belts.append(Belt(int_nodes[9], output_nodes[1], True))
    # ans.belts.append(Belt(int_nodes[10], output_nodes[2], True))
    # ans.belts.append(Belt(int_nodes[11], output_nodes[3], True))

    ans.postprocess_nodes()
    return ans

def make_real_3x1_reduced() -> Balancer:

    ans = Balancer()

    input_nodes = [Node() for _ in range(3)]
    output_node = Node()
    int_nodes = [Node() for _ in range(18)]

    ans.belts.append(Belt(input_nodes[0], int_nodes[0], False, True))
    ans.belts.append(Belt(input_nodes[1], int_nodes[1], False, True))
    ans.belts.append(Belt(input_nodes[2], int_nodes[2], False, True))

    ans.belts.append(Belt(int_nodes[0], int_nodes[3]))
    ans.belts.append(Belt(int_nodes[1], int_nodes[3]))
    ans.belts.append(Belt(int_nodes[2], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[3], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[3], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[7]))
    ans.belts.append(Belt(int_nodes[6], int_nodes[7]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[8]))
    ans.belts.append(Belt(int_nodes[8], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[8], int_nodes[0]))
    ans.belts.append(Belt(int_nodes[7], int_nodes[1]))
    ans.belts.append(Belt(int_nodes[7], int_nodes[2]))

    ans.belts.append(Belt(int_nodes[6], output_node))


    ans.postprocess_nodes()
    return ans

def make_4x4_universal() -> Balancer:

    ans = Balancer()

    input_nodes = [Node() for _ in range(4)]
    output_nodes = [Node() for _ in range(4)]
    int_nodes = [Node() for _ in range(18)]

    ans.belts.append(Belt(input_nodes[0], int_nodes[0], False, True))
    ans.belts.append(Belt(input_nodes[1], int_nodes[1], False, True))
    ans.belts.append(Belt(input_nodes[2], int_nodes[2], False, True))
    ans.belts.append(Belt(input_nodes[3], int_nodes[3], False, True))
    ans.belts.append(Belt(int_nodes[0], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[1], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[2], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[3], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[7]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[7]))
    ans.belts.append(Belt(int_nodes[6], int_nodes[8]))
    ans.belts.append(Belt(int_nodes[6], int_nodes[9]))
    ans.belts.append(Belt(int_nodes[7], int_nodes[10]))
    ans.belts.append(Belt(int_nodes[7], int_nodes[11]))
    ans.belts.append(Belt(int_nodes[8], int_nodes[13]))
    ans.belts.append(Belt(int_nodes[9], int_nodes[12]))
    ans.belts.append(Belt(int_nodes[10], int_nodes[12]))
    ans.belts.append(Belt(int_nodes[11], int_nodes[13]))
    ans.belts.append(Belt(int_nodes[12], int_nodes[14]))
    ans.belts.append(Belt(int_nodes[12], int_nodes[15]))
    ans.belts.append(Belt(int_nodes[13], int_nodes[14]))
    ans.belts.append(Belt(int_nodes[13], int_nodes[15]))
    ans.belts.append(Belt(int_nodes[14], int_nodes[16]))
    ans.belts.append(Belt(int_nodes[15], int_nodes[16]))
    ans.belts.append(Belt(int_nodes[14], int_nodes[17]))
    ans.belts.append(Belt(int_nodes[15], int_nodes[17]))
    ans.belts.append(Belt(int_nodes[16], int_nodes[3]))
    ans.belts.append(Belt(int_nodes[16], int_nodes[1]))
    ans.belts.append(Belt(int_nodes[17], int_nodes[0]))
    ans.belts.append(Belt(int_nodes[17], int_nodes[2]))
    ans.belts.append(Belt(int_nodes[8], output_nodes[0], True))
    ans.belts.append(Belt(int_nodes[9], output_nodes[1], True))
    ans.belts.append(Belt(int_nodes[10], output_nodes[2], True))
    ans.belts.append(Belt(int_nodes[11], output_nodes[3], True))

    ans.postprocess_nodes()
    return ans

def make_4x4_universal_blocked() -> Balancer:

    ans = make_4x4_universal()

    ans.get_inputs()[0].enabled = False

    outputs = ans.get_outputs()
    outputs[0].enabled = False
    outputs[1].enabled = False
    outputs[2].enabled = False

    return ans

def make_8x8_TU() -> Balancer:
    ans = Balancer()

    input_nodes = [Node() for _ in range(8)]
    output_nodes = [Node() for _ in range(8)]
    int_nodes = [Node() for _ in range(20)]

    ans.belts.append(Belt(input_nodes[0], int_nodes[0]))
    ans.belts.append(Belt(input_nodes[1], int_nodes[0]))
    ans.belts.append(Belt(input_nodes[2], int_nodes[1]))
    ans.belts.append(Belt(input_nodes[3], int_nodes[1]))
    ans.belts.append(Belt(input_nodes[4], int_nodes[2]))
    ans.belts.append(Belt(input_nodes[5], int_nodes[2]))
    ans.belts.append(Belt(input_nodes[6], int_nodes[3]))
    ans.belts.append(Belt(input_nodes[7], int_nodes[3]))

    ans.belts.append(Belt(int_nodes[0], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[0], int_nodes[7]))
    ans.belts.append(Belt(int_nodes[1], int_nodes[4]))
    ans.belts.append(Belt(int_nodes[1], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[2], int_nodes[5]))
    ans.belts.append(Belt(int_nodes[2], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[3], int_nodes[6]))
    ans.belts.append(Belt(int_nodes[3], int_nodes[7]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[12]))
    ans.belts.append(Belt(int_nodes[4], int_nodes[13]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[8]))
    ans.belts.append(Belt(int_nodes[5], int_nodes[9]))
    ans.belts.append(Belt(int_nodes[6], int_nodes[12]))
    ans.belts.append(Belt(int_nodes[6], int_nodes[13]))
    ans.belts.append(Belt(int_nodes[7], int_nodes[8]))
    ans.belts.append(Belt(int_nodes[7], int_nodes[9]))
    ans.belts.append(Belt(int_nodes[8], int_nodes[10]))
    ans.belts.append(Belt(int_nodes[8], int_nodes[11]))
    ans.belts.append(Belt(int_nodes[9], int_nodes[10]))
    ans.belts.append(Belt(int_nodes[9], int_nodes[11]))
    ans.belts.append(Belt(int_nodes[10], int_nodes[17]))
    ans.belts.append(Belt(int_nodes[10], int_nodes[18]))
    ans.belts.append(Belt(int_nodes[11], int_nodes[16]))
    ans.belts.append(Belt(int_nodes[11], int_nodes[19]))
    ans.belts.append(Belt(int_nodes[12], int_nodes[14]))
    ans.belts.append(Belt(int_nodes[12], int_nodes[15]))
    ans.belts.append(Belt(int_nodes[13], int_nodes[14]))
    ans.belts.append(Belt(int_nodes[13], int_nodes[15]))
    ans.belts.append(Belt(int_nodes[14], int_nodes[16]))
    ans.belts.append(Belt(int_nodes[14], int_nodes[17]))
    ans.belts.append(Belt(int_nodes[15], int_nodes[18]))
    ans.belts.append(Belt(int_nodes[15], int_nodes[19]))

    ans.belts.append(Belt(int_nodes[16], output_nodes[0]))
    ans.belts.append(Belt(int_nodes[16], output_nodes[1]))
    ans.belts.append(Belt(int_nodes[17], output_nodes[2]))
    ans.belts.append(Belt(int_nodes[17], output_nodes[3]))
    ans.belts.append(Belt(int_nodes[18], output_nodes[4]))
    ans.belts.append(Belt(int_nodes[18], output_nodes[5]))
    ans.belts.append(Belt(int_nodes[19], output_nodes[6]))
    ans.belts.append(Belt(int_nodes[19], output_nodes[7]))

    ans.postprocess_nodes()
    return ans