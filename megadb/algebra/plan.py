from megadb.tree import LeafNode, TreeNode

class Field(object):
    def __init__(self, full_name):
        full_name = full_name.split('.')
        if len(full_name) > 1:
            self.namespace = full_name[0]
            self.name = full_name[1]
        else:
            self.namespace = None
            self.name = full_name[0]

    def __repr__(self):
        if self.namespace:
            return 'Field(' + self.namespace + '.' + self.name + ')'
        else:
            return 'Field(' + self.name + ')'

    def __str__(self):
        if self.namespace:
            return '.'.join([self.namespace, self.name])
        else:
            return self.name

    def __eq__(self, other):
        if self.namespace is None or other.namespace is None:
            return self.name == other.name

        return self.name == other.name and self.namespace == other.namespace

    def __hash__(self):
        return hash((self.name, self.namespace))

    @classmethod
    def from_components(cls, name, namespace=None):
        if namespace:
            field_fullname = '.'.join([namespace, name])
        else:
            field_fullname = name
        return cls(field_fullname)

class Comparison(object):
    def __init__(self, x, y, comp):
        self.x = x
        self.y = y
        self.comp = comp

    def __repr__(self):
        return ' '.join([repr(x) for x in [self.x, self.comp, self.y]])

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

class CartesianProduct(TreeNode):
    def __init__(self, parent):
        super(CartesianProduct, self).__init__(parent)

    def __repr__(self):
        return "CartesianProduct"

class ThetaJoin(TreeNode):
    def __init__(self, parent, conds):
        super(ThetaJoin, self).__init__(parent)
        self.conds = conds

    def __repr__(self):
        return "ThetaJoin: " + str(self.conds)