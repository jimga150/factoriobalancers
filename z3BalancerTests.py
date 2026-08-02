import unittest

from Balancer import Balancer
import Balancer_Book


class MyTestCase(unittest.TestCase):

    balancer22 = Balancer_Book.make_2x2()
    balancer44 = Balancer_Book.make4x4()
    balancer44TU = Balancer.combine_endtoend(balancer44)

    def test_TU(self):
        _, _, is_tu = Balancer_Book.test_balance_z3(self.balancer44TU)
        self.assertEqual(is_tu, True)

    def test_not_TU(self):
        _, _, is_tu = Balancer_Book.test_balance_z3(self.balancer44)
        self.assertEqual(is_tu, False)

    def test_not_input_balanced(self):
        inb, _, _ = Balancer_Book.test_balance_z3(self.balancer44)
        self.assertEqual(inb, False)

    def test_not_output_balanced(self):
        _, outb, _ = Balancer_Book.test_balance_z3(self.balancer44)
        self.assertEqual(outb, False)

    def test_2x2_TU(self):
        _, _, is_tu = Balancer_Book.test_balance_z3(self.balancer22)
        self.assertEqual(is_tu, True)

    def test_2x2_input_balanced(self):
        inb, _, _ = Balancer_Book.test_balance_z3(self.balancer22)
        self.assertEqual(inb, True)

    def test_2x2_output_balanced(self):
        _, outb, _ = Balancer_Book.test_balance_z3(self.balancer22)
        self.assertEqual(outb, True)


if __name__ == '__main__':
    unittest.main()
