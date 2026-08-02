import unittest

from Balancer import Balancer
import Balancer_Book


class MyTestCase(unittest.TestCase):

    balancer22 = Balancer_Book.make_2x2()
    balancer44 = Balancer_Book.make4x4()
    balancer44TU = Balancer.combine_endtoend(balancer44)

    def test_TU(self):
        self.assertEqual(Balancer_Book.test_tu_z3(self.balancer44TU), True)

    def test_not_TU(self):
        self.assertEqual(Balancer_Book.test_tu_z3(self.balancer44), False)

    def test_not_input_balanced(self):
        self.assertEqual(Balancer_Book.test_input_balanced_z3(self.balancer44), False)

    def test_not_output_balanced(self):
        self.assertEqual(Balancer_Book.test_output_balanced_z3(self.balancer44), False)

    def test_2x2_TU(self):
        self.assertEqual(Balancer_Book.test_tu_z3(self.balancer22), True)

    def test_2x2_input_balanced(self):
        self.assertEqual(Balancer_Book.test_input_balanced_z3(self.balancer22), True)

    def test_2x2_output_balanced(self):
        self.assertEqual(Balancer_Book.test_output_balanced_z3(self.balancer22), True)


if __name__ == '__main__':
    unittest.main()
