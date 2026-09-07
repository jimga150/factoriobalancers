import copy
import os
import unittest
from multiprocessing.dummy import Pool

import z3

import common
from Balancer import Balancer
import Balancer_Book
import BalancerTests
from Belt import ColorStrategy
from Blueprint import Blueprint
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
                self.assertEqual(1, len(same_names))

class Z3BalancerTests(unittest.TestCase):

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
    #     self.assertEqual(False, Balancer_Book.test_input_balanced_z3(self.balancer44))

    def test_2x2(self):
        self.runtest_balancer(self.balancer22, True, True, True, True, True, True)

    def test_2x2d(self):

        # s = self.balancer22d.get_solver()
        # s.push()
        # s.assert_and_track(z3.Sum([x.supply_var() for x in self.balancer22d.get_outputs()]) == z3.Sum([x.demand_var() for x in self.balancer22d.get_outputs()]), "all_equal")

        self.runtest_balancer(self.balancer22d, True, True, True, True, True, True)

        # s.pop()

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
            self.assertEqual(ptu, BalancerTests.test_partial_tu_z3(balancer))

        with self.subTest(msg="TU"):
            self.assertEqual(tu, BalancerTests.test_tu_z3(balancer))

        with self.subTest(msg="Partially Input Balanced"):
            self.assertEqual(pi, BalancerTests.test_partial_input_balanced_z3(balancer))

        with self.subTest(msg="Input balanced"):
            self.assertEqual(fi, BalancerTests.test_input_balanced_z3(balancer))

        with self.subTest(msg="Partially Output Balanced"):
            self.assertEqual(po, BalancerTests.test_partial_output_balanced_z3(balancer))

        with self.subTest(msg="Output Balanced"):
            self.assertEqual(fo, BalancerTests.test_output_balanced_z3(balancer))

class SplitterTests(unittest.TestCase):
    # test various configurations of supply and demand against actual data in factorio

    # all external vars are of the form n/denominator
    denominator = common.ext_var_quant_denom if common.use_quant_ext_vars else 1

    @classmethod
    def setUpClass(cls):
        cls.balancer22 = Balancer_Book.make_2x2()
        cls.solver = cls.balancer22.get_solver()

    def setUp(self):
        if common.use_quant_ext_vars:
            self.assertGreaterEqual(common.ext_var_quant_denom, self.denominator)
        self.solver.push()

    def tearDown(self):
        self.solver.pop()

    def runtest_splitter(self, in_supplies: list[float], in_demands: list[float|str], out_supplies: list[float|str], out_demands: list[float]):

        self.assertEqual(2, len(in_supplies))
        self.assertEqual(2, len(in_demands))
        self.assertEqual(2, len(out_supplies))
        self.assertEqual(2, len(out_demands))

        if common.use_quant_ext_vars:
            in_supplies = [x*self.denominator for x in in_supplies]
            out_demands = [x*self.denominator for x in out_demands]

        for belt, supply in zip(self.balancer22.get_inputs(), in_supplies):
            self.solver.assert_and_track(belt.supply_var() == supply, f"{belt}_s_eq_{supply}")

        for belt, demand in zip(self.balancer22.get_outputs(), out_demands):
            self.solver.assert_and_track(belt.demand_var() == demand, f"{belt}_d_eq_{demand}")

        check_result = self.solver.check()

        if check_result == z3.unsat:
            self.balancer22.logger.error("Unsat core:")
            self.balancer22.logger.error(self.solver.unsat_core())

        self.assertEqual(z3.sat, check_result)

        self.balancer22.set_to_model()
        if common.debug:
            test_dbg_name = ""
            test_dbg_name += "[" + (", ".join(str(x) for x in in_supplies)) + "], "
            test_dbg_name += "[" + (", ".join(str(x) for x in in_demands)) + "], "
            test_dbg_name += "[" + (", ".join(str(x) for x in out_supplies)) + "], "
            test_dbg_name += "[" + (", ".join(str(x) for x in out_demands)) + "]"
            self.balancer22.render(test_dbg_name, ColorStrategy.BACKPRESSURE)

        for belt, demand in zip(self.balancer22.get_inputs(), in_demands):
            self.compareVals(float(belt.demand)/self.denominator, demand)

        for belt, supply in zip(self.balancer22.get_outputs(), out_supplies):
            self.compareVals(float(belt.supply)/self.denominator, supply)

    def compareVals(self, actual: float, expected: float|str):
        if expected == "X":
            return
        elif type(expected) is int or type(expected) is float:
            self.assertEqual(expected, actual)
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
        self.runtest_splitter([0.25, 1], [0.25, 1], [">=0.5", 0.75], [0.5, 0.75])

    def test_oversupply(self):
        # total supply > total demand, so both supplies just need to saturate demand
        self.runtest_splitter([0.75, 0.75], [0.375, 0.375], [">=0.5", ">=0.25"], [0.5, 0.25])

