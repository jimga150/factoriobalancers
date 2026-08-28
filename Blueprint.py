
import base64
import enum
import json
import sys

import zlib


class Direction(enum.Enum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3

major_version_offset_bits = 6*8

class BPEntity:
    def __init__(self, entity: dict | None = None):
        self.entity = entity

class Blueprint:

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

    @staticmethod
    def decode_blueprint_str(string: str):
        leading_version_byte = string[0]
        if leading_version_byte != '0':
            raise RuntimeError('Invalid blueprint version')
        string = string[1:]
        compressed = base64.b64decode(string)
        raw_bytes = zlib.decompress(compressed)
        data = json.loads(raw_bytes)["blueprint"]
        print(type(data))
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

            try:
                bp_dir = entity["direction"]
            except KeyError:
                entity["direction"] = 0

            self.min_x = min(self.min_x, pos_x)
            self.min_y = min(self.min_y, pos_y)
            self.max_x = max(self.max_x, pos_x)
            self.max_y = max(self.max_y, pos_y)

        self.width = self.max_x - self.min_x + 1
        self.height = self.max_y - self.min_y + 1

        # print(f"{min_x=} {min_y=} {max_x=} {max_y=}")

        for _ in range(self.min_y, self.max_y+1):
            self.tiles.append([])
            for _ in range(self.min_x, self.max_x+1):
                self.tiles[-1].append(BPEntity())

        # print(f"{len(self.tiles)=}, {len(self.tiles[0])=}")

        for entity in entities:
            pos_x = int(entity["position"]["x"])
            pos_y = int(entity["position"]["y"])
            self.tiles[pos_y-self.min_y][pos_x-self.min_x] = BPEntity(entity)