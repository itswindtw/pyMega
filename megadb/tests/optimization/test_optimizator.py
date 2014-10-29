import unittest

from megadb.algebra.parser import parse_sql, print_parse_tree
from megadb.optimization.optimizator import *

class PushSelectionDownOptimizatorTestCase(unittest.TestCase):
    def test_basic(self):
        tree = parse_sql("SELECT * FROM R, S, T WHERE R.a = S.a AND S.t = T.t AND R.a = 8")

        opt = PushSelectionDownOptimizator()
        print_parse_tree(opt.run(tree))

    def test_complex(self):
        tree = parse_sql("SELECT * FROM Professor, Course, Grade, Student  WHERE \
            Grade.StudentID = Student.ID AND Grade.CourseID = Course.ID AND Course.ProfessorID = Professor.ID AND \
            Student.GraduationYear = 2005 AND Course.Department = 'ECE' AND Professor.Department = 'CS'")

        opt = PushSelectionDownOptimizator()
        print_parse_tree(opt.run(tree))


class CartesianProductToThetaJoinOptimizatorTestCase(unittest.TestCase):
    def test_complex(self):
        tree = parse_sql("SELECT * FROM Professor, Course, Grade, Student  WHERE \
            Student.GraduationYear = 2005 AND Course.Department = 'ECE' AND Professor.Department = 'CS' \
            Grade.CourseID = Course.ID AND Course.ProfessorID = Professor.ID AND Grade.StudentID = Student.ID")

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator()

        print_parse_tree(join_opt.run(push_opt.run(tree)))

    def test_natural_join(self):
        tree = parse_sql("SELECT * FROM Professor, Course, Grade, Student WHERE \
            Grade.StudentID = Student.StudentID AND Grade.CourseID = Course.CourseID AND Course.ProfessorID = Professor.ProfessorID AND \
            Student.GraduationYear = 2005 AND Course.Department = 'ECE' AND Professor.Department = 'CS'")

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator()

        print_parse_tree(join_opt.run(push_opt.run(tree)))

class JoinOrderTestCase(unittest.TestCase):
    def test_enumerate_join_orders(self):
        tree = parse_sql("SELECT * FROM Professor, Course, Grade, Student WHERE \
            Grade.StudentID = Student.StudentID AND Grade.CourseID = Course.CourseID AND Course.ProfessorID = Professor.ProfessorID")
            # Student.GraduationYear = 2005 AND Course.Department = 'ECE' AND Professor.Department = 'CS'")
        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator()
        tree = join_opt.run(push_opt.run(tree))

        print "Join Order Enumeration:"
        print_parse_tree(tree)
        results = enumerate_join_orders(tree)

        for idx, t in enumerate(results):
            print "%d: " % (idx+1)
            print_parse_tree(t)


class HelperTestCase(unittest.TestCase):
    def test_clone_tree(self):
        tree = parse_sql("SELECT * FROM R, S, T WHERE R.a = S.a AND S.t = T.t AND R.a = 8")
        new_tree = clone_tree(tree)

        self.assertIsNot(tree, new_tree)
        self.assertIsNot(tree.fields, new_tree.fields)
        self.assertIsNot(tree.children[0].children[0].parent, new_tree.children[0].children[0].parent)

        # print_parse_tree(tree)
        # print_parse_tree(new_tree)

    def test_clone_parital_tree(self):
        tree = parse_sql("SELECT * FROM R, S, T")
        join = tree.children[0].children[0]

        old_parent = tree
        new_parent = clone_partial_tree(join)

        new_join = clone_tree(join)
        new_join.parent = new_parent
        new_root = new_parent.parent

        self.assertIsNot(old_parent, new_parent)
        self.assertIsNot(new_join, join)
        self.assertIsNot(new_join.parent, join.parent)

