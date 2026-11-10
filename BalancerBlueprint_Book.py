import BalancerNetwork_Book
import common
from BPEntity import BeltLevel, BLExpress
from BalancerBlueprint import BalancerBlueprint

logger = common.setup_logger(__name__)

def make_NxN(num_ios: int, level: BeltLevel = BLExpress) -> BalancerBlueprint:
    if num_ios < 5:
        return BalancerBlueprint.from_network(BalancerNetwork_Book.make_NxN(num_ios), level)

    # find the lowest even number A that is greater than or equal to num_ios
    # Make an AxA balancer, use that as a baseline
    # this will consist of two A/2 size balancers combined side by side
    A = num_ios
    if num_ios % 2:
        A += 1

    ans = make_NxN(int(A / 2))

    ans = BalancerBlueprint.combine_sidebyside(ans)

    # loopback remaining I/Os
    ans.loopback_ios(A - num_ios)

    return ans
