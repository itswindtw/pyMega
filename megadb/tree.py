class HasParent(object):
    def __init__(self, parent):
        self.parent = parent

    @property
    def parent(self):
        return self._parent
    @parent.setter
    def parent(self, value):
        if getattr(self, '_parent', None):
            self._parent.children.remove(self)

        if value:
            value.children.append(self)

        self._parent = value

class LeafNode(HasParent):
    pass

class TreeNode(HasParent):
    def __init__(self, parent):
        super(TreeNode, self).__init__(parent)
        self.children = []
