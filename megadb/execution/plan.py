import re, os, __builtin__
import collections
import operator

import megadb.settings as settings
from megadb.tree import LeafNode, TreeNode
from megadb.algebra.plan import Field

class Schema(object):
    def __init__(self):
        super(Schema, self).__init__()
        self.relations = {}

    def load(self):
        pattern = re.compile('^(\w+)\((.*)\)$')

        def wrapped_field(field):
            # [abc, STR] -> [abc, type<str>]
            return [field[0], getattr(__builtin__, field[1].lower())]

        def parse_line(line):
            match = pattern.search(line)
            if match is None:
                print "Can't parse {0}".format(line)
                return

            rname = match.group(1)
            fields = [wrapped_field(f.split(':')) for f in match.group(2).split(',')]

            return rname, fields

        path = os.path.join(settings.RELATIONS_PATH, 'Schema')
        with open(path, 'r') as f:
            for line in f:
                rname, fields = parse_line(line)
                if rname:
                    self.relations[rname] = fields

    # TODO: a factory method for relation

class Plan(object):
    # FIXME: we only need iterate api here?
    def open(self):
        raise NotImplementedError()

    def iterate(self):
        raise NotImplementedError()

    def get_costs(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, type, value, traceback):
        self.close()

class Relation(LeafNode, Plan):
    def __init__(self, parent, name, fields):
        super(Relation, self).__init__(parent)

        self.name = name
        self.fields = fields
        self.path = os.path.join(settings.RELATIONS_PATH, name)

    def open(self):
        # self._file = open(self.path, 'r')
        self.cost = 0

    def iterate(self):
        with open(self.path, 'r') as relation_file:
            for line in relation_file:
                tuple = collections.OrderedDict()

                values = line.rstrip().split('#')
                for (field_name, field_type), value in zip(self.fields, values):
                    field = Field.from_components(field_name, self.name)
                    tuple[field] = field_type(value)

                self.cost += 1
                yield tuple

    # def get_tuples(self):
    #     tuples = []

    #     with open(self.path, 'r') as relation_file:
    #         for line in relation_file:
    #             tuple = collections.OrderedDict()

    #             values = line.rstrip().split('#')
    #             for (field_name, field_type), value in zip(self.fields, values):
    #                 field = Field.from_components(field_name, self.name)
    #                 tuple[field] = field_type(value)

    #             tuples.append(tuple)
    #     return tuples

    def get_costs(self):
        return [self.cost]

    def close(self):
        # self._file.close()
        pass

class Projection(TreeNode, Plan):
    def __init__(self, parent, fields):
        super(Projection, self).__init__(parent)
        self.fields = fields

    def open(self):
        assert(len(self.children) == 1)
        self.children[0].open()
        self.cost = 0

    def iterate(self):
        for tuple in self.children[0].iterate():
            self.cost += 1
            if len(self.fields) == 0:
                yield tuple.items()
            else:
                # FIXME: ambiguous?
                yield [(k, v) for (k, v) in tuple.iteritems() if k in self.fields]

    # def get_tuples(self):
    #     tuples = self.children[0].get_tuples()

    #     if len(self.fields) == 0:
    #         return tuples
    #     else:
    #         return [ [(k, v) for (k, v) in tuple.iteritems() if k in self.fields]
    #                 for tuple in tuples]

    def get_costs(self):
        costs = self.children[0].get_costs()
        costs.append(self.cost)
        return costs

    def close(self):
        self.children[0].close()

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
        self.cost = 0

    def iterate(self):
        for tuple in self.children[0].iterate():
            if eval_conds(tuple, self.conds):
                self.cost += 1
                yield tuple

    def get_costs(self):
        costs = self.children[0].get_costs()
        costs.append(self.cost)
        return costs

    def close(self):
        self.children[0].close()

def merge_tuples(p, q):
    return collections.OrderedDict(p.items() + q.items())

class CrossJoin(TreeNode, Plan):
    def __init__(self, parent):
        super(CrossJoin, self).__init__(parent)

    def open(self):
        assert(len(self.children) == 2)
        self.children[0].open()
        self.cost = 0

    def iterate(self):
        for tuple_l in self.children[0].iterate():
            with self.children[1]:
                for tuple_r in self.children[1].iterate():
                    self.cost +=1
                    yield merge_tuples(tuple_l, tuple_r)

    def get_costs(self):
        l_cost = self.children[0].get_costs()
        r_cost = self.children[1].get_costs()

        return l_cost + r_cost + [self.cost]

    def close(self):
        self.children[0].close()


class ThetaJoin(TreeNode, Plan):
    def __init__(self, parent, conds):
        super(ThetaJoin, self).__init__(parent)
        self.conds = conds

    def open(self):
        assert(len(self.children) == 2)
        self.children[0].open()
        self.cost = 0

    def iterate(self):
        for tuple_p in self.children[0].iterate():
            with self.children[1]:
                for tuple_q in self.children[1].iterate():
                    result = merge_tuples(tuple_p, tuple_q)
                    if eval_conds(result, self.conds):
                        self.cost += 1
                        yield result

    def get_costs(self):
        l_cost = self.children[0].get_costs()
        r_cost = self.children[1].get_costs()

        return l_cost + r_cost + [self.cost]

    def close(self):
        self.children[0].close()
