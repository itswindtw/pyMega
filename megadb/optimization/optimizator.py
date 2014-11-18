import copy
import itertools

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
        result = visit(root)
        return result

    for c in children:
        result = tree_traverse_first(c, type, visit)
        if result:
            return result

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

def extract_join_order(node):
    if not isinstance(node, algebra.NaturalJoin):
        return []

    lc, rc = node.children
    if isinstance(rc, algebra.NaturalJoin):
        rc, lc = lc, rc

    if isinstance(lc, algebra.NaturalJoin):
        participants = [rc]
        participants.extend(extract_join_order(lc))
        return participants

    return [lc, rc]

def enumerate_join_orders(root):
    def enumerate_join_order_left_deep(node):
        def combine(x, y):
            join = algebra.NaturalJoin(None)
            new_y = clone_tree(y)
            new_y.parent = join
            x.parent = join
            return join

        enums = []
        participants = set(extract_join_order(node))
        combs = itertools.combinations(participants, 2)
        for p1, p2 in combs:
            for perm in itertools.permutations(participants - set((p1, p2))):
                init_join = algebra.NaturalJoin(None)
                new_p1 = clone_tree(p1)
                new_p2 = clone_tree(p2)

                new_p1.parent = init_join
                new_p2.parent = init_join

                join_tree = reduce(combine, perm, init_join)
                partial_tree = clone_partial_tree(node)
                join_tree.parent = partial_tree

                enums.append(find_root(partial_tree))

        return enums

    def enumerate_join_order_bushy(node):
        def combine(pair):
            if len(pair) == 1:
                return pair[0]
            else:
                join = algebra.NaturalJoin(None)
                new_x = clone_tree(pair[0])
                new_y = clone_tree(pair[1])
                new_x.parent = join
                new_y.parent = join
                return join

        def build_two_pair(parts):
            if len(parts) == 0:
                return []
            elif len(parts) == 1:
                return [[(parts.pop(),)]]

            results = []
            part_sets = set(parts)
            for p1, p2 in itertools.combinations(part_sets, 2):
                rest = build_two_pair(part_sets - set((p1, p2)))
                if rest:
                    for r in rest:
                        r.append((p1, p2))

                    results.append(rest)
                else:
                    results.append([[(p1, p2)]])

            return list(itertools.chain.from_iterable(results))

        def enumerate_pairs(parts):
            results = []
            pairs = build_two_pair(parts)
            for p in pairs:
                folded = map(combine, p)

                if len(folded) == 1:
                    new_tree = clone_partial_tree(node)
                    folded[0].parent = new_tree
                    results.append(find_root(new_tree))
                else:
                    results.extend(enumerate_pairs(folded))
            return results

        participants = set(extract_join_order(node))
        # return build_two_pair([1,2])
        return enumerate_pairs(participants)
    left_deep_trees = tree_traverse_first(root, algebra.NaturalJoin, enumerate_join_order_left_deep)
    bushy_trees = tree_traverse_first(root, algebra.NaturalJoin, enumerate_join_order_bushy)

    combined = left_deep_trees + bushy_trees
    return combined or [root]

def enumerate_selections(root):
    """
    1. traverse to leafnode
    2. climb up to find selections
    3. if there is consecutive selections: build permutations of selections into new trees
    """
    def climb_up(node):
        if getattr(node, 'traversed', None):
            return []
        node.traversed = True
        enums = []
        while node:
            while node and not isinstance(node, algebra.Selection):
                prev = node
                node = node.parent

            if node is None:
                return enums

            start = prev
            selects = []
            while isinstance(node, algebra.Selection):
                selects.append(node)
                node = node.parent

            if len(selects) > 1:
                select_perms = itertools.permutations(selects)
                for perms in select_perms:
                    new_tree = clone_tree(start)

                    new_end = new_tree
                    for _ in selects:
                        new_end = new_end.parent

                    for p in perms:
                        new_selection = algebra.Selection(None, p.conds[:])
                        new_tree.parent = new_selection
                        new_tree = new_selection

                    new_tree.parent = new_end.parent
                    new_end.parent = None
                    enums.append(find_root(new_tree))

    enums = tree_traverse_first(root, tree.LeafNode, climb_up)
    while enums:
        next_results = []
        for e in enums:
            next_enums = tree_traverse_first(e, tree.LeafNode, climb_up)
            if next_enums:
                next_results.extend(next_enums)

        if len(next_results) == 0:
            break

        enums = next_results

    return enums or [root]

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

                    if ((isinstance(cond.x, algebra.Field) and cond.x.namespace is None) or
                        (isinstance(cond.y, algebra.Field) and cond.y.namespace is None)):
                        related_ns.add(None)

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

                assert len(selection.children) == 1

                selection.conds = new_conds

            tree_traverse(selection, algebra.CartesianProduct, visit_join)

            if not selection.conds:
                selection.children[0].parent = selection.parent
                selection.parent = None

        tree_traverse(root, algebra.Selection, visit_selection)
        return root


#########

class CostBasedOptimizator(BaseOptimizator):
    def __init__(self, stats):
        self.stats = stats

