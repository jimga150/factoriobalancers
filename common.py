import logging
import sys

import z3


logger = logging.getLogger(__name__)


decimals_iter = 5
decimals_verif = decimals_iter-2

diff_threshold_iter = 10 ** (-decimals_iter)
diff_threshold_verif = 10 ** (-decimals_verif)

# print extremely verbose
debug = False

output_folder = "output"

# use quantized external variables
# when true, input supplies and output demands must be of the form N/ext_var_quant_denom
use_quant_ext_vars = False
ext_var_quant_denom = 4


def setup_logger(logger: logging.Logger):
    
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    if not logger.hasHandlers():
        logger.addHandler(logging.StreamHandler(sys.stdout))
        logger.addHandler(logging.FileHandler("main_out.txt", mode='w+'))
    
setup_logger(logger)

def term_str(name, frac: float) -> str:

    if name is None:
        name = ""

    if type(name) != str:
        name = str(name)

    if frac < diff_threshold_verif:
        return ""
    if frac == 1:
        return name if name != "" else "1"

    for numerator_candidate in range(1, 10):
        # print(f"numerator_candidate: {numerator_candidate}")
        denominator_candidate = int(numerator_candidate / frac + 0.5)
        # print(f"denominator_candidate: {denominator_candidate}")

        if denominator_candidate == 0:
            continue

        if 1.0/denominator_candidate < diff_threshold_verif * 100:
            # print(f"Denominator candidate too small")
            continue

        diff = abs(frac - numerator_candidate*1.0/denominator_candidate)
        # print(f"diff: {diff}; diff_threshold_verif: {diff_threshold_verif}")

        if diff < diff_threshold_verif:
            # print("fraction!")
            # other_diff = abs(numerator_candidate / frac - denominator_candidate)
            # print(f"diff the other way: {other_diff}")
            if numerator_candidate == denominator_candidate:
                return name if name != "" else "1"
            if name == "":
                return f"{numerator_candidate}/{denominator_candidate}" if denominator_candidate != 1 else f"{numerator_candidate}"
            if numerator_candidate == 1:
                num_str = name if name != "" else "1"
                return f"{num_str}/{denominator_candidate}" if denominator_candidate != 1 else f"{num_str}"
            return f"{numerator_candidate}{name}/{denominator_candidate}" if denominator_candidate != 1 else f"{numerator_candidate}{name}"

    # print("no fraction")
    frac_str = f"{frac:.{decimals_verif}f}"
    return f"{frac_str}*{name}" if name != "" else frac_str

def frac_str(frac: float) -> str:
    return term_str("", frac)

def z3realMin(a: z3.ArithRef, b: z3.ArithRef) -> z3.ArithRef:
    return z3.If(a < b, a, b)

def z3realMax(a: z3.ArithRef, b: z3.ArithRef) -> z3.ArithRef:
    return z3.If(a < b, b, a)

def z3RealBound(arg: z3.ArithRef, min: z3.ArithRef, max: z3.ArithRef) -> z3.ArithRef:
    return z3realMax(min, z3realMin(arg, max))

def nested_objs_eq(a, b, debug: bool = False) -> bool:

    if debug:
        print(f"nested_objs_eq called")
        print(f"a ({type(a)}) = {a}")
        print(f"b ({type(b)}) = {b}")

    if type(a) != type(b):
        if debug:
            print(f"{type(a)=} != {type(b)=}")
        return False

    if type(a) == dict:
        return dicts_eq(a, b, debug)

    if type(a) == list:
        return lists_eq(a, b, debug)

    return a == b

def dicts_eq(a: dict, b: dict, debug: bool = False) -> bool:
    if debug:
        print(f"dicts_eq called")
        print(f"a = {a}")
        print(f"b = {b}")

    if type(a) != type(b):
        if debug:
            print(f"{type(a)=} != {type(b)=}")
        return False

    if type(a) != dict:
        if debug:
            print(f"{type(a)=} != dict")
        return False

    for k, v in a.items():
        if k not in b:
            if debug:
                print(f"{k=} not in b")
            return False
        if not nested_objs_eq(v, b[k], debug):
            return False

    return True

def lists_eq(a: list, b: list, debug: bool = False) -> bool:
    if debug:
        print(f"lists_eq called")
        print(f"a = {a}")
        print(f"b = {b}")

    if type(a) != type(b):
        if debug:
            print(f"{type(a)=} != {type(b)=}")
        return False
    if type(a) != list:
        if debug:
            print(f"{type(a)=} != list")
        return False

    for ia, ib in zip(a, b):
        if type(ia) != type(ib):
            if debug:
                print(f"{type(ia)=} != {type(ib)=}")
            return False
        if not nested_objs_eq(ia, ib, debug):
            return False

    return True