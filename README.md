# ktransw
v0.2.4

A wrapper around Fanuc Robotics' command-line Karel translator (`ktrans.exe`)
that makes it work a little more like a modern compiler by adding some missing
functionality (like support for multiple include paths and dependency file
generation).

As of v0.2.4 support for FANUC dictionaries and forms has been added to support preprocessor directives, multiple include paths, and functionality to build using [rossum][].


## Requirements

`ktransw` is written in Python 3, so naturally it needs a Python 3 install.

The script itself doesn't do any translation, so a copy of `ktrans.exe` (and
related libraries) is also needed.

Finally, pre-processing is handled by a patched version of Tristan Miller's
GPP (the "Generic PreProcessor").


## Installation

Clone this repository to your machine (or download any of the [releases][])
and add the directory containing `ktransw.py`/`ktransw.cmd` and `kcdictw.py`/`kcdictw.cmd` to your `PATH`.
Command sessions opened after setting up the `PATH` should be able to
successfully run `ktransw` from anywhere.

Alternatively, don't change your `PATH`, but start `ktransw` by specifying
the full path on the command line.

For maximum convenience, make sure that `ktrans.exe` is also on the `PATH`.
`ktransw` does not try to locate `ktrans.exe` on its own, so if it is not
on the `PATH`, its location must be provided by using the `--ktrans` command
line option with each invocation.

Download the latest binary release from [gpp releases][], and place it on
the `PATH`. If `gpp.exe` cannot be placed on the path, the `--gpp` command
line option may be used to tell `ktransw` where it is.


## Usage

```
usage: ktransw [-h] [-v] [-q] [-d] [-E] [-M] [-MM] [-MT target] [-MF file]
               [-MG] [-MP] [--ktrans PATH] [--gpp PATH] [-I PATH]
               [ARG [ARG ...]]

Version 0.2.3

A wrapper around Fanuc Robotics' command-line Karel translator (ktrans.exe)
that adds a C-like preprocessor, support for multiple include directories,
conditional compilation, include guards, macros and more.

positional arguments:
  ARG                   Arguments to pass on to ktrans. Use normal (forward-
                        slash) notation here

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Print (lots of) debug information
  -q, --quiet           Print nothing, except when ktrans encounters an error
  -d, --dry-run         Do nothing, except checking parameters
  -E                    Preprocess only; do not translate
  -M                    Output GCC compatible dependency file
  -MM                   Like '-M', but don't include system headers
  -MT target            Change the target of the rule emitted by dependency
                        generation (default: base name of source, with object
                        extension (.pc))
  -MF file              When used with -M or -MM, specifies a file to write the
                        dependencies to.
  -MG                   Assume missing header files are generated files and add them
                        to the dependency list without raising an error
  -MP                   Add a phony target for each dependency to support renaming
                        dependencies without having to update the Makefile to match
  -k, --keep-build-dir  Don't delete the temporary build directory on exit
  --ktrans PATH         Location of ktrans (by default ktransw assumes it's on the
                        Windows PATH)
  --gpp PATH            Location of gpp (by default ktransw assumes it's on the
                        Windows PATH)
  -I PATH               Include paths (multiple allowed)
  -D  /D                Define user macros from command line

Example invocation:

  ktransw /IC:\foo\bar\include /IC:\baz\include C:\my_prog.kl /config robot.ini

All arguments using forward-slash notation (except '/I') are passed on
to ktrans.
```


## Examples

### As ktrans stand-in

`ktransw` is supposed to be a transparent wrapper around `ktrans.exe`. Refer
for more information on the use of `ktrans.exe` to the relevant Fanuc Robotics
manuals.

See also [rossum][].

### Using the pre-processor

See the [gpp documentation][] for more information.

## \%class pre-processor directive

Object construction or generic templating can be achieved with the \%class
directive, and proper formatting:

```
%class <class-name>('<class-file>.klc','<class-header>.klh','<template-file>.klt')
```

**Note** : the *.klt* file is optional, used for creating generic templates but is 
not needed for creating a class.

