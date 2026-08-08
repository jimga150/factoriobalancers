import copy
import unittest
from multiprocessing.dummy import Pool

from Balancer import Balancer
import Balancer_Book
from Node import Node
import UniqueIDObj

class NodeTests(unittest.TestCase):

    def setUp(self):
        num_nodes = 1000
        self.nodes = []
        for i in range(num_nodes):
            self.nodes.append(Node())

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

    def setUp(self):
        self.balancer22 = Balancer_Book.make_2x2()
        self.balancer44 = Balancer.combine_sidebyside(self.balancer22)
        self.balancer44TU = Balancer.combine_endtoend(self.balancer44)
        # self.balancer44TU.render_all_methods("balancer44TU")
        self.balancer44loop = Balancer.make_tap_loop(self.balancer44TU, self.balancer44)
        # self.balancer44loop.render_all_methods("balancer44loop")
        self.balancer88 = Balancer.combine_sidebyside(self.balancer44)
        self.balancer88TU = Balancer.combine_endtoend(self.balancer88)
        # self.balancer88TU2 = Balancer.combine_endtoend(self.balancer88TU)

    # def test_play(self):
    #     self.assertTrue(True)
    #     self.assertEqual(Balancer_Book.test_input_balanced_z3(self.balancer44), False)

    def test_2x2(self):
        self.runtest_balancer(self.balancer22, True, True, True, True, True, True)

    def test_4x4(self):
        self.runtest_balancer(self.balancer44, True, False, True, False, True, False)

    def test_4x4TU(self):
        self.runtest_balancer(self.balancer44TU, True, True, True, False, True, False)

    def test_4x4Universal(self):
        self.runtest_balancer(self.balancer44loop, True, True, True, True, True, True)

    def test_8x8(self):
        self.runtest_balancer(self.balancer88, True, False, True, False, True, False)

    def test_8x8TU(self):
        self.runtest_balancer(self.balancer88TU, True, False, True, False, True, False)

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


if __name__ == '__main__':
    unittest.main()
