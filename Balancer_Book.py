from Balancer import Balancer
from Belt import Belt
from Node import Node


def make3x3() -> Balancer:
    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_c = Node()
    node_1 = Node()
    node_2 = Node()
    node_3 = Node()
    node_4 = Node()
    node_5 = Node()
    node_6 = Node()
    node_o1 = Node()
    node_o2 = Node()
    node_o3 = Node()

    ans.balance.append(Belt(node_a, node_1))
    ans.balance.append(Belt(node_b, node_1))
    ans.balance.append(Belt(node_c, node_2))
    ans.balance.append(Belt(node_1, node_2))
    ans.balance.append(Belt(node_2, node_3))
    ans.balance.append(Belt(node_1, node_3))
    ans.balance.append(Belt(node_2, node_4))
    ans.balance.append(Belt(node_3, node_5))
    ans.balance.append(Belt(node_4, node_5))
    ans.balance.append(Belt(node_3, node_6))
    ans.balance.append(Belt(node_4, node_6))
    ans.balance.append(Belt(node_5, node_4))
    ans.balance.append(Belt(node_5, node_o1))
    ans.balance.append(Belt(node_6, node_o2))
    ans.balance.append(Belt(node_6, node_o3))

    ## make BAD 3->1
    # node_7 = Node()
    # node_o = Node()
    # self.balance.append(Belt(node_6, node_7))
    # self.balance.append(Belt(node_7, node_o))

    ans.postprocess_nodes()
    return ans

def make4x4() -> Balancer:
    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_c = Node()
    node_d = Node()
    node_1 = Node()
    node_2 = Node()
    node_3 = Node()
    node_4 = Node()
    node_o1 = Node()
    node_o2 = Node()
    node_o3 = Node()
    node_o4 = Node()

    ans.balance.append(Belt(node_a, node_1))
    ans.balance.append(Belt(node_b, node_1))
    ans.balance.append(Belt(node_c, node_2))
    ans.balance.append(Belt(node_d, node_2))
    ans.balance.append(Belt(node_1, node_3))
    ans.balance.append(Belt(node_1, node_4))
    ans.balance.append(Belt(node_2, node_3))
    ans.balance.append(Belt(node_2, node_4))
    ans.balance.append(Belt(node_3, node_o1))
    ans.balance.append(Belt(node_3, node_o2))
    ans.balance.append(Belt(node_4, node_o3))
    ans.balance.append(Belt(node_4, node_o4))

    ans.postprocess_nodes()
    return ans

def make_3x1() -> Balancer:
    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_c = Node()
    node_1 = Node()
    node_2 = Node()
    node_3 = Node()
    node_o = Node()

    ans.balance.append(Belt(node_a, node_1))
    ans.balance.append(Belt(node_b, node_2))
    ans.balance.append(Belt(node_c, node_2))
    ans.balance.append(Belt(node_1, node_3))
    ans.balance.append(Belt(node_2, node_3))
    ans.balance.append(Belt(node_3, node_1))
    ans.balance.append(Belt(node_3, node_o, True))

    ans.postprocess_nodes()
    return ans

def make_2x2() -> Balancer:

    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_1 = Node()
    node_o1 = Node()
    node_o2 = Node()

    ans.balance.append(Belt(node_a, node_1))
    ans.balance.append(Belt(node_b, node_1))
    ans.balance.append(Belt(node_1, node_o1))
    ans.balance.append(Belt(node_1, node_o2))

    ans.postprocess_nodes()
    return ans

def make_2x2_pri_out() -> Balancer:

    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_1 = Node()
    node_o1 = Node()
    node_o2 = Node()

    ans.balance.append(Belt(node_a, node_1))
    ans.balance.append(Belt(node_b, node_1))
    ans.balance.append(Belt(node_1, node_o1, True))
    ans.balance.append(Belt(node_1, node_o2))

    ans.postprocess_nodes()
    return ans

def make_2x1_pri_in() -> Balancer:

    ans = Balancer()

    node_a = Node()
    node_b = Node()
    node_1 = Node()
    node_o1 = Node()

    ans.balance.append(Belt(node_a, node_1, False, True))
    ans.balance.append(Belt(node_b, node_1))
    ans.balance.append(Belt(node_1, node_o1))

    ans.postprocess_nodes()
    return ans

