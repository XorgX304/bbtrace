import os
import idaapi
import idautils
import idc
import ida_ua
from PyQt5 import QtCore, QtGui, QtWidgets
import sip
from InfoParser import InfoParser
from FlameGraphReader import FlameGraphReader
import random

def asset_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), 'assets', path)

def MonospaceFont():
    """
    Convenience alias for creating a monospace Qt font object.
    """
    font = QtGui.QFont("Monospace", 10)
    font.setStyleHint(QtGui.QFont.TypeWriter)
    return font


class Drawing:
    def __init__(self, reader):
        self.reader = reader
        self.lines = {}
        self.colors = {}
        self.activeIndex = None

    def new_color(self, theme):
        """
        https://github.com/brendangregg/FlameGraph/blob/a8d807a11c0f22871134324bda709618ca482b58/flamegraph.pl#L442
        """

        v1 = random.random()

        if theme == 'green':
            g = 200 + int(55 * v1)
            x = 50 + int(60 * v1)
            return (x, g, x)
        elif theme == 'purple':
            x = 190 + int(65 * v1)
            g = 80 + int(60 * v1)
            return (x, g ,x)
        elif theme == 'red':
            r = 200 + int(55 * v1)
            x = 50 + int(80 * v1);
            return (r, x ,x)

    def draw(self, min_x, max_x):
        self.lines = {}

        root_tree = self.reader.roots[self.activeIndex]

        trees = [(root_tree, 0, 0)]
        while len(trees) > 0:
            tree, x, y = trees.pop(0)

            width = tree['size']

            if x + width > min_x and x < max_x:

                if y not in self.lines: self.lines[y] = []

                addr = tree['addr']

                if addr == 0:
                    name = '(root)'
                    theme = 'red'
                else:
                    symbol = self.reader.infoparser.symbols.get(addr)
                    if symbol:
                        theme = 'purple'
                    else:
                        theme = 'green'

                    name = idc.get_name(addr)
                    if not name:
                        if symbol:
                            name = symbol['name']
                        else:
                            name = "proc_%X" % (addr,)

                if addr not in self.colors:
                    self.colors[addr] = self.new_color(theme)

                self.lines[y].append({
                    'addr': addr,
                    'x0': max(0, x - min_x),
                    'x1': min(max_x, x - min_x + width),
                    'color': self.colors[addr],
                    'name': name
                    })

                children = self.reader.get_children(tree)
                x_child = x + 1
                for child in children:
                    trees.append((child, x_child, y + 1))
                    x_child += child['size']

        return self.lines

class Canvas(QtWidgets.QWidget):
    def __init__(self):
        super(Canvas, self).__init__()
        self.initUI()
        self.drawing = None
        self.startX = 0

    def initUI(self):
        # self.setGeometry(300, 300, 280, 170)
        self.setWindowTitle('Drawing graph')
        self.show()

    def paintEvent(self, event):

        qp = QtGui.QPainter()
        qp.begin(self)
        self.drawWidget(qp)
        qp.end()

    def drawWidget(self, qp):
        size = self.size()
        #rect = QtCore.QRect(QtCore.QPoint(0, 0), size)
        qp.setFont(MonospaceFont())

        #metrics = qp.fontMetrics()
        #fw = metrics.width(self.text)

        pen = QtGui.QPen(QtGui.QColor(20, 20, 20), 1,
            QtCore.Qt.SolidLine)

        qp.setPen(pen)
        qp.setBrush(QtCore.Qt.NoBrush)
        qp.drawRect(0, 0, size.width()-1, size.height()-1)

        WIDTH_tree = 20

        if self.drawing:
            min_x = self.startX
            max_x = min_x + ((size.width() + WIDTH_tree) / WIDTH_tree)
            lines = self.drawing.draw(min_x, max_x)
            for y, line in lines.iteritems():
                for box in line:
                    if box['color']:
                        r, g, b = box['color']
                        qp.setBrush(QtGui.QBrush(QtGui.QColor(r, g, b)))
                    else:
                        qp.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))

                    w = (box['x1'] - box['x0']) * WIDTH_tree - 1
                    h = WIDTH_tree - 1

                    x0 = 1+(box['x0'] * WIDTH_tree)
                    y0 = 1+(y * WIDTH_tree)

                    qp.setPen(QtCore.Qt.NoPen)
                    rect = QtCore.QRect(x0, y0, w, h)
                    qp.drawRect(rect)

                    qp.setPen(QtGui.QColor(10, 10, 10))
                    qp.drawText(rect, QtCore.Qt.AlignLeading, box['name'])

    def setDrawing(self, drawing):
        self.drawing = drawing
        self.update()

    def setActiveIndex(self, idx):
        self.startX = 0
        self.drawing.activeIndex = idx
        self.update()

    def setStartX(self, x):
        self.startX = x
        self.update()

