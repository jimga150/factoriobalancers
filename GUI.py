import copy
import sys

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QSizePolicy

import BalancerNetwork_Book
import BalancerProofs
import BluePrintRenderer
import common
from BPEntity import Rotation, BLExpress
from BalancerBlueprint import BalancerBlueprint
from PhotoViewer import PhotoViewer
from QtAppInst import app

logger = common.setup_logger(__name__)

class BPDrawArea(QtWidgets.QWidget):
    def __init__(self, bp: BalancerBlueprint):
        super().__init__()
        self.bp = bp
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

        self.viewer = PhotoViewer(self)
        self.img = BluePrintRenderer.renderToQImage(self.bp)
        self.viewer.setPhoto(QPixmap.fromImage(self.img))

        layout = QtWidgets.QGridLayout(self)
        layout.addWidget(self.viewer, 0, 0)


class GUI(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()

        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # bp = Blueprint.from_bp_str(sat.blueprint(sat.interchange(6, 4, 8, True)[0], True, level="express")[0])
        balancer = BalancerNetwork_Book.make_NxN(3)
        self.bp = BalancerBlueprint.from_network(balancer, BLExpress)

        BPDWidget = BPDrawArea(self.bp)
        # layout.addWidget(BPDWidget, 0, 0)
        layout.addWidget(BPDWidget, 0, 0, 1, 2)

        # rotation test
        # bp_temp = copy.deepcopy(BPDWidget.bp)
        # for i in range(3):
        #     bp_temp = copy.deepcopy(bp_temp)
        #     bp_temp.rotate(Rotation.CW)
        #     BPWidget_temp = BPDrawArea(bp_temp)
        #     layout.addWidget(BPWidget_temp, 0, i+1)
        #
        # bp_temp = copy.deepcopy(BPDWidget.bp)
        # for i in range(3):
        #     bp_temp = copy.deepcopy(bp_temp)
        #     bp_temp.rotate(Rotation.CCW)
        #     BPWidget_temp = BPDrawArea(bp_temp)
        #     layout.addWidget(BPWidget_temp, 1, i+1)

        bp2 = copy.deepcopy(BPDWidget.bp)
        bp2.rotate(Rotation.CCW)
        bp2 = bp2.combine_endtoend(bp2)
        BPDWidget2 = BPDrawArea(bp2)
        layout.addWidget(BPDWidget2, 1, 0)

        bp3 = copy.deepcopy(BPDWidget.bp)
        bp3.rotate(Rotation.CCW)
        bp3 = BalancerBlueprint.combine_sidebyside(bp3)
        BPDWidget3 = BPDrawArea(bp3)
        layout.addWidget(BPDWidget3, 1, 1)

        bp4 = BalancerBlueprint.combine_endtoend(bp3)
        BPDWidget4 = BPDrawArea(bp4)
        layout.addWidget(BPDWidget4, 2, 0)

        bp5 = copy.deepcopy(bp4)
        bp5.loopback_ios(2)
        BPDWidget5 = BPDrawArea(bp5)
        layout.addWidget(BPDWidget5, 2, 1)

        layout.addWidget(QtWidgets.QLabel("Label"), 3, 0, Qt.AlignmentFlag.AlignCenter)

        self.resize(600, 600)

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