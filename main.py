import Balancer_Book
import common
from Balancer import Balancer

# TODO: add output balance test
# TODO: make networks for all N - M balancers for N,M = {1, 2, 3, 5, 7}
# TODO: add blueprint parsing (rip from Factorio SAT)
# TODO: add network optimization
# TODO: add blueprint export
# TODO: add P&R

# balancer3x3TU = Balancer.combine_balancers(Balancer_Book.make3x3(), Balancer_Book.make3x3())
# balancer = Balancer_Book.combine_balancers(balancer3x3TU, Balancer_Book.make_3x1())
# balancer = Balancer_Book.make_2x1_pri_in()
# balancer = Balancer_Book.make_3x1()
# balancer = Balancer_Book.make_4x4_universal()
# balancer = Balancer_Book.make_real_3x1_reduced()
balancer = Balancer_Book.make_4x3()

num_outputs = balancer.get_num_outputs()
num_inputs = balancer.get_num_inputs()

exp_balance_coeff = num_outputs/num_inputs if num_outputs < num_inputs else num_inputs/num_outputs

num_inputs_1dry = num_inputs-1
exp_balance_coeff_1dry = 1/num_outputs
exp_balance_coeff_1blocked = 1/num_inputs

# test drying each input individually
for in_belt in balancer.get_inputs():

    in_belt.enabled = False

    print(f"Calculating balance with {in_belt.source} dry")

    balancer.calc_balance()
    balancer.render(f"Sans_{in_belt.source}")

    is_balanced = True
    for out_belt in balancer.get_outputs():
        for name, frac in out_belt.supply_balance.items():
            if abs(frac - exp_balance_coeff_1dry) > common.diff_threshold_verif:
                print(f"Error on {out_belt.dest}: expected balance of input {name} to be "
                      f"{exp_balance_coeff_1dry:.{common.decimals_iter}f}, got {frac:.{common.decimals_iter}f}"
                      f" (diff > {common.diff_threshold_verif})")
                is_balanced = False

    if not is_balanced:
        print(f"Balancer unbalanced when input {in_belt.source} is dry.")

    in_belt.enabled = True

# test blocking each output
for out_belt in balancer.get_outputs():
    out_belt.enabled = False

    print(f"Calculating balance with {out_belt.dest} blocked")

    balancer.calc_balance()
    balancer.render(f"Block_{out_belt.dest}")

    is_balanced = True
    for enabled_out_belt in balancer.get_outputs():
        if not enabled_out_belt.enabled:
            continue
        for name, frac in enabled_out_belt.supply_balance.items():
            if abs(frac - exp_balance_coeff_1blocked) > common.diff_threshold_verif:
                print(f"Error on {enabled_out_belt.dest}: expected balance of input {name} to be "
                      f"{exp_balance_coeff_1blocked:.{common.decimals_iter}f}, got {frac:.{common.decimals_iter}f}"
                      f" (diff > {common.diff_threshold_verif})")
                is_balanced = False

    if not is_balanced:
        print(f"Balancer unbalanced when output {out_belt.dest} is blocked.")

    out_belt.enabled = True

balancer.calc_balance()
balancer.render()
balancer.export_to_sat_network()