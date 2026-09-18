from io import TextIOWrapper
from types import NoneType

from factorio_sat.belt_balancer import *

def parse_network_str(net_str: str) -> list[tuple[int, int]]:
    network = []
    for line in net_str.splitlines():
        line = line.strip()
        if len(line) == 0:
            continue

        if line.startswith('#'):
            continue

        colours = [int(colour) for colour in line.split()]

        for i, colour in enumerate(colours):
            if colour == -1:
                colours[i] = None

        if len(colours) != 4:
            raise ValueError('Invalid network string')
        network.append((tuple(colours[:2]), tuple(colours[2:])))
    return network

def belt_balancer(
        network: str | TextIOWrapper,
        width: int,
        height: int,
        turn_90: bool = False,
        turn_180: bool = False,
        custom: bool = False,
        edge_splitters: bool = False,
        edge_belts: bool = False,
        glue_splitters: bool = False,
        expand_underground: bool = False,
        prevent_mergeable_underground: bool = False,
        prevent_bad_patterns: bool = False,
        break_symmetry: bool = False,
        use_ends: bool = False,
        fast: bool = False,
        aligned: bool = False,
        underground_length: int = 4,
        all: bool = False,
        solver: str = 'Glucose3',
        partial: TextIOWrapper | NoneType = None,
) -> list[str]:

    if underground_length == -1:
        underground_length = float('inf')

    if edge_splitters and edge_belts:
        raise RuntimeError('--edge-splitters and --edge-belts are mutually exclusive')

    if sum([aligned, turn_90, turn_180, custom]) >= 2:
        raise RuntimeError('--aligned, --90, --180 and --custom are mutually exclusive')

    if break_symmetry and turn_90:
        raise RuntimeError('--break-symmetry and --90 are mutually exclusive')

    if isinstance(network, str):
        network = parse_network_str(network)
    else:
        network = open_network(network)
        network.close()

    network = deduplicate_network(network)

    grid = create_balancer(network, width, height, underground_length)
    grid.prevent_intersection()

    if edge_splitters or fast:
        enforce_edge_splitters(grid, network)
    if edge_belts:
        prevent_double_edge_belts(grid)
    if glue_splitters or fast:
        optimisations.glue_splitters(grid)
        optimisations.glue_partial_splitters(grid)
    if expand_underground or fast:
        optimisations.expand_underground(grid, min_x=1, max_x=grid.width - 2)
    if prevent_mergeable_underground or fast:
        optimisations.prevent_mergeable_underground(grid)
    if break_symmetry:
        optimisations.break_vertical_symmetry(grid)
    if prevent_bad_patterns or fast:
        optimisations.prevent_belt_hooks(grid)
        optimisations.prevent_semicircles(grid)
        optimisations.prevent_small_loops(grid)
        optimisations.prevent_underground_hook(grid)
        optimisations.prevent_zigzags(grid)
        optimisations.prevent_belt_parallel_splitter(grid)

    grid.enforce_maximum_underground_length()
    optimisations.prevent_empty_along_underground(grid)

    if partial is not None:
        with partial:
            set_nonempty_tiles(grid, partial.read())

    if turn_90:
        setup_balancer_ends_90(grid, network, use_ends)
    elif turn_180:
        setup_balancer_ends_180(grid, network)
    elif custom:
        pass
    else:
        setup_balancer_ends(grid, network, aligned, use_ends)

    ans = []

    for solution in grid.itersolve(solver=solver, ignore_colour=True):
        ans.append(json.dumps(solution.tolist()))
        if not all:
            break

    if len(ans) == 0:
        raise RuntimeError('No solutions found')

    return ans

if __name__ == '__main__':
    main()