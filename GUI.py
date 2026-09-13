import copy
import logging
import os
import shutil
import sys
from pathlib import Path

from PySide6 import QtWidgets
from PySide6.QtCore import QSize, QPoint, QRect, Qt
from PySide6.QtGui import QPainter, QImage, QColor, QStaticText
from PySide6.QtWidgets import QSizePolicy
from vdfparse import VDFParse

import BalancerProofs
import Blueprint_Book
import common
from BPEntity import BPEntity, Direction, Rotation, IOType
from Blueprint import Blueprint


logger = logging.getLogger(__name__)
common.setup_logger(logger)


def fetch_assets():

    # taken from Factorio-SAT

    if sys.platform.startswith('linux'):
        steam_directory = os.path.expanduser('~/.steam')
    elif sys.platform.startswith('win32'):
        steam_directory = 'C:\\Program Files (x86)\\Steam'
    elif sys.platform.startswith('darwin'):
        steam_directory = os.path.expanduser('~/Library/Application Support/Steam')
    else:
        raise RuntimeError('Unknown platform: {}'.format(sys.platform))

    steam_directory = Path(steam_directory)

    if not Path.exists(steam_directory):
        raise RuntimeError('No steam installation found at: {}'.format(steam_directory))

    game_directories = []

    lib_folders_file = steam_directory / "steamapps" / "libraryfolders.vdf"
    vdf = VDFParse(str(lib_folders_file))
    lib_folders = vdf["libraryfolders"]

    i = 0
    while True:
        lib_node = lib_folders[f"{i}"]
        if not lib_node.GetNode():
            break
        path_str = lib_node["path"].ToString().replace("\"", "")
        # print(f"Found Steam library at {path_str}")
        game_directories.append(path_str)
        i = i + 1

    game_directory = None
    for x in game_directories:
        path_to_check = Path(x) / 'steamapps' / 'common' / 'Factorio'
        # print(f"Checking for factorio install at {path_to_check}")
        if Path.exists(path_to_check):
            game_directory = path_to_check
            # print(f"Found install.")
            break

    if game_directory is None:
        raise RuntimeError("No Factorio installation found")

    mac_path = game_directory / "factorio.app" / "Contents"
    if Path.exists(mac_path):
        game_directory = mac_path

    entity_dirs = [
        "base",
        "space-age"
    ]
    entity_dirs = [game_directory / 'data' / x / "graphics" / "entity" for x in entity_dirs]

    spritesheet_paths_base = [
        Path(BPEntity.NAME_BELT) / "transport-belt.png",
        Path(BPEntity.NAME_SPLITTER) / "splitter-east.png",
        Path(BPEntity.NAME_SPLITTER) / "splitter-east-top_patch.png",
        Path(BPEntity.NAME_SPLITTER) / "splitter-north.png",
        Path(BPEntity.NAME_SPLITTER) / "splitter-south.png",
        Path(BPEntity.NAME_SPLITTER) / "splitter-west.png",
        Path(BPEntity.NAME_SPLITTER) / "splitter-west-top_patch.png",
        Path(BPEntity.NAME_UNDERGROUND) / "underground-belt-structure.png",
    ]

    spritesheet_paths = copy.deepcopy(spritesheet_paths_base)

    anchors = [BPEntity.NAME_BELT, BPEntity.NAME_SPLITTER, BPEntity.NAME_UNDERGROUND]
    for prefix in BPEntity.belt_prefixes:
        prefixed_ss_paths = copy.deepcopy(spritesheet_paths_base)
        for anchor in anchors:
            prefixed_ss_paths = [Path(str(x).replace(anchor, f"{prefix}-{anchor}")) for x in prefixed_ss_paths]
        spritesheet_paths.extend(prefixed_ss_paths)

    for ss_path in spritesheet_paths:
        found_ss = False
        for entity_dir in entity_dirs:
            full_ss_path = entity_dir / ss_path
            if not Path.exists(full_ss_path):
                continue

            found_ss = True

            dest_ss_path = Path("assets") / ss_path.name
            if Path.exists(dest_ss_path):
                # skip copying
                break

            source_file = str(full_ss_path)
            # print('Copying: {} -> {}'.format(source_file, dest_ss_path))

            if full_ss_path.is_file():
                shutil.copyfile(source_file, dest_ss_path)
            else:
                shutil.copy(source_file, dest_ss_path)

            break
            
        if not found_ss:
            raise RuntimeError('No sprite sheet found for {}'.format(ss_path))

