import unittest
from megadb.execution.plan import *
from megadb.algebra.plan import Comparison, Field

class SchemaTestCase(unittest.TestCase):
    def test_load(self):
        schema = Schema()
        schema.load()

        self.assertTrue(len(schema.relations) > 0)

class PlanTestCase(unittest.TestCase):
    def setUp(self):
        self.schema = Schema()
        self.schema.load()

        print "Schema is ready..."

    def test_relation(self):
        alpha = Relation(None, 'Alpha', self.schema.relations['Alpha'])

        with alpha:
            it = alpha.iterate()
            for s in it:
                print s

    def test_projection(self):
        fields = [Field(name) for (name, type) in self.schema.relations['Alpha'][0:1]]
        projection = Projection(None, fields)
        alpha = Relation(projection, 'Alpha', self.schema.relations['Alpha'])

        with projection:
            it = projection.iterate()
            for t in it:
                print t

    def test_selection_one_cond(self):
        selection = Selection(None, [Comparison(Field('a1'), '3', '=')])
        alpha = Relation(selection, 'Alpha', self.schema.relations['Alpha'])

        with selection:
            it = selection.iterate()
            for t in it:
                print t

    def test_selection_two_cond(self):
        selection = Selection(None, [Comparison(Field('a1'), '3', '='), Comparison(Field('a2'), 'cc', '=')])
        alpha = Relation(selection, 'Alpha', self.schema.relations['Alpha'])

        with selection:
            it = selection.iterate()
            for t in it:
                print t

    def test_selection_then_projection(self):
        fields = [Field(name) for (name, type) in self.schema.relations['Alpha'][1:]]
        projection = Projection(None, fields)
        selection = Selection(projection, [Comparison(Field('a1'), '3', '=')])
        alpha = Relation(selection, 'Alpha', self.schema.relations['Alpha'])

        with projection:
            it = projection.iterate()
            for t in it:
                print t

    def test_cross_join_then_selection(self):
        selection = Selection(None, [Comparison(Field('a1'), '3', '=')])
        cross_join = CrossJoin(selection)
        alpha = Relation(cross_join, 'Alpha', self.schema.relations['Alpha'])
        beta = Relation(cross_join, 'Beta', self.schema.relations['Beta'])

        with selection:
            it = selection.iterate()
            for t in it:
                print t

    def test_cross_join_with_field_comparison(self):
        projection = Projection(None, [])
        selection = Selection(projection, [Comparison(Field('a1'), Field('b1'), '=')])
        cross_join = CrossJoin(selection)
        alpha = Relation(cross_join, 'Alpha', self.schema.relations['Alpha'])
        beta = Relation(cross_join, 'Beta', self.schema.relations['Beta'])

        with projection:
            it = projection.iterate()
            for t in it:
                print t

            print "Cost: ", projection.get_costs()

    def test_theta_join(self):
        projection = Projection(None, [])
        theta = ThetaJoin(projection, [Comparison(Field('a1'), 3, '='), Comparison(Field('a1'), Field('b1'), '=')])

        alpha = Relation(theta, 'Alpha', self.schema.relations['Alpha'])
        beta = Relation(theta, 'Beta', self.schema.relations['Beta'])

        with projection:
            it = projection.iterate()
            for t in it:
                print t

            print "Cost: ", projection.get_costs()

    def test_cost_of_cross_join(self):
        costs = []

        # naive
        projection = Projection(None, [])
        selection = Selection(projection, [Comparison(Field('a1'), 3, '='), Comparison(Field('a1'), Field('b1'), '=')])

        join = CrossJoin(selection)

        alpha = Relation(join, 'Alpha', self.schema.relations['Alpha'])
        beta = Relation(join, 'Beta', self.schema.relations['Beta'])

        with projection:
            it = projection.iterate()
            for t in it:
                pass

            costs.append(sum(projection.get_costs()))

        # push selections down
        projection = Projection(None, [])
        selection = Selection(projection, [Comparison(Field('a1'), Field('b1'), '=')])

        join = CrossJoin(selection)

        a1_selection = Selection(join, [Comparison(Field('a1'), 3, '=')])
        alpha = Relation(a1_selection, 'Alpha', self.schema.relations['Alpha'])
        beta = Relation(join, 'Beta', self.schema.relations['Beta'])

        with projection:
            it = projection.iterate()
            for t in it:
                pass

            costs.append(sum(projection.get_costs()))


        print costs
