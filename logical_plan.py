import sqlparse
import sqlparse.sql as sql

class Comparison(object):
    def __init__(self, x, y, comp):
        self.x = x
        self.y = y
        self.comp = comp

    def __repr__(self):
        return ' '.join([str(x) for x in [self.x, self.comp, self.y]])

    @classmethod
    def parse(cls, cond):
        tokens = sql.TokenList(cond.tokens)

        x = tokens.token_first()
        comp = tokens.token_next(tokens.token_index(x))
        y = tokens.token_next(tokens.token_index(comp))

        return cls(str(x), str(y), str(comp))

# class Identifier(object):
#     def __init__(self, value):
#         self.value = unicode(value)

#     def __repr__(self):
#         return "Identifier:" + self.value

# class Integer(object):
#     def __init__(self, value):
#         self.value = int(value)

#     def __repr__(self):
#         return "Integer:" + str(self.value)

class LeafNode(object):
    def __init__(self, parent):
        if parent:
            parent.children.append(self)

        self.parent = parent

    # def __repr__(self):
    #     return repr(self.value)

class Relation(LeafNode):
    def __init__(self, parent, name):
        super(Relation, self).__init__(parent)
        self.name = name

    def __repr__(self):
        return "Relation:" + str(self.name)

class TreeNode(object):
    def __init__(self, parent):
        if parent:
            parent.children.append(self)
        self.parent = parent
        self.children = []

    # def __repr__(self):
    #     s = super(TreeNode, self).__repr__()
    #     cs = [repr(c) for c in self.children]

    #     return s + '\n' + ', '.join(cs)

class Projection(TreeNode):
    def __init__(self, parent, fields):
        super(Projection, self).__init__(parent)
        self.fields = fields

    def __repr__(self):
        return "Projection: " + str(self.fields)

class Selection(TreeNode):
    def __init__(self, parent, conds):
        super(Selection, self).__init__(parent)
        self.conds = conds

    def __repr__(self):
        return "Selection: " + str(self.conds)

class CrossJoin(TreeNode):
    def __init__(self, parent):
        super(CrossJoin, self).__init__(parent)

    def __repr__(self):
        return "CrossJoin"

# class ThetaJoin(TreeNode):
#     def __init__(self, parent, conds, tables):
#         super(ThetaJoin, self).__init__(parent)
#         self.conds = conds
#         self.tables = tables

def parse_sql(sql):
    # TODO: parse validation
    parsed = sqlparse.parse(sql)[0]
    return parse_select(parsed)

def parse_select(stmt):
    # SELECT (1: fields) FROM (2: tables) WHERE (3: where)
    assert(stmt.get_type() == 'SELECT')
    tokens = sql.TokenList(stmt.tokens)

    # 1
    fields = tokens.token_next(0)
    inx = tokens.token_index(fields)
    # 2
    from_kw = tokens.token_next_match(inx, sqlparse.tokens.Keyword, 'FROM')
    inx = tokens.token_index(from_kw)
    tables = tokens.token_next(inx)
    # 3
    where_clause = tokens.token_next_by_instance(inx, sql.Where)

    # Tree Construction
    node = None

    if isinstance(fields, sql.Identifier):
        node = Projection(node, [str(fields)])
    elif isinstance(fields, sql.IdentifierList):
        node = Projection(node, [str(f) for f in fields.get_identifiers()])

    if where_clause is not None:
        conds = parse_where_clause(where_clause)
        node = Selection(node, conds)

    if isinstance(tables, sql.Identifier):
        node = Relation(node, str(tables))
    elif isinstance(tables, sql.IdentifierList):
        node = CrossJoin(node)

        for f in tables.get_identifiers():
            Relation(node, f)

    while node.parent:
        node = node.parent

    return node

def parse_where_clause(clause):
    print repr(clause.tokens)
    tokens = sql.TokenList(clause.tokens)

    conds = []
    inx = 0
    cond = tokens.token_next_by_instance(inx, sql.Comparison)
    while cond:
        if cond.is_group():
            conds.append(Comparison.parse(cond))
        else:
            print repr(cond)
            x = tokens.token_prev(tokens.token_index(cond))
            y = tokens.token_next(tokens.token_index(cond))
            conds.append(Comparison(x, y, cond))

        inx = tokens.token_index(cond)
        cond = tokens.token_next_by_instance(inx+1, sql.Comparison)

    return conds


def print_parse_tree(root):
    def aux(node, level):
        print '  '*level + repr(node)
        if isinstance(node, TreeNode):
            for c in node.children:
                aux(c, level+1)
    aux(root, 0)
    print

if __name__ == '__main__':
    tree = parse_sql("SELECT title, a FROM StarsIn WHERE starName = name AND movieYear = 2008")
    print_parse_tree(tree)

    tree = parse_sql("SELECT * FROM StarsIn, MovieStar, SomeTable WHERE starName = name AND birthAt = 2014")
    print_parse_tree(tree)

    tree = parse_sql("SELECT office FROM Students, Depts WHERE Students.dept = Depts.name AND Students.name='Smith'")
    print_parse_tree(tree)


