import os
import shutil
import sys
from pathlib import Path as path

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QSize
from PySide6.QtGui import QPainter, QImage
from vdfparse import VDFParse

from Blueprint import Blueprint, Direction, IOType


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

    spritesheet_paths = [
        path("transport-belt") / "transport-belt.png",
        path("splitter") / "splitter-east.png",
        path("splitter") / "splitter-east-top_patch.png",
        path("splitter") / "splitter-north.png",
        path("splitter") / "splitter-south.png",
        path("splitter") / "splitter-west.png",
        path("splitter") / "splitter-west-top_patch.png",
        path("underground-belt") / "underground-belt-structure.png",
    ]

    for ss_path in spritesheet_paths:
        found_ss = False
        for entity_dir in entity_dirs:
            full_ss_path = entity_dir / ss_path
            if not path.exists(full_ss_path):
                continue
            dest_ss_path = path("assets") / ss_path.name
            source_file = str(full_ss_path)
            print('Copying: {} -> {}'.format(source_file, dest_ss_path))
            found_ss = True

            if full_ss_path.is_file():
                shutil.copyfile(source_file, dest_ss_path)
            else:
                shutil.copy(source_file, dest_ss_path)
        if not found_ss:
            print('No sprite sheet found for {}'.format(ss_path))

class Sprite:
    def __init__(self, img: QImage = QImage(), offset: QtCore.QPoint = QtCore.QPoint(0, 0)):
        self.img = img
        self.offset = offset

class GUI(QtWidgets.QMainWindow):
    def __init__(self, bp: Blueprint):
        super().__init__()
        self.sprite_size = QSize(64, 64)
        self.bp = bp

        asset_dir = "assets"
        self.ss_imgs = {}

        for file in os.listdir(asset_dir):
            filename = os.fsdecode(file)
            if filename.endswith(".png"):
                # print(os.path.join(asset_dir, filename))
                self.ss_imgs[filename] = QImage(os.path.join(asset_dir, filename))

        self.sprites = {}

    def get_tbelt_sprite(self, bp_dir: Direction) -> Sprite:

        ss_y_offsets = [Direction.RIGHT, Direction.LEFT, Direction.UP, Direction.DOWN]
        ss_y_offset = ss_y_offsets.index(bp_dir)

        init_sprite_loc = QtCore.QPoint(30, 38)
        sprite_spacing = QtCore.QPoint(158, 166) - init_sprite_loc

        sprite_rect = QtCore.QRect(
            init_sprite_loc + QtCore.QPoint(sprite_spacing.x(), sprite_spacing.y() * ss_y_offset),
            self.sprite_size
        )

        return Sprite(self.ss_imgs["transport-belt.png"].copy(sprite_rect), QtCore.QPoint(0, 0))

    def get_splitter_sprite(self, bp_dir: Direction) -> Sprite:
        if bp_dir == Direction.UP:
            sprite_rect = QtCore.QRect(3, 5, 128, 64)
            return Sprite(self.ss_imgs["splitter-north.png"].copy(sprite_rect), QtCore.QPoint(-64, 0))
        if bp_dir == Direction.DOWN:
            sprite_rect = QtCore.QRect(10, 6, 128, 64)
            return Sprite(self.ss_imgs["splitter-south.png"].copy(sprite_rect), QtCore.QPoint(-64, 0))
        if bp_dir == Direction.LEFT:

            # Make tall image, ~(64x128)
            ss_format = self.ss_imgs["splitter-west-top_patch.png"].format()
            ans = QImage(QSize(64, 128), ss_format)

            # top patch to the top half first
            top_sprite_rect = QtCore.QRect(1, 5, 64, 64)
            QPainter(ans).drawImage(QtCore.QPoint(0, 0), self.ss_imgs["splitter-west-top_patch.png"], top_sprite_rect)

            # then other sprite 65 pixels down (no x trans)
            top_sprite_rect = QtCore.QRect(1, 3, 64, 64)
            QPainter(ans).drawImage(QtCore.QPoint(0, 60), self.ss_imgs["splitter-west.png"], top_sprite_rect)

            return Sprite(ans, QtCore.QPoint(0, -64))
        if bp_dir == Direction.RIGHT:
            # Make tall image, ~(64x128)
            ss_format = self.ss_imgs["splitter-east-top_patch.png"].format()
            ans = QImage(QSize(64, 128), ss_format)

            # top patch to the top half first
            top_sprite_rect = QtCore.QRect(1, 5, 64, 64)
            QPainter(ans).drawImage(QtCore.QPoint(0, 0), self.ss_imgs["splitter-east-top_patch.png"], top_sprite_rect)

            # then other sprite 65 pixels down (no x trans)
            top_sprite_rect = QtCore.QRect(1, 3, 64, 64)
            QPainter(ans).drawImage(QtCore.QPoint(0, 60), self.ss_imgs["splitter-east.png"], top_sprite_rect)

            return Sprite(ans, QtCore.QPoint(0, -64))
        return Sprite()

    def get_underground_belt_sprite(self, bp_dir: Direction, io_type: IOType) -> Sprite:

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

        return Sprite(self.ss_imgs["underground-belt-structure.png"].copy(sprite_rect), offset)

    def get_entity_sprite(self, entity) -> Sprite:
        e_name = entity["name"]

        if e_name not in self.sprites:
            self.sprites[e_name] = {}

        bp_dir = self.bp.dir_from_int(entity["direction"])
        io_type = IOType.from_type(entity["type"])
        entity_key = (bp_dir, io_type)

        if bp_dir not in self.sprites[entity["name"]]:

            self.sprites[entity["name"]][entity_key] = Sprite()

            if e_name == "transport-belt":
                self.sprites[entity["name"]][entity_key] = self.get_tbelt_sprite(bp_dir)

            if e_name == "splitter":
                self.sprites[entity["name"]][entity_key] = self.get_splitter_sprite(bp_dir)

            if e_name == "underground-belt":
                self.sprites[entity["name"]][entity_key] = self.get_underground_belt_sprite(bp_dir, io_type)

        return self.sprites[entity["name"]][entity_key]

    def paintEvent(self, event):
        print("Paint")
        with QPainter(self) as p:

            # p.setPen(QColor(0, 0, 0))
            # p.setBrush(QtCore.Qt.BrushStyle.SolidPattern)
            # p.drawRect(QtCore.QRect(0, 0, 800, 800))

            for entity in self.bp.entities():

                bp_pos_x = int(entity["position"]["x"])
                bp_pos_y = int(entity["position"]["y"])
                r_x = bp_pos_x - self.bp.min_x
                r_y = bp_pos_y - self.bp.min_y

                # print(r_x, r_y)
                sprite = self.get_entity_sprite(entity)
                p.drawImage(QtCore.QPoint(r_x, r_y) * self.sprite_size.width() + sprite.offset, sprite.img)

