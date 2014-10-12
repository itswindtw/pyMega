import unittest

from megadb.algebra.parser import parse_sql, print_parse_tree
from megadb.optimization.optimizator import *

class PushSelectionDownOptimizatorTestCase(unittest.TestCase):
    def test_run(self):
        tree = parse_sql("SELECT * FROM R, S, T WHERE R.a = S.a AND S.t = T.t AND R.a = 8")

        opt = PushSelectionDownOptimizator()
        print_parse_tree(opt.run(tree))

