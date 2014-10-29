import copy

import megadb.tree as tree
import megadb.algebra as algebra

from megadb.algebra.parser import print_parse_tree

class BaseOptimizator(object):
    def run(self, tree):
        raise NotImplementedError()

def tree_traverse(root, type, visit):
    children = root.children[:] if isinstance(root, tree.TreeNode) else []

    if isinstance(root, type):
        visit(root)

    for c in children:
        tree_traverse(c, type, visit)

def tree_traverse_first(root, type, visit):
    children = root.children[:] if isinstance(root, tree.TreeNode) else []

    if isinstance(root, type):
        visit(root)
        return True

    for c in children:
        if tree_traverse_first(c, type, visit):
            return

def collect_namespaces(node):
    if isinstance(node, algebra.Relation):
        return set([str(node.name)])
    else:
        ns = set()
        for c in node.children:
            ns = ns | collect_namespaces(c)
        return ns

def clone_tree(root):
    node = copy.deepcopy(root)
    return node

def clone_partial_tree(node):
    if node.parent is None:
        return None
    else:
        old_children = node.parent.children
        new_children = [c for c in old_children if c is not node]

        node.parent.children = new_children
        new_parent = copy.deepcopy(node.parent)
        node.parent.children = old_children

        parent_of_new_parent = clone_partial_tree(new_parent)
        if parent_of_new_parent is not None:
            new_parent.parent = parent_of_new_parent

        return new_parent

def find_root(node):
    while node.parent:
        node = node.parent

    return node

def enumerate_join_orders(root):
    swaps = []

    def enumerate_join_order(node):
        # swaps.append(find_root(node))
        lc, rc = node.children
        enumerate_swaps((0, lc, rc))

    def enumerate_swaps(nodes):
        depth, lc, rc = nodes

        if (not isinstance(lc, algebra.NaturalJoin) and
            not isinstance(rc, algebra.NaturalJoin)):
            return

        if isinstance(rc, algebra.NaturalJoin):
            rc, lc = lc, rc

        # RC swap with LC.LC and LC.RC
        for i in range(2):
            parent_tree = clone_partial_tree(rc)
            new_rc = clone_tree(rc)
            new_lc = parent_tree.children[0]

            j = depth
            while j > 0:
                if isinstance(new_lc.children[0], algebra.NaturalJoin):
                    new_lc = new_lc.children[0]
                else:
                    new_lc = new_lc.children[1]
                j -= 1

            # we only consider left-deep tree
            if isinstance(new_lc.children[i], algebra.NaturalJoin):
                # new_lc_lc = new_lc.children[i]
                # enumerate_swaps((depth+1, new_lc_lc.children[0], new_rc))
                # enumerate_swaps((depth+1, new_lc_lc.children[1], new_rc))
                continue

            new_lc.children[i].parent = parent_tree
            new_rc.parent = new_lc

            swaps.append(find_root(parent_tree))

            enumerate_join_order(parent_tree.children[0])

        swaps.append(find_root(rc))
        enumerate_join_order(lc)
        enumerate_swaps((depth+1, lc.children[0], rc))
        enumerate_swaps((depth+1, lc.children[1], rc))

    tree_traverse_first(root, algebra.NaturalJoin, enumerate_join_order)
    return swaps

class PushSelectionDownOptimizator(BaseOptimizator):
    """
    1. find selection
    2. find join
    3. check namespace set of two children
    4. move applicable conditions to corresponding side
    -> recursive on children
    """

    def run(self, root):
        def visit_selection(selection):
            def visit_join(join):
                child_p, child_q = join.children

                # collect namespaces of two children
                ns_p = collect_namespaces(child_p)
                ns_q = collect_namespaces(child_q)

                new_conds = []
                for cond in selection.conds:
                    related_ns = set()
                    if isinstance(cond.x, algebra.Field) and cond.x.namespace:
                        related_ns.add(cond.x.namespace)

                    if isinstance(cond.y, algebra.Field) and cond.y.namespace:
                        related_ns.add(cond.y.namespace)

                    if related_ns <= ns_p or related_ns <= ns_q:
                        new_selection = algebra.Selection(join, [cond])

                        if related_ns <= ns_p:
                            child_p.parent = new_selection
                            child_p = new_selection
                        else:
                            child_q.parent = new_selection
                            child_q = new_selection
                    else:
                        new_conds.append(cond)

                assert(len(selection.children) == 1)

                selection.conds = new_conds

            tree_traverse(selection, algebra.CartesianProduct, visit_join)

            if not selection.conds:
                selection.children[0].parent = selection.parent
                selection.parent = None

        tree_traverse(root, algebra.Selection, visit_selection)
        return root


class CartesianProductToThetaJoinOptimizator(BaseOptimizator):
    """
    Notice: apply this after push selections down optimizator (or conds will be folded in join)
    1. find selection
    2. check that its child is cross join
    3. if yes: merge two node into one thetajoin or natrualjoin
    """

    def run(self, root):
        def can_do_natural_join(selection, cross_children):
            for cond in selection.conds:
                if not isinstance(cond.x, algebra.Field) or not isinstance(cond.y, algebra.Field):
                    return False
                if cond.x.name != cond.y.name:
                    return False

            return True

        def visit_selection(selection):
            if (selection.children
                    and isinstance(selection.children[0], algebra.CartesianProduct)):

                cross_join = selection.children[0]

                if can_do_natural_join(selection, cross_join.children):
                    join = algebra.NaturalJoin(selection.parent)
                else:
                    join = algebra.ThetaJoin(selection.parent, selection.conds)

                for c in cross_join.children[:]:
                    c.parent = join

                selection.parent = None

                tree_traverse(join, algebra.Selection, visit_selection)

        tree_traverse(root, algebra.Selection, visit_selection)
        return root


class PushProjectionDownOptimizator(BaseOptimizator):
    def run(self, root):
        return root

#########

class CostBasedOptimizator(BaseOptimizator):
    def __init__(self, schema):
        self.schema = schema


