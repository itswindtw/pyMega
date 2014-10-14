import sqlparse
import sqlparse.sql as sql

from plan import *

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
        node = Projection(node, [Field(str(fields))])
    elif isinstance(fields, sql.IdentifierList):
        node = Projection(node, [Field(str(f)) for f in fields.get_identifiers()])
    else:
        node = Projection(node, []) # represent '*'

    if where_clause is not None:
        conds = parse_where_clause(where_clause)
        node = Selection(node, conds)

    if isinstance(tables, sql.Identifier):
        node = Relation(node, str(tables))
    elif isinstance(tables, sql.IdentifierList):
        node = parse_relations(node, tables.get_identifiers())

    while node.parent:
        node = node.parent

    return node

def parse_relations(parent, ids):
    def combine(x, y):
        node = CrossJoin(None)
        x.parent = node
        Relation(node, y)
        return node

    head = Relation(None, next(ids))
    join_tree = reduce(combine, list(ids), head)
    join_tree.parent = parent
    return join_tree

def parse_where_clause(clause):
    tokens = sql.TokenList(clause.tokens)

    conds = []
    inx = 0
    cond = tokens.token_next_by_instance(inx, sql.Comparison)
    while cond:
        if cond.is_group():
            conds.append(parse_conditions(cond))
        else:
            # FIXME: unnecessary now?
            x = tokens.token_prev(tokens.token_index(cond))
            y = tokens.token_next(tokens.token_index(cond))
            conds.append(Comparison(x, y, cond))

        inx = tokens.token_index(cond)
        cond = tokens.token_next_by_instance(inx+1, sql.Comparison)

    return conds

def parse_conditions(cond):
    tokens = sql.TokenList(cond.tokens)

    field_token = tokens.token_first()
    if isinstance(field_token, sql.Identifier):
        x = Field(str(field_token))
    else:
        x = str(field_token)

    comp = tokens.token_next(tokens.token_index(field_token))


    value_token = tokens.token_next(tokens.token_index(comp))
    if isinstance(value_token, sql.Identifier):
        y = Field(str(value_token))
    elif value_token.ttype == sqlparse.tokens.String.Single:
        y = str(value_token)[1:-1]
    else:
        y = str(value_token)

    return Comparison(x, y, str(comp))

def print_parse_tree(root):
    def aux(node, level):
        print '  '*level + repr(node)
        if isinstance(node, TreeNode):
            for c in node.children:
                aux(c, level+1)
    aux(root, 0)
    print
