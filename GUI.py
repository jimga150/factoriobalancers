import copy
import os
import shutil
import sys
from pathlib import Path as path

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSize, QPoint
from PySide6.QtGui import QPainter, QImage, QColor
from vdfparse import VDFParse

from Blueprint import Blueprint, Direction, IOType, Rotation, BPEntity


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

    steam_directory = path(steam_directory)

    if not path.exists(steam_directory):
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
        print(f"Found Steam library at {path_str}")
        game_directories.append(path_str)
        i = i + 1

    game_directory = None
    for x in game_directories:
        path_to_check = path(x) / 'steamapps' / 'common' / 'Factorio'
        print(f"Checking for factorio install at {path_to_check}")
        if path.exists(path_to_check):
            game_directory = path_to_check
            break

    if game_directory is None:
        raise RuntimeError("No Factorio installation found")

    entity_dirs = [
        "base",
        "space-age"
    ]
    entity_dirs = [game_directory / 'data' / x / "graphics" / "entity" for x in entity_dirs]

    spritesheet_paths_base = [
        path(BPEntity.NAME_BELT) / "transport-belt.png",
        path(BPEntity.NAME_SPLITTER) / "splitter-east.png",
        path(BPEntity.NAME_SPLITTER) / "splitter-east-top_patch.png",
        path(BPEntity.NAME_SPLITTER) / "splitter-north.png",
        path(BPEntity.NAME_SPLITTER) / "splitter-south.png",
        path(BPEntity.NAME_SPLITTER) / "splitter-west.png",
        path(BPEntity.NAME_SPLITTER) / "splitter-west-top_patch.png",
        path(BPEntity.NAME_UNDERGROUND) / "underground-belt-structure.png",
    ]

    spritesheet_paths = copy.deepcopy(spritesheet_paths_base)

    anchors = [BPEntity.NAME_BELT, BPEntity.NAME_SPLITTER, BPEntity.NAME_UNDERGROUND]
    for prefix in Blueprint.belt_prefixes:
        prefixed_ss_paths = copy.deepcopy(spritesheet_paths_base)
        for anchor in anchors:
            prefixed_ss_paths = [path(str(x).replace(anchor, f"{prefix}-{anchor}")) for x in prefixed_ss_paths]
        spritesheet_paths.extend(prefixed_ss_paths)

    for ss_path in spritesheet_paths:
        found_ss = False
        for entity_dir in entity_dirs:
            full_ss_path = entity_dir / ss_path
            if not path.exists(full_ss_path):
                continue

            found_ss = True

            dest_ss_path = path("assets") / ss_path.name
            if path.exists(dest_ss_path):
                # skip copying
                break

            source_file = str(full_ss_path)
            print('Copying: {} -> {}'.format(source_file, dest_ss_path))

            if full_ss_path.is_file():
                shutil.copyfile(source_file, dest_ss_path)
            else:
                shutil.copy(source_file, dest_ss_path)

            break
            
        if not found_ss:
            print('No sprite sheet found for {}'.format(ss_path))

class Sprite:
    def __init__(self, img: QImage = QImage(), offset: QtCore.QPoint = QtCore.QPoint(0, 0)):
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

