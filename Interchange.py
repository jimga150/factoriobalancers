from io import TextIOWrapper
from types import NoneType

import factorio_sat.blueprint
from factorio_sat.interchange import *
from factorio_sat.solver import Grid
from factorio_sat.util import set_number, set_numbers

def custom_interchange(
        height: int,
        width: int,
        underground_length: int = 4,
        alternating: bool = False,
        rot_symmetry: bool = False,
        partial: TextIOWrapper | NoneType = None,
        solver: str = "Glucose3",
        gen_all: bool = False,
) -> list[str]:
    if height < 1:
        raise RuntimeError('Height not positive')

    if height % 2 == 1:
        raise RuntimeError('Height not multiple of 2')

    grid = Grid(width, height, 2, underground_length)

    # No splitters
    for tile in grid.iterate_tiles():
        grid.clauses.append([-tile.is_splitter])

    for y in range(0, grid.height):
        grid.clauses.append([grid.get_tile_instance(0, y).input_direction[0]])
        grid.clauses.append([grid.get_tile_instance(grid.width - 1, y).output_direction[0]])

    for y in range(0, grid.height // 2):
        grid.set_colour(0, y, 0)
    for y in range(grid.height // 2, grid.height):
        grid.set_colour(0, y, 1)

    if alternating:
        for y in range(grid.height):
            tile = grid.get_tile_instance(grid.width - 1, y)
            grid.clauses += set_number(y % 2, tile.colour)
    else:
        for y in range(0, grid.height, 2):
            tile0 = grid.get_tile_instance(grid.width - 1, y)
            tile1 = grid.get_tile_instance(grid.width - 1, y + 1)
            grid.clauses += set_numbers(0, 1, tile0.colour, tile1.colour)

    grid.block_underground_through_edges()
    grid.block_belts_through_edges((False, True))

    grid.prevent_bad_undergrounding()
    grid.prevent_bad_colouring()

    grid.prevent_intersection()
    grid.enforce_maximum_underground_length()

    if rot_symmetry:
        require_rotational_symmetry(grid)
        optimisations.expand_underground(grid)
        optimisations.prevent_small_loops(grid)
        optimisations.prevent_empty_along_underground(grid)
        optimisations.prevent_belt_hooks(grid)
        optimisations.prevent_mergeable_underground(grid)
        optimisations.prevent_semicircles(grid)
        optimisations.prevent_underground_hook(grid)
    else:
        optimisations.apply_generic_optimisations(grid)

    prevent_passing(grid)

    prevent_awkward_underground_entry(grid)
    require_correct_transport_through_edges(grid)

    if partial is not None:
        with partial:
            belt_balancer.set_nonempty_tiles(grid, partial.read())

    ans = []

    for solution in grid.itersolve(solver=solver, ignore_colour=True):
        ans.append(json.dumps(solution.tolist()))
        if not gen_all:
            break

    return ans


def make_interchange_bp_str(width: int, height: int, belt_level: str = "normal") -> str:
    bl = factorio_sat.blueprint.TransportBeltLevel.NORMAL
    underground_len = 4

    if belt_level == "turbo":
        raise NotImplemented
    elif belt_level == "express":
        underground_len = 8
        bl = factorio_sat.blueprint.TransportBeltLevel.EXPRESS
    elif belt_level == "fast":
        underground_len = 6
        bl = factorio_sat.blueprint.TransportBeltLevel.FAST

    interchange_sat_dict_strs = custom_interchange(height, width, alternating=True, underground_length=underground_len)

    if len(interchange_sat_dict_strs) == 0:
        raise RuntimeError('No interchange')

    interchange_sat_dict_str = interchange_sat_dict_strs[0]

    tiles = np.array(json.loads(interchange_sat_dict_str))
    tiles = np.vectorize(factorio_sat.blueprint.read_tile)(tiles)

    sat_bp = factorio_sat.blueprint.make_blueprint(tiles, f"interchange {width}x{height}", bl)
    bp_str = factorio_sat.blueprint.encode_blueprint(sat_bp)

    return bp_str