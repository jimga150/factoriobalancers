import Balancer_Book
import common
from Balancer import Balancer

# first result is true if balancer is input balanced (meaning it draws evenly from all inputs no matter what)
# second result is true if the balancer is throughput unlimited
# (meaning it always provides the maximum throughput possible no matter what)
def test_input_balance(balancer: Balancer) -> (bool, bool):
    is_balanced = True
    is_tu = True

    exp_throughput = min(balancer.get_num_outputs(), balancer.get_num_inputs() - 1)
    actual_coeff = -1

    # test drying each input individually
    for in_belt in balancer.get_inputs():

        in_belt.enabled = False

        print(f"Calculating balance with {in_belt.source} dry")

        balancer.calc_balance()
        balancer.render(f"Sans_{in_belt.source}")

        total_throughput = sum([x.get_strength() for x in balancer.get_outputs()])
        if abs(total_throughput - exp_throughput) > common.diff_threshold_verif:
            print(f"Error: expected throughput to be "
                  f"{exp_throughput}, got {total_throughput}"
                  f" (diff > {common.diff_threshold_verif})")
            is_tu = False

        for out_belt in balancer.get_outputs():
            for name, frac in out_belt.supply_balance.items():
                if actual_coeff == -1:
                    actual_coeff = frac
                if abs(frac - actual_coeff) > common.diff_threshold_verif:
                    print(f"Error on {out_belt.dest}: expected balance of input {name} to be "
                          f"{actual_coeff:.{common.decimals_iter}f}, got {frac:.{common.decimals_iter}f}"
                          f" (diff > {common.diff_threshold_verif})")
                    is_balanced = False


        if not is_balanced:
            print(f"Balancer unbalanced when input {in_belt.source} is dry.")

        in_belt.enabled = True

    return is_balanced, is_tu

def test_output_balance(balancer: Balancer) -> (bool, bool):
    is_balanced = True
    is_tu = True

    exp_throughput = min(balancer.get_num_outputs() - 1, balancer.get_num_inputs())
    actual_coeff = -1

    # test blocking each output
    for out_belt in balancer.get_outputs():
        out_belt.enabled = False

        print(f"Calculating balance with {out_belt.dest} blocked")

        balancer.calc_balance()
        balancer.render(f"Block_{out_belt.dest}")

        total_throughput = sum([x.get_strength() for x in balancer.get_outputs()])
        if abs(total_throughput - exp_throughput) > common.diff_threshold_verif:
            print(f"Error: expected throughput to be "
                  f"{exp_throughput}, got {total_throughput}"
                  f" (diff > {common.diff_threshold_verif})")
            is_tu = False

        for enabled_out_belt in balancer.get_outputs():
            if not enabled_out_belt.enabled:
                continue
            for name, frac in enabled_out_belt.supply_balance.items():
                if actual_coeff == -1:
                    actual_coeff = frac
                if abs(frac - actual_coeff) > common.diff_threshold_verif:
                    print(f"Error on {out_belt.dest}: expected balance of input {name} to be "
                          f"{actual_coeff:.{common.decimals_iter}f}, got {frac:.{common.decimals_iter}f}"
                          f" (diff > {common.diff_threshold_verif})")
                    is_balanced = False

        if not is_balanced:
            print(f"Balancer unbalanced when output {out_belt.dest} is blocked.")

        out_belt.enabled = True

    return is_balanced, is_tu

# TODO: make I/O tests more thorough
# TODO: make networks for all N - M balancers for N,M = {1, 2, 3, 5, 7}
# TODO: add blueprint parsing (rip from Factorio SAT)
# TODO: add network optimization
# TODO: add blueprint export
# TODO: add P&R

# balancer3x3TU = Balancer.combine_balancers(Balancer_Book.make3x3(), Balancer_Book.make3x3())
# balancer = Balancer_Book.combine_balancers(balancer3x3TU, Balancer_Book.make_3x1())
# balancer = Balancer_Book.make_2x1_pri_in()
# balancer = Balancer_Book.make_3x1()
balancer = Balancer_Book.make_4x4_universal()
# balancer = Balancer_Book.make_real_3x1_reduced()
# balancer = Balancer_Book.make_4x3()

input_balanced, is_input_tu = test_input_balance(balancer)
output_balanced, is_output_tu = test_output_balance(balancer)

if not input_balanced:
    print("Balancer is not input balanced")

if not output_balanced:
    print("Balancer is not output balanced")

if not is_input_tu or not is_output_tu:
    print("Balancer is not TU")

balancer.calc_balance()
balancer.render()
balancer.export_to_sat_network()