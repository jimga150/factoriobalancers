import itertools
import os.path
import shutil

import common
from Balance import Balance
from Balancer import Balancer
from Belt import Belt
from Node import Node

# return true if balancer passes test
def test_balance(balancer: Balancer, exit_on_fail: bool = True) -> bool:

    # balancer is input balanced (meaning it draws evenly from all inputs no matter what)
    is_input_balanced = True

    # balancer is output balanced (meaning it supplies evenly to all outputs no matter what)
    is_output_balanced = True

    # balancer is throughput unlimited (meaning it always provides the maximum throughput possible no matter what)
    is_tu = True

    output_folder_path = os.path.abspath("test")

    # clear test folder output
    try:
        shutil.rmtree(output_folder_path)
    except FileNotFoundError:
        pass

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

    common.debug_print("Output sets:")
    for output_set_to_block in output_sets_to_block:
        common.debug_print(", ".join([str(x.dest) for x in output_set_to_block]))

    common.debug_print("Input sets:")
    for input_set_to_block in input_sets_to_block:
        common.debug_print(", ".join([str(x.source) for x in input_set_to_block]))

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
            if len(blocked_input_names) > 0:
                img_filename += "_"
            img_filename += "_".join(blocked_input_names)

            img_filepath = os.path.join(output_folder_path, img_filename)

            balancer.calc_balance()
            balancer.render(img_filepath)

            exp_throughput = min(num_enabled_inputs, num_enabled_outputs)
            exp_input_flow = exp_throughput / num_enabled_inputs
            exp_output_flow = exp_throughput / num_enabled_outputs

            exp_output_balance = Balance()
            for in_belt in balancer.get_inputs():
                if not in_belt.enabled:
                    continue
                exp_output_balance[in_belt.source] = exp_input_flow / num_enabled_outputs

            total_throughput = sum([x.flow() for x in balancer.get_outputs()])
            if abs(total_throughput - exp_throughput) > common.diff_threshold_verif:
                print(f"Error: expected throughput to be "
                      f"{exp_throughput:.{common.decimals_iter}f}, "
                      f"got {total_throughput:.{common.decimals_iter}f} "
                      f"(diff > {common.diff_threshold_verif})")
                is_tu = False

            for out_belt in balancer.get_outputs():
                if not out_belt.enabled:
                    continue
                flow = out_belt.flow()
                if abs(flow - exp_output_flow) > common.diff_threshold_verif:
                    print(f"Error on {out_belt.dest}: expected flow to be "
                          f"{exp_output_flow:.{common.decimals_iter}f}, "
                          f"got {flow:.{common.decimals_iter}f} "
                          f"(diff > {common.diff_threshold_verif})")
                    is_output_balanced = False

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
                #     print(f"Error on {out_belt.dest}: expected output to be balanced (balance: {out_belt.balance})")
                #     is_output_balanced = False
                #
                # if out_belt.balance != exp_output_balance:
                #     print(f"Error on {out_belt.dest}: expected balance to be "
                #           f"{exp_output_balance}, "
                #           f"got {out_belt.balance} "
                #           f"(diff > {common.diff_threshold_verif})")
                #     is_output_balanced = False

            for in_belt in balancer.get_inputs():
                if not in_belt.enabled:
                    continue
                flow = in_belt.flow()
                if abs(flow - exp_input_flow) > common.diff_threshold_verif:
                    print(f"Error on {in_belt.source}: expected flow to be "
                          f"{exp_input_flow:.{common.decimals_iter}f}, "
                          f"got {flow:.{common.decimals_iter}f} "
                          f"(diff > {common.diff_threshold_verif})")
                    is_input_balanced = False

            for input_belt in input_set_to_block:
                input_belt.enabled = True

            if exit_on_fail and not (is_input_balanced and is_output_balanced and is_tu):
                break

        for output_belt in output_set_to_block:
            output_belt.enabled = True

        if exit_on_fail and not (is_input_balanced and is_output_balanced and is_tu):
            break

    if not is_input_balanced:
        print("Balancer is not input balanced")

    if not is_output_balanced:
        print("Balancer is not output balanced")

    if not is_tu:
        print("Balancer is not TU")

    return is_input_balanced and is_output_balanced and is_tu

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