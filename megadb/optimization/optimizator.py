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

def collect_namespaces(node):
    if isinstance(node, algebra.Relation):
        return set([str(node.name)])
    else:
        ns = set()
        for c in node.children:
            ns = ns | collect_namespaces(c)
        return ns

class PushSelectionDownOptimizator(BaseOptimizator):
    # 1. find selection
    # 2. find join
    # 3. check namespace set of two children
    # 4. move applicable conditions to corresponding side
    # recursive on children

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

            tree_traverse(selection, algebra.CrossJoin, visit_join)

            if not selection.conds:
                selection.children[0].parent = selection.parent
                selection.parent = None

        tree_traverse(root, algebra.Selection, visit_selection)
        return root


class CrossJoinToThetaJoinOptimizator(BaseOptimizator):
    # Notice: apply this after push selections down optimizator
    # 1. find selection
    # 2. check that its child is cross join
    # 3. if yes: merge two node into one thetajoin

    def run(self, root):
        def visit_selection(selection):
            if (selection.children
                    and isinstance(selection.children[0], algebra.CrossJoin)):
                theta_join = algebra.ThetaJoin(selection.parent, selection.conds)

                cross_join = selection.children[0]
                for c in cross_join.children[:]:
                    c.parent = theta_join

                selection.parent = None

                tree_traverse(theta_join, algebra.Selection, visit_selection)

        tree_traverse(root, algebra.Selection, visit_selection)
        return root


class PushProjectionDownOptimizator(BaseOptimizator):
    def run(self, root):
        return root

#########

class CostBasedOptimizator(BaseOptimizator):
    def __init__(self, schema):
        self.schema = schema
