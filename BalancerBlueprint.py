
import base64
import copy
import json
import sys
from itertools import chain
from typing import Optional

import zlib

import BluePrintRenderer
import common
import factorio_sat_callable as sat
from BPEntity import BPEntity, Direction, Rotation, IOType, BeltLevel
from BalancerNetwork import BalancerNetwork
from Belt import Belt
from Node import Node
from factorio_sat_callable.belt_balancer import NoSolutionsException

logger = common.setup_logger(__name__)

class BalancerBlueprint:

    def __init__(self):

        self.width = 0
        self.height = 0
        self.orientation = None
        self.beltlevel = None

        self.version = BPEntity.default_version
        self.description = None
        self.label = None
        self.icons = None

        self.network = None
        self.net_mapping = None

        self.entity_grid: list[list[BPEntity]] = []

    @staticmethod
    def from_bp_str(bp_str: str) -> BalancerBlueprint:
        ans = BalancerBlueprint()
        ans.parse_bp_dict(BalancerBlueprint.decode_blueprint_str(bp_str))
        return ans

    @staticmethod
    def from_entity_grid(entity_grid: list[list[BPEntity]]) -> BalancerBlueprint:
        ans = BalancerBlueprint()
        ans.entity_grid = copy.deepcopy(entity_grid)
        ans.enumerate()
        return ans

    @staticmethod
    def from_network(network: BalancerNetwork, bl: BeltLevel) -> BalancerBlueprint:
        if network.get_num_internal_nodes() > 6:
            raise RuntimeError(f"Too many nodes in network: {len(network.nodes)}")

        sat_net_str = network.export_to_sat_network()
        logger.debug(sat_net_str)

        max_io_cnt = max(network.get_num_inputs(), network.get_num_outputs())
        sat_bp_tuples = []

        for test_height in range(max_io_cnt, max_io_cnt+3):
            # bump height by one if width range doesnt work
            for test_width in range(max_io_cnt+1, 3*max_io_cnt):
                # but first try making it wide
                try:
                    sat_bp = sat.belt_balancer(
                        sat_net_str,
                        test_width,
                        test_height,
                        fast=True,
                        underground_length=bl.underground_length
                    )[0]
                    sat_bp_tuples.append((sat_bp, test_width, test_height))
                except NoSolutionsException:
                    pass

        if len(sat_bp_tuples) == 0:
            raise NoSolutionsException("No Solutions Found")

        sat_bp_tuples.sort(key=lambda x: x[1]*x[2])
        sat_bp = sat_bp_tuples[0][0]

        bp_str = sat.blueprint_encode(sat_bp, level=bl.name)[0]
        logger.info(bp_str)
        return BalancerBlueprint.from_bp_str(bp_str)

    @staticmethod
    def combine_sidebyside(sub_bp: BalancerBlueprint) -> BalancerBlueprint:
        # stamp down two right next to each other
        # use as partial solution for Factorio-SAT, solving for the complete network

        sub_bp.rotate_to(Direction.RIGHT)

        network, _ = sub_bp.get_network()

        logger.debug(f"Combining sidebyside: {network.get_num_inputs()}x{network.get_num_outputs()}")

        if common.debug:
            BluePrintRenderer.renderToFile(sub_bp, "sub_bp")
            network.render("sub_bp_network")

        desired_network = BalancerNetwork.combine_sidebyside(network)
        desired_sat_network = desired_network.export_to_sat_network()

        logger.debug(f"Sat: {desired_sat_network}")

        if common.debug:
            sat.network_render(desired_sat_network)

        new_width = sub_bp.width
        new_height = sub_bp.height * 2

        new_entity_grid = []
        for y in range(new_height):
            new_entity_grid.append([])
            for x in range(new_width):
                entity = sub_bp.entity_grid[y % sub_bp.height][x]
                new_entity_grid[-1].append(entity)

        partialbp = BalancerBlueprint.from_entity_grid(new_entity_grid)

        partial_str = partialbp.to_bp_str((0, partialbp.width - 2))

        partial_bp_name = f"sbs_partial"
        logger.debug(f"SBS: partial BP str rendering to {partial_bp_name}")
        if common.debug:
            to_render = BalancerBlueprint.from_bp_str(partial_str)
            BluePrintRenderer.renderToFile(to_render, partial_bp_name)

        sat_ans = []

        ichange_min_width = 4
        ichange_max_width = 10

        for interchange_width in range(ichange_min_width, ichange_max_width+1):
            try:
                sat_ans = sat.belt_balancer(
                    desired_sat_network,
                    partialbp.width + interchange_width,
                    ##im in
                    partialbp.height,
                    edge_splitters=True,
                    prevent_bad_patterns=True,
                    ungroup_ios=True,
                    underground_length=sub_bp.beltlevel.underground_length,
                    partial=partial_str
                )
                logger.debug(f"SBS: Solution Found for interchange width = {interchange_width}")
                break
            except NoSolutionsException:
                logger.debug(f"SBS: No Solutions Found for interchange width = {interchange_width}")

        if len(sat_ans) == 0:
            raise RuntimeError(f"SBS: No Solutions Found for interchange width <= {ichange_max_width}")

        ans_bp_str = sat.blueprint_encode(sat_ans, level=sub_bp.beltlevel.name)[0]

        ans = BalancerBlueprint.from_bp_str(ans_bp_str)

        return ans

    @staticmethod
    def combine_endtoend(upstream: BalancerBlueprint, downstream: Optional[BalancerBlueprint] = None) -> BalancerBlueprint:
        # stamp down one
        # stamp down the other downstream, separating until Factorio-SAT can connect them end to end

        # turn to face L->R
        upstream.rotate_to(Direction.RIGHT)

        if downstream is None:
            # we can't just reference shallowly, later network operations require these pointers be distinct
            downstream = copy.deepcopy(upstream)
        elif downstream != upstream:
            downstream.rotate_to(Direction.RIGHT)

        if common.debug:
            BluePrintRenderer.renderToFile(upstream, f"ce2e_upstream")
            BluePrintRenderer.renderToFile(downstream, f"ce2e_downstream")

        beltlevel = upstream.beltlevel
        if downstream.beltlevel > beltlevel:
            beltlevel = downstream.beltlevel

        u_net, u_map = upstream.get_network()
        d_net, d_map = downstream.get_network()

        desired_network = BalancerNetwork.combine_endtoend_inplace(
            u_net,
            d_net,
            optimize=False,
            upstream_net_map=u_map,
            downstream_net_map=d_map
        )

        if common.debug:
            desired_network.render("desired_network")

        desired_sat_network = desired_network.export_to_sat_network()

        if common.debug:
            sat.network_render(desired_sat_network, output_filename="desired_sat_network")

        # get downstream BP without input belts
        d_str = downstream.to_bp_str((1, downstream.width), (0, downstream.height))
        downstream = BalancerBlueprint.from_bp_str(d_str)

        # get upstream BP without output belts
        u_str = upstream.to_bp_str((0, upstream.width-2), (0, upstream.height))
        upstream = BalancerBlueprint.from_bp_str(u_str)

        new_height = max(upstream.height, downstream.height)

        max_inter_spacing = 7

        new_width = upstream.width + downstream.width + max_inter_spacing

        new_entity_grid_templ = []
        for y in range(new_height):
            new_entity_grid_templ.append([])
            for x in range(new_width):
                new_entity_grid_templ[-1].append(BPEntity())

        upstream_y_offset = (new_height - upstream.height) // 2
        upstream_x_offset = 0

        downstream_y_offset = (new_height - downstream.height) // 2

        sat_ans = []

        for inter_spacing in range(0, max_inter_spacing+1):
            downstream_x_offset = upstream.width + inter_spacing

            new_entity_grid = copy.deepcopy(new_entity_grid_templ)

            for y in range(upstream.height):
                for x in range(upstream.width):
                    new_entity_grid[y + upstream_y_offset][x + upstream_x_offset] = upstream.entity_grid[y][x]

            for y in range(downstream.height):
                for x in range(downstream.width):
                    new_entity_grid[y + downstream_y_offset][x + downstream_x_offset] = downstream.entity_grid[y][x]

            partialbp = BalancerBlueprint.from_entity_grid(new_entity_grid)
            partial_str = partialbp.to_bp_str()

            logger.debug(f"Trying inter-balancer spacing of {inter_spacing} (w={partialbp.width}, h={partialbp.height})")

            try:
                sat_ans = sat.belt_balancer(
                    desired_sat_network,
                    partialbp.width,
                    partialbp.height,
                    edge_splitters=True,
                    prevent_bad_patterns=True,
                    ungroup_ios=True,
                    underground_length=beltlevel.underground_length,
                    partial=partial_str
                )
                logger.debug(f"E2E: Solution found: interchange width = {inter_spacing}")
                break
            except NoSolutionsException:
                logger.debug(f"E2E: No Solutions Found for interchange width = {inter_spacing}")
                partial_bp_name = f"e2e_failed_partial_{inter_spacing}"
                logger.debug(f"partial BP str rendering to {partial_bp_name}")
                if common.debug:
                    to_render = BalancerBlueprint.from_bp_str(partial_str)
                    BluePrintRenderer.renderToFile(to_render, partial_bp_name)

        if len(sat_ans) == 0:
            raise RuntimeError(f"E2E: No solutions found for inter-balancer spacing <= {max_inter_spacing}")

        ans_bp_str = sat.blueprint_encode(sat_ans, level=beltlevel.name)[0]

        ans = BalancerBlueprint.from_bp_str(ans_bp_str)

        return ans

    def __str__(self):
        dir_graph = "Direction graph:\n"
        dir_graph += "-" * (self.width * 2 + 1)
        dir_graph += "\n"
        for y in range(self.height):
            dir_graph += "|"
            for x in range(self.width):
                curr_dir = self.entity_grid[y][x].direction
                if curr_dir == Direction.UP:
                    dir_graph += "^"
                elif curr_dir == Direction.DOWN:
                    dir_graph += "v"
                elif curr_dir == Direction.LEFT:
                    dir_graph += "<"
                elif curr_dir == Direction.RIGHT:
                    dir_graph += ">"
                else:
                    dir_graph += "0"
                dir_graph += "|"
            dir_graph += "\n"
            dir_graph += "-" * (self.width * 2 + 1)
            dir_graph += "\n"

        rot_graph = "Rotation graph:\n"
        rot_graph += "-" * (self.width * 2 + 1)
        rot_graph += "\n"
        for y in range(self.height):
            rot_graph += "|"
            for x in range(self.width):
                rot = self.entity_grid[y][x].bend
                if rot == Rotation.CW:
                    rot_graph += "1"
                elif rot == Rotation.CCW:
                    rot_graph += "2"
                else:
                    rot_graph += " "
                rot_graph += "|"
            rot_graph += "\n"
            rot_graph += "-"*(self.width*2 + 1)
            rot_graph += "\n"

        return dir_graph + "\n" + rot_graph + "\n"

    @staticmethod
    def decode_blueprint_str(string: str):
        leading_version_byte = string[0]
        if leading_version_byte != '0':
            raise RuntimeError('Invalid blueprint version')
        string = string[1:]
        compressed = base64.b64decode(string)
        raw_bytes = zlib.decompress(compressed)
        data = json.loads(raw_bytes)["blueprint"]

        # sort entities by number so that list comparison works
        data["entities"].sort(key=lambda x: int(x["entity_number"]))

        logger.debug(type(data))
        logger.debug(json.dumps(data, sort_keys=True, indent=4, ))
        logger.debug(f"Version: {hex(data["version"])}")

        return data

    def get_coord_in_direction(self, x: int | float, y: int | float, direction: Direction) -> tuple[int | float, int | float]:
        if direction == Direction.UP:
            if y == 0:
                raise ValueError
            return x, y - 1
        if direction == Direction.DOWN:
            if y == self.height-1:
                raise ValueError
            return x, y + 1
        if direction == Direction.RIGHT:
            if x == self.width-1:
                raise ValueError
            return x + 1, y
        if direction == Direction.LEFT:
            if x == 0:
                raise ValueError
            return x - 1, y
        raise RuntimeError('Invalid direction')

    def parse_bp_dict(self, blueprint: dict):

        self.version = int(blueprint["version"])

        self.icons = blueprint["icons"]
        self.label = blueprint["label"]

        if "description" in blueprint:
            self.description = blueprint["description"]

        entities = blueprint["entities"]

        min_x = min_y = sys.maxsize
        max_x = max_y = -sys.maxsize

        bp_entities = [BPEntity(self.version, x) for x in entities]

        for entity in bp_entities:
            min_x = min(min_x, entity.pos_x)
            min_y = min(min_y, entity.pos_y)
            max_x = max(max_x, entity.pos_x)
            max_y = max(max_y, entity.pos_y)

        self.height = round(max_y - min_y + 1)
        self.width = round(max_x - min_x + 1)

        self.entity_grid = []
        for _ in range(self.height):
            self.entity_grid.append([])
            for _ in range(self.width):
                self.entity_grid[-1].append(BPEntity())

        for entity in bp_entities:

            entity.pos_x -= min_x
            entity.pos_y -= min_y

            y, x = entity.pos

            self.entity_grid[y][x] = entity

            # account for splitters being 2 tiles, entity is only marked as southeast half
            if entity.is_splitter():

                # make copy of splitter entity at that coord
                splitter_cap_entity = copy.deepcopy(entity)

                if entity.direction.is_vertical():
                    self.entity_grid[y][x - 1] = splitter_cap_entity
                    splitter_cap_entity.pos_x = entity.pos_x - 1
                    splitter_cap_entity.pos_y = entity.pos_y
                else:
                    self.entity_grid[y - 1][x] = splitter_cap_entity
                    splitter_cap_entity.pos_x = entity.pos_x
                    splitter_cap_entity.pos_y = entity.pos_y - 1

                # set entities to point to each other
                splitter_cap_entity.splitter_sibling = entity
                entity.splitter_sibling = splitter_cap_entity

                splitter_cap_entity.is_phantom = True

        self.enumerate()

