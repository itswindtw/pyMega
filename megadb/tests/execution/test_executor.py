import unittest
from megadb.execution.executor import Schema, Executor
from megadb.algebra.parser import parse_sql, print_parse_tree
from megadb.execution.plan import *
from megadb.algebra.plan import Comparison, Field, NaturalJoin
from megadb.optimization.optimizator import *

class SchemaTestCase(unittest.TestCase):
    def test_load(self):
        schema = Schema()
        schema.load()

        self.assertTrue(len(schema.relations) > 0)

    def test_load_statistics(self):
        schema = Schema()
        schema.load()
        schema.load_statistics()

        print repr(schema.stats)

class ExecutorTestCase(unittest.TestCase):
    def setUp(self):
        schema = Schema()
        schema.load()
        schema.load_statistics()

        self.executor = Executor(schema)

    def test_translate_tree(self):
        tree = parse_sql("SELECT * FROM Alpha WHERE a1 = 3")
        translated = self.executor.translate_tree(tree)

        print_parse_tree(translated)

    def test_simple_plan_execution(self):
        # from parser
        tree = parse_sql("SELECT * FROM Alpha, Beta WHERE a1 = b1")
        translated = self.executor.translate_tree(tree)

        # construct from scratch
        projection = Projection(None, [])
        selection = Selection(projection, [Comparison(Field('a1'), Field('b1'), '=')])
        cross = CartesianProduct(selection)
        alpha = Relation(cross, 'Alpha', self.executor.schema.relations['Alpha'])
        beta = Relation(cross, 'Beta', self.executor.schema.relations['Beta'])

        parser_result = self.executor.execute_plan(translated)
        scratch_result = self.executor.execute_plan(projection)

        self.assertEqual(parser_result[0], scratch_result[0])
        self.assertEqual(parser_result[1], scratch_result[1])

    def test_translate_natural_joins(self):
        tree = parse_sql("SELECT * FROM Alpha, Beta WHERE Alpha.c = Beta.c")
        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(self.executor.schema.stats)
        tree = join_opt.run(push_opt.run(tree))

        self.assertTrue(isinstance(tree.children[0], NaturalJoin))

        translated = self.executor.translate_tree(tree)
        print_parse_tree(translated)

        self.assertTrue(isinstance(translated.children[0], NLJoin))
