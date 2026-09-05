
import base64
import enum
import json
import sys

import zlib

class Rotation(enum.Enum):
    NONE = -1
    CW = 0
    CCW = 1


class Direction(enum.Enum):
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
    INPUT = 0
    OUTPUT = 1
    NONE = 2

    @staticmethod
    def from_type(bp_str: str):
        if bp_str == "input":
            return IOType.INPUT
        elif bp_str == "output":
            return IOType.OUTPUT
        return IOType.NONE

major_version_offset_bits = 6*8

class BPEntity:
    def __init__(self, entity: dict | None = None):
        self.entity = entity

class Blueprint:

    entity_keys_to_ensure = {
        "direction": 0,
        "type": "none"
    }

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
        self.dirs = []
        self.bends = []
        self.parse_bp_dict(self.bp_dict)

        return

        dir_graph = "Direction graph:\n"
        dir_graph += "-" * (self.width * 2 + 1)
        dir_graph += "\n"
        for y in range(self.height):
            dir_graph += "|"
            for x in range(self.width):
                curr_dir = self.dirs[y][x]
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

    def dir_from_int(self, direction: int) -> Direction:
        divisor = 2 if self.version >> major_version_offset_bits == 1 else 4
        direction /= divisor
        return Direction(direction)

    def entities(self) -> list:
        return self.bp_dict["entities"]

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

        for entity in entities:
            pos_x = int(entity["position"]["x"])
            pos_y = int(entity["position"]["y"])

            for k, dv in self.entity_keys_to_ensure.items():
                try:
                    x = entity[k]
                except KeyError:
                    entity[k] = dv

            self.min_x = min(self.min_x, pos_x)
            self.min_y = min(self.min_y, pos_y)
            self.max_x = max(self.max_x, pos_x)
            self.max_y = max(self.max_y, pos_y)

        self.width = self.max_x - self.min_x + 1
        self.height = self.max_y - self.min_y + 1

        # print(f"{min_x=} {min_y=} {max_x=} {max_y=}")

        for _ in range(self.min_y, self.max_y+1):
            self.tiles.append([])
            self.dirs.append([])
            self.bends.append([])
            for _ in range(self.min_x, self.max_x+1):
                self.tiles[-1].append(BPEntity())
                self.dirs[-1].append(None)
                self.bends[-1].append(Rotation.NONE)

        # print(f"{len(self.tiles)=}, {len(self.tiles[0])=}")

        for entity in entities:
            pos_x = int(entity["position"]["x"])
            pos_y = int(entity["position"]["y"])
            self.tiles[pos_y-self.min_y][pos_x-self.min_x] = BPEntity(entity)

            e_dir = self.dir_from_int(int(entity["direction"]))
            self.dirs[pos_y-self.min_y][pos_x-self.min_x] = e_dir

            # account for splitters being 2 tiles, entity is only marked as southeast half
            if "splitter" in entity["name"]:
                if e_dir in [Direction.UP, Direction.DOWN]:
                    self.dirs[pos_y-self.min_y][pos_x-self.min_x-1] = e_dir
                else:
                    self.dirs[pos_y-self.min_y-1][pos_x-self.min_x] = e_dir

        for y in range(self.height):
            for x in range(self.width):

                if self.tiles[y][x].entity is None:
                    continue

                if "transport-belt" not in self.tiles[y][x].entity["name"]:
                    continue

                b_dir = self.dirs[y][x]

                connected_from_behind = False
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, Direction.reverse(b_dir))
                    connected_from_behind = self.dirs[y1][x1] == b_dir
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
                    connected_from_left = self.dirs[y1][x1] == dir_cw
                except ValueError:
                    pass

                connected_from_right = False
                try:
                    x1, y1 = self.get_coord_in_direction(x, y, dir_cw)
                    connected_from_right = self.dirs[y1][x1] == dir_ccw
                except ValueError:
                    pass

                if connected_from_left == connected_from_right:
                    # if both or neither, no bend
                    continue

                if connected_from_left:
                    # implies not connected from right so the input of the belt bends left (so it bends clockwise)
                    self.bends[y][x] = Rotation.CCW
                else:
                    # implies not connected from left so the input of the belt bends right (so it bends counterclockwise)
                    self.bends[y][x] = Rotation.CW