class GUI(QtWidgets.QMainWindow):
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
        self.ss_imgs = {}

        for file in os.listdir(asset_dir):
            filename = os.fsdecode(file)
            if filename.endswith(".png"):
                # print(os.path.join(asset_dir, filename))
                self.ss_imgs[filename] = QImage(os.path.join(asset_dir, filename))

        self.sprites = {}

    def get_tbelt_sprite(self, prefix: str, bp_dir: Direction, rotation: Rotation) -> Sprite:

        ss_y_offsets = [
            (Direction.RIGHT, Rotation.NONE),
            (Direction.LEFT, Rotation.NONE),
            (Direction.UP, Rotation.NONE),
            (Direction.DOWN, Rotation.NONE),
            (Direction.UP, Rotation.CW),
            (Direction.RIGHT, Rotation.CCW),
            (Direction.UP, Rotation.CCW),
            (Direction.LEFT, Rotation.CW),
            (Direction.RIGHT, Rotation.CW),
            (Direction.DOWN, Rotation.CCW),
            (Direction.LEFT, Rotation.CCW),
            (Direction.DOWN, Rotation.CW)
        ]
        ss_y_offset = ss_y_offsets.index((bp_dir, rotation))

        # take sprite from column 15 cause it has a more clear arrow position for each spritesheet
        ss_x_offset = 15

        init_sprite_loc = QtCore.QPoint(32, 38)
        sprite_spacing = 128

        sprite_rect = QtCore.QRect(
            init_sprite_loc + QtCore.QPoint(sprite_spacing * ss_x_offset, sprite_spacing * ss_y_offset) - self.tile_offset,
            self.sprite_window
        )

        return Sprite(self.ss_imgs[f"{prefix}transport-belt.png"].copy(sprite_rect), self.tile_offset*(-1))

    def get_splitter_sprite(self, prefix: str, bp_dir: Direction) -> Sprite:

        if bp_dir in [Direction.UP, Direction.DOWN]:
            offset = QtCore.QPoint(-64, 0)
        else:
            offset = QtCore.QPoint(0, -64)

        belt_sprite = self.get_sprite_by_attr(f"{prefix}transport-belt", bp_dir, IOType.NONE, Rotation.NONE)

        ans = Sprite.from_sprite(belt_sprite)

        # add belt twice in two splitter squares
        ans.add(Sprite(belt_sprite.img, belt_sprite.offset + offset))

        splitter_sprite = Sprite()
        if bp_dir == Direction.UP:
            sprite_rect = QtCore.QRect(2, 5, 155, 58)
            sprite_offset = QtCore.QPoint(1, -8)
            if "turbo" in prefix:
                sprite_rect = QtCore.QRect(0, 1, 157, 63)
            splitter_sprite = Sprite(self.ss_imgs[f"{prefix}splitter-north.png"].copy(sprite_rect), offset + sprite_offset)
        elif bp_dir == Direction.DOWN:
            sprite_rect = QtCore.QRect(0, 5, 163, 53)
            sprite_offset = QtCore.QPoint(-10, -4)
            splitter_sprite = Sprite(self.ss_imgs[f"{prefix}splitter-south.png"].copy(sprite_rect), offset + sprite_offset)
        elif bp_dir == Direction.LEFT:

            top_sprite_rect = QtCore.QRect(1, 3, 88, 93)
            splitter_sprite = Sprite(self.ss_imgs[f"{prefix}splitter-west-top_patch.png"].copy(top_sprite_rect), offset + QtCore.QPoint(-1, -17))

            bot_sprite_rect = QtCore.QRect(1, 3, 88, 83)
            if "turbo" in prefix:
                bot_sprite_rect = QtCore.QRect(0, 1, 88, 83)
            splitter_sprite.add(Sprite(self.ss_imgs[f"{prefix}splitter-west.png"].copy(bot_sprite_rect), offset + QtCore.QPoint(-1, -17 + 60)))
        elif bp_dir == Direction.RIGHT:
            top_sprite_rect = QtCore.QRect(3, 6, 86, 98)
            if "turbo" in prefix:
                top_sprite_rect = QtCore.QRect(3, 4, 86, 98)
            splitter_sprite = Sprite(self.ss_imgs[f"{prefix}splitter-east-top_patch.png"].copy(top_sprite_rect),
                                     offset + QtCore.QPoint(-1, -17))

            bot_sprite_rect = QtCore.QRect(4, 1, 85, 83)
            if "turbo" in prefix:
                bot_sprite_rect = QtCore.QRect(0, 1, 85, 83)
            splitter_sprite.add(Sprite(self.ss_imgs[f"{prefix}splitter-east.png"].copy(bot_sprite_rect),
                                       offset + QtCore.QPoint(0, -17 + 71)))
        ans.add(splitter_sprite)
        return ans

    def get_underground_belt_sprite(self, prefix: str, bp_dir: Direction, io_type: IOType) -> Sprite:

        belt_sprite = self.get_sprite_by_attr(f"{prefix}transport-belt", bp_dir, IOType.NONE, Rotation.NONE)
        ans = Sprite.from_sprite(belt_sprite)

        # the direction of an underground refers to which way the belt is flowing, not which way its opening

        opening_dir = bp_dir if io_type == IOType.OUTPUT else Direction.reverse(bp_dir)

        sprite_rect = QtCore.QRect(0, 0, 1, 1)
        offset = QtCore.QPoint(0, 0)
        if opening_dir == Direction.UP:
            sprite_rect = QtCore.QRect(448, 73 if io_type == IOType.OUTPUT else 265, 107, 70)
        if opening_dir == Direction.DOWN:
            sprite_rect = QtCore.QRect(64, 65 if io_type == IOType.OUTPUT else 257, 107, 70)
        if opening_dir == Direction.LEFT:
            sprite_rect = QtCore.QRect(259, 54 if io_type == IOType.OUTPUT else 246, 107, 70)
            offset = QtCore.QPoint(0, -10)
        if opening_dir == Direction.RIGHT:
            sprite_rect = QtCore.QRect(639, 54 if io_type == IOType.OUTPUT else 246, 107, 70)
            offset = QtCore.QPoint(0, -10)

        return ans.add(Sprite(self.ss_imgs[f"{prefix}underground-belt-structure.png"].copy(sprite_rect), offset))

    def get_sprite_by_entity(self, entity: BPEntity) -> Sprite:
        return self.get_sprite_by_attr(entity.name, entity.direction, entity.type, entity.bend)

    def get_sprite_by_attr(self, e_name: str, bp_dir: Direction, io_type: IOType, rot: Rotation) -> Sprite:

        entity_key = (e_name, bp_dir, io_type, rot)

        # get filename prefix for image fetching
        prefix = ""
        for p in Blueprint.belt_prefixes:
            if p in e_name:
                prefix = f"{p}-"
                break

        if entity_key not in self.sprites:

            self.sprites[entity_key] = Sprite()

            if BPEntity.NAME_BELT in e_name:
                self.sprites[entity_key] = self.get_tbelt_sprite(prefix, bp_dir, rot)

            if BPEntity.NAME_SPLITTER in e_name:
                self.sprites[entity_key] = self.get_splitter_sprite(prefix, bp_dir)

            if BPEntity.NAME_UNDERGROUND in e_name:
                self.sprites[entity_key] = self.get_underground_belt_sprite(prefix, bp_dir, io_type)

        return self.sprites[entity_key]

    def drawEntity(self, p: QPainter, entity: BPEntity):

        if entity.empty:
            return

        r_x = entity.pos_x - self.bp.min_x
        r_y = entity.pos_y - self.bp.min_y

        sprite = self.get_sprite_by_entity(entity)
        p.drawImage(QtCore.QPoint(r_x, r_y) * self.tile_size.width() + sprite.offset, sprite.img)

    def paintEvent(self, event):

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(84, 84, 84))
        self.setPalette(p)

        with QPainter(self) as p:
            p.translate(0, 16)
            for y in range(0, self.bp.height):
                for x in range(0, self.bp.width):
                    self.drawEntity(p, self.bp.tiles[y][x])


