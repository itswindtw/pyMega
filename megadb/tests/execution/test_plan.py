import unittest
from megadb.execution.plan import *
from megadb.execution.executor import Schema
from megadb.algebra.plan import Comparison, Field

class PlanTestCase(unittest.TestCase):
    def setUp(self):
        self.schema = Schema()
        self.schema.load()

        print "Schema is ready..."

class BasicPlanTestCase(PlanTestCase):
    def test_relation(self):
        alpha = Relation(None, 'Alpha', self.schema.relations['Alpha'])

        with alpha:
            tuples = alpha.get_tuples()
            print tuples

    def test_projection(self):
        fields = [Field(name) for (name, type) in self.schema.relations['Alpha'][0:1]]
        projection = Projection(None, fields)
        alpha = Relation(projection, 'Alpha', self.schema.relations['Alpha'])

        with projection:
            tuples = projection.get_tuples()
            print tuples

    def test_select_with_one_cond(self):
        selection = Selection(None, [Comparison(Field('a1'), '3', '=')])
        alpha = Relation(selection, 'Alpha', self.schema.relations['Alpha'])

        with selection:
            tuples = selection.get_tuples()
            print tuples

    def test_select_with_two_cond(self):
        selection = Selection(None, [Comparison(Field('a1'), '3', '='), Comparison(Field('a2'), 'cc', '=')])
        alpha = Relation(selection, 'Alpha', self.schema.relations['Alpha'])

        with selection:
            tuples = selection.get_tuples()
            print tuples

    def test_selection_then_projection(self):
        fields = [Field(name) for (name, type) in self.schema.relations['Alpha'][1:]]
        projection = Projection(None, fields)
        selection = Selection(projection, [Comparison(Field('a1'), '3', '=')])
        alpha = Relation(selection, 'Alpha', self.schema.relations['Alpha'])

        with projection:
            tuples = projection.get_tuples()
            print tuples

class CartesianProductPlanTestCase(PlanTestCase):
    def test_cartesian_product_then_selection(self):
        selection = Selection(None, [Comparison(Field('a1'), '3', '=')])
        cross = CartesianProduct(selection)
        alpha = Relation(cross, 'Alpha', self.schema.relations['Alpha'])
        beta = Relation(cross, 'Beta', self.schema.relations['Beta'])

        with selection:
            tuples = selection.get_tuples()
            print tuples

    def test_cartesian_product_with_field_comparison(self):
        projection = Projection(None, [])
        selection = Selection(projection, [Comparison(Field('a1'), Field('b1'), '=')])
        cross = CartesianProduct(selection)
        alpha = Relation(cross, 'Alpha', self.schema.relations['Alpha'])
        beta = Relation(cross, 'Beta', self.schema.relations['Beta'])

        with projection:
            tuples = selection.get_tuples()
            print tuples

class NLJoinPlanTestCase(PlanTestCase):
    def test_theta_join(self):
        projection = Projection(None, [])
        theta = NLJoin(projection, [Comparison(Field('a1'), Field('b1'), '=')])

        alpha = Relation(theta, 'Alpha', self.schema.relations['Alpha'])
        beta = Relation(theta, 'Beta', self.schema.relations['Beta'])

        with projection:
            tuples = projection.get_tuples()
            print tuples

class OptimizationPlanTestCase(PlanTestCase):
    def test_cost_of_join(self):
        pass
        # costs = []

        # # Naive
        # projection = Projection(None, [])
        # selection = Selection(projection, [Comparison(Field('a1'), 3, '='), Comparison(Field('a1'), Field('b1'), '=')])

        # join = CrossJoin(selection)

        # alpha = Relation(join, 'Alpha', self.schema.relations['Alpha'])
        # beta = Relation(join, 'Beta', self.schema.relations['Beta'])

        # with projection:
        #     _, cost = projection.get_tuples()

        #     costs.append(sum(cost))

        # # Push selections down
        # projection = Projection(None, [])
        # selection = Selection(projection, [Comparison(Field('a1'), Field('b1'), '=')])

        # join = CrossJoin(selection)

        # a1_selection = Selection(join, [Comparison(Field('a1'), 3, '=')])
        # alpha = Relation(a1_selection, 'Alpha', self.schema.relations['Alpha'])
        # beta = Relation(join, 'Beta', self.schema.relations['Beta'])

        # with projection:
        #     _, cost = projection.get_tuples()

        #     costs.append(sum(cost))

        # # NL Join instead of Cross
        # projection = Projection(None, [])
        # join = NLJoin(projection, [Comparison(Field('a1'), Field('b1'), '=')])

        # a1_selection = Selection(join, [Comparison(Field('a1'), 3, '=')])
        # alpha = Relation(a1_selection, 'Alpha', self.schema.relations['Alpha'])
        # beta = Relation(join, 'Beta', self.schema.relations['Beta'])

        # with projection:
        #     _, cost = projection.get_tuples()

        #     costs.append(sum(cost))

        # print costs
