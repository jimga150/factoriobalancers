import copy
import os
import unittest
from multiprocessing.dummy import Pool

import z3

from Balancer import Balancer
import Balancer_Book
from Node import Node
import UniqueIDObj

class NodeTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        num_nodes = 1000
        cls.nodes = []
        for i in range(num_nodes):
            cls.nodes.append(Node())

    def test_node_collision(self):
        self.check_collisions(self.nodes)

    def test_node_copying(self):
        new_nodes = copy.deepcopy(self.nodes)
        new_nodes.extend(copy.deepcopy(self.nodes))
        self.check_collisions(new_nodes)

    def test_node_attr_copying(self):
        new_nodes = copy.deepcopy(self.nodes)
        i = 0
        prefix = "node_"
        for node in new_nodes:
            node.name = f"{prefix}{i}"
        new_nodes2 = copy.deepcopy(new_nodes)

        for node in new_nodes2:
            self.assertEqual(prefix in str(node), True)

    def test_node_threadsafe(self):

        UniqueIDObj.copy_delay = 0.01

        result_nodes = []
        with Pool() as pool:
            results = pool.imap_unordered(copy.deepcopy, self.nodes, chunksize=10)
            for result in results:
                result_nodes.append(result)

        self.check_collisions(result_nodes)

    def check_collisions(self, nodes: list[Node]):
        for node in nodes:
            same_names = [x for x in nodes if str(x) == str(node)]
            if len(same_names) > 1:
                print(f"Error: {node} has a duplicate in the node list. Nodes:")
                for node in nodes:
                    print(f"{str(node)} ({hash(node)}) ({id(node)})")
                print("same_names:")
                for node in same_names:
                    print(f"{str(node)} ({hash(node)}) ({id(node)})")
                self.assertEqual(len(same_names), 1)

class BalancerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # remove all PNGs
        dir_name = "."
        test = os.listdir(dir_name)

        for item in test:
            if item.endswith(".png"):
                os.remove(os.path.join(dir_name, item))

        cls.balancer22 = Balancer_Book.make_2x2()
        cls.balancer22d = Balancer_Book.make_2x2_double()
        cls.balancer31 = Balancer_Book.make_3x1()
        cls.balancer44 = Balancer.combine_sidebyside(cls.balancer22)
        cls.balancer44TU = Balancer.combine_endtoend(cls.balancer44)
        # cls.balancer44TU.render_all_methods("balancer44TU")
        cls.balancer44loop = Balancer.make_tap_loop(cls.balancer44TU, cls.balancer44)
        # cls.balancer44loop.render_all_methods("balancer44loop")
        cls.balancer88 = Balancer.combine_sidebyside(cls.balancer44)
        # cls.balancer88TU = Balancer.combine_endtoend(cls.balancer88)
        cls.balancer88TU = Balancer_Book.make_8x8_TU()

    # def test_play(self):
    #     self.assertTrue(True)
    #     self.assertEqual(Balancer_Book.test_input_balanced_z3(self.balancer44), False)

    def test_2x2(self):
        self.runtest_balancer(self.balancer22, True, True, True, True, True, True)

    def test_2x2d(self):

        s = self.balancer22d.get_solver()
        s.assert_and_track(z3.Sum([x.supply_var() for x in self.balancer22d.get_outputs()]) == z3.Sum([x.demand_var() for x in self.balancer22d.get_outputs()]), "all_equal")

        self.runtest_balancer(self.balancer22d, True, True, True, True, True, True)

    def test_3x1(self):
        self.runtest_balancer(self.balancer31, True, True, True, False, True, True)

    def test_4x4(self):
        self.runtest_balancer(self.balancer44, True, False, True, False, True, False)

    def test_4x4TU(self):
        self.runtest_balancer(self.balancer44TU, True, True, True, False, True, False)

    def test_4x4Universal(self):
        self.runtest_balancer(self.balancer44loop, True, True, True, True, True, True)

    def test_8x8(self):
        self.runtest_balancer(self.balancer88, True, False, True, False, True, False)

    def test_8x8TU(self):
        self.runtest_balancer(self.balancer88TU, True, True, True, False, True, False)

    def runtest_balancer(self, balancer: Balancer, ptu: bool, tu: bool, pi: bool, fi: bool, po: bool, fo: bool):

        with self.subTest(msg="Partially TU"):
            self.assertEqual(Balancer_Book.test_partial_tu_z3(balancer), ptu)

        with self.subTest(msg="TU"):
            self.assertEqual(Balancer_Book.test_tu_z3(balancer), tu)

        with self.subTest(msg="Partially Input Balanced"):
            self.assertEqual(Balancer_Book.test_partial_input_balanced_z3(balancer), pi)

        with self.subTest(msg="Input balanced"):
            self.assertEqual(Balancer_Book.test_input_balanced_z3(balancer), fi)

        with self.subTest(msg="Partially Output Balanced"):
            self.assertEqual(Balancer_Book.test_partial_output_balanced_z3(balancer), po)

        with self.subTest(msg="Output Balanced"):
            self.assertEqual(Balancer_Book.test_output_balanced_z3(balancer), fo)

