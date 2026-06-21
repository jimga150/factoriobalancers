import Balancer_Book
from Balancer import Balancer

# TODO: make networks for all N - M balancers for N,M = {1, 2, 3, 5, 7}
# TODO: add blueprint parsing (rip from Factorio SAT)
# TODO: add network optimization
# TODO: add blueprint export
# TODO: add P&R

# balancer3x3TU = Balancer.combine_endtoend(Balancer_Book.make3x3(), Balancer_Book.make3x3())
# balancer = Balancer_Book.combine_endtoend(balancer3x3TU, Balancer_Book.make_3x1())
# balancer = Balancer_Book.make_2x1_pri_in()
# balancer = Balancer_Book.make_3x1()
# balancer = Balancer_Book.make_3x1_bigloop()
balancer = Balancer_Book.make_4x4_universal()
# balancer = Balancer_Book.make_4x4_universal_blocked()
# balancer = Balancer_Book.make_real_3x1_reduced()
# balancer = Balancer_Book.make2x4_tl()
# balancer = Balancer_Book.make_4x3()
# balancer = Balancer_Book.make3x3()
# balancer = Balancer_Book.make_2x2()

balancer = Balancer.combine_sidebyside(balancer)

# balancer44TU = Balancer_Book.make4x4TU()
# balancer44 = Balancer_Book.make4x4()
# balancer = Balancer.make_tap_loop(balancer44)

'''
I->O TU | reb TU    | Pass
   N    |   N       |   N
   N    |   Y       |   Y
   Y    |   N       |   Y
   Y    |   Y       |   Y
'''

# universal balancers cannot simply be combined to make larger universal balancers
# you have to make a rebalancer at the net I/O layer

# two partial TU balancers can be combined to make a full TU balancer
# A TU balancer rebalancing a non-TU balancer (or vice versa) makes a universal balancer

if Balancer_Book.test_balance(balancer, exit_on_fail=True, test_input_blocking=True, test_output_blocking=True):
    print("Pass")
else:
    print("Fail")

balancer.calc_balance()
balancer.render()
balancer.export_to_sat_network()