import sys

import Balancer_Book
from Balancer import Balancer

import z3

from Belt import ColorStrategy

# TODO: add blueprint parsing (rip from Factorio SAT)
#   TODO: extend this to fast, express, and turbo components
#   TODO: add blueprint export
# TODO: generate balancers
#   TODO: generate 2^nx2^n balancers
#   TODO: generate NXN balancers
#   TODO: generate NxM redistributors
#   TODO: generate universal NxM balancers by applying universal method to NxM balancers
# TODO: add P&R\
# TODO: make actual UI


if __name__ == '__main__':

    # p1, p2, p3 = z3.Bools('p1 p2 p3')
    # x, y = z3.Ints('x y')
    # s = z3.Solver()
    # s.add(z3.Implies(p1, x > 0))
    # s.add(z3.Implies(p2, y > x))
    # s.add(z3.Implies(p2, y < 1))
    # s.add(z3.Implies(p3, y > -3))
    # s.check(p1, p2, p3)
    # core = s.unsat_core()
    #
    # print(f"Unsat core:")
    # for a in core:
    #     print(a)

    # balancer3x3TU = Balancer.combine_endtoend(Balancer_Book.make3x3(), Balancer_Book.make3x3())
    # balancer = Balancer_Book.combine_endtoend(balancer3x3TU, Balancer_Book.make_3x1())
    # balancer = Balancer_Book.make_2x1_pri_in()
    # balancer = Balancer_Book.make_3x1()
    # balancer = Balancer_Book.make_3x1_bigloop()
    # balancer = Balancer_Book.make_4x4_universal()
    # balancer = Balancer_Book.make_4x4_universal_blocked()
    # balancer = Balancer_Book.make4x4()
    # balancer = Balancer_Book.make4x4TU()
    # balancer = Balancer_Book.make_real_3x1_reduced()
    # balancer = Balancer_Book.make2x4_tl()
    # balancer = Balancer_Book.make_4x3()
    # balancer = Balancer_Book.make3x3()
    # balancer = Balancer_Book.make_2x2()

    # hopefully this makes a TU 8x8
    balancer44 = Balancer_Book.make4x4()
    balancer44TU = Balancer.combine_endtoend(balancer44)
    balancer88 = Balancer.combine_sidebyside(balancer44)
    balancer88TU = Balancer.combine_endtoend(balancer88)
    balancer88Uni = Balancer.make_tap_loop(balancer88, balancer88TU)
    balancer = balancer44TU

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

    # if Balancer_Book.test_balance(balancer, exit_on_fail=False, test_input_blocking=True, test_output_blocking=True, max_threads=3):
    #     print("Pass")
    # else:
    #     print("Fail")
    #
    # balancer.calc_balance()
    # balancer.render()
    # balancer.export_to_sat_network()

    if Balancer_Book.test_total_balance_z3(balancer):
        print("Pass")
    else:
        print("Fail")

    balancer.render("pri", color_strat=ColorStrategy.PRIORITY)
    balancer.render("flow", color_strat=ColorStrategy.FLOW)
    balancer.render("bp", color_strat=ColorStrategy.BACKPRESSURE)