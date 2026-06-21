import Balancer_Book
from Balancer import Balancer

# TODO: experiment with universal balancer generation
# TODO: multithreading on test (takes nCr(n)*nCr(m) iterations)
# TODO: add blueprint parsing (rip from Factorio SAT)
# TODO: add network optimization
# TODO: add P&R
# TODO: add blueprint export

if __name__ == '__main__':

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
    balancer88 = Balancer.combine_sidebyside(balancer44)
    balancer88TU = Balancer.combine_endtoend(balancer88)
    balancer88Uni = Balancer.make_tap_loop(balancer88TU, balancer88)
    balancer = balancer44

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

    if Balancer_Book.test_balance(balancer, exit_on_fail=False, test_input_blocking=True, test_output_blocking=True):
        print("Pass")
    else:
        print("Fail")

    balancer.calc_balance()
    balancer.render()
    balancer.export_to_sat_network()