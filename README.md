# ktransw
v0.0.1

A wrapper around Fanuc Robotics' command-line Karel translator (`ktrans.exe`)
that fakes support for multiple include paths by running `ktrans` from a
temporary directory containing a copy of the contents of the specified include
paths.


## Requirements

`ktransw` is written in Python 2, so naturally it needs a Python 2 install.

The script itself doesn't do any translation, so a copy of `ktrans.exe` (and
related libraries) is also needed.


## Installation

Clone this repository to your machine and add the directory containing
`ktransw.py` and `ktransw.cmd` to your `PATH`. Command sessions opened after
setting up the `PATH` should be able to successfully run `ktransw` from
anywhere.

Alternatively, don't change your `PATH`, but start `ktransw` by specifying
the full path on the command line.

For maximum convenience, make sure that `ktrans.exe` is also on the `PATH`.
`ktransw` does not try to locate `ktrans.exe` on it's own, so if it is not
on the `PATH`, its location must be provided by using the `--ktrans` command
line option with each invocation.


## Usage

```
usage: ktransw [-h] [-v] [-d] [-k] [--ktrans PATH] [-I PATH] [ARG [ARG ...]]

Version 0.0.1

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
  -d, --dry-run         Do everything except copying files and starting ktrans
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


## Future improvements

This tool might be migrated to a C/C++ implementation to avoid the overhead of
starting the Python interpreter.
