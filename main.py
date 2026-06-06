import common
from Balancer import Balancer

balancer = Balancer.make3x3()

num_outputs = balancer.get_num_outputs()
num_inputs = balancer.get_num_inputs()

exp_balance_coeff = num_outputs/num_inputs if num_outputs < num_inputs else num_inputs/num_outputs

num_inputs_1dry = num_inputs-1
exp_balance_coeff_1dry = 1.0/num_outputs

# test drying each input individually
for in_belt in balancer.get_inputs():

    in_belt.enabled = False

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

balancer.calc_balance()
balancer.render()