import itertools
import os

import Balancer_Book
import common
from Balancer import Balancer

# first result is true if balancer is input balanced (meaning it draws evenly from all inputs no matter what)
# first result is true if balancer is output balanced (meaning it supplies evenly to all outputs no matter what)
# third result is true if the balancer is throughput unlimited
# (meaning it always provides the maximum throughput possible no matter what)
def test_balance(balancer: Balancer) -> tuple[bool, bool, bool]:
    is_input_balanced = True
    is_output_balanced = True
    is_tu = True

    outputs = balancer.get_outputs()
    inputs = balancer.get_inputs()

    num_outputs = len(outputs)
    num_inputs = len(inputs)

    output_sets_to_block = []
    for i in range(num_outputs):
        output_sets_to_block.extend(list(itertools.combinations(outputs, i)))

    input_sets_to_block = []
    for i in range(num_inputs):
        input_sets_to_block.extend(list(itertools.combinations(inputs, i)))

    # common.debug_print("Output sets:")
    # for output_set_to_block in output_sets_to_block:
    #     common.debug_print(", ".join([str(x.dest) for x in output_set_to_block]))
    #
    # common.debug_print("Input sets:")
    # for input_set_to_block in input_sets_to_block:
    #     common.debug_print(", ".join([str(x.source) for x in input_set_to_block]))

    for output_set_to_block in output_sets_to_block:

        for output_belt in output_set_to_block:
            output_belt.enabled = False

        blocked_output_names = [str(x.dest) for x in output_set_to_block]
        num_blocked_outputs = len(blocked_output_names)
        num_enabled_outputs = num_outputs - num_blocked_outputs

        for input_set_to_block in input_sets_to_block:

            for input_belt in input_set_to_block:
                input_belt.enabled = False

            blocked_input_names = [str(x.source) for x in input_set_to_block]
            num_blocked_inputs = len(blocked_input_names)
            num_enabled_inputs = num_inputs - num_blocked_inputs

            print("Blocking Outputs:")
            print(", ".join(blocked_output_names))
            print("Blocking Inputs:")
            print(", ".join(blocked_input_names))

            img_filename = "Sans_" + "_".join(blocked_output_names)
            img_filename += "_".join(blocked_input_names)


            balancer.calc_balance()
            balancer.render(img_filename)

            exp_throughput = min(num_enabled_inputs, num_enabled_outputs)
            exp_input_strength = exp_throughput / num_enabled_inputs
            exp_output_strength = exp_throughput / num_enabled_outputs
            actual_coeff = -1

            total_throughput = sum([x.get_strength() for x in balancer.get_outputs()])
            if abs(total_throughput - exp_throughput) > common.diff_threshold_verif:
                print(f"Error: expected throughput to be "
                      f"{exp_throughput:.{common.decimals_iter}f}, "
                      f"got {total_throughput:.{common.decimals_iter}f} "
                      f"(diff > {common.diff_threshold_verif})")
                is_tu = False

            for out_belt in balancer.get_outputs():
                if not out_belt.enabled:
                    continue
                strength = out_belt.get_strength()
                if abs(strength - exp_output_strength) > common.diff_threshold_verif:
                    print(f"Error on {out_belt.dest}: expected strength to be "
                          f"{exp_output_strength:.{common.decimals_iter}f}, "
                          f"got {strength:.{common.decimals_iter}f} "
                          f"(diff > {common.diff_threshold_verif})")
                    is_output_balanced = False

            for in_belt in balancer.get_inputs():
                if not in_belt.enabled:
                    continue
                strength = in_belt.get_strength()
                if abs(strength - exp_input_strength) > common.diff_threshold_verif:
                    print(f"Error on {in_belt.source}: expected strength to be "
                          f"{exp_input_strength:.{common.decimals_iter}f}, "
                          f"got {strength:.{common.decimals_iter}f} "
                          f"(diff > {common.diff_threshold_verif})")
                    is_input_balanced = False

            for input_belt in input_set_to_block:
                input_belt.enabled = True

        for output_belt in output_set_to_block:
            output_belt.enabled = True

    return is_input_balanced, is_output_balanced, is_tu

# TODO: make networks for all N - M balancers for N,M = {1, 2, 3, 5, 7}
# TODO: add blueprint parsing (rip from Factorio SAT)
# TODO: add network optimization
# TODO: add blueprint export
# TODO: add P&R

# remove all PNGs first
path = "."
files = os.listdir(path=path)
for file in files:
    if file.endswith(".png"):
        os.remove(os.path.join(path, file))

# balancer3x3TU = Balancer.combine_balancers(Balancer_Book.make3x3(), Balancer_Book.make3x3())
# balancer = Balancer_Book.combine_balancers(balancer3x3TU, Balancer_Book.make_3x1())
# balancer = Balancer_Book.make_2x1_pri_in()
# balancer = Balancer_Book.make_3x1()
balancer = Balancer_Book.make_4x4_universal()
# balancer = Balancer_Book.make_real_3x1_reduced()
# balancer = Balancer_Book.make_4x3()

is_input_balanced, is_output_balanced, is_tu = test_balance(balancer)

if not is_input_balanced:
    print("Balancer is not input balanced")

if not is_output_balanced:
    print("Balancer is not output balanced")

if not is_tu:
    print("Balancer is not TU")

balancer.calc_balance()
balancer.render()
balancer.export_to_sat_network()