#  ROFL:ROFL:ROFL:ROFL
#          _^___
#  L    __/   [] \
# LOL===__        \
#  L      \________]
#          I   I
#         --------/

    def to_bp_dict(self, x_bounds: Optional[tuple[int, int]] = None, y_bounds: Optional[tuple[int, int]] = None) -> dict:
        bp_dict = {
            "entities": [],
            "version": self.version,
            "icons": self.icons,
            "item": "blueprint",
            "label": self.label,
        }

        if self.description:
            bp_dict["description"] = self.description

        if x_bounds is not None:
            min_x, max_x = x_bounds
        else:
            min_x, max_x = 0, self.width - 1

        if y_bounds is not None:
            min_y, max_y = y_bounds
        else:
            min_y, max_y = 0, self.height - 1

        for y in range(self.height):
            if not (min_y <= y <= max_y):
                continue
            for x in range(self.width):
                if not (min_x <= x <= max_x):
                    continue
                bp_entity = self.entity_grid[y][x]
                if bp_entity.is_real():
                    bp_dict["entities"].append(bp_entity.to_entity_dict())
        return {"blueprint": bp_dict}

    def to_bp_str(self, x_bounds: Optional[tuple[int, int]] = None, y_bounds: Optional[tuple[int, int]] = None) -> str:
        raw_bytes = json.dumps(self.to_bp_dict(x_bounds, y_bounds)).encode('utf-8')
        compressed = zlib.compress(raw_bytes, level=9)
        string = base64.b64encode(compressed).decode('utf-8')
        return '0' + string

    def entites_as_flat_list(self) -> list[BPEntity]:
        return list(chain.from_iterable(self.entity_grid))

    def get_network(self) -> tuple[BalancerNetwork, dict[BPEntity, Belt | Node]]:

        logger.debug(f"get_network called")

        if self.network is not None:
            logger.debug(f"returning existing network and mapping")
            return self.network, self.net_mapping

        logger.debug(f"making new existing network and mapping")

        # key is BPEntity
        # value is Belt or Node
        self.net_mapping = {}

        internal_nodes = {}

        # make nodes for each splitter
        for entity in self.entites_as_flat_list():
            if entity.is_splitter():
                internal_nodes[entity] = Node()
                self.net_mapping[entity] = internal_nodes[entity]
                logger.debug(f"Adding {entity} to internal_nodes")

        io_nodes = []

        self.network = BalancerNetwork()

        # iterate over all splitter entities:
        # for each output x direction:
        #   trace to destination in direction
        #   make belt, if belt not on list
        #   add belt to list

        belts_made = []

        for splitter_entity, node in internal_nodes.items():
            for reverse in [True, False]:
                for use_head in [True, False]:
                    # use_head: True when using true splitter entity, false when using splitter cap (nearly empty entity next to it)
                    start_entity = splitter_entity if use_head else splitter_entity.splitter_sibling
                    curr_entity = start_entity
                    logger.debug(f"Seeking from {splitter_entity} ({reverse=}, {use_head=}) (start_entity={start_entity})")
                    other_node = None
                    other_node_splitter_cap = False
                    belts_visited = []
                    while True:

                        last_entity = curr_entity

                        curr_entity = self.find_connected_entity(curr_entity, reverse)

                        if curr_entity.is_splitter_cap():
                            curr_entity = curr_entity.splitter_sibling
                            other_node_splitter_cap = True

                        if curr_entity.empty:
                            if last_entity.is_belt() or last_entity.is_underground():
                                # empty entity, found I/O belt
                                other_node = Node()
                                io_nodes.append(other_node)
                                self.net_mapping[last_entity] = other_node
                                belts_visited.remove(last_entity)
                                logger.debug(f"net_mapping[{last_entity}] = {other_node}")
                                connector_str = " <- " if reverse else " -> "
                                logger.debug(str(splitter_entity) + connector_str + f"I/O node @ ({last_entity.pos})")
                            else:
                                # splitter with nothing connecting to it is not an I/O
                                pass
                            break
                        elif curr_entity.is_splitter():
                            # found dest node
                            other_node = internal_nodes[curr_entity]
                            connector_str = " <- " if reverse else " -> "
                            logger.debug(str(splitter_entity) + connector_str + str(curr_entity))
                            break
                        elif not curr_entity.is_underground() and not curr_entity.is_belt():
                            raise RuntimeError(
                                "Belt in balancer faces an entity that is not a splitter, belt, or underground.")
                        else:
                            # visited belt/underground, track it
                            belts_visited.append(curr_entity)

                        logger.debug(f"\t{curr_entity}")

                    if other_node is None:
                        # no belt to be made
                        continue

                    # check priority of source and dest splitter

                    # remember if the belt connects to the other entity at a splitter cap,
                    # and use that to fetch its relevant priority
                    curr_entity_connect = curr_entity.splitter_sibling if other_node_splitter_cap else curr_entity
                    logger.debug(f"\t{curr_entity_connect=}")

                    if reverse:
                        source_priority = curr_entity_connect.has_priority(IOType.OUTPUT)
                        dest_priority = start_entity.has_priority(IOType.INPUT)
                    else:
                        source_priority = start_entity.has_priority(IOType.OUTPUT)
                        dest_priority = curr_entity_connect.has_priority(IOType.INPUT)

                    logger.debug(f"\t{source_priority=}, {dest_priority=}")

                    # get "key" for belt to avoid duplicating internal belts
                    if not curr_entity_connect.empty:
                        # other_node is from a splitter, so we need to check if we already connected these two positions
                        # this checks the positions, not the splitter head entity,
                        # so two belts between the same two splitters will still both be added this way
                        if reverse:
                            # seeking backwards, so starting node was actually dest
                            belt_key = (curr_entity_connect.pos_x, curr_entity_connect.pos_y, start_entity.pos_x, start_entity.pos_y)
                        else:
                            belt_key = (start_entity.pos_x, start_entity.pos_y, curr_entity_connect.pos_x, curr_entity_connect.pos_y)

                        logger.debug(f"Checking {belt_key}")

                        if belt_key in belts_made:
                            logger.debug(f"Belt already made")
                            continue

                        belts_made.append(belt_key)

                    # make belt
                    if reverse:
                        # seeking backwards, so starting node was actually dest
                        belt = Belt(other_node, node, source_priority, dest_priority)
                    else:
                        belt = Belt(node, other_node, source_priority, dest_priority)

                    logger.debug(f"New belt: {belt}")

                    self.network.belts.append(belt)

                    for visited_entity in belts_visited:
                        self.net_mapping[visited_entity] = belt
                        logger.debug(f"net_mapping[{visited_entity}] = {belt}")

        self.network.postprocess_nodes()
        return self.network, self.net_mapping

    def find_connected_entity(self, from_entity: BPEntity, reverse: bool = False) -> BPEntity:
        logger.debug(f"find_connected_entity called (from_entity={str(from_entity)}, {reverse=})")
        y, x = from_entity.pos
        if (from_entity.is_underground() and
                ((from_entity.type == IOType.OUTPUT and reverse) or
                 (from_entity.type == IOType.INPUT and not reverse))):
            # find the location of the corresponding underground
            candidate_x = x
            candidate_y = y
            dist_from_start = 0
            while True:
                try:
                    dir_to_try = Direction.reverse(from_entity.direction) if reverse else from_entity.direction
                    candidate_x, candidate_y = self.get_coord_in_direction(candidate_x, candidate_y,
                                                                           dir_to_try)
                    dist_from_start += 1
                    if dist_from_start > from_entity.get_underground_len() + 1:
                        raise ValueError
                except ValueError:
                    # out of bounds (or out of range), no partner
                    raise RuntimeError(f"Underground in balancer ({str(from_entity)}) has no corresponding underground")

                candidate_entity = self.entity_grid[candidate_y][candidate_x]

                if not candidate_entity.is_underground():
                    continue
                if candidate_entity.direction.is_perpendicular(from_entity.direction):
                    continue

                if Direction.reverse(candidate_entity.direction) == from_entity.direction:
                    raise RuntimeError(
                        f"Underground in balancer ({str(from_entity)}) has broken link--sees underground flowing in opposite direction")

                if candidate_entity.opening_dir() == from_entity.opening_dir():
                    raise RuntimeError(
                        f"Underground in balancer ({str(from_entity)}) has broken link--sees underground opening in the same direction")

                # found corresponding underground. exit
                x1 = candidate_x
                y1 = candidate_y
                break
        elif reverse:
            # not looking for an underground pair, just look for things pointing here
            dirs_to_try = [
                Direction.reverse(from_entity.direction),
                Direction.turn(from_entity.direction, Rotation.CW),
                Direction.turn(from_entity.direction, Rotation.CCW)
            ]

            if from_entity.is_underground() or from_entity.is_splitter() or from_entity.is_splitter_cap():
                # underground entrance or splitter, only relevant direction is backwards
                dirs_to_try = [
                    Direction.reverse(from_entity.direction)
                ]

            entities_pointing_here = []
            debug_str = f"\t({x}, {y}) -> "
            for dir_to_try in dirs_to_try:
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, dir_to_try)
                except ValueError:
                    # out of bounds, nothing here
                    continue

                candidate_entity = self.entity_grid[y1][x1]

                if (candidate_entity.direction == Direction.reverse(dir_to_try) and
                        not (candidate_entity.is_underground() and candidate_entity.type == IOType.INPUT)):
                    # this entity is pointing to from_entity (excluding undergrounds closing to this direction)
                    debug_str += f"({x1}, {y1})"
                    entities_pointing_here.append(candidate_entity)

            if len(entities_pointing_here) == 0:
                # nothing pointing here, return empty entity
                logger.debug(debug_str + "(None)")
                return BPEntity()

            if len(entities_pointing_here) == 1:
                # unambiguous
                logger.debug(debug_str)
                return entities_pointing_here[0]

            eph_str = "; ".join([str(x) for x in entities_pointing_here])

            # more than one entity points here, meaning lane shenanigans will be happening
            raise RuntimeError(f"Lane balancing techniques are being used for this balancer, "
                               f"which is currently unsupported. "
                               f"{eph_str}")

        else:
            # not looking for an underground pair, just find next belt
            try:
                x1, y1 = self.get_coord_in_direction(x, y, from_entity.direction)
            except ValueError:
                # out of bounds, return empty entity
                return BPEntity()

        logger.debug(f"\t({x}, {y}) -> ({x1}, {y1})")

        candidate_entity = self.entity_grid[y1][x1]

        if (candidate_entity.is_splitter() or candidate_entity.is_splitter_cap()) and candidate_entity.direction != from_entity.direction:
            if from_entity.is_underground() or from_entity.is_belt():
                raise RuntimeError(f"{str(from_entity)} points to the side of a splitter at {str(candidate_entity)}")

            # else, assumed to be splitter. return empty entity, which will be interpreted as "connects to nothing"
            return BPEntity()

        return candidate_entity

    def enumerate(self):

        # call after populating an entity grid

        # ensures unique entity instances
        # ensures unique entity numbers
        # recalculates height and width
        # sets version of self
        # ensures splitter siblings are linked
        # calculates orientation of baalncer
        # sets "bend" of belt entities to ensure correct rendering

        self.net_mapping = None
        self.version = None
        self.orientation = None

        max_x = max_y = 0

        e_num = 1
        entity_ids_seen = []
        for y in range(len(self.entity_grid)):
            for x in range(len(self.entity_grid[0])):

                entity: BPEntity = self.entity_grid[y][x]

                old_id = id(entity)

                if id(entity) in entity_ids_seen:
                    entity = copy.deepcopy(entity)
                    self.entity_grid[y][x] = entity
                entity_ids_seen.append(id(entity))

                new_id = id(entity)

                # assign positions to all entities
                entity.pos_x = x
                entity.pos_y = y

                if entity.empty:
                    # skip min/max X calcs and enumeration for empty entities
                    continue

                max_x = max(max_x, entity.pos_x)
                max_y = max(max_y, entity.pos_y)

                logger.debug(f"\t{entity} ({hex(old_id)[3:]}) -> ({hex(new_id)[3:]})")

                if entity.is_phantom:
                    # skip enumeration for splitter phantoms
                    continue

                entity.entity_number = e_num
                e_num += 1

                if self.version is None:
                    # pull the version of the blueprint from the first real entity
                    self.version = entity.version

        # reestablish splitter sibling links
        for y in range(len(self.entity_grid)):
            for x in range(len(self.entity_grid[0])):

                entity: BPEntity = self.entity_grid[y][x]

                if not entity.is_splitter():
                    continue

                # if entity.direction in [Direction.UP, Direction.RIGHT]:
                #     return Direction.RIGHT
                # else:
                #     return Direction.LEFT

                ss_x = entity.pos_x
                ss_y = entity.pos_y

                if entity.direction.is_vertical():
                    ss_x -= 1
                else:
                    ss_y -= 1

                ss_entity: BPEntity = self.entity_grid[ss_y][ss_x]

                entity.splitter_sibling = ss_entity
                ss_entity.splitter_sibling = entity

                logger.debug(f"\tRe-linked {entity} and {ss_entity}")

        self.width = max_x + 1
        self.height = max_y + 1

        # seek belts that can orient us (belts outputting to an edge)
        # also detect max belt level
        for y in range(len(self.entity_grid)):
            for x in range(len(self.entity_grid[0])):

                entity: BPEntity = self.entity_grid[y][x]

                if entity.empty:
                    continue

                if entity.is_belt() and self.orientation is None:
                    if y == 0 and entity.direction == Direction.UP:
                        self.orientation = Direction.UP
                    elif y == self.height - 1 and entity.direction == Direction.DOWN:
                        self.orientation = Direction.DOWN
                    elif x == self.width - 1 and entity.direction == Direction.RIGHT:
                        self.orientation = Direction.RIGHT
                    elif x == 0 and entity.direction == Direction.LEFT:
                        self.orientation = Direction.LEFT

                bl = entity.level
                if self.beltlevel is None or bl > self.beltlevel:
                    self.beltlevel = bl

        # find belts that should bend when rendered
        for y in range(self.height):
            for x in range(self.width):

                entity = self.entity_grid[y][x]

                if entity.empty:
                    continue

                if not entity.is_belt():
                    continue

                # set default
                entity.bend = Rotation.NONE

                b_dir = entity.direction

                connected_from_behind = False
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, Direction.reverse(b_dir))
                    candidate_entity = self.entity_grid[y1][x1]
                    if candidate_entity.is_underground():
                        if candidate_entity.opening_dir() != b_dir:
                            # closed end, ignore
                            raise ValueError
                    connected_from_behind = candidate_entity.direction == b_dir
                except ValueError:
                    pass
                except AttributeError:
                    pass

                if connected_from_behind:
                    # will never be bent
                    continue

                dir_cw = Direction.turn(b_dir, Rotation.CW)
                dir_ccw = Direction.turn(b_dir, Rotation.CCW)

                connected_from_left = False
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, dir_ccw)
                    candidate_entity = self.entity_grid[y1][x1]
                    if candidate_entity.is_underground():
                        if candidate_entity.opening_dir() != dir_cw:
                            # closed end, ignore
                            raise ValueError
                    connected_from_left = candidate_entity.direction == dir_cw
                except ValueError:
                    pass
                except AttributeError:
                    pass

                connected_from_right = False
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, dir_cw)
                    candidate_entity = self.entity_grid[y1][x1]
                    if candidate_entity.is_underground():
                        if candidate_entity.opening_dir() != dir_ccw:
                            # closed end, ignore
                            raise ValueError
                    connected_from_right = candidate_entity.direction == dir_ccw
                except ValueError:
                    pass
                except AttributeError:
                    pass

                if connected_from_left == connected_from_right:
                    # if both or neither, no bend
                    continue

                if connected_from_left:
                    # implies not connected from right so the input of the belt bends left (so it bends clockwise)
                    entity.bend = Rotation.CCW
                else:
                    # implies not connected from left so the input of the belt bends right (so it bends counterclockwise)
                    entity.bend = Rotation.CW

    def rotate(self, rot: Rotation):

        new_entity_grid = []

        for y in range(self.width):
            new_entity_grid.append([])
            for x in range(self.height):
                new_entity_grid[-1].append(BPEntity())

        for y in range(self.height):
            for x in range(self.width):
                entity = self.entity_grid[y][x]
                if not entity.is_splitter():
                    continue
                # swap splitter heads with phantoms, in specific situations
                if (rot == Rotation.CW and entity.direction.is_horizontal()) or \
                        (rot == Rotation.CCW and entity.direction.is_vertical()):
                    ss_y, ss_x = entity.splitter_sibling.pos
                    self.entity_grid[ss_y][ss_x] = entity
                    self.entity_grid[y][x] = entity.splitter_sibling
                    logger.debug(f"Swapped splitter head/phantom: "
                                 f"Head is {self.entity_grid[ss_y][ss_x]} now @ {ss_x}, {ss_y}; "
                                 f"Phantom is {self.entity_grid[y][x]} now @ {x}, {y}")

        for y in range(self.height):
            for x in range(self.width):
                entity = self.entity_grid[y][x]
                if entity.empty:
                    continue
                # rotate all entities in place
                entity.direction = Direction.turn(entity.direction, rot)

        for y in range(self.height):
            for x in range(self.width):

                entity = self.entity_grid[y][x]
                if entity.empty:
                    continue

                if rot == Rotation.CCW:
                    new_entity_grid[self.width-x-1][y] = entity
                else:
                    new_entity_grid[x][self.height-y-1] = entity

        self.entity_grid = new_entity_grid
        self.enumerate()

    def rotate_to(self, direction: Direction):

        test_dir = self.orientation
        num_cw_turns = 0
        while test_dir != direction:
            test_dir = Direction.turn(test_dir, Rotation.CW)
            num_cw_turns += 1

        test_dir = self.orientation
        num_ccw_turns = 0
        while test_dir != direction:
            test_dir = Direction.turn(test_dir, Rotation.CCW)
            num_ccw_turns += 1

        if num_cw_turns < num_ccw_turns:
            for i in range(num_cw_turns):
                self.rotate(Rotation.CW)
        else:
            for i in range(num_ccw_turns):
                self.rotate(Rotation.CCW)

    def loopback_ios(self, num_ios: int):

        assert num_ios >= 0

        if num_ios == 0:
            return

        if num_ios > 1:
            for i in range(num_ios):
                self.loopback_ios(1)
            return

        self.rotate_to(Direction.RIGHT)

        # 1. ensure there is space on the bottom side for a loopback

        #   a. check if all tiles on bottom row are empty
        bot_row_empty = True
        for x in range(self.width):
            if not self.entity_grid[self.height-1][x].empty:
                bot_row_empty = False
                break

        #   b. if not, add a row at the bottom
        if not bot_row_empty:
            self.entity_grid.append([])
            for x in range(self.width):
                self.entity_grid[-1].append(BPEntity())

            # need to place a belt in this new row so that future calls to enumerate wont ignore it and cut the height down
            self.height += 1

            dummy_belt = None
            for y in range(self.height):
                for x in range(self.width):
                    entity = self.entity_grid[y][x]
                    if entity.is_belt():
                        dummy_belt = entity
                        break
            self.entity_grid[self.height-1][self.width // 2] = dummy_belt

            # no need to fully enumerate, save a bit of time


        # 2. find bottommost input
        bot_inp_x = 0
        bot_inp_y = None
        for y in range(self.height-1, -1, -1):
            # bottom to top
            entity = self.entity_grid[y][0]
            if entity.is_input(self.width, self.height):
                bot_inp_y = y
                break

        # 3. ensure there is space below the input for a loopback

        #   a. check if all tiles on input column below the input are empty
        below_input_empty = True
        for y in range(bot_inp_y+1, self.height):
            if not self.entity_grid[y][0].empty:
                below_input_empty = False
                break

        #   b. if not, add a new column before the input, and extend all inputs to the new column
        if not below_input_empty:
            for y in range(self.height):
                input_was_here = self.entity_grid[y][0].is_input(self.width, self.height)
                self.entity_grid[y].insert(0, BPEntity())
                if input_was_here:
                    self.entity_grid[y][0] = self.entity_grid[y][1]

            self.enumerate()

        # 4. find bottommost output
        bot_out_x = self.width-1
        bot_out_y = None
        for y in range(self.height - 1, -1, -1):
            # bottom to top
            logger.info(f"checking entity at ({self.width-1}, {y})")
            entity = self.entity_grid[y][self.width-1]
            if entity.is_output(self.width, self.height):
                bot_out_y = y
                break

        # 5. ensure there is space below the output for a loopback

        #   a. check if all tiles on output column below the output are empty
        below_output_empty = True
        for y in range(bot_out_y+1, self.height):
            if not self.entity_grid[y][self.width-1].empty:
                below_output_empty = False
                break

        #   b. if not, add a new column after the output, and extend all outputs to the new column (update bottommost output ref)
        if not below_output_empty:
            for y in range(self.height):
                output_was_here = self.entity_grid[y][self.width-1].is_output(self.width, self.height)
                self.entity_grid[y].append(BPEntity())
                if output_was_here:
                    self.entity_grid[y][-1] = self.entity_grid[y][self.width-1]

            self.enumerate()
            bot_out_x += 1

        # 6. turn output from 4. south
        bot_out = self.entity_grid[bot_out_y][bot_out_x]
        bot_out.direction = Direction.DOWN

        # 7. add belts to complete loopback path

        #   a. south to (one before) bottom
        for y in range(bot_out_y+1, self.height-1):
            self.entity_grid[y][self.width-1] = bot_out

        #   b. west to (one before) input column
        reverse_belt = copy.deepcopy(bot_out)
        reverse_belt.direction = Direction.LEFT

        for x in range(1, self.width):
            self.entity_grid[self.height-1][x] = reverse_belt

        up_belt = copy.deepcopy(bot_out)
        up_belt.direction = Direction.UP

        #   c. up to (one before) input
        for y in range(bot_inp_y+1, self.height):
            self.entity_grid[y][0] = up_belt

        # 8. enumerate
        self.enumerate()