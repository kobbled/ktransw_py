# ktransw
v0.1.2

A wrapper around Fanuc Robotics' command-line Karel translator (`ktrans.exe`)
that makes it work a little more like a modern compiler by adding some missing
functionality (like support for multiple include paths and dependency file
generation).


## Requirements

`ktransw` is written in Python 2, so naturally it needs a Python 2 install.

The script itself doesn't do any translation, so a copy of `ktrans.exe` (and
related libraries) is also needed.


## Installation

Clone this repository to your machine (or download any of the [releases][])
and add the directory containing `ktransw.py` and `ktransw.cmd` to your `PATH`.
Command sessions opened after setting up the `PATH` should be able to
successfully run `ktransw` from anywhere.

Alternatively, don't change your `PATH`, but start `ktransw` by specifying
the full path on the command line.

For maximum convenience, make sure that `ktrans.exe` is also on the `PATH`.
`ktransw` does not try to locate `ktrans.exe` on its own, so if it is not
on the `PATH`, its location must be provided by using the `--ktrans` command
line option with each invocation.


## Usage

```
usage: ktransw [-h] [-v] [-q] [-d] [-M] [-MM] [-MT target] [-MF file] [-MG]
               [-MP] [-k] [--ktrans PATH] [-I PATH]
               [ARG [ARG ...]]

Version 0.1.2

A wrapper around Fanuc Robotics' command-line Karel translator (ktrans.exe)
that fakes support for multiple include paths by running ktrans.exe from a
temporary directory containing a copy of the contents of the specified
include paths.

positional arguments:
  ARG                   Arguments to pass on to ktrans. Use normal (forward-
                        slash) notation here

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Print (lots of) debug information
  -q, --quiet           Print nothing, except when ktrans encounters an error
  -d, --dry-run         Do everything except copying files and starting ktrans
  -M                    Output GCC compatible dependency file
  -MM                   Like '-M', but don't include system headers
  -MT target            Change the target of the rule emitted by dependency
                        generation (default: base name of source, with object
                        extension (.pc))
  -MF file              When used with -M or -MM, specifies a file to write
                        the dependencies to.
  -MG                   Assume missing header files are generated files and
                        add them to the dependency list without raising an
                        error
  -MP                   Add a phony target for each dependency to support
                        renaming dependencies without having to update the
                        Makefile to match
  -k, --keep-build-dir  Don't delete the temporary build directory on exit
  --ktrans PATH         Location of ktrans (by default ktransw assumes it's on
                        the Windows PATH)
  -I PATH               Include paths (multiple allowed)

Example invocation:

  ktransw /IC:\foo\bar\include /IC:\baz\include C:\my_prog.kl /config robot.ini

All arguments using forward-slash notation (except '/I') are passed on
to ktrans.
```


## Examples

`ktransw` is supposed to be a transparent wrapper around `ktrans.exe`. Refer
for more information on the use of `ktrans.exe` to the relevant Fanuc Robotics
manuals.

See also [rossum][].


## FAQ

#### Does this run on Windows?
Yes, it only runs on Windows, actually.

#### Is Roboguide (still) needed?
`ktransw` only wraps `ktrans.exe`, it does not replace it or Roboguide, so
depending on your project's requirements (is it Karel only? Do you need to
translate TP programs, etc), yes, you still need Roboguide.

#### This is not a solution, it looks more like a work around?
Well, yes, true. That is also stated in the *Overview* section. `ktrans.exe` is
developed by Fanuc, and I don't have any special access to it, nor to any
other parts of Roboguide or related infrastructure. This means we'll have to
make do with what we have.

If you know of a better work-around (or even a real solution), please contact
me.

#### How about backwards compatibility with non-ktransw users?
There are two situations to consider: manually invoking `ktrans.exe` on the
command line, and compiling Karel sources in Roboguide.

As for Roboguide: it actually supports multiple include paths natively, so all
that would be needed to be able to translate the sources would be to add the
`include` directory to a workcell's *include path*. This can easily be
done by selecting the *Set Extra Includes* option from the *Cell Browser*
context-menu. See the Roboguide help for more information.

When not using Roboguide, just copy the directory *inside* the `include`
directory to your project directory. Compilation should now work as usual.

#### I let A include B, which includes C. A also include C. Now I get errors
As `ktrans` doesn't support the concept of *include guards*, it's impossible
to protect against multiple inclusion of the same header (or of any file that
gets included: Karel doesn't really have a header concept). In practice this
means that anything that is intended to be included in something else (ie:
headers or code fragments) cannot themselves `%INCLUDE` something, or they
run the risk of introducing redefinition errors into the program they are
included in.

A current work-around is to delegate the responsibility of including the
required headers to *top-level* artefacts (such as programs), but those will
have to do a recursive `%INCLUDE` of all headers required for all dependencies,
*and their dependencies*.

[issue 7][] asks for the inclusion of a pre-processor, which would allow to use
include guards to avoid multiple inclusion.


## Future improvements

This tool might be migrated to a C/C++ implementation to avoid the overhead of
starting the Python interpreter.


## Disclaimer

WinOLPC, OlpcPRO and Roboguide are products of Fanuc America Corporation. The
author of `ktransw` is not affiliated with Fanuc in any way.



[releases]: https://github.com/gavanderhoorn/ktransw_py/releases
[rossum]: https://github.com/gavanderhoorn/rossum
[issue 7]: https://github.com/gavanderhoorn/ktransw_py/issues/7