def make_4x3() -> Balancer:

    ans = Balancer()

    input_nodes = [Node() for _ in range(4)]
    output_nodes = [Node() for _ in range(3)]
    int_nodes = [Node() for _ in range(7)]

    ans.balance.append(Belt(input_nodes[0], int_nodes[0]))
    ans.balance.append(Belt(input_nodes[1], int_nodes[0]))
    ans.balance.append(Belt(input_nodes[2], int_nodes[1]))
    ans.balance.append(Belt(input_nodes[3], int_nodes[1]))
    ans.balance.append(Belt(int_nodes[0], int_nodes[2]))
    ans.balance.append(Belt(int_nodes[0], int_nodes[4], True))
    ans.balance.append(Belt(int_nodes[1], int_nodes[4], True))
    ans.balance.append(Belt(int_nodes[1], int_nodes[2]))
    ans.balance.append(Belt(int_nodes[2], int_nodes[3], False, True))
    ans.balance.append(Belt(int_nodes[3], int_nodes[5], False, True))
    ans.balance.append(Belt(int_nodes[3], int_nodes[6], False, True))
    ans.balance.append(Belt(int_nodes[4], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[4], int_nodes[6]))
    ans.balance.append(Belt(int_nodes[5], int_nodes[3]))
    ans.balance.append(Belt(int_nodes[5], output_nodes[0]))
    ans.balance.append(Belt(int_nodes[6], output_nodes[1]))
    ans.balance.append(Belt(int_nodes[6], output_nodes[2]))

    ans.postprocess_nodes()
    return ans

def make_3x1_subbalancer() -> Balancer:

    # this is the subtree of the 4 - 4 universal balancer that takes leftover output, balances it,
    # and then loops it back to each input
    # im cutting out I/Os to force it to act as a 3 - 1 as it does in the 3 - 1 case for the universal balancer

    ans = Balancer()

    input_nodes = [Node() for _ in range(3)]
    output_nodes = [Node() for _ in range(1)]
    int_nodes = [Node() for _ in range(18)]

    ans.balance.append(Belt(input_nodes[0], int_nodes[0]))
    ans.balance.append(Belt(input_nodes[1], int_nodes[0]))
    ans.balance.append(Belt(input_nodes[2], int_nodes[1]))
    ans.balance.append(Belt(int_nodes[0], int_nodes[2]))
    ans.balance.append(Belt(int_nodes[1], int_nodes[2]))
    ans.balance.append(Belt(int_nodes[0], int_nodes[3]))
    ans.balance.append(Belt(int_nodes[1], int_nodes[3]))
    # ans.balance.append(Belt(int_nodes[2], int_nodes[4]))
    # ans.balance.append(Belt(int_nodes[3], int_nodes[4]))
    ans.balance.append(Belt(int_nodes[2], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[3], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[5], output_nodes[0]))
    # ans.balance.append(Belt(int_nodes[9], output_nodes[1], True))
    # ans.balance.append(Belt(int_nodes[10], output_nodes[2], True))
    # ans.balance.append(Belt(int_nodes[11], output_nodes[3], True))

    ans.postprocess_nodes()
    return ans

def make_real_3x1() -> Balancer:

    ans = Balancer()

    input_nodes = [Node() for _ in range(4)]
    output_nodes = [Node() for _ in range(4)]
    int_nodes = [Node() for _ in range(18)]

    ans.balance.append(Belt(input_nodes[0], int_nodes[0], False, True))
    ans.balance.append(Belt(input_nodes[1], int_nodes[1], False, True))
    ans.balance.append(Belt(input_nodes[2], int_nodes[2], False, True))
    # ans.balance.append(Belt(input_nodes[3], int_nodes[3], False, True))
    ans.balance.append(Belt(int_nodes[0], int_nodes[4]))
    ans.balance.append(Belt(int_nodes[1], int_nodes[4]))
    ans.balance.append(Belt(int_nodes[2], int_nodes[5]))
    # ans.balance.append(Belt(int_nodes[3], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[4], int_nodes[6]))
    ans.balance.append(Belt(int_nodes[4], int_nodes[7]))
    ans.balance.append(Belt(int_nodes[5], int_nodes[6]))
    ans.balance.append(Belt(int_nodes[5], int_nodes[7]))
    ans.balance.append(Belt(int_nodes[6], int_nodes[8]))
    ans.balance.append(Belt(int_nodes[6], int_nodes[12]))
    ans.balance.append(Belt(int_nodes[7], int_nodes[12]))
    ans.balance.append(Belt(int_nodes[7], int_nodes[13]))
    ans.balance.append(Belt(int_nodes[8], int_nodes[13]))
    # ans.balance.append(Belt(int_nodes[9], int_nodes[12]))
    # ans.balance.append(Belt(int_nodes[10], int_nodes[12]))
    # ans.balance.append(Belt(int_nodes[11], int_nodes[13]))
    ans.balance.append(Belt(int_nodes[12], int_nodes[14]))
    ans.balance.append(Belt(int_nodes[12], int_nodes[15]))
    ans.balance.append(Belt(int_nodes[13], int_nodes[14]))
    ans.balance.append(Belt(int_nodes[13], int_nodes[15]))
    ans.balance.append(Belt(int_nodes[14], int_nodes[16]))
    ans.balance.append(Belt(int_nodes[15], int_nodes[16]))
    ans.balance.append(Belt(int_nodes[14], int_nodes[17]))
    ans.balance.append(Belt(int_nodes[15], int_nodes[17]))
    ans.balance.append(Belt(int_nodes[16], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[16], int_nodes[1]))
    ans.balance.append(Belt(int_nodes[17], int_nodes[0]))
    ans.balance.append(Belt(int_nodes[17], int_nodes[2]))
    ans.balance.append(Belt(int_nodes[8], output_nodes[0], True))
    # ans.balance.append(Belt(int_nodes[9], output_nodes[1], True))
    # ans.balance.append(Belt(int_nodes[10], output_nodes[2], True))
    # ans.balance.append(Belt(int_nodes[11], output_nodes[3], True))

    ans.postprocess_nodes()
    return ans

