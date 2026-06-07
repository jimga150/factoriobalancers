decimals_iter = 5
decimals_verif = decimals_iter-2

diff_threshold_iter = 10 ** (-decimals_iter)
diff_threshold_verif = 10 ** (-decimals_verif)

debug = False

def debug_print(*args, **kwargs):
    if debug:
        print(*args, **kwargs)