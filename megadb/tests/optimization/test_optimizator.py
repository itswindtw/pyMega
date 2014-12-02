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
    def test_easy_1(self):
        tree = parse_sql("SELECT * FROM A, B, C WHERE A.b = B.b AND B.c = C.c AND A.a = C.a")

        test_stats = {
            'A': [1, {'a': 1, 'b': 1}],
            'B': [1, {'b': 1, 'c': 1}],
            'C': [1, {'c': 1, 'a': 1}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        print_parse_tree(join_opt.run(push_opt.run(tree)))

    def test_easy_2(self):
        tree = parse_sql("SELECT * FROM B, C, A WHERE A.b = B.b AND A.a = C.a")

        test_stats = {
            'A': [1, {'a': 1, 'b': 1}],
            'B': [1, {'b': 1, 'c': 1}],
            'C': [1, {'a': 1}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        print_parse_tree(join_opt.run(push_opt.run(tree)))


    def test_complex(self):
        tree = parse_sql("SELECT * FROM Professor, Course, Grade, Student  WHERE \
            Student.GraduationYear = 2005 AND Course.Department = 'ECE' AND Professor.Department = 'CS' \
            Grade.CourseID = Course.ID AND Course.ProfessorID = Professor.ID AND Grade.StudentID = Student.ID")

        test_stats = {
            'Student':      [1000, {'GraduationYear': 100, 'ID': 100}],
            'Course':       [1000, {'Department': 100, 'ProfessorID': 100}],
            'Professor':    [ 100, {'Department': 100, 'ID':  10}],
            'Grade':        [ 100, {'CourseID':  10, 'StudentID': 100}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        print_parse_tree(join_opt.run(push_opt.run(tree)))

    def test_natural_join(self):
        tree = parse_sql("SELECT * FROM Professor, Course, Grade, Student WHERE \
            Grade.StudentID = Student.StudentID AND Grade.CourseID = Course.CourseID AND Course.ProfessorID = Professor.ProfessorID AND Course.Department = Professor.Department AND \
            Student.GraduationYear = 2005 AND Course.Department = 'ECE' AND Professor.Department = 'CS'")

        test_stats = {
            'Student':      [1000, {'GraduationYear': 100, 'StudentID': 100}],
            'Course':       [1000, {'Department': 100, 'CourseID': 3, 'ProfessorID': 100}],
            'Professor':    [ 100, {'Department': 100, 'ProfessorID':  10}],
            'Grade':        [ 100, {'CourseID':  10, 'StudentID': 100}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        print_parse_tree(join_opt.run(push_opt.run(tree)))

class JoinOrderTestCase(unittest.TestCase):
    def test_simple_case(self):
        tree = parse_sql("SELECT * FROM A, B, C WHERE A.b = B.b AND A.a = C.a")

        test_stats = {
            'A': [1, {'a': 1, 'b': 1}],
            'B': [1, {'b': 1, 'c': 1}],
            'C': [1, {'a': 1}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)
        tree = join_opt.run(push_opt.run(tree))

        print "Join Order Enumeration:"
        print_parse_tree(tree)
        results = enumerate_join_orders(tree)

        for idx, t in enumerate(results):
            print "%d: " % (idx+1)
            print_parse_tree(t)

    def test_enumerate_join_orders(self):
        tree = parse_sql("SELECT * FROM Professor, Course, Grade, Student, Test WHERE \
            Grade.StudentID = Student.StudentID AND Grade.CourseID = Course.CourseID AND Course.ProfessorID = Professor.ProfessorID AND Test.TestID = Course.TestID")
            # Student.GraduationYear = 2005 AND Course.Department = 'ECE' AND Professor.Department = 'CS'")

        test_stats = {
            'Student':      [1000, {'GraduationYear': 100, 'StudentID': 100}],
            'Course':       [1000, {'Department': 100, 'ProfessorID': 100, 'TestID': 3}],
            'Professor':    [ 100, {'Department': 100, 'ProfessorID':  10}],
            'Grade':        [ 100, {'CourseID':  10, 'StudentID': 100}],
            'Test':         [ 100, {'TestID': 1}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)
        tree = join_opt.run(push_opt.run(tree))

        print "Join Order Enumeration:"
        print_parse_tree(tree)
        results = enumerate_join_orders(tree)

        for idx, t in enumerate(results):
            print "%d: " % (idx+1)
            print_parse_tree(t)


class SelectivityTestCase(unittest.TestCase):
    def test_enumerate_selections(self):
        tree = parse_sql("SELECT * FROM Student, Professor WHERE \
            Student.StudentID = 123456789 AND Student.Name = 'Ohmygod' AND Student.Age = 25 \
            Professor.Name = 'SomeOne' AND Professor.ProfessorID = 1234")

        push_opt = PushSelectionDownOptimizator()
        tree = push_opt.run(tree)

        results = enumerate_selections(tree)

        for idx, t in enumerate(results):
            print "%d: " % (idx+1)
            print_parse_tree(t)


class GreedyJoinOrderOptimizatorTestCase(unittest.TestCase):
    def test_easy(self):
        tree = parse_sql("SELECT * FROM R, S, T, U WHERE \
            R.b = S.b AND S.c = T.c AND T.d = U.d AND U.a = R.a")

        print_parse_tree(tree)

        test_stats = {
            'R': [1000, {'a': 100, 'b': 100}],
            'U': [1000, {'a': 100, 'd': 100}],
            'S': [ 100, {'b': 100, 'c':  10}],
            'T': [ 100, {'c':  10, 'd': 100}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        tree = push_opt.run(tree)
        # print_parse_tree(tree)
        tree = join_opt.run(tree)
        # print_parse_tree(tree)

        print "GreedyJoinOrder: "
        greedy_opt = GreedyJoinOrderOptimizator(test_stats)
        print_parse_tree(greedy_opt.run(tree))

class EnumerationBasedOptimizatorTestCase(unittest.TestCase):
    def test_single(self):
        tree = parse_sql("SELECT * FROM A WHERE A.a = 3 AND A.b = 2 AND A.c = 3")

        test_stats = {
            'A': [100, {'a': 100, 'b': 50, 'c': 3}]
        }
        
        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        tree = push_opt.run(tree)
        # print_parse_tree(tree)
        tree = join_opt.run(tree)
        # print_parse_tree(tree)

        print "JoinOrderEnumeration: "
        greedy_opt = EnumerationBasedOptimizator(test_stats)
        print_parse_tree(greedy_opt.run(tree))

    def test_easy(self):
        tree = parse_sql("SELECT * FROM R, S, T, U WHERE \
            R.b = S.b AND S.c = T.c AND T.d = U.d AND U.a = R.a")

        print_parse_tree(tree)

        test_stats = {
            'R': [1000, {'a': 100, 'b': 100}],
            'U': [1000, {'a': 100, 'd': 100}],
            'S': [ 100, {'b': 100, 'c':  10}],
            'T': [ 100, {'c':  10, 'd': 100}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        tree = push_opt.run(tree)
        # print_parse_tree(tree)
        tree = join_opt.run(tree)
        # print_parse_tree(tree)

        print "JoinOrderEnumeration: "
        greedy_opt = EnumerationBasedOptimizator(test_stats)
        print_parse_tree(greedy_opt.run(tree))

    def test_easy_with_selectivity(self):
        tree = parse_sql("SELECT * FROM R, S, T, U WHERE \
            R.a = 3 AND S.b = 5 AND S.c = 1 AND \
            R.b = S.b AND S.c = T.c AND T.d = U.d AND U.a = R.a")

        print_parse_tree(tree)

        test_stats = {
            'R': [1000, {'a': 100, 'b': 100}],
            'U': [1000, {'a': 100, 'd': 100}],
            'S': [ 100, {'b': 100, 'c':  10}],
            'T': [ 100, {'c':  10, 'd': 100}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        tree = push_opt.run(tree)
        # print_parse_tree(tree)
        tree = join_opt.run(tree)
        # print_parse_tree(tree)

        print "JoinOrderEnumeration: "
        greedy_opt = EnumerationBasedOptimizator(test_stats)
        print_parse_tree(greedy_opt.run(tree))

class GreedyOptimizatorTestCase(unittest.TestCase):
    def test_single(self):
        tree = parse_sql("SELECT * FROM A WHERE A.a = 3 AND A.b = 2 AND A.c = 3")

        test_stats = {
            'A': [100, {'a': 100, 'b': 50, 'c': 3}]
        }
        
        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        tree = push_opt.run(tree)
        # print_parse_tree(tree)
        tree = join_opt.run(tree)
        # print_parse_tree(tree)

        print "GreedyOptimizator: "
        greedy_opt = GreedyOptimizator(test_stats)
        print_parse_tree(greedy_opt.run(tree))


    def test_easy(self):
        #tree = parse_sql("SELECT title, a FROM StarsIn, Movies, MovieStars, Hello WHERE \
        #    Hello.MovieYear = MovieStars.MovieYear AND Hello.StarName = MovieStars.StarName AND \
        #    StarsIn.MovieName = Movies.MovieName AND \
        #    MovieStars.StarName = StarsIn.StarName AND MovieStars.MovieYear = Movies.MovieYear AND \
        #    Movies.MovieYear = 2008 AND Movies.MovieName = 'King Kong'")
        tree = parse_sql("SELECT Students.StudentName, Students.StudentId \
            FROM Students, Grades, Sessions, Programs \
            WHERE Grades.StudentId = Students.StudentId AND Grades.SessionId = Sessions.SessionId AND Sessions.year = 2014 AND Grades.grade = 'A' AND Programs.ProgramId = Students.ProgramId AND Programs.ProgramName = 'Computer Science'")

        print_parse_tree(tree)

        test_stats = {
            'Colleges': [6, {'CollegeId': 6, 'CollegeName': 6}],
            'Courses': [100, {'CourseId': 100, 'CourseName': 91, 'CollegeId': 6}],
            'Grades': [1812, {'GradeId': 1812, 'SessionId': 250, 'StudentId': 900, 'grade': 5}],
            'Professors': [250, {'ProfessorId': 250, 'ProfessorName': 250, 'CollegeId': 6}],
            'Programs': [34, {'ProgramId': 34, 'ProgramName': 34, 'CollegeId': 6}],
            'Sessions': [250, {'SessionId': 250, 'year': 5, 'place': 7, 'ProfessorId': 150, 'CourseId': 92}],
            'Students': [900, {'StudentId': 900, 'StudentName': 900, 'StudentGender': 2, 'StudentDegree': 3, 'ProgramId': 34}]
        }

        push_opt = PushSelectionDownOptimizator()
        join_opt = CartesianProductToThetaJoinOptimizator(test_stats)

        tree = push_opt.run(tree)
        # print_parse_tree(tree)
        tree = join_opt.run(tree)
        print_parse_tree(tree)

        print "GreedyOptimizator: "
        greedy_opt = GreedyOptimizator(test_stats)
        print_parse_tree(greedy_opt.run(tree))


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

    def test_convert_cascading_selections(self):
        tree = parse_sql("SELECT * FROM R WHERE R.a = 1")
        print_parse_tree(tree)

        convert_cascading_selections(tree)
        print_parse_tree(tree)
        