class SplitterTests(unittest.TestCase):
    # test various configurations of supply and demand against actual data in factorio

    @classmethod
    def setUpClass(cls):
        cls.balancer22 = Balancer_Book.make_2x2()
        cls.solver = cls.balancer22.get_solver()

    def setUp(self):
        self.solver.push()

    def tearDown(self):
        self.solver.pop()

    def runtest_splitter(self, in_supplies: list[float], in_demands: list[float|str], out_supplies: list[float|str], out_demands: list[float]):

        self.assertEqual(len(in_supplies), 2)
        self.assertEqual(len(in_demands), 2)
        self.assertEqual(len(out_supplies), 2)
        self.assertEqual(len(out_demands), 2)

        for belt, supply in zip(self.balancer22.get_inputs(), in_supplies):
            self.solver.assert_and_track(belt.supply_var() == supply, f"{belt}_s_eq_{supply}")

        for belt, demand in zip(self.balancer22.get_outputs(), out_demands):
            self.solver.assert_and_track(belt.demand_var() == demand, f"{belt}_d_eq_{demand}")

        self.assertEqual(self.solver.check(), z3.sat)

        self.balancer22.set_to_model()

        for belt, demand in zip(self.balancer22.get_inputs(), in_demands):
            self.compareVals(belt.demand, demand)

        for belt, supply in zip(self.balancer22.get_outputs(), out_supplies):
            self.compareVals(belt.supply, supply)

    def compareVals(self, actual: float, expected: float|str):
        if expected == "X":
            return
        elif type(expected) is int or type(expected) is float:
            self.assertEqual(actual, expected)
        elif expected[:2] == '<=':
            self.assertLessEqual(actual, float(expected[2:]))
        elif expected[:1] == '<':
            self.assertLess(actual, float(expected[1:]))
        elif expected[:2] == '>=':
            self.assertGreaterEqual(actual, float(expected[2:]))
        elif expected[:1] == '>':
            self.assertGreater(actual, float(expected[1:]))
        else:
            self.assertTrue(False, msg="value check failed all type/formatting checks")

    # depreciated--with the way supply is currently handled (generating oversupply when reacting to demand),
    # splitters no longer are totally reversible the way this test checks them.
    # the flow is still reversible, but this test makes supply imperative
    def runtest_splitter_bothways(self, in_supplies: list[float], in_demands: list[float|str], out_supplies: list[float|str], out_demands: list[float]):
        # run a splitter test, both in the intended way, and reversing supply and demand parameters. should produce the same result both times

        # normal way
        self.runtest_splitter(in_supplies, in_demands, out_supplies, out_demands)

        # clear asserts from last test
        self.solver.pop()
        self.solver.push()

        # reverse
        self.runtest_splitter(out_demands, out_supplies, in_demands, in_supplies)

    def test_even_supply(self):
        # distributes supply evenly among higher demands
        self.runtest_splitter([0, 1], [">=0", ">=1"], [0.5, 0.5], [1, 1])

    def test_uneven_unsaturated_supply(self):
        # total supply is still less than total demand, but one supply gets higher to meet higher demand
        # while the other one caps out at its lower demand
        self.runtest_splitter([0.25, 1], [">=0.25", ">=1"], [">=0.5", 0.75], [0.5, 1])

    def test_uneven_saturated_supply(self):
        # total supply = total demand, but the numbers change so we can see its redistributing
        self.runtest_splitter([0.25, 1], [0.25, 1], [">=0.5", ">=0.75"], [0.5, 0.75])

    def test_oversupply(self):
        # total supply > total demand, so both supplies just need to saturate demand
        self.runtest_splitter([0.75, 0.75], [0.375, 0.375], [">=0.5", ">=0.25"], [0.5, 0.25])

if __name__ == '__main__':
    unittest.main()