class Display(idaapi.PluginForm):
    def OnCreate(self, form):
        """
        Called when the plugin form is created
        """

        # Initalize Data
        exename = idc.GetInputFile()
        path = os.path.dirname(idc.GetInputFilePath())

        infoname = "bbtrace.%s.log.csv" % (exename,)
        infoname = os.path.join(path, infoname)

        self.infoparser = InfoParser(infoname)
        self.infoparser.load()

        self.flamegraph = FlameGraphReader(self.infoparser)
        self.flamegraph.parse()

        self.infoparser.flow()

        self.canvas = None

        # Get parent widget
        self.parent = self.FormToPyQtWidget(form)
        self.PopulateForm()

        drawing = Drawing(self.flamegraph)

        for idx in xrange(0, len(self.flamegraph.roots)):
            root = self.flamegraph.roots[idx]
            self._combobox.addItem("%d: %x" % (idx, root['size']), idx)
            if drawing.activeIndex is None: drawing.activeIndex = idx

        self.canvas.setDrawing(drawing)

    def CreateToolbar(self):
        toolbar = QtWidgets.QToolBar()

        btn_prev = QtWidgets.QPushButton(
            QtGui.QIcon(asset_path('black-left-pointing-double-triangle-with-vertical-bar_23ee.png')),
            ""
        )
        btn_prev.clicked.connect(self._btn_prev_clicked)
        toolbar.addWidget(btn_prev)

        label = QtWidgets.QLabel("Hello from <font color=blue>IDAPython</font>")
        label.setFont(MonospaceFont())

        toolbar.addWidget(label)

        btn_next = QtWidgets.QPushButton(
            QtGui.QIcon(asset_path('black-right-pointing-double-triangle-with-vertical-bar_23ed.png')),
            ""
        )
        btn_next.clicked.connect(self._btn_next_clicked)
        toolbar.addWidget(btn_next)

        btn_trace_color = QtWidgets.QPushButton(
            QtGui.QIcon(asset_path('herb_1f33f.png')),
            "Trace"
        )
        btn_trace_color.clicked.connect(self._btn_trace_color_clicked)
        toolbar.addWidget(btn_trace_color)

        btn_clear_color = QtWidgets.QPushButton(
            QtGui.QIcon(asset_path('splashing-sweat-symbol_1f4a6.png')),
            "Clear"
        )
        btn_clear_color.clicked.connect(self._btn_clear_color_clicked)

        toolbar.addWidget(btn_clear_color)

        combobox = QtWidgets.QComboBox()
        combobox.setStyleSheet("QComboBox { padding: 0 2ex 0 2ex; }")
        combobox.activated.connect(self._ui_selection_changed)
        self._combobox = combobox

        toolbar.addWidget(combobox)

        return toolbar

    def PopulateForm(self):
        # Create layout
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(
            self.CreateToolbar()
        )

        self.canvas = Canvas()
        layout.addWidget(
            self.canvas
        )
        self.parent.setLayout(layout)

    def OnClose(self, form):
        """
        Called when the plugin form is closed
        """
        idaapi.msg("Close")

    def _btn_clear_color_clicked(self):
        ea = idc.NextHead(0)
        while ea != idaapi.BADADDR:
            idc.SetColor(ea, idc.CIC_ITEM, 0xFFFFFFFF)
            ea = idc.NextHead(ea)

    def _btn_trace_color_clicked(self):
        col = 0xccffcc
        col2 = 0xbbeebb

        for ea, basic_block in self.infoparser.basic_blocks.iteritems():
            while ea != idaapi.BADADDR:
                idc.set_color(ea, idc.CIC_ITEM, col)
                ea = idc.next_head(ea, basic_block['end'])

        for target_pc, flow in self.infoparser.flows.iteritems():
            refs = []
            for xref in idautils.XrefsTo(target_pc):
                refs.append(xref.frm)

            for jump_from_pc, flowtype in flow.iteritems():

                if jump_from_pc in refs:
                    continue

                if ida_ua.ua_mnem(jump_from_pc) == 'call':
                    flowtype = idaapi.fl_CN
                else:
                    flowtype = idaapi.fl_JN

                idc.set_color(jump_from_pc, idc.CIC_ITEM, col2)
                idc.AddCodeXref(jump_from_pc, target_pc, flowtype)

    def _ui_selection_changed(self, index):
        self.canvas.setActiveIndex(self._combobox.itemData(index))

    def _btn_next_clicked(self):
        x = self.canvas.startX + 10
        self.canvas.setStartX(x)

    def _btn_prev_clicked(self):
        x = self.canvas.startX - 10 if self.canvas.startX > 10 else 0
        self.canvas.setStartX(x)
