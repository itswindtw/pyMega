import os, re, __builtin__

import megadb.settings as settings

import megadb.algebra.plan as logical
import megadb.execution.plan as plan

class Schema(object):
    def __init__(self):
        super(Schema, self).__init__()
        self.relations = {}
        self.stats = {}

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

    def load_statistics(self):
        def extract_stat(relation):
            tuples, _ = relation.get_tuples()

            total = len(tuples)
            distinct = {}

            for fname, _ in relation.fields:
                values = set()
                field = logical.Field.from_components(fname, relation.name)

                for tuple in tuples:
                    value = tuple[field]
                    values.add(value)

                distinct[fname] = len(values)

            return [total, distinct]

        for (rname, fields) in self.relations.iteritems():
            relation = plan.Relation(None, rname, fields)

            self.stats[rname] = extract_stat(relation)

    # TODO: a factory method for relation

class Executor(object):
    def __init__(self, schema):
        self.schema = schema

    def translate_tree(self, root):
        """Translate a logical plan tree into execution tree"""

        def aux(parent, node):
            if isinstance(node, logical.Relation):
                return plan.Relation(parent, str(node.name), self.schema.relations[str(node.name)])
            elif isinstance(node, logical.Projection):
                projection = plan.Projection(parent, node.fields)
                for c in node.children:
                    aux(projection, c)
                return projection
            elif isinstance(node, logical.Selection):
                selection = plan.Selection(parent, node.conds)
                for c in node.children:
                    aux(selection, c)
                return selection
            elif isinstance(node, logical.CrossJoin):
                join = plan.CrossJoin(parent)
                for c in node.children:
                    aux(join, c)
                return join
            elif isinstance(node, logical.ThetaJoin):
                join = plan.ThetaJoin(parent, node.conds)
                for c in node.children:
                    aux(join, c)
                return join
            else:
                raise NotImplementedError()

        return aux(None, root)

    def execute_plan(self, root):
        with root:
            return root.get_tuples()