See [bank_class] test in [rossum_example_ws](https://github.com/kobbled/rossum_example_ws) 
to see how to format classes.

**Note** : Take note of the usage of instances of `class_name`. This is a pre-processor
macro that will be replaced with the class name defined in %class for each object.

In *ktransw* objects are first created with pure gpp:

```
%defeval class_name <class-name>
%include <template-file>.klt
%include <class-file>.klc
```

Running these files through a few cycles of GPP will flatten and replace preprocessor
directives with their defined karel code. The user is responsible for managing the 
namespacing and scoping of members/attributes. The user can do this as they wish by defining 
multiple header files, one for usage only in **\%class**, and another for outside of the 
object instantantiation to give member visibility to the main program. The user can also 
choose to follow the method in [bank_class] which leverages a third party package [ktransw-macros]. 
The only thing that is required is that `class_name` is included in the *.klc*, and *.klh* 
file for each routine, and program definition so that they resolve to the same definition as 
outside of the class scope.

**Note** : If you are building to roboguide < v9.10, you might have a 12 character limit for
definitions. In this case it is advisable to use [ktransw-macros], and the \<class_name\>\_\_\<function\>
namespacing technique, giving short alias names to each function.

**Note** : Processing of **\%class** directives assumes extensive use of GPP mode:

```
%mode string QQQ "`" "`" "\\"
```

Using specifically the **\`** char for defining multi-line GPP functions to comply with the
current GPP syntax definition:

```python
'+z',       # Set text mode to Unix mode (LF terminator)

'--includemarker "-- INCLUDE_MARKER %:%:%"',
          # line:file:op

'-U',       # User-defined mode
'""',       # the macro start sequence
'""',       # the macro end sequence for a call without arguments
'"("',      # the argument start sequence
'","',      # the argument separator
'")"',      # the argument end sequence
'"("',      # the list of characters to stack for argument balancing
'")"',      # the list of characters to unstack
'"#"',      # the string to be used for referring to an argument by number
'""',       # and finally the quote character (escapes embedded string chars)

'-M',       # User-defined mode specifications for meta-macros
'"\\n%\w"', # the macro start sequence
'"\\n"',    # the macro end sequence for a call without arguments
'" "',      # the argument start sequence
'" "',      # the argument separator
'"\\n"',    # the argument end sequence
'""',       # the list of characters to stack for argument balancing
'""',       # and the list of characters to unstack
```

This is done as a return character cannot be used to seperate a pre-processor function
without conflicting with karel. The **\`** string mode is incorperated into *ktransw* 
in order to dispose of the leftover **\`** chars to resolve nested macros.

## \%from \<file-name\> \%import <function>, <function>, etc...

A "from/import" custom directive similar to that in python is included with ktransw. This
is done to decrease the size of compiled .pc files, as the ktrans compiler does not exclude
routines from an \%include file that do not link to any routine calls in the program being
compiled.

## user macros

Pre-processor macros can be defined from the command line invoking **-D***name=val*, or **/D***name=val*. See [GPP documentation][GPP].

## kcdictw

A wrapper tool for kcdict is also included in this package called `kcdictw`. This tool will compress the **.ftx**, or **.utx** dictionary
file into the temp directory, %TEMP%, and copy over the output **.tx**, **.vr** into the working directory, and the **.kl** karel include file into the root directory of the **.ftx** or **.utx** file. If you would like to keep the other **.ftx** files created by kcdict, use the **--keep-build-dir** option as to not delete the temp folder, where yo u can manually copy over the files after.

## FAQ

#### Does this run on Windows?
Yes, it only runs on Windows, actually.

If you know of a way to run `ktrans.exe` under Linux, I'd be interested.

#### Is Roboguide (still) needed?
`ktransw` only wraps `ktrans.exe`, it does not replace it or Roboguide, so
depending on your project's requirements (is it Karel only? Do you need to
translate TP programs, etc), yes, you still need Roboguide.

#### What about backwards compatibility with non-ktransw users?
Backwards compatibility is currently not guaranteed, as the functionality
provided by the pre-processor cannot be duplicated by plain `ktrans`. With
care, avoiding multiple inclusions of the same file would be possible, but
that would seriously hamper the development of stand-alone, re-usable
libraries (as the including entity would be made responsible for tracking
includes and making sure that all required definitions are available at
translation time).

In cases where plain `ktrans` must be used, it should be possible to use
`ktransw`s `-E` command line option: this will make `ktransw` only pre-process
the input file, without doing any translation. The resulting output is a
completely flattened file, without any pre-processor directives. `ktrans` and
Roboguide should be able to translate this.

#### I let A include B, which includes C. A also include C. Now I get errors
Make sure to include the appropriate *include guards*, to avoid problems with
multiple inclusion of headers. The pre-processor supports the typical `%IFNDEF`,
`%DEFINE`, `%ENDIF` pattern as is common in C/C++ headers. Either wrap
`%INCLUDE` directives in such conditionals, or add them to the respective
headers.

For headers that cannot be changed (or are not supposed to be changed),
wrapping `%INCLUDE` directives is recommended.

(for the headers distributed by Fanuc in the support directories (kliotyps.kl
and friends), see the [fr_hdrs][] convenience package)


## Future improvements

This tool might be migrated to a C/C++ implementation to avoid the overhead of
starting the Python interpreter.

Backward compatibility with plain `ktrans` would be nice to restore. A
carefully chosen notation for the new pre-processor directives might allow
for this.


## Disclaimer

WinOLPC, OlpcPRO and Roboguide are products of Fanuc America Corporation. The
author of `ktransw` is not affiliated with Fanuc in any way.



[releases]: https://github.com/gavanderhoorn/ktransw_py/releases
[gpp releases]: https://github.com/gavanderhoorn/gpp/releases
[rossum]: https://github.com/gavanderhoorn/rossum
[gpp documentation]: https://logological.org/gpp
[fr_hdrs]: https://github.com/gavanderhoorn/fr_hdrs
[bank_class]: https://github.com/kobbled/rossum_example_ws/tree/master/src/bank_class
[ktransw-macros]: https://github.com/kobbled/ktransw-macros
