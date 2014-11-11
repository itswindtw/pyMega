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
            tuples = relation.get_tuples()

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
        def extract_fields(node):
            if isinstance(node, logical.Relation):
                fnames = self.schema.stats[str(node.name)][1].keys()
                fields = map(lambda x: logical.Field.from_components(x, str(node.name)), fnames)
                return set(fields)
            elif isinstance(node, logical.Selection):
                return extract_fields(node.children[0])
            elif isinstance(node, logical.CartesianProduct) or isinstance(node, logical.NaturalJoin):
                return extract_fields(node.children[0]) | extract_fields(node.children[1])
            else:
                raise NotImplementedError()

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
            elif isinstance(node, logical.CartesianProduct):
                join = plan.CartesianProduct(parent)
                for c in node.children:
                    aux(join, c)
                return join
            elif isinstance(node, logical.ThetaJoin):
                join = plan.NLJoin(parent, node.conds) # default is Nested loop join
                for c in node.children:
                    aux(join, c)
                return join
            elif isinstance(node, logical.NaturalJoin):
                fs_left, fs_right = map(extract_fields, node.children)
                fns_left = {x.name for x in fs_left}
                fns_right = {x.name for x in fs_right}
                # common_attr_names = fns_left & fns_right

                conds = []
                for f_left in fs_left:
                    for f_right in fs_right:
                        if f_left.name == f_right.name:
                            conds.append(Comparison(f_left, f_right, '='))
                            break

                join = plan.NLJoin(parent, conds)
                for c in node.children:
                    aux(join, c)
            else:
                raise NotImplementedError()

        return aux(None, root)

    def execute_plan(self, root):
        with root:
            return root.run()
