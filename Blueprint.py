
import base64
import json
import sys

import zlib
from itertools import chain

from BPEntity import *
from Balancer import Balancer
from Belt import Belt
from Node import Node


class Blueprint:

    def __init__(self, bp_str: str):

        self.max_y = None
        self.min_y = None
        self.min_x = None
        self.max_x = None
        self.width = None
        self.height = None

        self.version = None
        self.description = None
        self.label = None
        self.icons = None

        self.bp_dict = Blueprint.decode_blueprint_str(bp_str)
        self.entity_grid = []
        self.parse_bp_dict(self.bp_dict)

        return

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
        print(dir_graph)

        rot_graph = "Rotation graph:\n"
        rot_graph += "-" * (self.width * 2 + 1)
        rot_graph += "\n"
        for y in range(self.height):
            rot_graph += "|"
            for x in range(self.width):
                rot = self.bends[y][x]
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
        print(rot_graph)

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

        # print(type(data))
        print(json.dumps(data, sort_keys=True, indent=4, ))
        print(f"Version: {hex(data["version"])}")
        # print("keys:")
        # for key, value in data.items():
        #     print(f"{key}: {value}")
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

    def get_entity_idxs(self, entity: BPEntity) -> tuple[int, int]:
        if entity.is_splitter_cap():
            entity = entity.splitter_sibling
        y = int(entity.pos_y - self.min_y + 0.5)
        x = int(entity.pos_x - self.min_x + 0.5)
        return y, x

    def parse_bp_dict(self, blueprint: dict):

        self.version = int(blueprint["version"])

        self.icons = blueprint["icons"]
        self.label = blueprint["label"]

        if "description" in blueprint:
            self.description = blueprint["description"]

        entities = blueprint["entities"]

        self.max_x = -sys.maxsize - 1
        self.min_x = sys.maxsize
        self.min_y = self.min_x
        self.max_y = self.max_x

        bp_entities = [BPEntity(self.version, x) for x in entities]

        for entity in bp_entities:
            self.min_x = min(self.min_x, entity.pos_x)
            self.min_y = min(self.min_y, entity.pos_y)
            self.max_x = max(self.max_x, entity.pos_x)
            self.max_y = max(self.max_y, entity.pos_y)

        self.width = int(self.max_x - self.min_x + 1 + 0.5)
        self.height = int(self.max_y - self.min_y + 1 + 0.5)

        for _ in range(self.height):
            self.entity_grid.append([])
            for _ in range(self.width):
                self.entity_grid[-1].append(BPEntity())

        # print(f"{len(self.tiles)=}, {len(self.tiles[0])=}")

        for entity in bp_entities:

            y, x = self.get_entity_idxs(entity)

            self.entity_grid[y][x] = entity

            # account for splitters being 2 tiles, entity is only marked as southeast half
            if entity.is_splitter():

                if entity.direction in [Direction.UP, Direction.DOWN]:
                    splitter_cap_entity = self.entity_grid[y][x - 1]
                else:
                    splitter_cap_entity = self.entity_grid[y - 1][x]

                # populate direction of empty entity next to splitter
                splitter_cap_entity.direction = entity.direction

                # set entities to point to each other
                splitter_cap_entity.splitter_sibling = entity
                entity.splitter_sibling = splitter_cap_entity

        # find belts that should bend when rendered
        for y in range(self.height):
            for x in range(self.width):

                entity = self.entity_grid[y][x]

                if entity.empty:
                    continue

                if not entity.is_belt():
                    continue

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

    def to_bp_dict(self) -> dict:
        bp_dict = {
            "entities": [],
            "version": self.version,
            "icons": self.icons,
            "item": "blueprint",
            "label": self.label,
        }

        if self.description:
            bp_dict["description"] = self.description

        for y in range(self.height):
            for x in range(self.width):
                bp_entity = self.entity_grid[y][x]
                if bp_entity.empty:
                    continue
                bp_dict["entities"].append(bp_entity.to_entity_dict())
        return {"blueprint": bp_dict}

    def to_bp_str(self) -> str:
        raw_bytes = json.dumps(self.to_bp_dict()).encode('utf-8')
        compressed = zlib.compress(raw_bytes, level=9)
        string = base64.b64encode(compressed).decode('utf-8')
        return '0' + string

    def entites_as_flat_list(self) -> list[BPEntity]:
        return list(chain.from_iterable(self.entity_grid))

    def get_network(self):

        internal_nodes = {}

        # make nodes for each splitter
        for entity in self.entites_as_flat_list():
            if entity.is_splitter():
                internal_nodes[entity] = Node()

        print(internal_nodes)

        io_nodes = []

        ans = Balancer()

        # iterate over all splitter entities:
        # for each output x direction:
        #   trace to destination in direction
        #   make belt, if belt not on list
        #   add belt to list

        for splitter_entity, node in internal_nodes.items():
            for reverse in [True, False]:
                for use_head in [True, False]:
                    # use_head: True when using true splitter entity, false when using splitter cap (nearly empty entity next to it)
                    curr_entity = splitter_entity if use_head else splitter_entity.splitter_sibling
                    other_node = None
                    while True:

                        last_entity = curr_entity

                        # did we start at a belt this iteration
                        from_belt = curr_entity.is_belt() or curr_entity.is_underground()

                        curr_entity = self.find_connected_entity(curr_entity, reverse)

                        if curr_entity.is_splitter_cap():
                            # found dest node, need to fetch "true" splitter entity
                            other_node = internal_nodes[curr_entity.splitter_sibling]
                            break

                        if curr_entity.empty:
                            if from_belt:
                                # empty entity, found I/O belt
                                other_node = Node()
                                io_nodes.append(other_node)
                                print(f"I/O node @ ({self.get_entity_idxs(last_entity)})")
                            else:
                                # splitter with nothing connecting to it is not an I/O
                                pass
                            break

                        if curr_entity.is_splitter():
                            # found dest node
                            other_node = internal_nodes[curr_entity]
                            break

                        if not curr_entity.is_underground() and not curr_entity.is_belt():
                            raise RuntimeError(
                                "Belt in balancer faces an entity that is not a splitter, belt, or underground.")

                    if other_node is None:
                        # no belt to be made
                        continue

                    if reverse:
                        # seeking backwards, so starting node was actually dest
                        belt = Belt(other_node, node)
                    else:
                        belt = Belt(node, other_node)

                    # we will have duplicates (for belts that aren't I/O) but that's OK
                    ans.belts.append(belt)

        ans.postprocess_nodes()
        return ans

    def find_connected_entity(self, from_entity: BPEntity, reverse: bool = False) -> BPEntity:
        # print(f"find_connected_entity called (from_entity={str(from_entity)}, {reverse=})")
        y, x = self.get_entity_idxs(from_entity)
        if (from_entity.is_underground() and
                ((from_entity.type == IOType.OUTPUT and reverse) or
                 (from_entity.type == IOType.INPUT and not reverse))):
            # find the location of the corresponding underground
            candidate_x = x
            candidate_y = y
            while True:
                try:
                    dir_to_try = Direction.reverse(from_entity.direction) if reverse else from_entity.direction
                    candidate_x, candidate_y = self.get_coord_in_direction(candidate_x, candidate_y,
                                                                           dir_to_try)
                except ValueError:
                    # out of bounds, no partner
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

            if from_entity.is_underground() or from_entity.is_splitter():
                # underground entrance or splitter, only relevant direction is backwards
                dirs_to_try = [
                    Direction.reverse(from_entity.direction)
                ]

            entities_pointing_here = []
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
                    entities_pointing_here.append(candidate_entity)

            if len(entities_pointing_here) == 0:
                # nothing pointing here, return empty entity
                return BPEntity()

            if len(entities_pointing_here) == 1:
                # unambiguous
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

        return self.entity_grid[y1][x1]