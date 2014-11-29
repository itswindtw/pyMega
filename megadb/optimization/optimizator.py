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

# contributed by Jianqing Zhang and Jian Yuan
class GreedyOptimizator(CostBasedOptimizator):
    def run(self, root):
        # order in statforS indicates the selection order
        self.statforS = {}
        self.statforJ = {}

        self.projFields = []
        self.relationTobeJoin = []
        self.forSelec = []
        self.cascadeSele = False

        self.subTrees = {}

        def Traverse(node):
            # if node type is 'Projection', then record the fields to perform Projection
            if isinstance(node, algebra.Projection):
                self.projFields = node.fields
            # record the relations to perform Natural Join
            if isinstance(node, algebra.NaturalJoin):
                if isinstance(node.children[0], algebra.Relation):
                    self.relationTobeJoin.append(str(node.children[0].name))
                    # set up a dictionary to store the statistics used for Natural Join
                    self.statforJ[str(node.children[0].name)] = self.stats[str(node.children[0].name)]
                elif isinstance(node.children[1], algebra.Relation):
                    self.relationTobeJoin.append(str(node.children[1].name))
                    # set up a dictionary to store the statistics used for Natural Join
                    self.statforJ[str(node.children[0].name)] = self.stats[str(node.children[0].name)]

            if isinstance(node, algebra.Selection):
                rName = node.conds[0].x.namespace
                attrName = node.conds[0].x.name
                cond = node.conds[0]
                # record the condition to perform Selection
                self.forSelec.append(cond)

                assert(self.stats.has_key(rName))
                # set up a new dictionary to store statistics used for Selection only
                if not self.statforS.has_key(rName):
                    self.statforS[rName] = []
                else:
                    self.cascadeSele = True   # used to decide whether to determine Selection Order
                T = self.stats[rName][0]  # number of tuples in Relation "rName"
                newT = T / self.stats[rName][1][attrName]
                assert(newT >= 1)
                # temperary dictionary to store post selection statistics
                tmp = {}
                for eachAttr in self.stats[rName][1].keys():
                    if eachAttr == attrName:
                        newVar = 1
                        tmp[eachAttr] = newVar
                    else:
                        # asumption that after selection, variance of other attributes won't change unless it's greater than the new T
                        newVar = min(self.stats[rName][1][eachAttr], newT)
                        tmp[eachAttr] = newVar
                data = []
                data.append(attrName)   # different from original statistics, used to tell the selection is performed on which attribute
                data.append(newT)
                data.append(tmp)
                self.statforS[rName].append(data)
                # also should update the dictionary of statistics for Natural Join
                if not self.statforJ.has_key(rName):
                    self.statforJ[rName] = []
                    self.statforJ[rName].append(newT)
                    self.statforJ[rName].append(tmp)
                else:
                    newStat = []
                    newT = self.statforJ[rName][0] / self.statforJ[rName][1][attrName]  # cascade Selection
                    assert(newT >= 1)
                    tmp = {}
                    for eachAttr in self.statforJ[rName][1].keys():
                        if eachAttr == attrName:
                            newVar = 1
                            tmp[eachAttr] = newVar
                        else:
                            # asumption that after selection, variance of other attributes won't change unless it's greater than the new T
                            newVar = min(self.statforJ[rName][1][eachAttr], newT)
                            tmp[eachAttr] = newVar
                    newStat.append(newT)
                    newStat.append(tmp)
                    self.statforJ[rName] = newStat

            if isinstance(node, tree.LeafNode):
                if isinstance(node.parent, algebra.Selection):
                    self.relationTobeJoin.append(str(node.name))

            if isinstance(node, tree.TreeNode):
                for child in node.children:
                    Traverse(child)
        Traverse(root)

        def SelectOrder():
            if self.cascadeSele == False:
                return
            for each in self.statforS.keys():
                # sort the statistic based on # of tuples to implement the select order
                self.statforS[each] = sorted(self.statforS[each], key=lambda item: item[1])
        SelectOrder()

        def JoinOrder():
            newNode = None
            # if only two relations to be join, then no need to decide the join order
            if len(self.relationTobeJoin) == 2:
                # add the last relation into the joinOrder list
                newNode = algebra.NaturalJoin(newNode)
                newRName = self.relationTobeJoin[0] + ' ' + self.relationTobeJoin[1]
                if self.relationTobeJoin[0].find(' ') == -1:
                    algebra.Relation(newNode, self.relationTobeJoin[0])
                    self.subTrees[self.relationTobeJoin[1]].parent = newNode
                    del self.subTrees[self.relationTobeJoin[1]]
                elif self.relationTobeJoin[1].find(' ') == -1:
                    Relation(newNode, self.relationTobeJoin[1])
                    self.subTrees[self.relationTobeJoin[0]].parent = newNode
                    del self.subTrees[self.relationTobeJoin[0]]
                else:
                    self.subTrees[self.relationTobeJoin[0]].parent = newNode
                    self.subTrees[self.relationTobeJoin[1]].parent = newNode
                    del self.subTrees[self.relationTobeJoin[0]]
                    del self.subTrees[self.relationTobeJoin[1]]
                self.subTrees[newRName] = newNode
                # Now subTrees dict should only have one entry
                assert(len(self.subTrees) == 1)
                return newNode
            tmp1 = []    # tmp1 temperarily store the cost of all possible join pairs
            # for each possible relation join pairs
            for each in self.relationTobeJoin:
                for another in self.relationTobeJoin:
                    if self.relationTobeJoin.index(each) >= self.relationTobeJoin.index(another):
                        continue
                    else:
                        # try to find if they have common attributes
                        attr = None
                        attrEach = set(self.statforJ[each][1].keys())
                        attrAnot = set(self.statforJ[another][1].keys())
                        attr = list(attrEach.intersection(attrAnot))

                        numofAttr = len(attr)
                        if numofAttr > 0:
                            # calculate the cost of the join of these two relations
                            T1 = self.statforJ[each][0]
                            T2 = self.statforJ[another][0]
                            cost = T1 * T2
                            # if have multiple attributes in common
                            for i in range(0, numofAttr):   # remember 'i' won't reach numofAttr
                                cost = cost / max(self.statforJ[each][1][attr[i]], self.statforJ[another][1][attr[i]])
                                if cost == 0:
                                    cost = 1
                            tmp2 = []          # tmp2 temperarily store the cost information of one possible join pair
                            tmp2.append(each)
                            tmp2.append(another)
                            tmp2.append(cost)
                            tmp1.append(tmp2)
            # sort the list tmp1 based on the cost
            # the first pair has the least cost
            tmp1 = sorted(tmp1, key=lambda item: item[2])

            # Construct the sub-tree using this least cost pair
            newNode = algebra.NaturalJoin(newNode)
            newRName = tmp1[0][0] + ' ' + tmp1[0][1]    # name of the post-join relation is indicated by the space in the name
            if tmp1[0][0].find(' ') == -1:
                thisNode = None
                thisNode = algebra.Relation(newNode, tmp1[0][0])
        #############################################           # add selection node
                if tmp1[0][0] in self.statforS:
                    for e in self.statforS[tmp1[0][0]]:
                        seleAttr = e[0]
                        for eCond in self.forSelec:
                            if eCond.x.namespace == tmp1[0][0] and eCond.x.name == seleAttr:
                                tNode = None
                                tNode = algebra.Selection(newNode, eCond)
                                thisNode.parent = tNode
                                thisNode = tNode
        #############################################
            else:
                self.subTrees[tmp1[0][0]].parent = newNode
                del self.subTrees[tmp1[0][0]]
            if tmp1[0][1].find(' ') == -1:
                thisNode = None
                thisNode = algebra.Relation(newNode, tmp1[0][1])
        #############################################           # add selection node
                if tmp1[0][1] in self.statforS:
                    for e in self.statforS[tmp1[0][1]]:
                        seleAttr = e[0]
                        for eCond in self.forSelec:
                            if eCond.x.namespace == tmp1[0][1] and eCond.x.name == seleAttr:
                                tNode = None
                                tNode = algebra.Selection(newNode, eCond)
                                thisNode.parent = tNode
                                thisNode = tNode
        #############################################
            else:
                self.subTrees[tmp1[0][1]].parent = newNode
                del self.subTrees[tmp1[0][1]]
            # update the sub-tree dictionary
            self.subTrees[newRName] = newNode
            # update the statistic for join
            newRSize = tmp1[0][2]
            # add a new entry in the statforJ dictionary
            self.statforJ[newRName] = []
            self.statforJ[newRName].append(newRSize)
            data = {}   # data dictionary to temperarily store the variance information of the new post-join relation
            # determine the value of variance for each attribute of the new post-join relation
            for attr in self.statforJ[tmp1[0][0]][1].keys():
                if data.has_key(attr):
                    if self.statforJ[tmp1[0][0]][1][attr] < data[attr]:
                        data[attr] = self.statforJ[tmp1[0][0]][1][attr]
                else:
                    data[attr] = min(self.statforJ[tmp1[0][0]][1][attr], newRSize)
            for attr in self.statforJ[tmp1[0][1]][1].keys():
                if data.has_key(attr):
                    if self.statforJ[tmp1[0][1]][1][attr] < data[attr]:
                        data[attr] = self.statforJ[tmp1[0][1]][1][attr]
                else:
                    data[attr] = min(self.statforJ[tmp1[0][1]][1][attr], newRSize)
            self.statforJ[newRName].append(data)
            # delete the two entries for the relations been joined
            del self.statforJ[tmp1[0][0]]
            del self.statforJ[tmp1[0][1]]
            # update relation to be join
            self.relationTobeJoin.append(newRName)
            self.relationTobeJoin.remove(tmp1[0][0])
            self.relationTobeJoin.remove(tmp1[0][1])
            # for the new relationTobeJoin and new statistic for join, continue to do JoinOrder()

            newNode = JoinOrder()
            return newNode

        newTree = JoinOrder()

        def AddProject(newTree):
            newRoot = algebra.Projection(None, self.projFields)
            newTree.parent = newRoot
            return newRoot

        newTree = AddProject(newTree)
        return newTree


