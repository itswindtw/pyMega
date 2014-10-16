import os
import collections
import operator
import timeit

import megadb.settings as settings
from megadb.tree import LeafNode, TreeNode
from megadb.algebra.plan import Field

class Plan(object):
    def open(self):
        raise NotImplementedError()

    def run(self):
        start_at = timeit.default_timer()
        tuples = self.get_tuples()
        end_at = timeit.default_timer()

        self.time_duration = end_at - start_at
        self.table_size = len(tuples)
        return tuples

    def get_tuples(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def __str__(self):
        raise NotImplementedError()

class Relation(LeafNode, Plan):
    def __init__(self, parent, name, fields):
        super(Relation, self).__init__(parent)

        self.name = name
        self.fields = fields
        self.path = os.path.join(settings.RELATIONS_PATH, name)

    def open(self):
        pass

    def get_tuples(self):
        tuples = []

        with open(self.path, 'r') as relation_file:
            for line in relation_file:
                tuple = collections.OrderedDict()

                values = line.rstrip().split('#')
                for (field_name, field_type), value in zip(self.fields, values):
                    field = Field.from_components(field_name, self.name)
                    tuple[field] = field_type(value)

                tuples.append(tuple)

        return tuples

    def close(self):
        pass

    def __str__(self):
        return "Table Scan: %s" % self.name

class Projection(TreeNode, Plan):
    def __init__(self, parent, fields):
        super(Projection, self).__init__(parent)
        self.fields = fields

    def open(self):
        assert(len(self.children) == 1)
        self.children[0].open()

    def get_tuples(self):
        tuples = self.children[0].run()

        if len(self.fields) == 0:
            return [list(tuple.iteritems()) for tuple in tuples]
        else:
            return [ [(k, v) for (k, v) in tuple.iteritems() if k in self.fields]
                    for tuple in tuples]

    def close(self):
        self.children[0].close()

    def __str__(self):
        if self.fields:
            return "Projection: %s" % (','.join([str(f) for f in self.fields]))
        else:
            return "Projection: *"

def eval_conds(tuple, conds):
    def extract_field(tuple, field):
        if not isinstance(field, Field):
            return field

        field_value = tuple.get(field)

        if field_value is not None:
            return field_value

        for (k, v) in tuple.iteritems():
            if k.name == field.name:
                return v


    def eval_cond(tuple, cond):
        lopnd = extract_field(tuple, cond.x)
        ropnd = extract_field(tuple, cond.y)

        ropnd = type(lopnd)(ropnd)

        # TODO: support more operators
        optr = operator.eq
        return optr(lopnd, ropnd)

    for cond in conds:
        if eval_cond(tuple, cond) is False:
            return False

    return True

class Selection(TreeNode, Plan):
    def __init__(self, parent, conds):
        super(Selection, self).__init__(parent)
        self.conds = conds

    def open(self):
        assert(len(self.children) == 1)
        self.children[0].open()

    def get_tuples(self):
        tuples = self.children[0].run()

        return [tuple for tuple in tuples if eval_conds(tuple, self.conds)]

    def close(self):
        self.children[0].close()

    def __str__(self):
        return "Selection: %s" % ('\nAND '.join([str(c) for c in self.conds]))

def merge_tuples(p, q):
    return collections.OrderedDict(p.items() + q.items())

class CartesianProduct(TreeNode, Plan):
    def __init__(self, parent):
        super(CartesianProduct, self).__init__(parent)

    def open(self):
        assert(len(self.children) == 2)
        self.children[0].open()

    def get_tuples(self):
        ts1, ts2 = [c.run() for c in self.children]

        return [merge_tuples(t1, t2) for t1 in ts1 for t2 in ts2]

    def close(self):
        self.children[0].close()

    def __str__(self):
        return "CartesianProduct"

class NLJoin(TreeNode, Plan):
    def __init__(self, parent, conds):
        super(NLJoin, self).__init__(parent)
        self.conds = conds

    def open(self):
        assert(len(self.children) == 2)
        self.children[0].open()

    def get_tuples(self):
        ts1, ts2 = [c.run() for c in self.children]

        joined = []

        for p in ts1:
            for q in ts2:
                r = merge_tuples(p, q)
                if eval_conds(r, self.conds):
                    joined.append(r)

        return joined

    def close(self):
        self.children[0].close()

    def __str__(self):
        return 'Nested Loop Join: %s' % (' AND '.join([str(c) for c in self.conds]))