class CartesianProductToThetaJoinOptimizator(CostBasedOptimizator):
    """
    Notice: apply this after push selections down optimizator (or conds will be folded in join)
    1. find selection
    2. check that its child is cross join
    3. if yes: merge two node into one thetajoin or natrualjoin
    """

    def run(self, root):
        def extract_fields(node):
            if isinstance(node, algebra.Relation):
                fnames = self.stats[str(node.name)][1].keys()
                fields = map(lambda x: algebra.Field.from_components(x, str(node.name)), fnames)
                return set(fields)
            elif isinstance(node, algebra.Selection):
                return extract_fields(node.children[0])
            elif isinstance(node, algebra.CartesianProduct):
                return extract_fields(node.children[0]) | extract_fields(node.children[1])
            else:
                raise NotImplementedError()

        def can_do_natural_join(conds, cross_children):
            fs_left, fs_right = map(extract_fields, cross_children)
            fns_left = {x.name for x in fs_left}
            fns_right = {x.name for x in fs_right}
            common_attrs = fns_left & fns_right

            join_attrs = set()
            for cond in conds:
                if not isinstance(cond.x, algebra.Field) or not isinstance(cond.y, algebra.Field):
                    return False
                if cond.x.name != cond.y.name:
                    return False
                join_attrs.add(cond.x.name)

            return common_attrs == join_attrs

        def visit_selection(selection):
            if (selection.children
                    and isinstance(selection.children[0], algebra.CartesianProduct)):

                prev_selection = None
                curr_selection = selection
                all_conds = []
                while isinstance(curr_selection, algebra.Selection):
                    all_conds.extend(curr_selection.conds)
                    prev_selection = curr_selection
                    curr_selection = curr_selection.parent

                cross_join = selection.children[0]

                if can_do_natural_join(all_conds, cross_join.children):
                    join = algebra.NaturalJoin(prev_selection.parent)
                else:
                    join = algebra.ThetaJoin(prev_selection.parent, all_conds)

                for c in cross_join.children[:]:
                    c.parent = join

                prev_selection.parent = None

                tree_traverse(join, algebra.Selection, visit_selection)

        tree_traverse(root, algebra.Selection, visit_selection)
        return root

class GreedyJoinOrderOptimizator(CostBasedOptimizator):
    """
    1. find NaturalJoin
    2. extract_join_order on join
    3. compute estimation for each participant
    4. using T(P) * T(Q) / (max{V(P, a), V(Q, a)}) to fold
    """
    def run(self, root):
        def estimate_stat(p):
            if isinstance(p, algebra.Relation):
                return copy.copy(self.stats[str(p.name)])
            elif isinstance(p, algebra.Selection):
                child_stat = estimate_stat(p.children[0])
                cond = p.conds[0]
                attr_name = cond.x.name if isinstance(cond.x, algebra.Field) else cond.y.name

                var = child_stat[1][attr_name]
                child_stat[1][attr_name] = 1

                return [float(child_stat[0]) / var, child_stat[1]]

            raise NotImplementedError()

        def estimate_cost(p, q):
            p_stat, q_stat = p[1], q[1]
            new_table_size = float(p_stat[0] * q_stat[0])
            new_value_set = dict(p_stat[1].items() + q_stat[1].items())

            common_attrs = (set(p_stat[1]) & set(q_stat[1]))
            # if not common_attrs:
                # equal to Cartesian product
                # return [p_stat[0] * q_stat[0], new_value_set]

            for common_attr in common_attrs:
                new_table_size /= max(p_stat[1][common_attr], q_stat[1][common_attr])
                new_value_set[common_attr] = min(p_stat[1][common_attr], q_stat[1][common_attr])

            return [new_table_size, new_value_set]

        def visit_join(join):
            participants = extract_join_order(join)
            estimations = map(estimate_stat, participants)
            participants = zip(participants, estimations)

            while len(participants) > 1:
                min_pair = None
                min_cost = None
                for p1, p2 in itertools.combinations(participants, 2):
                    cost = estimate_cost(p1, p2)
                    if min_cost is None or min_cost[0] > cost[0]:
                        min_pair = (p1, p2)
                        min_cost = cost

                for p in min_pair:
                    participants.remove(p)

                new_join = algebra.NaturalJoin(None)
                for p, _ in min_pair:
                    p.parent = new_join

                participants.append([new_join, min_cost])

            new_join, _ = participants[0]
            new_join.parent = join.parent
            join.parent = None

        tree_traverse_first(root, algebra.NaturalJoin, visit_join)
        return root


# contributed by Ray Chien
class EnumerationBasedOptimizator(CostBasedOptimizator):
    def run(self, root):
        def cost(node, cost_list):
            if isinstance(node, algebra.Relation):
                return copy.copy(self.stats[str(node.name)])
            elif isinstance(node, algebra.Projection):
                return cost(node.children[0], cost_list)
            elif isinstance(node, algebra.Selection): # T(S) = T(R) / V(R, a)
                child = cost(node.children[0], cost_list)
                cond = node.conds[0]
                attr_name = cond.x.name if isinstance(cond.x, algebra.Field) else cond.y.name

                var = child[1][attr_name]
                new_t = float(child[0]) / var
                cost_list.append(new_t)
                return [new_t, child[1]]
            else: # T(R) * T(S) / max(V(R, a), V(S, a))
                child_r = cost(node.children[0], cost_list)
                child_s = cost(node.children[1], cost_list)

                new_t = float(child_r[0] * child_s[0])
                new_v = dict(child_r[1].items() + child_s[1].items())

                common_attrs = set(child_r[1]) & set(child_s[1])
                for common_attr in common_attrs:
                    new_t /= max(child_r[1][common_attr], child_s[1][common_attr])

                cost_list.append(new_t)
                return [new_t, new_v]

        def find_optimized_tree(root, enumerator):
            optimized_tree = None
            smallest_cost = float('inf')

            possible_trees = enumerator(root)
            for tree in possible_trees:
                cost_list = []
                cost(tree, cost_list)
                total_cost = sum(cost_list)

                if total_cost < smallest_cost:
                    smallest_cost = total_cost
                    optimized_tree = tree

            return optimized_tree

        best_selection_tree = find_optimized_tree(root, enumerate_selections)
        best_join_order_tree = find_optimized_tree(best_selection_tree, enumerate_join_orders)
        return best_join_order_tree

