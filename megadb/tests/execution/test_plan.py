import unittest
from megadb.execution.plan import *
from megadb.algebra.plan import Comparison

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
        students = Relation(None, 'Students', self.schema.relations['Students'])

        with students:
            it = students.iterate()
            for s in it:
                print s

    def test_projection(self):
        fields = [name for (name, type) in self.schema.relations['Students'][0:2]]
        projection = Projection(None, fields)
        students = Relation(projection, 'Students', self.schema.relations['Students'])

        with projection:
            it = projection.iterate()
            for t in it:
                print t

    def test_selection_one_cond(self):
        selection = Selection(None, [Comparison('name', 'Xue Song', '=')])
        students = Relation(selection, 'Students', self.schema.relations['Students'])

        with students:
            it = selection.iterate()
            for t in it:
                print t

    def test_selection_two_cond(self):
        selection = Selection(None, [Comparison('gender', 'M', '='), Comparison('name', 'Xue Song', '=')])
        students = Relation(selection, 'Students', self.schema.relations['Students'])

        with students:
            it = selection.iterate()
            for t in it:
                print t

    def test_selection_then_projection(self):
        fields = [name for (name, type) in self.schema.relations['Students'][0:2]]
        projection = Projection(None, fields)
        selection = Selection(projection, [Comparison('name', 'Xue Song', '=')])
        students = Relation(selection, 'Students', self.schema.relations['Students'])

        with projection:
            it = projection.iterate()
            for t in it:
                print t



