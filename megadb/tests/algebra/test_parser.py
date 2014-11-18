import unittest
from megadb.algebra.parser import parse_sql, print_parse_tree

class ParserTestCase(unittest.TestCase):
    def test_parse_sql(self):
        def print_and_parse(stmt):
            print stmt
            tree = parse_sql(stmt)
            print_parse_tree(tree)

        print

        print_and_parse("SELECT title, a FROM StarsIn WHERE starName = name AND movieYear = 2008")
        print_and_parse("SELECT * FROM StarsIn, MovieStar, SomeTable WHERE starName = name AND birthAt = 2014")
        print_and_parse("SELECT office FROM Students, Depts WHERE Students.dept = Depts.name AND Students.name='Smith'")
        print_and_parse("SELECT R.B,D FROM R,S WHERE R.A='c' AND S.E=2 AND R.C = S.C")
        print_and_parse("SELECT office FROM Students, Depts WHERE Students.dept = Depts.name")
