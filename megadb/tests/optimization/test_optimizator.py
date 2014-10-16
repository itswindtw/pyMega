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
            Grade.StudentID = Student.ID AND Grade.CourseID = Course.ID AND Course.ProfessorID = Professor.ID AND \
            Student.GraduationYear = 2005 AND Course.Department = 'ECE' AND Professor.Department = 'CS'")

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator()

        print_parse_tree(join_opt.run(push_opt.run(tree)))

