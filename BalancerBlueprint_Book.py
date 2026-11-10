import BalancerNetwork_Book
import common
from BPEntity import BeltLevel, BLExpress, BPEntity, Direction
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

def make_1x1(version: int, level: BeltLevel = BLExpress) -> BalancerBlueprint:

    belt_dict = {
        "direction": Direction.RIGHT.to_int(version),
        "entity_number": 1,
        "name": f"{level.prefix()}transport-belt",
        "position": {
            "x": 0.5,
            "y": 0.5
        }
    }

    belt_entity = BPEntity(version=version, entity=belt_dict)

    entity_grid = [[belt_entity, belt_entity]]

    return BalancerBlueprint.from_entity_grid(entity_grid)