import unittest
from megadb.algebra.parser import parse_sql, print_parse_tree

class ParserTestCase(unittest.TestCase):
    def test_parse_sql(self):
        print

        tree = parse_sql("SELECT title, a FROM StarsIn WHERE starName = name AND movieYear = 2008")
        print_parse_tree(tree)

        tree = parse_sql("SELECT * FROM StarsIn, MovieStar, SomeTable WHERE starName = name AND birthAt = 2014")
        print_parse_tree(tree)

        tree = parse_sql("SELECT office FROM Students, Depts WHERE Students.dept = Depts.name AND Students.name='Smith'")
        print_parse_tree(tree)

        tree = parse_sql("SELECT B,D FROM R,S WHERE R.A='c' AND S.E=2 AND R.C = S.C")
        print_parse_tree(tree)