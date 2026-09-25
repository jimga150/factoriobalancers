import copy
import logging
import sys

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QSizePolicy

import common
import BalancerNetwork_Book
import BalancerProofs
import BluePrintRenderer
from BPEntity import Rotation
from Blueprint import Blueprint
import factorio_sat_callable as sat
from QtAppInst import app

logger = logging.getLogger(__name__)
common.setup_logger(logger)

class BPDrawArea(QtWidgets.QWidget):
    def __init__(self, bp: Blueprint):
        super().__init__()
        self.bp = bp
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.setMinimumSize(QSize(bp.width*BluePrintRenderer.tile_size.width(), bp.height*BluePrintRenderer.tile_size.height()))

    def paintEvent(self, event):

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor(84, 84, 84))
        self.setPalette(p)

        with QPainter(self) as p:
            BluePrintRenderer.paintBPTo(self.bp, p)


class GUI(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()

        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # bp = Blueprint(sat.blueprint(sat.interchange(6, 4, 8, True)[0], True, level="express")[0])
        balancer = BalancerNetwork_Book.make_NxN(4)
        sat_net_str = balancer.export_to_sat_network()
        sat_bp = sat.belt_balancer(sat_net_str, 10, 4, fast=True, underground_length=8)[0]
        bp_str = sat.blueprint(sat_bp, True, level="express")[0]
        bp = Blueprint.from_bp_str(bp_str)

        BPDWidget = BPDrawArea(bp)
        self.bp = BPDWidget.bp
        layout.addWidget(BPDWidget, 0, 0, 1, 2)

        bp2 = copy.deepcopy(BPDWidget.bp)
        bp2.rotate(Rotation.CW)
        BPDWidget2 = BPDrawArea(bp2)
        layout.addWidget(BPDWidget2, 1, 0)

        bp3 = copy.deepcopy(BPDWidget.bp)
        bp3.rotate(Rotation.CCW)
        BPDWidget3 = BPDrawArea(bp3)
        layout.addWidget(BPDWidget3, 1, 1)

        layout.addWidget(QtWidgets.QLabel("Label"), 2, 0, Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        pass

if __name__ == '__main__':

    widget = GUI()

    try:
        network, _ = widget.bp.get_network()
        network.render()
        for fxn in BalancerProofs.all_z3_tests:
            logger.info(f"{fxn.__name__}: {fxn(network)}")
    except Exception as e:
        logger.error("Network rendering failed:")
        logger.error(str(e))

    widget.show()

    sys.exit(app.exec())