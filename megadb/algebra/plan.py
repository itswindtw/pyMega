from megadb.tree import LeafNode, TreeNode

class Comparison(object):
    def __init__(self, x, y, comp):
        self.x = x
        self.y = y
        self.comp = comp

    def __repr__(self):
        return ' '.join([str(x) for x in [self.x, self.comp, self.y]])

###

class Relation(LeafNode):
    def __init__(self, parent, name):
        super(Relation, self).__init__(parent)
        self.name = name

    def __repr__(self):
        return "Relation:" + str(self.name)

###

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