class Sprite:
    def __init__(self, img: QImage = QImage(), offset: QPoint = QPoint(0, 0)):
        self.img = img
        self.offset = offset

    @staticmethod
    def from_sprite(arg: Sprite):
        img = arg.img.copy()
        offset = copy.deepcopy(arg.offset)
        return Sprite(img, offset)

    def add(self, other: Sprite) -> Sprite:

        new_offset = QPoint(min(self.offset.x(), other.offset.x()), min(self.offset.y(), other.offset.y()))

        # make new image with size enough for both, accounting for offset difference
        min_x = min(self.offset.x(), other.offset.x())
        max_x = max(self.offset.x() + self.img.width(), other.offset.x() + other.img.width())
        min_y = min(self.offset.y(), other.offset.y())
        max_y = max(self.offset.y() + self.img.height(), other.offset.y() + other.img.height())
        new_img = QImage(max_x - min_x + 1, max_y - min_y + 1, self.img.format())
        new_img.fill(QColor(0, 0, 0, 0))

        p = QPainter(new_img)
        p.drawImage(self.offset - new_offset, self.img)
        p.drawImage(other.offset - new_offset, other.img)

        self.img = new_img
        self.offset = new_offset

        return self

class BPDrawArea(QtWidgets.QWidget):
    def __init__(self, bp: Blueprint):
        super().__init__()
        self.tile_size = QSize(64, 64)
        self.sprite_window = QSize(92, 92)
        self.tile_offset = QPoint(
            int((self.sprite_window.width() - self.tile_size.width())/2),
            int((self.sprite_window.height() - self.tile_size.height())/2)
        )

        self.bp = bp

        asset_dir = "assets"
        os.makedirs(asset_dir, exist_ok=True)

        self.ss_imgs = {}

        for file in os.listdir(asset_dir):
            filename = os.fsdecode(file)
            if filename.endswith(".png"):
                # print(os.path.join(asset_dir, filename))
                self.ss_imgs[filename] = QImage(os.path.join(asset_dir, filename))

        self.sprites = {}

    def get_tbelt_sprite(self, entity: BPEntity) -> Sprite:

        ss_y_offsets = [
            (Direction.RIGHT, Rotation.NONE, IOType.NONE),
            (Direction.LEFT, Rotation.NONE, IOType.NONE),
            (Direction.UP, Rotation.NONE, IOType.NONE),
            (Direction.DOWN, Rotation.NONE, IOType.NONE),
            (Direction.UP, Rotation.CW, IOType.NONE),
            (Direction.RIGHT, Rotation.CCW, IOType.NONE),
            (Direction.UP, Rotation.CCW, IOType.NONE),
            (Direction.LEFT, Rotation.CW, IOType.NONE),
            (Direction.RIGHT, Rotation.CW, IOType.NONE),
            (Direction.DOWN, Rotation.CCW, IOType.NONE),
            (Direction.LEFT, Rotation.CCW, IOType.NONE),
            (Direction.DOWN, Rotation.CW, IOType.NONE),
            (Direction.UP, Rotation.NONE, IOType.OUTPUT),
            (Direction.DOWN, Rotation.NONE, IOType.INPUT),
            (Direction.RIGHT, Rotation.NONE, IOType.OUTPUT),
            (Direction.LEFT, Rotation.NONE, IOType.INPUT),
            (Direction.DOWN, Rotation.NONE, IOType.OUTPUT),
            (Direction.UP, Rotation.NONE, IOType.INPUT),
            (Direction.LEFT, Rotation.NONE, IOType.OUTPUT),
            (Direction.RIGHT, Rotation.NONE, IOType.INPUT),
        ]
        ss_y_offset = ss_y_offsets.index((entity.direction, entity.bend, entity.type))

        # take sprite from column 15 cause it has a more clear arrow position for each spritesheet
        ss_x_offset = 15

        init_sprite_loc = QPoint(32, 38)
        sprite_spacing = 128

        sprite_rect = QRect(
            init_sprite_loc + QPoint(sprite_spacing * ss_x_offset, sprite_spacing * ss_y_offset) - self.tile_offset,
            self.sprite_window
        )

        return Sprite(self.ss_imgs[f"{entity.name}.png"].copy(sprite_rect), self.tile_offset*(-1))

    def get_tbelt_sprite_under(self, entity: BPEntity) -> Sprite:
        belt_entity = BPEntity()
        belt_entity.name = f"{entity.prefix()}transport-belt"
        belt_entity.direction = entity.direction
        belt_entity.bend = Rotation.NONE
        belt_entity.type = entity.type

        return self.get_tbelt_sprite(belt_entity)

    def get_splitter_sprite(self, entity: BPEntity) -> Sprite:

        if entity.direction in [Direction.UP, Direction.DOWN]:
            offset = QPoint(-64, 0)
        else:
            offset = QPoint(0, -64)

        belt_sprite = self.get_tbelt_sprite_under(entity)

        ans = Sprite.from_sprite(belt_sprite)

        # add belt twice in two splitter squares
        ans.add(Sprite(belt_sprite.img, belt_sprite.offset + offset))

        splitter_sprite = Sprite()
        if entity.direction == Direction.UP:

            sprite_rect = QRect(2, 5, 155, 58)
            sprite_offset = QPoint(1, -8)

            if "turbo" in entity.prefix():
                sprite_rect = QRect(0, 1, 157, 63)

            splitter_sprite = Sprite(self.ss_imgs[f"{entity.name}-north.png"].copy(sprite_rect), offset + sprite_offset)

        elif entity.direction == Direction.DOWN:

            sprite_rect = QRect(0, 5, 163, 53)
            sprite_offset = QPoint(-10, -4)

            splitter_sprite = Sprite(self.ss_imgs[f"{entity.name}-south.png"].copy(sprite_rect), offset + sprite_offset)

        elif entity.direction == Direction.LEFT:

            top_sprite_rect = QRect(1, 3, 88, 93)

            splitter_sprite = Sprite(self.ss_imgs[f"{entity.name}-west-top_patch.png"].copy(top_sprite_rect), offset + QPoint(-1, -17))

            bot_sprite_rect = QRect(1, 3, 88, 83)
            if "turbo" in entity.prefix():
                bot_sprite_rect = QRect(0, 1, 88, 83)

            splitter_sprite.add(Sprite(self.ss_imgs[f"{entity.name}-west.png"].copy(bot_sprite_rect), offset + QPoint(-1, -17 + 60)))

        elif entity.direction == Direction.RIGHT:

            top_sprite_rect = QRect(3, 6, 86, 98)
            if "turbo" in entity.prefix():
                top_sprite_rect = QRect(3, 4, 86, 98)

            splitter_sprite = Sprite(self.ss_imgs[f"{entity.name}-east-top_patch.png"].copy(top_sprite_rect),
                                     offset + QPoint(-1, -17))

            bot_sprite_rect = QRect(4, 1, 85, 83)
            if "turbo" in entity.prefix():
                bot_sprite_rect = QRect(0, 1, 85, 83)

            splitter_sprite.add(Sprite(self.ss_imgs[f"{entity.name}-east.png"].copy(bot_sprite_rect),
                                       offset + QPoint(0, -17 + 71)))

        ans.add(splitter_sprite)
        return ans

    def get_underground_belt_sprite(self, entity: BPEntity) -> Sprite:

        opening_dir = entity.opening_dir()

        belt_sprite = self.get_tbelt_sprite_under(entity)

        ans = Sprite.from_sprite(belt_sprite)

        sprite_rect = QRect(0, 0, 1, 1)
        offset = QPoint(0, 0)
        if opening_dir == Direction.UP:
            sprite_rect = QRect(447, 73 if entity.type == IOType.OUTPUT else 265, 108, 62)
            offset = QPoint(1, 0)
        if opening_dir == Direction.DOWN:
            sprite_rect = QRect(63, 65 if entity.type == IOType.OUTPUT else 257, 108, 70)
            offset = QPoint(1, 0)
        if opening_dir == Direction.LEFT:
            sprite_rect = QRect(259, 54 if entity.type == IOType.OUTPUT else 246, 84, 80)
            offset = QPoint(0, -10)
        if opening_dir == Direction.RIGHT:
            sprite_rect = QRect(639, 54 if entity.type == IOType.OUTPUT else 246, 98, 81)
            offset = QPoint(0, -10)

        return ans.add(Sprite(self.ss_imgs[f"{entity.name}-structure.png"].copy(sprite_rect), offset))

    def get_sprite_by_entity(self, entity: BPEntity) -> Sprite:

        entity_key = (entity.name, entity.direction, entity.type, entity.bend)

        if entity_key not in self.sprites:

            self.sprites[entity_key] = Sprite()

            if entity.is_belt():
                self.sprites[entity_key] = self.get_tbelt_sprite(entity)

            if entity.is_splitter():
                self.sprites[entity_key] = self.get_splitter_sprite(entity)

            if entity.is_underground():
                self.sprites[entity_key] = self.get_underground_belt_sprite(entity)

        return self.sprites[entity_key]

    def drawEntity(self, p: QPainter, entity: BPEntity):

        if not entity.is_real():
            return

        r_y, r_x = self.bp.get_entity_idxs(entity)

        sprite_pos = QPoint(r_x, r_y) * self.tile_size.width()

        sprite = self.get_sprite_by_entity(entity)
        p.drawImage(sprite_pos + sprite.offset, sprite.img)

        if common.debug and entity.is_splitter() and self.bp.internal_nodes is not None:
            node = self.bp.internal_nodes[entity]
            p.drawStaticText(sprite_pos, QStaticText(str(node)))

    def paintEvent(self, event):

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(84, 84, 84))
        self.setPalette(p)

        with QPainter(self) as p:
            p.scale(0.8, 0.8)
            p.translate(0, 16)
            for y in range(0, self.bp.height):
                for x in range(0, self.bp.width):
                    entity = self.bp.entity_grid[y][x]
                    if entity.is_belt():
                        self.drawEntity(p, entity)
            for y in range(0, self.bp.height):
                for x in range(0, self.bp.width):
                    entity = self.bp.entity_grid[y][x]
                    if not entity.is_belt():
                        self.drawEntity(p, entity)

class GUI(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()

        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        BPDWidget = BPDrawArea(Blueprint(Blueprint_Book.blueprints["8x8 TU yellow"]))
        self.bp = BPDWidget.bp
        BPDWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout.addWidget(BPDWidget, 0, 0)

        layout.addWidget(QtWidgets.QLabel("Label"), 1, 0, Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        pass

if __name__ == '__main__':

    fetch_assets()

    app = QtWidgets.QApplication([])

    # widget = BPDrawArea(Blueprint(Blueprint_Book.blueprints["8x8 TU yellow"]))
    widget = GUI()

    try:
        network = widget.bp.get_network()
        network.render()
        for fxn in BalancerProofs.all_z3_tests:
            logger.info(f"{fxn.__name__}: {fxn(network)}")
    except Exception as e:
        logger.error("Network rendering failed:")
        logger.error(str(e))

    widget.resize(800, 800)
    widget.show()

    sys.exit(app.exec())