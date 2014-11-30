pyMega
======================================

Install sqlparse (dep)
---------

    $ git clone git@github.com:itswindtw/sqlparse.git
    $ cd sqlparse
    $ python setup.py install

Run tests
---------

    $ cd pyMega
    $ python -m unittest discover -v


Test schema
-----------
    Colleges - Programs ------- Students
      |                             |
      |                           Grades
      |------- Courses -------\     |
      |                         Sessions
      |------- Professors-----/
