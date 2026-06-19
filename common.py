decimals_iter = 5
decimals_verif = decimals_iter-2

diff_threshold_iter = 10 ** (-decimals_iter)
diff_threshold_verif = 10 ** (-decimals_verif)

# print extremely verbose iteration updates
debug = False

# Limit each iteration to one splitter update and render network on each iteration.
# This is liable to generate hundreds of MBs of images for each balancer calculation.
deep_iteration_debug = False

max_iters = 100

def debug_print(*args, **kwargs):
    if debug:
        print(*args, **kwargs)

def term_str(name, frac: float) -> str:

    if name is None:
        name = ""

    if type(name) != str:
        name = str(name)

    if frac < diff_threshold_verif:
        return ""
    if frac == 1:
        return str(name) if name != "" else "1"

    for numerator_candidate in range(1, 10):
        # print(f"numerator_candidate: {numerator_candidate}")
        denominator_candidate = int(numerator_candidate / frac + 0.5)
        # print(f"denominator_candidate: {denominator_candidate}")

        if denominator_candidate == 0 or denominator_candidate == numerator_candidate:
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
            if name == "":
                return f"{numerator_candidate}/{denominator_candidate}"
            if numerator_candidate == 1:
                return f"{name}/{denominator_candidate}"
            return f"{numerator_candidate}{name}/{denominator_candidate}"

    # print("no fraction")
    frac_str = f"{frac:.{decimals_verif}f}"
    return f"{frac_str}*{name}" if name != "" else frac_str

def frac_str(frac: float) -> str:
    return term_str("", frac)