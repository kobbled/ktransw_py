
from ktransw import scan_for_inc_stmts


def test_bare_includes():
    inc_path = 'foo'
    incs = scan_for_inc_stmts('%INCLUDE ' + inc_path)
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo\bar'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo\bar\baz'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs


def test_includes_with_extension():
    inc_path = 'foo.h'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo\bar.h'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo\bar\baz.h'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo\bar\\baz.h'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs


def test_includes_with_double_extension():
    inc_path = 'baz.baz.h'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'baz.baz.k.h'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs

    # illegal, but ok
    inc_path = 'baz.baz.k.h.j.y.s.f.r.w..ddd.d.d.t..u.a.zzz.zz.uu'
    incs = scan_for_inc_stmts('\n%INCLUDE ' + inc_path + '\n')
    assert len(incs) == 1
    assert inc_path in incs


def test_whitespace():
    inc_path = 'foo\bar.h'
    incs = scan_for_inc_stmts('%INCLUDE       ' + inc_path)
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo\bar.h'
    incs = scan_for_inc_stmts('    %INCLUDE       ' + inc_path + '    ')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo\bar.h'
    incs = scan_for_inc_stmts(' \n  \n  \t\t \n \t\t%INCLUDE\t\t' + inc_path + '  \t    ')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'foo\bar.h'
    incs = scan_for_inc_stmts('%INCLUDE\t  \t' + inc_path)
    assert len(incs) == 1
    assert inc_path in incs

    # but whitespace *inside* paths is illegal, and should not be stripped,
    # but it won't match correctly either
    inc_path = 'foo\  bar.h'
    incs = scan_for_inc_stmts('%INCLUDE\t  \t' + inc_path)
    assert len(incs) == 1
    assert 'foo\\' in incs


def test_comments():
    # no space between filename and comment: illegal in ktrans
    inc_path = 'baz.h'
    incs = scan_for_inc_stmts('%INCLUDE ' + inc_path + '-- this is a comment')
    assert len(incs) == 1
    assert inc_path + '--' in incs

    inc_path = 'baz.h'
    incs = scan_for_inc_stmts('  \t\n\t%INCLUDE\t  \t' + inc_path + ' -- this is a comment')
    assert len(incs) == 1
    assert inc_path in incs

    inc_path = 'baz.h'
    incs = scan_for_inc_stmts('--%INCLUDE ' + inc_path + ' -- this is a comment')
    assert len(incs) == 0

    inc_path = 'baz.h'
    incs = scan_for_inc_stmts('--    %INCLUDE ' + inc_path)
    assert len(incs) == 0

    inc_path = 'baz.h'
    incs = scan_for_inc_stmts('    -- %INCLUDE ' + inc_path)
    assert len(incs) == 0

    inc_path = 'baz.h'
    incs = scan_for_inc_stmts('\t  \t   -- %INCLUDE ' + inc_path)
    assert len(incs) == 0


def test_multiple_lines():
    inc_paths = ['foo.h', 'bar.th']
    incs = scan_for_inc_stmts('\n'.join(['%INCLUDE ' + p for p in inc_paths]))
    assert len(incs) == len(inc_paths)
    assert inc_paths <= incs and inc_paths >= incs

    inc_paths = ['foo.h', 'bar.th', 'long_filename_with_underscores.h.hh', r'some\nested\path\and_underscore.kl']
    incs = scan_for_inc_stmts('\n'.join(['  \t\n\t%INCLUDE ' + p + ' -- this is a comment' for p in inc_paths]))
    assert len(incs) == len(inc_paths)
    assert inc_paths <= incs and inc_paths >= incs

    inc_paths = ['foo.h', 'bar.th']
    inc_stmts = ['%INCLUDE ' + p for p in inc_paths]
    inc_stmts.extend(['--%INCLUDE baz.th', '--%INCLUDE baz2.th -- another comment'])
    inc_stmts.extend(['-- %INCLUDE baz.th', ' \t  --%INCLUDE baz2.th'])
    incs = scan_for_inc_stmts('\n'.join(inc_stmts))
    assert len(incs) == len(inc_paths)
    assert inc_paths <= incs and inc_paths >= incs