def make_real_3x1_reduced() -> Balancer:

    ans = Balancer()

    input_nodes = [Node() for _ in range(3)]
    output_node = Node()
    int_nodes = [Node() for _ in range(18)]

    ans.balance.append(Belt(input_nodes[0], int_nodes[0], False, True))
    ans.balance.append(Belt(input_nodes[1], int_nodes[1], False, True))
    ans.balance.append(Belt(input_nodes[2], int_nodes[2], False, True))

    ans.balance.append(Belt(int_nodes[0], int_nodes[3]))
    ans.balance.append(Belt(int_nodes[1], int_nodes[3]))
    ans.balance.append(Belt(int_nodes[2], int_nodes[4]))
    ans.balance.append(Belt(int_nodes[3], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[4], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[3], int_nodes[6]))
    ans.balance.append(Belt(int_nodes[4], int_nodes[6]))
    ans.balance.append(Belt(int_nodes[5], int_nodes[7]))
    ans.balance.append(Belt(int_nodes[6], int_nodes[7]))
    ans.balance.append(Belt(int_nodes[5], int_nodes[8]))
    ans.balance.append(Belt(int_nodes[8], int_nodes[4]))
    ans.balance.append(Belt(int_nodes[8], int_nodes[0]))
    ans.balance.append(Belt(int_nodes[7], int_nodes[1]))
    ans.balance.append(Belt(int_nodes[7], int_nodes[2]))

    ans.balance.append(Belt(int_nodes[6], output_node))


    ans.postprocess_nodes()
    return ans

def make_4x4_universal() -> Balancer:

    ans = Balancer()

    input_nodes = [Node() for _ in range(4)]
    output_nodes = [Node() for _ in range(4)]
    int_nodes = [Node() for _ in range(18)]

    ans.balance.append(Belt(input_nodes[0], int_nodes[0], False, True))
    ans.balance.append(Belt(input_nodes[1], int_nodes[1], False, True))
    ans.balance.append(Belt(input_nodes[2], int_nodes[2], False, True))
    ans.balance.append(Belt(input_nodes[3], int_nodes[3], False, True))
    ans.balance.append(Belt(int_nodes[0], int_nodes[4]))
    ans.balance.append(Belt(int_nodes[1], int_nodes[4]))
    ans.balance.append(Belt(int_nodes[2], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[3], int_nodes[5]))
    ans.balance.append(Belt(int_nodes[4], int_nodes[6]))
    ans.balance.append(Belt(int_nodes[4], int_nodes[7]))
    ans.balance.append(Belt(int_nodes[5], int_nodes[6]))
    ans.balance.append(Belt(int_nodes[5], int_nodes[7]))
    ans.balance.append(Belt(int_nodes[6], int_nodes[8]))
    ans.balance.append(Belt(int_nodes[6], int_nodes[9]))
    ans.balance.append(Belt(int_nodes[7], int_nodes[10]))
    ans.balance.append(Belt(int_nodes[7], int_nodes[11]))
    ans.balance.append(Belt(int_nodes[8], int_nodes[13]))
    ans.balance.append(Belt(int_nodes[9], int_nodes[12]))
    ans.balance.append(Belt(int_nodes[10], int_nodes[12]))
    ans.balance.append(Belt(int_nodes[11], int_nodes[13]))
    ans.balance.append(Belt(int_nodes[12], int_nodes[14]))
    ans.balance.append(Belt(int_nodes[12], int_nodes[15]))
    ans.balance.append(Belt(int_nodes[13], int_nodes[14]))
    ans.balance.append(Belt(int_nodes[13], int_nodes[15]))
    ans.balance.append(Belt(int_nodes[14], int_nodes[16]))
    ans.balance.append(Belt(int_nodes[15], int_nodes[16]))
    ans.balance.append(Belt(int_nodes[14], int_nodes[17]))
    ans.balance.append(Belt(int_nodes[15], int_nodes[17]))
    ans.balance.append(Belt(int_nodes[16], int_nodes[3]))
    ans.balance.append(Belt(int_nodes[16], int_nodes[1]))
    ans.balance.append(Belt(int_nodes[17], int_nodes[0]))
    ans.balance.append(Belt(int_nodes[17], int_nodes[2]))
    ans.balance.append(Belt(int_nodes[8], output_nodes[0], True))
    ans.balance.append(Belt(int_nodes[9], output_nodes[1], True))
    ans.balance.append(Belt(int_nodes[10], output_nodes[2], True))
    ans.balance.append(Belt(int_nodes[11], output_nodes[3], True))

    ans.postprocess_nodes()
    return ans