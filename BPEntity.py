import enum


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

    belt_prefixes = ["fast", "express", "turbo"]

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
                _ = entity[k]
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

    def opening_dir(self) -> Direction:
        if self.empty:
            raise ValueError("This BPEntity is empty")
        if not self.is_underground():
            raise ValueError("This BPEntity is not an underground")
        return self.direction if self.type == IOType.OUTPUT else Direction.reverse(self.direction)

    def prefix(self) -> str:
        for p in BPEntity.belt_prefixes:
            if p in self.name:
                return f"{p}-"
        return ""