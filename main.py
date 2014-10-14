# This is GUI for our query processor
#
#   Load necessary components
#   Accept user input
#   Process the query, and output result
#
#   TODO: refactor it!

import sys
import importlib

from PySide.QtCore import *
from PySide.QtGui import *

import megadb.optimization.optimizator as optimizator
from megadb.algebra.parser import parse_sql, print_parse_tree
from megadb.execution.executor import Schema, Executor

class MainWindow(QWidget):
    # with importlib.import_module
    OPTIMIZATIONS = [
        ('Push selections down', 'PushSelectionDownOptimizator'),
        ('Cartesian product to Join', 'CrossJoinToThetaJoinOptimizator')
    ]

    def __init__(self, schema):
        super(MainWindow, self).__init__()
        self.schema = schema

        self.setWindowTitle('Query Processor')
        self.setMinimumWidth(550)

        self._opts = [[False, opt] for opt in self.OPTIMIZATIONS]

        self.setup_widgets()

    def setup_widgets(self):
        self._layout = QVBoxLayout()

        # Query input
        self._query_text = QTextEdit(self)
        self._query_text.setMinimumHeight(80)
        self._query_text.setStyleSheet('QTextEdit { font: 18px; } QTextEdit[class=invalid] { background-color: #FFCDCD; };')

        self._layout.addWidget(self._query_text)

        # Optimizations + execute btn
        hlayout = QHBoxLayout()

        opts_group = QGroupBox('Optimizations', self)
        opts_layout = QGridLayout()
        row = 0
        for inx, (opt_name, _) in enumerate(self.OPTIMIZATIONS):
            cb = QCheckBox(opt_name)
            cb.stateChanged.connect(lambda x, inx=inx: self.on_opt_changed(x, inx))

            opts_layout.addWidget(cb, row, inx % 3)

            if inx % 3 == 2:
                row += 1

        opts_group.setLayout(opts_layout)

        hlayout.addWidget(opts_group)
        hlayout.addStretch(1)

        start_btn = QPushButton('Execute!', self)
        start_btn.clicked.connect(self.execute)
        hlayout.addWidget(start_btn)

        self._layout.addLayout(hlayout)

        self.setLayout(self._layout)

    def on_opt_changed(self, status, inx):
        self._opts[inx][0] = (status == 2)

    def refresh_interface(self):
        self._query_text.setStyle(self._query_text.style())

    def execute(self):
        def instantiate_optimizator(opt_name):
            cls = getattr(optimizator, opt_name)
            if issubclass(cls, optimizator.CostBasedOptimizator):
                return cls(self.schema)
            else:
                return cls()

        # reset color
        self._query_text.setProperty('class', None)
        self.refresh_interface()

        # fetch query text
        query_text = self._query_text.toPlainText()
        if query_text.strip() == '':
            return

        # collect optimizations selected
        executor = Executor(self.schema)
        optimizators = [instantiate_optimizator(v[1][1]) for v in self._opts if v[0]]

        # parsing, optimizing and executing
        try:
            parsed_tree = parse_sql(query_text)
            for opt in optimizators:
                parsed_tree = opt.run(parsed_tree)
            translated_tree = executor.translate_tree(parsed_tree)
        except:
            self._query_text.setProperty('class', 'invalid')
            self.refresh_interface()
            return

        result = executor.execute_plan(translated_tree)

        # show table_view for result, treeview for final tree, dialog for execution time
        rw = ResultWindow(self, parsed_tree, result)
        rw.show()

class ResultWindow(QWidget):
    def __init__(self, parent, tree, tuples):
        super(ResultWindow, self).__init__(parent, Qt.Window)
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        self.build_tree(tree)
        self.build_tuples(tuples[0])

        table_view = QTableView(self)
        table_view.setModel(self.table_model)
        layout.addWidget(table_view)

        self.setLayout(layout)

    def build_tree(self, tree):
        pass

    def build_tuples(self, tuples):
        self.table_model = QStandardItemModel(self)

        if tuples:
            tuple = tuples[0]
            fields = [str(f) for f in tuple.keys()]
            self.table_model.setHorizontalHeaderLabels(fields)

        for row, tuple in enumerate(tuples):
            for col, (field, value) in enumerate(tuple.iteritems()):
                item = QStandardItem(str(value))
                self.table_model.setItem(row, col, item)


if __name__ == '__main__':
    app = QApplication([])
    schema = Schema()
    schema.load()
    schema.load_statistics()

    main = MainWindow(schema)
    main.show()
    app.exec_()
