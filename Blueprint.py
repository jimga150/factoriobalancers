
import base64
import copy
import enum
import json
import sys

import zlib

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

major_version_offset_bits = 6*8

class BPEntity:
    entity_keys_to_ensure = {
        "direction": 0,
        "type": "none"
    }

    NAME_SPLITTER = "splitter"
    NAME_BELT = "transport-belt"
    NAME_UNDERGROUND = "underground-belt"

    def __init__(self, version: int = 1, entity: dict | None = None):

        self.empty = entity is None

        if self.empty:
            return

        for k, dv in self.entity_keys_to_ensure.items():
            try:
                x = entity[k]
            except KeyError:
                entity[k] = dv

        self.name = entity["name"]
        self.version = version

        divisor = 2 if self.version >> major_version_offset_bits == 1 else 4
        self.direction = Direction(int(entity["direction"]) / divisor)

        self.type = IOType.from_type(entity["type"])
        self.pos_x = int(entity["position"]["x"])
        self.pos_y = int(entity["position"]["y"])

        # to be filled in later
        self.bend = Rotation.NONE

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
        self.bp_dict = Blueprint.decode_blueprint_str(bp_str)
        self.tiles = []
        self.parse_bp_dict(self.bp_dict)

        return

        dir_graph = "Direction graph:\n"
        dir_graph += "-" * (self.width * 2 + 1)
        dir_graph += "\n"
        for y in range(self.height):
            dir_graph += "|"
            for x in range(self.width):
                curr_dir = self.tiles[y][x].direction
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
        # print(type(data))
        print(json.dumps(data, sort_keys=True, indent=4, ))
        print(f"Version: {hex(data["version"])}")
        # print("keys:")
        # for key, value in data.items():
        #     print(f"{key}: {value}")
        return data

    def get_coord_in_direction(self, x: int, y: int, direction: Direction) -> tuple[int, int]:
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

        self.width = self.max_x - self.min_x + 1
        self.height = self.max_y - self.min_y + 1

        for _ in range(self.min_y, self.max_y+1):
            self.tiles.append([])
            for _ in range(self.min_x, self.max_x+1):
                self.tiles[-1].append(BPEntity())

        # print(f"{len(self.tiles)=}, {len(self.tiles[0])=}")

        for entity in bp_entities:
            self.tiles[entity.pos_y-self.min_y][entity.pos_x-self.min_x] = entity

            # account for splitters being 2 tiles, entity is only marked as southeast half
            if BPEntity.NAME_SPLITTER in entity.name:
                sp_entity_cap = copy.deepcopy(entity)
                sp_entity_cap.name = "split_cap"
                if entity.direction in [Direction.UP, Direction.DOWN]:
                    self.tiles[entity.pos_y - self.min_y][entity.pos_x - self.min_x - 1] = sp_entity_cap
                else:
                    self.tiles[entity.pos_y - self.min_y - 1][entity.pos_x - self.min_x] = sp_entity_cap

        for y in range(self.height):
            for x in range(self.width):

                if self.tiles[y][x].empty:
                    continue

                if BPEntity.NAME_BELT not in self.tiles[y][x].name:
                    continue

                b_dir = self.tiles[y][x].direction

                connected_from_behind = False
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, Direction.reverse(b_dir))
                    connected_from_behind = self.tiles[y1][x1].direction == b_dir
                except ValueError:
                    pass

                if connected_from_behind:
                    # will never be bent
                    continue

                dir_cw = Direction.turn(b_dir, Rotation.CW)
                dir_ccw = Direction.turn(b_dir, Rotation.CCW)

                connected_from_left = False
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, dir_ccw)
                    connected_from_left = self.tiles[y1][x1].direction == dir_cw
                except ValueError:
                    pass

                connected_from_right = False
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, dir_cw)
                    connected_from_right = self.tiles[y1][x1].direction == dir_ccw
                except ValueError:
                    pass

                if connected_from_left == connected_from_right:
                    # if both or neither, no bend
                    continue

                if connected_from_left:
                    # implies not connected from right so the input of the belt bends left (so it bends clockwise)
                    self.tiles[y][x].bend = Rotation.CCW
                else:
                    # implies not connected from left so the input of the belt bends right (so it bends counterclockwise)
                    self.tiles[y][x].bend = Rotation.CW