if __name__ == '__main__':

    fetch_assets()

    app = QtWidgets.QApplication([])

    # 4 belt pinwheel
    # widget = GUI(Blueprint("0eJylkstugzAQRX+lumuDeBjTeNkv6L6KKkhG7UjGINtpgpD/vQIWbdp0UbKc0dwzdx4TWnOiwbEN0BP40FsP/TLB85ttzJwL40DQ4EAdBGzTzVFwjfVD70LSkgmIAmyPdIHOo9guLu4Rl/eIZdwLkA0cmNYFLMH4ak9dSw46/4shMPSeA/d27nqBTqTM0kpghE5KlVZx9vWDVmyj1WkVBY7s6LCWFDfY5T/Y5e7K6RVb3WDLbexfvpd1L6fR3x5QwDQtGWg8kQkPz2zP70QGAh/k/DrwYy5ruatVnWeqUl8HzOInTeLqGg=="))

    # 8x8 TU yellow balancer
    # widget = GUI(Blueprint("0eJydmttu4zYQhl9F4FULKIFISzz4MRbZq2JRyDGbCFAkQ6aSdQO/e2G7ieiE9PDnpYPo03DOM+I72/Sz3U3d4Nj6nW3t/nHqdq4bB7ZmD8/TOD8972Z3Nw9999I5uy3+ePj5Z7Fp+3Z4tNO+aPu39rAvdtP42m1t8c/c94X7fO6+KH7Yp7lvJ/+RyRbj0B+Kp7md2sFZuy3cGEMUb892KNq+L7phN7t9MU7nX+Pszj9PtNl1ffev3d6zknWP47Bn67/e2b57Gtr+dCx32Fm2Zq/d5Oa2ZyUb2pfTHy7/cafZsWTdsLW/2Zofy8wnBfTkwfb9+OY9voIef/CerI+/SmYH17nOXk5+/nH4e5hfNnZia/75tJvaYb8bJ3e3sb1jJduN++5i7Xf2m62Vau6bkh3YWtTqvjmeZPoCEwBMUbAVAJMUrAZghoI1AExTMJkO05yCKQBWUTANwAQFM4uX7vrOOTsF7fg/RIchvMryVhOh8SSZNCGTSKIoQpZVCkVXhCyIm2tSP4ifG5Imk04oiBOqJAonZMlz7RjN5HhlU0VyaJaPNzxCW3x8HrZ2eprGedjSSfksXflRaS71lIX4AuJLmJ9VBc7aKNm2m+zj5T+4CMGRcFEoPKtKRO0IlAmPFvMxoE4skR2VDYgmjxaTzSAetVSxVI9aVRCfw3ygo/Lo35yqDrGBBsvTTBobiLQlJ8asuAJCy6NFPGyFxNKSE1dJ50Yia2GLr2wdYidVq48O48wMUZD4UlenD9GQaiUxXdZQbHn0b9o8dVVkqNVJDdxH0xRTb42VMPNFJbSUK4ivYT4SahXlHjUQal76+uYewZpYy8zce8s/zqN/UDHINCRuvSsEz2oho1rPayHrlKBs8hrKJjL7IgsDRdKw2FNfTk55QIOFnrwSNwFfZ+K/2y3hZXn9ZJPkzQ1SBA0KV5kdXaIVkEjkVzYI0XLbzxs2jedumduMpqlGIr2ooFQjke5TUKEvkzYeHxuhRkYoyAi3JLfYLg6JMXVFI9OwhGqflyxUWhsg82a6mCaQnlODmkjaBX62bRHLKyx0KlSfKq25FISUUIHzAjxVyrypLbY+zosmkzILqbwZLrIHVFg0qSteil6RaJJxTQQLotKZqUBnjUkKaS4VeBaNjXw6bIhoBdPY/tKg+LTlvfFUEqIgQchvWTMER8Y7fmW9EK3JzJq3XC+uXuTjVhX3vFAV0XnTXSSf6LxxLqblrHFOVinnNlnjnEzaARos2uQNyWnnMGmxp71XhCjIBwJ1pY4QDSmAElRug7Q90fNmTWrR8yJlTpM0qK4tyeqW+8TLmgGCzHtX2tcbXgFhtqSumGZ4lTWJxZyAV1mjWPLZkZhaUkxkv8qrrK5SRlZlvIJKmBelIqkl4FVma5nMT/sooCg1ZH11ixsJKVmGNBJ0U0OT0nFk66hp6TKnslQTc2jv6KWPVH6dVEo4pQZk1y9oIyHdnqCNhNSmJW1E1k3cu/ORsG+SkR0Yhy57SFIq6LaHonHQlaboIQVykU/TUiH1xNC4NO+vqEMi3l/RUmVd5Ivj0i46CeqQWXPNRapfJeucfWFr7x5wyfp2Y3u2ZvpOF5eLqsXDz88bvKxkr3ban6mNFKY2plGmXgkjvXu05vgf8zhUBg=="))

    # Render test 1 (only yellow)
    # widget = GUI(Blueprint("0eNqdmN1uozAQhV9l5Wu2woNtbB5jb1fVKmmtCokAArPaKOLda6gE2cYO47nJD4JvxuM5h4EbOzeT7Ye6day6sfqta0dW/b6xsf5oT81yrD1dLKuYG07t2HeD+3m2jWNzxur23f5jFZ+zwOlj39TO2eHuRJhfM2ZbV7vafgVZ/1z/tNPl7M+seBYJlrG+G/1lXbtEWGIK+SIzdvW//A8f4r0e7NvXCWLJ5xsZEsgqiVxs5MmvcvgYOv8dZZdxdsbctV84ddtPS30fQomkUAYRqptcJJbEF0zypIKpBHKeRC4TyBAl6wBZUxrT99EcYBkKqwyzeE7pa4UpJk8RY5mGJqkxVoI0Aep73H+ZLlkdKZATJVgS1M53CW5e+mxBClH4BO3tyeP2tKQYRokRH9cUtEKhDcWMUAWBPKVVdj96LMlxqwCnOB+qQgBJHb8Zll7hh7cZIN4+DUFQIFCC2mLo7/4QYkqKlemwlYFCJaj2EoQgJQpinkM0zec0ZdQAQ3NwTeiBIk2VOaLf4gsrOGYr9iAaMW0CxQsNRulFgcoWIsUPIgXNA03cA59UW5KcCvJ7p4o3jiKMbcDD8ipKwmy1wo4dqdAER1qLEIIZCiyyapHjBpr7bTloMJEypOq0QgrAqTcl3YIwbmDTFQRnwLIpT4PIkijC6PKYdhBNeR5EZk15IASI6IIkMkDtnMwpToNkc9yksVExTCDNAqGMMS85CtI08DRa9A4iSQJFboWktHqI/Zqx2tmLB+3vBTPWnDzMH/tllzL9cHZcjv61w7heJxUYYYzUQpX+Y54/Ab6ll7o="))

    # render test 2 (all types)
    widget = GUI(Blueprint("0eNqlWttO4zAQ/RXk54B8GY/tfsa+rtCqhSyKVNIqSVcg1H/fFFBvxM3M+AVE1M71zDkehw+1Wu/qbde0g1p8qOZp0/Zq8ftD9c1Lu1wfnrXL11ot1NAt23676Yb7Vb0e1L5STftcv6mF2VcTH/+77If77Hfs/rFSdTs0Q1N/+fv84/1Pu3td1d1otMr4rdR2049f27QHZwf3Pj34Sr2rhXMPfnTx3HT109cH4BDalWV7tLwbY+leus34O2cbdd52pYb37cFO0253h+R+uHL0JNCxkgBWEpaQxGY3ZLLw1a2eTrjzrFSQUSTIWo4TlsNl4JRKYUm7I7dQPOAmfjqxqPFGMxMKmtUfIxryEQP7KWOsuT6Z85+RzteCM8v6PNbZvhqQmPaZMpymtd+um2EYH06YMccICfFxJtTyUg8ShgQSuKKYtnIIEwygZ8LMahaxQ74k83RlDQkqcJ7ATNGt5RYdWXixTmw/My8WLi3eqkRgDI1lq2bkVQLFYkMaH8sXz6CL0BjJjQiaA8kk04VwPrD5E55mEJi5tH0WuLFTto1EF8I0zp0lDft3ZTFjRHSgRUqbHEhMEwvpC4ibiAOU8TbmJyUvEi5IjsyB1Aa2agZmL5KYwTPIBk1ncLwJbzBiTiVhHKzYPq244ApIWwRFAPGKQMIjnEZ32HWrzT1jUUikRRolO0jMAChcRcu6YUiClRMii3fMeQJXeKJ0O0kUKZKw6zW30ycZIHXaG0FzLKE5N25OeHdNjtKdLBS8Iyn8MaNIaQqwmwLZik3Ntz/Nd/227eq+5yxqtL6jeBHMjLkX6S9xDOKPgrDurSQk4gWLbShjEtTiYwCtjmhEdYxF845WgGaeXiFf4jEV8QoyNuTIIRcUzH7QLHpBFB9PiDAL4vMJ6Gl2wcjXqZNRQ7tnwsQmdn0e9yxOg5Y7MNOFCdcCTrngBE2I1bJjtbxiOPHZ5qeDyTcdIDjbQN7FPCsEz2gGnGNzLhUUEbdnDkAIBQeP3OiGn+JNuU8kYTQJ4sWZiYq6xCgJ+tEUSCIN/FGiupGXheM09vt+kob3CBK8B10yvNGXSIwj3YhFZHOeufQwp70xyCXGZQYiMljtu8s2YyrJOd9SgJPkCzOxwMmUqIqV3CclK144gfTOObkyeaGBPwFLCPAmkpIvYekM0hMKjAYmfkIJ9xN9xBIftEFLBXsKDZVG6zIVEA2b0Ua+veRekmsrIA1zbpV/m2C0k0sBkHBmtOSI7Sh5ZVnEaM4h+7iSACkdlBMttWJFR+wsvmIJG1JDTyKVCIUwNpolG5HVcSO7EUtlEDa2hDyn2vVYqWaoX0eDp/9crdR6ORobn/2qDzndDXU/3Nnx+b+66z+/6dEmSMlHwDD+2O//A5gAEC4="))

    widget.resize(800, 800)
    widget.show()

    sys.exit(app.exec())