if __name__ == '__main__':

    fetch_assets()

    app = QtWidgets.QApplication([])

    # widget = GUI(Blueprint("0eJylkstugzAQRX+lumuDeBjTeNkv6L6KKkhG7UjGINtpgpD/vQIWbdp0UbKc0dwzdx4TWnOiwbEN0BP40FsP/TLB85ttzJwL40DQ4EAdBGzTzVFwjfVD70LSkgmIAmyPdIHOo9guLu4Rl/eIZdwLkA0cmNYFLMH4ak9dSw46/4shMPSeA/d27nqBTqTM0kpghE5KlVZx9vWDVmyj1WkVBY7s6LCWFDfY5T/Y5e7K6RVb3WDLbexfvpd1L6fR3x5QwDQtGWg8kQkPz2zP70QGAh/k/DrwYy5ruatVnWeqUl8HzOInTeLqGg=="))
    # widget = GUI(Blueprint("0eJydmttu4zYQhl9F4FULKIFISzz4MRbZq2JRyDGbCFAkQ6aSdQO/e2G7ieiE9PDnpYPo03DOM+I72/Sz3U3d4Nj6nW3t/nHqdq4bB7ZmD8/TOD8972Z3Nw9999I5uy3+ePj5Z7Fp+3Z4tNO+aPu39rAvdtP42m1t8c/c94X7fO6+KH7Yp7lvJ/+RyRbj0B+Kp7md2sFZuy3cGEMUb892KNq+L7phN7t9MU7nX+Pszj9PtNl1ffev3d6zknWP47Bn67/e2b57Gtr+dCx32Fm2Zq/d5Oa2ZyUb2pfTHy7/cafZsWTdsLW/2Zofy8wnBfTkwfb9+OY9voIef/CerI+/SmYH17nOXk5+/nH4e5hfNnZia/75tJvaYb8bJ3e3sb1jJduN++5i7Xf2m62Vau6bkh3YWtTqvjmeZPoCEwBMUbAVAJMUrAZghoI1AExTMJkO05yCKQBWUTANwAQFM4uX7vrOOTsF7fg/RIchvMryVhOh8SSZNCGTSKIoQpZVCkVXhCyIm2tSP4ifG5Imk04oiBOqJAonZMlz7RjN5HhlU0VyaJaPNzxCW3x8HrZ2eprGedjSSfksXflRaS71lIX4AuJLmJ9VBc7aKNm2m+zj5T+4CMGRcFEoPKtKRO0IlAmPFvMxoE4skR2VDYgmjxaTzSAetVSxVI9aVRCfw3ygo/Lo35yqDrGBBsvTTBobiLQlJ8asuAJCy6NFPGyFxNKSE1dJ50Yia2GLr2wdYidVq48O48wMUZD4UlenD9GQaiUxXdZQbHn0b9o8dVVkqNVJDdxH0xRTb42VMPNFJbSUK4ivYT4SahXlHjUQal76+uYewZpYy8zce8s/zqN/UDHINCRuvSsEz2oho1rPayHrlKBs8hrKJjL7IgsDRdKw2FNfTk55QIOFnrwSNwFfZ+K/2y3hZXn9ZJPkzQ1SBA0KV5kdXaIVkEjkVzYI0XLbzxs2jedumduMpqlGIr2ooFQjke5TUKEvkzYeHxuhRkYoyAi3JLfYLg6JMXVFI9OwhGqflyxUWhsg82a6mCaQnlODmkjaBX62bRHLKyx0KlSfKq25FISUUIHzAjxVyrypLbY+zosmkzILqbwZLrIHVFg0qSteil6RaJJxTQQLotKZqUBnjUkKaS4VeBaNjXw6bIhoBdPY/tKg+LTlvfFUEqIgQchvWTMER8Y7fmW9EK3JzJq3XC+uXuTjVhX3vFAV0XnTXSSf6LxxLqblrHFOVinnNlnjnEzaARos2uQNyWnnMGmxp71XhCjIBwJ1pY4QDSmAElRug7Q90fNmTWrR8yJlTpM0qK4tyeqW+8TLmgGCzHtX2tcbXgFhtqSumGZ4lTWJxZyAV1mjWPLZkZhaUkxkv8qrrK5SRlZlvIJKmBelIqkl4FVma5nMT/sooCg1ZH11ixsJKVmGNBJ0U0OT0nFk66hp6TKnslQTc2jv6KWPVH6dVEo4pQZk1y9oIyHdnqCNhNSmJW1E1k3cu/ORsG+SkR0Yhy57SFIq6LaHonHQlaboIQVykU/TUiH1xNC4NO+vqEMi3l/RUmVd5Ivj0i46CeqQWXPNRapfJeucfWFr7x5wyfp2Y3u2ZvpOF5eLqsXDz88bvKxkr3ban6mNFKY2plGmXgkjvXu05vgf8zhUBg=="))
    widget = GUI(Blueprint("0eNqdmN1uozAQhV9l5Wu2woNtbB5jb1fVKmmtCokAArPaKOLda6gE2cYO47nJD4JvxuM5h4EbOzeT7Ye6day6sfqta0dW/b6xsf5oT81yrD1dLKuYG07t2HeD+3m2jWNzxur23f5jFZ+zwOlj39TO2eHuRJhfM2ZbV7vafgVZ/1z/tNPl7M+seBYJlrG+G/1lXbtEWGIK+SIzdvW//A8f4r0e7NvXCWLJ5xsZEsgqiVxs5MmvcvgYOv8dZZdxdsbctV84ddtPS30fQomkUAYRqptcJJbEF0zypIKpBHKeRC4TyBAl6wBZUxrT99EcYBkKqwyzeE7pa4UpJk8RY5mGJqkxVoI0Aep73H+ZLlkdKZATJVgS1M53CW5e+mxBClH4BO3tyeP2tKQYRokRH9cUtEKhDcWMUAWBPKVVdj96LMlxqwCnOB+qQgBJHb8Zll7hh7cZIN4+DUFQIFCC2mLo7/4QYkqKlemwlYFCJaj2EoQgJQpinkM0zec0ZdQAQ3NwTeiBIk2VOaLf4gsrOGYr9iAaMW0CxQsNRulFgcoWIsUPIgXNA03cA59UW5KcCvJ7p4o3jiKMbcDD8ipKwmy1wo4dqdAER1qLEIIZCiyyapHjBpr7bTloMJEypOq0QgrAqTcl3YIwbmDTFQRnwLIpT4PIkijC6PKYdhBNeR5EZk15IASI6IIkMkDtnMwpToNkc9yksVExTCDNAqGMMS85CtI08DRa9A4iSQJFboWktHqI/Zqx2tmLB+3vBTPWnDzMH/tllzL9cHZcjv61w7heJxUYYYzUQpX+Y54/Ab6ll7o="))
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec())