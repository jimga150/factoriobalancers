
import base64
import copy
import enum
import json
import sys

import zlib
from itertools import chain

from Balancer import Balancer
from Belt import Belt
from Node import Node


class Rotation(enum.Enum):
    NONE = -1
    CW = 0
    CCW = 1


class Direction(enum.Enum):
    NONE = -1
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3

    @staticmethod
    def reverse(arg: Direction):
        if arg == Direction.UP:
            return Direction.DOWN
        elif arg == Direction.DOWN:
            return Direction.UP
        elif arg == Direction.RIGHT:
            return Direction.LEFT
        elif arg == Direction.LEFT:
            return Direction.RIGHT
        raise RuntimeError('Invalid direction')

    @staticmethod
    def turn(direc: Direction, rot: Rotation):
        if direc == Direction.UP:
            return Direction.RIGHT if rot == Rotation.CW else Direction.LEFT
        elif direc == Direction.DOWN:
            return Direction.LEFT if rot == Rotation.CW else Direction.RIGHT
        elif direc == Direction.RIGHT:
            return Direction.DOWN if rot == Rotation.CW else Direction.UP
        elif direc == Direction.LEFT:
            return Direction.UP if rot == Rotation.CW else Direction.DOWN
        raise RuntimeError('Invalid direction')

    def is_vertical(self) -> bool:
        return self in [Direction.UP, Direction.DOWN]

    def is_horizontal(self) -> bool:
        return self in [Direction.LEFT, Direction.RIGHT]

    def is_perpendicular(self, other: Direction) -> bool:
        return self.is_vertical() != other.is_vertical()

class IOType(enum.Enum):
    NONE = -1
    INPUT = 0
    OUTPUT = 1

    @staticmethod
    def from_type(bp_str: str):
        if bp_str == "input":
            return IOType.INPUT
        elif bp_str == "output":
            return IOType.OUTPUT
        return IOType.NONE

    def __str__(self):
        if self == IOType.INPUT:
            return "input"
        if self == IOType.OUTPUT:
            return "output"
        return "none"

major_version_offset_bits = 6*8

class BPEntity:
    entity_keys_to_ensure = {
        "direction": 0,
    }

    NAME_SPLITTER = "splitter"
    NAME_BELT = "transport-belt"
    NAME_UNDERGROUND = "underground-belt"

    def __init__(self, version: int = 1, entity: dict | None = None):

        self.empty = entity is None

        # set to BPEntity of splitter on other tile when this is part of a pair
        self.splitter_sibling = None

        self.direction = Direction.NONE

        if self.empty:
            # dont bother setting other attributes
            return

        for k, dv in self.entity_keys_to_ensure.items():
            try:
                x = entity[k]
            except KeyError:
                entity[k] = dv

        self.name = entity["name"]
        self.version = version
        self.entity_number = entity["entity_number"]

        divisor = 2 if self.version >> major_version_offset_bits == 1 else 4
        self.direction = Direction(int(entity["direction"]) / divisor)

        try:
            self.type = IOType.from_type(entity["type"])
        except KeyError:
            self.type = IOType.NONE

        self.pos_x = float(entity["position"]["x"])
        self.pos_y = float(entity["position"]["y"])

        # cast to ints if they can be accurately, since blueprint comparison will read round numbers as ints
        if self.pos_x.is_integer():
            self.pos_x = int(round(self.pos_x))

        if self.pos_y.is_integer():
            self.pos_y = int(round(self.pos_y))

        # to be filled in later
        self.bend = Rotation.NONE

    def __str__(self):
        return f"{self.name} @ ({self.pos_x}, {self.pos_y})"

    def __eq__(self, other):
        return self.entity_number == other.entity_number

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.entity_number)

    def to_entity_dict(self) -> dict:

        if self.empty:
            raise ValueError("This BPEntity is empty")

        ans = {"name": self.name}

        mul = 2 if self.version >> major_version_offset_bits == 1 else 4
        ans["direction"] = int(self.direction.value) * mul

        if self.type != IOType.NONE:
            ans["type"] = str(self.type)

        # # most entities define "center" as the center of the single tile
        # x_center = self.pos_x + 0.5
        # y_center = self.pos_y + 0.5
        #
        # # splitters place the center on the line between the halves
        # if BPEntity.NAME_SPLITTER in self.name:
        #     if self.direction in [Direction.UP, Direction.DOWN]:
        #         x_center = self.pos_x
        #     else:
        #         y_center = self.pos_y

        ans["position"] = {"x": self.pos_x, "y": self.pos_y}

        ans["entity_number"] = self.entity_number

        return ans

    def is_belt(self) -> bool:
        if self.empty:
            return False
        return BPEntity.NAME_BELT in self.name

    def is_splitter(self) -> bool:
        if self.empty:
            return False
        return BPEntity.NAME_SPLITTER in self.name

    def is_splitter_cap(self) -> bool:
        return self.empty and self.splitter_sibling is not None

    def is_underground(self) -> bool:
        if self.empty:
            return False
        return BPEntity.NAME_UNDERGROUND in self.name

class Blueprint:

    belt_prefixes = ["fast", "express", "turbo"]

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
                        opening_dir = candidate_entity.direction \
                            if candidate_entity.type == IOType.OUTPUT \
                            else Direction.reverse(candidate_entity.direction)
                        if opening_dir != b_dir:
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
                        opening_dir = candidate_entity.direction \
                            if candidate_entity.type == IOType.OUTPUT \
                            else Direction.reverse(candidate_entity.direction)
                        if opening_dir != dir_cw:
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
                        opening_dir = candidate_entity.direction \
                            if candidate_entity.type == IOType.OUTPUT \
                            else Direction.reverse(candidate_entity.direction)
                        if opening_dir != dir_ccw:
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
                internal_nodes[self.get_entity_idxs(entity)] = Node()

        print(internal_nodes)

        io_nodes = []

        belts_explored = []
        for _ in range(self.height):
            belts_explored.append([])
            for _ in range(self.width):
                belts_explored[-1].append(False)

        ans = Balancer()

        for y in range(self.height):
            for x in range(self.width):
                entity = self.entity_grid[y][x]
                if not entity.is_belt() and not entity.is_underground():
                    continue

                # if belt/underground already seen as part of a Belt object
                if belts_explored[y][x]:
                    continue

                # trace path forwards to find dest node
                curr_entity = entity
                while True:

                    y, x = self.get_entity_idxs(curr_entity)

                    belts_explored[y][x] = True
                    curr_entity = self.find_connected_entity(curr_entity)

                    if curr_entity.is_splitter_cap():
                        # found dest node
                        dest_node = internal_nodes[self.get_entity_idxs(curr_entity.splitter_sibling)]
                        break

                    if curr_entity.empty:
                        # empty entity, found output belt
                        dest_node = Node()
                        io_nodes.append(dest_node)
                        break

                    if curr_entity.is_splitter():
                        # found dest node
                        dest_node = internal_nodes[self.get_entity_idxs(curr_entity)]
                        break

                    if not curr_entity.is_underground() and not curr_entity.is_belt():
                        raise RuntimeError("Belt in balancer faces an entity that is not a splitter, belt, or underground.")

                # trace path backwards to find src node
                curr_entity = entity
                while True:

                    y, x = self.get_entity_idxs(curr_entity)

                    belts_explored[y][x] = True
                    curr_entity = self.find_connected_entity(curr_entity, reverse=True)

                    if curr_entity.empty:
                        # empty entity, found input belt
                        src_node = Node()
                        io_nodes.append(src_node)
                        break

                    if curr_entity.is_splitter():
                        # found src node
                        src_node = internal_nodes[self.get_entity_idxs(curr_entity)]
                        break

                if src_node is None:
                    raise RuntimeError

                if dest_node is None:
                    raise RuntimeError

                ans.belts.append(Belt(src_node, dest_node))

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
            curr_opening_dir = from_entity.direction \
                if from_entity.type == IOType.OUTPUT \
                else Direction.reverse(from_entity.direction)
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

                opening_dir = candidate_entity.direction \
                    if candidate_entity.type == IOType.OUTPUT \
                    else Direction.reverse(candidate_entity.direction)

                if opening_dir == curr_opening_dir:
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

            if from_entity.is_underground():
                # underground entrance, only relevant direction is backwards
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

                if candidate_entity.direction == Direction.reverse(dir_to_try):
                    # this entity is pointing to from_entity
                    entities_pointing_here.append(candidate_entity)

            if len(entities_pointing_here) == 0:
                # nothing pointing here, return empty entity
                return BPEntity()

            if len(entities_pointing_here) == 1:
                # unambiguous
                return entities_pointing_here[0]

            # more than one entity points here, meaning lane shenanigans will be happening
            raise RuntimeError("Lane balancing techniques are being used for this balancer, which is currently unsupported.")

        else:
            # not looking for an underground pair, just find next belt
            try:
                x1, y1 = self.get_coord_in_direction(x, y, from_entity.direction)
            except ValueError:
                # out of bounds, return empty entity
                return BPEntity()

        return self.entity_grid[y1][x1]