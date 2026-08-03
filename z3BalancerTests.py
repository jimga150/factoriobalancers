import unittest

from Balancer import Balancer
import Balancer_Book


class MyTestCase(unittest.TestCase):

    def setUp(self):
        self.balancer22 = Balancer_Book.make_2x2()
        self.balancer44 = Balancer.combine_sidebyside(self.balancer22)
        self.balancer44TU = Balancer.combine_endtoend(self.balancer44)
        self.balancer44loop = Balancer.make_tap_loop(self.balancer44TU, self.balancer44TU)

    # def test_play(self):
    #     self.assertTrue(True)
    #     self.assertEqual(Balancer_Book.test_input_balanced_z3(self.balancer44), False)

    def test_2x2(self):
        self.runtest_balancer(self.balancer22, True, True, True, True, True)

    def test_4x4(self):
        self.runtest_balancer(self.balancer44, False, True, False, True, False)

    def test_4x4TU(self):
        self.runtest_balancer(self.balancer44TU, True, True, False, True, False)

    def test_4x4Universal(self):
        self.runtest_balancer(self.balancer44loop, True, True, True, True, True)

    def runtest_balancer(self, balancer: Balancer, tu: bool, pi: bool, fi: bool, po: bool, fo: bool):
        self.assertEqual(Balancer_Book.test_tu_z3(balancer), tu)
        self.assertEqual(Balancer_Book.test_partial_input_balanced_z3(balancer), pi)
        self.assertEqual(Balancer_Book.test_input_balanced_z3(balancer), fi)
        self.assertEqual(Balancer_Book.test_partial_output_balanced_z3(balancer), po)
        self.assertEqual(Balancer_Book.test_output_balanced_z3(balancer), fo)


if __name__ == '__main__':
    unittest.main()
