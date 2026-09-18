from io import TextIOWrapper
from types import NoneType

from factorio_sat.interchange import *

# finds an interchange for building composite balancers
# returns a list of strings
# each string representing a tile grid solution
# use blueprint to parse these strings into factorio blueprints
def interchange(
        width: int,
        height: int,
        underground_length: int = 4,
        alternating: bool = False,
        rot_symmetry: bool = False,
        all: bool = False,
        solver: str = "Glucose3",
        partial: TextIOWrapper | NoneType = None,
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
        if not all:
            break

    if len(ans) == 0:
        raise RuntimeError('No solution found')

    return ans


if __name__ == '__main__':
    main()