class BlueprintTests(unittest.TestCase):

    def test_rtest_1(self):
        # Render test 1 (only yellow)
        bp_str = "0eNqdmN1uozAQhV9l5Wu2woNtbB5jb1fVKmmtCokAArPaKOLda6gE2cYO47nJD4JvxuM5h4EbOzeT7Ye6day6sfqta0dW/b6xsf5oT81yrD1dLKuYG07t2HeD+3m2jWNzxur23f5jFZ+zwOlj39TO2eHuRJhfM2ZbV7vafgVZ/1z/tNPl7M+seBYJlrG+G/1lXbtEWGIK+SIzdvW//A8f4r0e7NvXCWLJ5xsZEsgqiVxs5MmvcvgYOv8dZZdxdsbctV84ddtPS30fQomkUAYRqptcJJbEF0zypIKpBHKeRC4TyBAl6wBZUxrT99EcYBkKqwyzeE7pa4UpJk8RY5mGJqkxVoI0Aep73H+ZLlkdKZATJVgS1M53CW5e+mxBClH4BO3tyeP2tKQYRokRH9cUtEKhDcWMUAWBPKVVdj96LMlxqwCnOB+qQgBJHb8Zll7hh7cZIN4+DUFQIFCC2mLo7/4QYkqKlemwlYFCJaj2EoQgJQpinkM0zec0ZdQAQ3NwTeiBIk2VOaLf4gsrOGYr9iAaMW0CxQsNRulFgcoWIsUPIgXNA03cA59UW5KcCvJ7p4o3jiKMbcDD8ipKwmy1wo4dqdAER1qLEIIZCiyyapHjBpr7bTloMJEypOq0QgrAqTcl3YIwbmDTFQRnwLIpT4PIkijC6PKYdhBNeR5EZk15IASI6IIkMkDtnMwpToNkc9yksVExTCDNAqGMMS85CtI08DRa9A4iSQJFboWktHqI/Zqx2tmLB+3vBTPWnDzMH/tllzL9cHZcjv61w7heJxUYYYzUQpX+Y54/Ab6ll7o="
        self.import_export_same(bp_str)

    def test_rtest_2(self):
        # render test 2 (all types)
        bp_str = "0eNqlWttO4zAQ/RXk54B8GY/tfsa+rtCqhSyKVNIqSVcg1H/fFFBvxM3M+AVE1M71zDkehw+1Wu/qbde0g1p8qOZp0/Zq8ftD9c1Lu1wfnrXL11ot1NAt23676Yb7Vb0e1L5STftcv6mF2VcTH/+77If77Hfs/rFSdTs0Q1N/+fv84/1Pu3td1d1otMr4rdR2049f27QHZwf3Pj34Sr2rhXMPfnTx3HT109cH4BDalWV7tLwbY+leus34O2cbdd52pYb37cFO0253h+R+uHL0JNCxkgBWEpaQxGY3ZLLw1a2eTrjzrFSQUSTIWo4TlsNl4JRKYUm7I7dQPOAmfjqxqPFGMxMKmtUfIxryEQP7KWOsuT6Z85+RzteCM8v6PNbZvhqQmPaZMpymtd+um2EYH06YMccICfFxJtTyUg8ShgQSuKKYtnIIEwygZ8LMahaxQ74k83RlDQkqcJ7ATNGt5RYdWXixTmw/My8WLi3eqkRgDI1lq2bkVQLFYkMaH8sXz6CL0BjJjQiaA8kk04VwPrD5E55mEJi5tH0WuLFTto1EF8I0zp0lDft3ZTFjRHSgRUqbHEhMEwvpC4ibiAOU8TbmJyUvEi5IjsyB1Aa2agZmL5KYwTPIBk1ncLwJbzBiTiVhHKzYPq244ApIWwRFAPGKQMIjnEZ32HWrzT1jUUikRRolO0jMAChcRcu6YUiClRMii3fMeQJXeKJ0O0kUKZKw6zW30ycZIHXaG0FzLKE5N25OeHdNjtKdLBS8Iyn8MaNIaQqwmwLZik3Ntz/Nd/227eq+5yxqtL6jeBHMjLkX6S9xDOKPgrDurSQk4gWLbShjEtTiYwCtjmhEdYxF845WgGaeXiFf4jEV8QoyNuTIIRcUzH7QLHpBFB9PiDAL4vMJ6Gl2wcjXqZNRQ7tnwsQmdn0e9yxOg5Y7MNOFCdcCTrngBE2I1bJjtbxiOPHZ5qeDyTcdIDjbQN7FPCsEz2gGnGNzLhUUEbdnDkAIBQeP3OiGn+JNuU8kYTQJ4sWZiYq6xCgJ+tEUSCIN/FGiupGXheM09vt+kob3CBK8B10yvNGXSIwj3YhFZHOeufQwp70xyCXGZQYiMljtu8s2YyrJOd9SgJPkCzOxwMmUqIqV3CclK144gfTOObkyeaGBPwFLCPAmkpIvYekM0hMKjAYmfkIJ9xN9xBIftEFLBXsKDZVG6zIVEA2b0Ua+veRekmsrIA1zbpV/m2C0k0sBkHBmtOSI7Sh5ZVnEaM4h+7iSACkdlBMttWJFR+wsvmIJG1JDTyKVCIUwNpolG5HVcSO7EUtlEDa2hDyn2vVYqWaoX0eDp/9crdR6ORobn/2qDzndDXU/3Nnx+b+66z+/6dEmSMlHwDD+2O//A5gAEC4="
        self.import_export_same(bp_str)

    def test_8x8_tu_yellow(self):
        # 8x8 TU yellow balancer
        bp_str = "0eJydmttu4zYQhl9F4FULKIFISzz4MRbZq2JRyDGbCFAkQ6aSdQO/e2G7ieiE9PDnpYPo03DOM+I72/Sz3U3d4Nj6nW3t/nHqdq4bB7ZmD8/TOD8972Z3Nw9999I5uy3+ePj5Z7Fp+3Z4tNO+aPu39rAvdtP42m1t8c/c94X7fO6+KH7Yp7lvJ/+RyRbj0B+Kp7md2sFZuy3cGEMUb892KNq+L7phN7t9MU7nX+Pszj9PtNl1ffev3d6zknWP47Bn67/e2b57Gtr+dCx32Fm2Zq/d5Oa2ZyUb2pfTHy7/cafZsWTdsLW/2Zofy8wnBfTkwfb9+OY9voIef/CerI+/SmYH17nOXk5+/nH4e5hfNnZia/75tJvaYb8bJ3e3sb1jJduN++5i7Xf2m62Vau6bkh3YWtTqvjmeZPoCEwBMUbAVAJMUrAZghoI1AExTMJkO05yCKQBWUTANwAQFM4uX7vrOOTsF7fg/RIchvMryVhOh8SSZNCGTSKIoQpZVCkVXhCyIm2tSP4ifG5Imk04oiBOqJAonZMlz7RjN5HhlU0VyaJaPNzxCW3x8HrZ2eprGedjSSfksXflRaS71lIX4AuJLmJ9VBc7aKNm2m+zj5T+4CMGRcFEoPKtKRO0IlAmPFvMxoE4skR2VDYgmjxaTzSAetVSxVI9aVRCfw3ygo/Lo35yqDrGBBsvTTBobiLQlJ8asuAJCy6NFPGyFxNKSE1dJ50Yia2GLr2wdYidVq48O48wMUZD4UlenD9GQaiUxXdZQbHn0b9o8dVVkqNVJDdxH0xRTb42VMPNFJbSUK4ivYT4SahXlHjUQal76+uYewZpYy8zce8s/zqN/UDHINCRuvSsEz2oho1rPayHrlKBs8hrKJjL7IgsDRdKw2FNfTk55QIOFnrwSNwFfZ+K/2y3hZXn9ZJPkzQ1SBA0KV5kdXaIVkEjkVzYI0XLbzxs2jedumduMpqlGIr2ooFQjke5TUKEvkzYeHxuhRkYoyAi3JLfYLg6JMXVFI9OwhGqflyxUWhsg82a6mCaQnlODmkjaBX62bRHLKyx0KlSfKq25FISUUIHzAjxVyrypLbY+zosmkzILqbwZLrIHVFg0qSteil6RaJJxTQQLotKZqUBnjUkKaS4VeBaNjXw6bIhoBdPY/tKg+LTlvfFUEqIgQchvWTMER8Y7fmW9EK3JzJq3XC+uXuTjVhX3vFAV0XnTXSSf6LxxLqblrHFOVinnNlnjnEzaARos2uQNyWnnMGmxp71XhCjIBwJ1pY4QDSmAElRug7Q90fNmTWrR8yJlTpM0qK4tyeqW+8TLmgGCzHtX2tcbXgFhtqSumGZ4lTWJxZyAV1mjWPLZkZhaUkxkv8qrrK5SRlZlvIJKmBelIqkl4FVma5nMT/sooCg1ZH11ixsJKVmGNBJ0U0OT0nFk66hp6TKnslQTc2jv6KWPVH6dVEo4pQZk1y9oIyHdnqCNhNSmJW1E1k3cu/ORsG+SkR0Yhy57SFIq6LaHonHQlaboIQVykU/TUiH1xNC4NO+vqEMi3l/RUmVd5Ivj0i46CeqQWXPNRapfJeucfWFr7x5wyfp2Y3u2ZvpOF5eLqsXDz88bvKxkr3ban6mNFKY2plGmXgkjvXu05vgf8zhUBg=="
        self.import_export_same(bp_str)

    def test_pinwheel(self):
        # 4 belt pinwheel
        bp_str = "0eJylkstugzAQRX+lumuDeBjTeNkv6L6KKkhG7UjGINtpgpD/vQIWbdp0UbKc0dwzdx4TWnOiwbEN0BP40FsP/TLB85ttzJwL40DQ4EAdBGzTzVFwjfVD70LSkgmIAmyPdIHOo9guLu4Rl/eIZdwLkA0cmNYFLMH4ak9dSw46/4shMPSeA/d27nqBTqTM0kpghE5KlVZx9vWDVmyj1WkVBY7s6LCWFDfY5T/Y5e7K6RVb3WDLbexfvpd1L6fR3x5QwDQtGWg8kQkPz2zP70QGAh/k/DrwYy5ruatVnWeqUl8HzOInTeLqGg=="
        self.import_export_same(bp_str)

    def import_export_same(self, bp_str: str):
        # imports a blueprint string, export it, then import it again and test if the blueprints are identical
        bp = Blueprint(bp_str)
        export_str = bp.to_bp_str()
        bp2 = Blueprint(export_str)
        self.assertEqual(True, common.dicts_eq(bp.bp_dict, bp2.bp_dict, debug=True))


if __name__ == '__main__':
    unittest.main()
