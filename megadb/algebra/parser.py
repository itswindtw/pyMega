import sqlparse
import sqlparse.sql as sql

from megadb.tree import TreeNode
from megadb.algebra.plan import Field, Comparison, Relation
from megadb.algebra.plan import Projection, Selection, CartesianProduct

def parse_sql(sql_str):
    # TODO: parsing validation
    parsed = sqlparse.parse(sql_str)[0]
    return parse_select(parsed)

def parse_select(stmt):
    """Parse SQL selection statement.

    Args:
        stmt: SELECT [fields] FROM [table_names] WHERE [where_clause]
    Return:
        A logical tree
    """
    def extract_parts(tokens):
        # fields
        fields = tokens.token_next(0)
        inx = tokens.token_index(fields)
        # table_names
        from_kw = tokens.token_next_match(inx, sqlparse.tokens.Keyword, 'FROM')
        inx = tokens.token_index(from_kw)
        table_names = tokens.token_next(inx)
        # where_clause
        where_clause = tokens.token_next_by_instance(inx, sql.Where)

        return fields, table_names, where_clause

    def construct_tree(fields, table_names, where_clause):
        node = None

        # Projection
        if isinstance(fields, sql.Identifier):
            node = Projection(node, [Field(str(fields))])
        elif isinstance(fields, sql.IdentifierList):
            node = Projection(
                node, [Field(str(f)) for f in fields.get_identifiers()])
        else:
            node = Projection(node, []) # represent '*'

        # Selection
        if where_clause is not None:
            conds = parse_where_clause(where_clause)
            node = Selection(node, conds)

        # Relation or CartesianProduct
        if isinstance(table_names, sql.Identifier):
            node = Relation(node, str(table_names))
        elif isinstance(table_names, sql.IdentifierList):
            node = parse_relations(node, table_names.get_identifiers())

        # find root of this tree
        while node.parent:
            node = node.parent

        return node

    assert stmt.get_type() == 'SELECT'
    tokens = sql.TokenList(stmt.tokens)

    # extract parts from tokens
    fields, table_names, where_clause = extract_parts(tokens)

    # construction of logical tree
    return construct_tree(fields, table_names, where_clause)

def parse_relations(parent, ids):
    """Fold relations into join nodes."""
    def combine(acc, relation):
        node = CartesianProduct(None)
        acc.parent = node
        Relation(node, relation)
        return node

    head = Relation(None, next(ids))
    join_tree = reduce(combine, list(ids), head)
    join_tree.parent = parent
    return join_tree

def parse_where_clause(clause):
    """Parse where_clause. It supports only AND conditions"""
    tokens = sql.TokenList(clause.tokens)
    conds = []

    inx = 0
    cond = tokens.token_next_by_instance(inx, sql.Comparison)
    while cond:
        conds.append(parse_condition(cond))

        inx = tokens.token_index(cond)
        cond = tokens.token_next_by_instance(inx+1, sql.Comparison)

    return conds

def parse_condition(cond):
    """Parse [field] [operator] [value]"""
    tokens = sql.TokenList(cond.tokens)

    field_token = tokens.token_first()
    if isinstance(field_token, sql.Identifier):
        field = Field(str(field_token))
    else:
        field = str(field_token)

    comp = tokens.token_next(tokens.token_index(field_token))

    value_token = tokens.token_next(tokens.token_index(comp))
    if isinstance(value_token, sql.Identifier):
        value = Field(str(value_token))
    elif value_token.ttype == sqlparse.tokens.String.Single:
        value = str(value_token)[1:-1]
    else:
        value = str(value_token)

    return Comparison(field, value, str(comp))

def print_parse_tree(root):
    """A helper to print out logical tree."""
    def aux(node, level):
        print '  '*level + repr(node)
        if isinstance(node, TreeNode):
            for child in node.children:
                aux(child, level+1)
    aux(root, 0)
    print
