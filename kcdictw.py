#
# Copyright (c) 2020, kobbled
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import sys
import argparse
import subprocess
import shutil
import logging
import re
import yaml

KCDICTW_VERSION='0.0.1'
KCDICT_BIN_NAME='kcdict.exe'
GPP_BIN_NAME='gpp.exe'
_OS_EX_DATAERR=65
FORM_SUFFIX = '.ftx'
DICT_SUFFIX = '.utx'
COMPRESSED_SUFFIX = '.tx'

FILE_MANIFEST = '.man_log'

EXT_MAP = {
      '.kl' : {'conversion' : '.pc'},
      '.vr' : {'conversion' : '.vr'},
      '.ftx' : {'conversion' : '.tx'},
      '.utx' : {'conversion' : '.tx'}
    }

#store files to run through kcdict
dict_files = []
#list to store header injections
header_injections = []

def main():
  """Shell wrapper for compressing .utx of .ftx files in a rossum environment
  """

  description=("Version {0}\n\n"
        "A wrapper around FANUC's kcdict compressor ({1})\n"
            .format(KCDICTW_VERSION, KCDICT_BIN_NAME))

  epilog=("Usage example:\n\n"
        "  kcdict <name>.utx <output_name>.tx /IC:\\baz\\include /config robot.ini")

  parser = argparse.ArgumentParser(prog='kcdictw', description=description,
        epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
        help='Print (lots of) debug information')
  parser.add_argument('-q', '--quiet', action='store_true', dest='quiet',
        help='Print nothing, except when ktrans encounters an error')
  parser.add_argument('-k', '--keep-build-dir', action='store_true',
        dest='keep_buildd', help="Don't delete the temporary build directory "
            "on exit")
  parser.add_argument('--kcdict', type=str, dest='kcdict_path', metavar='PATH',
      help="Location of kcdict (by default kcdictw assumes it's on the "
          "Windows PATH)")
  parser.add_argument('-E', action='store_true', dest='output_ppd_source',
        help="Preprocess only; do not translate")
  parser.add_argument('--gpp', type=str, dest='gpp_path', metavar='PATH',
      help="Location of gpp (by default ktransw assumes it's on the "
          "Windows PATH)")
  parser.add_argument('-I', action='append', type=str, dest='include_dirs',
        metavar='PATH', default=[], help='Include paths (multiple allowed)')
  parser.add_argument('kcdict_args', type=str, nargs='*', metavar='ARG',
        help="Arguments to pass on to kcdict. Use normal (forward-slash) "
        "notation here")
  
  # support forward-slash arg notation for include dirs
  for i in range(1, len(sys.argv)):
      if sys.argv[i].startswith('/I'):
          sys.argv[i] = sys.argv[i].replace('/I', '-I', 1)
  args = parser.parse_args()

  # we expect ktrans to be on the path. If it's not, user should have
  # provided an alternative location
  kcdict_path = os.path.abspath(args.kcdict_path) if args.kcdict_path else KCDICT_BIN_NAME

  # we expect gpp to be on the path. If it's not, user should have
  # provided an alternative location
  gpp_path = os.path.abspath(args.gpp_path) if args.gpp_path else GPP_BIN_NAME

  # extract args which refer to KAREL sources: we can just search for
  # arguments with '.kl' in it, as ktrans only considers files with that
  # extension.
  pre_gpp_files = []
  for arg in args.kcdict_args:
    if arg.endswith(FORM_SUFFIX) or arg.endswith(DICT_SUFFIX):
      pre_gpp_files.append(arg)
  
  # assume there's only one input source file (or: we ignore all others)
  kl_file = pre_gpp_files[0]

  # create temporary directory to store preprocessed file in. We
  # avoid problems with temporary files (via NamedTemporaryFile fi) being
  # not readable by other processes in this way.
  with TemporaryDirectory(prefix='kcdictw-', suffix='-buildd', do_clean=(not args.keep_buildd)) as dname:
    fname = os.path.join(dname, os.path.basename(kl_file))

    pre_file = os.path.join(dname, 'pre-' + os.path.basename(kl_file))
    run_gpp(kl_file, pre_file, args)
    remove_blank_lines(pre_file)
    #do final gpp pass
    run_gpp(pre_file, fname, args)

    #append processed file to ktrans list
    dict_files.append(fname)

    # target name we use is 'base source file name + .pc', OR the name
    # provided as a command line arg
    base_source_name = os.path.basename(os.path.splitext(kl_file)[0])
    target = dname + '\\' + base_source_name + COMPRESSED_SUFFIX
    # get include folder of local repository to plave .kl files in.
    # These are needed for the karel programs that accompany the .ftx file
    kl_dir = ''
    for inc in args.include_dirs:
      if os.path.abspath(os.path.join(inc, os.pardir)) in os.path.abspath(kl_file):
        kl_dir = inc
    
    if not kl_dir:
      sys.stdout.write('No parent include directory detected. Add include folder.')
      sys.exit(0)

    # output only pre-processed source if user asked for that
    if args.output_ppd_source:
        with open(fname, 'r') as inf:
            sys.stdout.write(inf.read())
        sys.exit(0)

    for i in range(0, len(dict_files)):
      ret_code = run_kcdict(dict_files[i], args, dname)

    file_list = [os.path.split(f)[-1] for f in dict_files]
    # copy .tx file, .vr file to cwd
    shutil.copy(target, os.getcwd())
    for file in os.listdir(dname):
      if file.endswith(".vr"):
        shutil.copy(dname + '\\' + file, os.getcwd())
        # add to file manifest
        file_list.append(file)
    
    #copy all kl files to first include folder
    for file in os.listdir(dname):
      if file.lower().endswith(".kl"):
        shutil.copy(dname + '\\' + file, kl_dir)
    
    #store dict files and vr definitions in manifest
    write_manifest(FILE_MANIFEST, file_list, os.path.split(kl_file)[-1])
    
    sys.exit(ret_code)


GPP_OP_ENTER='1'
GPP_OP_EXIT='2'
def scan_for_inc_stmts(text):
    matches = re.findall(r'^* INCLUDE_MARKER (\d+):(\S+):(\d+|)', text.decode('utf-8'), re.MULTILINE)
    incs = []
    for (line_nr, fpath, op) in matches:
        if (op == GPP_OP_ENTER) and (fpath not in incs):
            incs.append(fpath)
    return incs


def get_includes_from_file(fname):
    with open(fname, 'rb') as fd:
        source = fd.read()
        return scan_for_inc_stmts(source)


def remove_blank_lines(fname):
    with open(fname, 'r+') as inf:
      lines = inf.readlines()
      lines = [line for line in lines if line.strip() != ""]
          
      inf.seek(0)
      inf.write(''.join(lines))
      inf.truncate()


def run_gpp(inpt, outpt, args):
    gpp_path = os.path.abspath(args.gpp_path) if args.gpp_path else GPP_BIN_NAME
    # do actual pre-processing

    # setup command line for gpp
    gpp_cmdline = setup_gpp_cline(gpp_path, inpt, outpt, args.include_dirs)
    # TODO: why do we need to do this ourselves? gpp doesn't run
    #       correctly if we don't, but it shouldn't matter?
    gpp_cmdline = ' '.join(gpp_cmdline)

    # invoke gpp and save output
    gpp_proc = subprocess.Popen(gpp_cmdline, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    (pstdout, pstderr) = gpp_proc.communicate()

    # make sure to relay errors in case there are any, even if we're quiet
    if (gpp_proc.returncode != 0):
        sys.stderr.write(
            "{}\n"
            "Translation terminated\n".format(pstderr))

        # TODO: this is not very nice, as it essentially merges the set of
        # possible exit codes of gpp with those of ktrans (and gpp's are
        # positive, while ktrans' are negative ..)
        sys.exit(gpp_proc.returncode)


def run_kcdict(inpt, args, temp_dir):
    ktrans_path = os.path.abspath(args.kcdict_path) if args.kcdict_path else KCDICT_BIN_NAME
    run_files = [arg for arg in args.kcdict_args if arg.endswith(FORM_SUFFIX) or arg.endswith(DICT_SUFFIX)]
    # quote all paths as they may potentially contain spaces and ktrans
    # (or the shell really) can't handle that
    # ** hack arguments to insert the requested input file into the ktrans arguments
    ktrans_args = []
    for i in range(0, len(args.kcdict_args)):
        if (args.kcdict_args[i] == run_files[0]):
            ktrans_args.append('"{0}"'.format(inpt))
        elif (args.kcdict_args[i][0] != '/') and (args.kcdict_args[i][0] != 'V') and (args.kcdict_args[i][0] != 'v'):
            ktrans_args.append('"{0}"'.format(args.kcdict_args[i]))
        else:
            ktrans_args.append('{0}'.format(args.kcdict_args[i]))

    # setup ktrans command line args
    ktrans_cmdline = ['"{0}"'.format(ktrans_path)]
    ktrans_cmdline.extend(ktrans_args)
    ktrans_cmdline = ' '.join(ktrans_cmdline)

    # NOTE: we remap stderr to stdout as ktrans doesn't use those
    # consistently (ie: uses stderr when it should use stdout and
    # vice versa)
    ktrans_proc = subprocess.Popen(ktrans_cmdline, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, cwd=temp_dir)
    (pstdout, _) = ktrans_proc.communicate()

    # print ktrans output only on error or if we're not quiet
    if (ktrans_proc.returncode != 0) or args.verbose:
        # TODO: we loose stdout/stderr interleaving here
        # TODO: the error messages refer to lines in the temporary,
        # preprocessed KAREL source file, not the original one.
        sys.stdout.write(pstdout.decode('utf-8').replace(os.path.dirname(inpt), os.path.dirname(run_files[0])) + '\n')

    return ktrans_proc.returncode

def write_manifest(manifest, files, parent):

    file_list = dict()

    #remove parent from files
    children = [f for f in files if f not in parent]
    #replace extensions with their conversions
    for i in range(len(children)):
      ext = os.path.splitext(children[i])[-1]
      if ext in EXT_MAP.keys():
        children[i] = os.path.splitext(children[i])[0] + EXT_MAP[ext]['conversion']
    
    #replace parent extension with conversion
    if os.path.splitext(parent)[-1] in EXT_MAP.keys():
      parent = os.path.splitext(parent)[0] + EXT_MAP[os.path.splitext(parent)[-1]]['conversion']
    
    if os.path.exists(manifest):
      with open(manifest) as man:
        file_list = yaml.load(man, Loader=yaml.FullLoader)
    
    vals = {}
    if parent in file_list.keys():
      #retrieve list
      vals = set(file_list[parent])
    #add other files
    if len(vals) > 0:
      vals.update(set(children))
    else:
      vals = set(children)
    file_list[parent] = list(vals)

    #save back to yaml file
    with open(manifest, 'w') as man:
      yaml.dump(file_list, man)


def find_hdr_in_incdirs(header, include_dirs):
    for include_dir in include_dirs:
        if os.path.exists(os.path.join(include_dir, header)):
            return include_dir
    raise ValueError()


def setup_gpp_cline(gpp_exe, src_file, dest_file, include_dirs):
    # setup gpp command line (based on 'C++ compatibility mode', but with some
    # changes to better integrate -- style-wise -- with Karel sources)

    # TODO: see if we can restore bw-compat with plain ktrans by setting the
    # 'macro start sequence' to '\n--#\w' or something similar (a KAREL
    # comment), and by pre-processing (with ktransw) all includes to add
    # the '.kl' extension that ktrans expects (although that does make it
    # impossible to use alternative file extensions)
    #
    # Maybe make it an option? ie: --ktrans-bw

    gpp_cmdline = [
        gpp_exe,

        '+z',       # Set text mode to Unix mode (LF terminator)

        '--includemarker "* INCLUDE_MARKER %:%:%"',
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
        '"\\n#\w"', # the macro start sequence
        '"\\n"',    # the macro end sequence for a call without arguments
        '" "',      # the argument start sequence
        '" "',      # the argument separator
        '"\\n"',    # the argument end sequence
        '""',       # the list of characters to stack for argument balancing
        '""',       # and the list of characters to unstack

        # TODO: somehow line endings get screwed up with this
        #'+c',       # Specify comments
        #'"--"',     # the beginning of a comment
        #'"\\n"',    # end of comment

        # TODO: somehow line endings get screwed up with this
        #'+s',       # Specify strings
        #'"\'"',     # the beginning of a string
        #'"\'"',     # the end of a string
        #'""'        # string-quote character (escapes embedded string chars)
    ]

    # append include dirs we got from caller
    gpp_cmdline.extend(['-I"{0}"'.format(d) for d in include_dirs])

    # make gpp output to temporary file immediately, so we can have
    # ktrans open that, instead of having to write to the intermediary file
    # ourselves
    gpp_cmdline.extend(['-o "{0}"'.format(dest_file)])

    # finally: the input to gpp is the KAREL file that we are supposed
    # to be compiling
    gpp_cmdline.extend(['"{0}"'.format(src_file)])

    return gpp_cmdline


class TemporaryDirectory(object):
    # http://stackoverflow.com/a/19299884
    def __init__(self, suffix="", prefix="tmp", dir=None, do_clean=True):
        from tempfile import mkdtemp
        self._closed = False
        self._do_clean = do_clean
        self.name = None
        self.name = mkdtemp(suffix, prefix, dir)

    def __repr__(self):
        return "<{} {!r}>".format(self.__class__.__name__, self.name)

    def __enter__(self):
        return self.name

    def cleanup(self, _warn=False):
        if self.name and not self._closed and self._do_clean:
            try:
                self._rmtree(self.name)
            except (TypeError, AttributeError) as ex:
                if "None" not in str(ex):
                    raise
                print("ERROR: {!r} while cleaning up {!r}".format(ex, self,),
                      file=_sys.stderr)
                return
            self._closed = True
            if _warn:
                self._warn("Implicitly cleaning up {!r}".format(self),
                           ResourceWarning)

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def __del__(self):
        self.cleanup(_warn=True)

    _listdir = staticmethod(os.listdir)
    _path_join = staticmethod(os.path.join)
    _isdir = staticmethod(os.path.isdir)
    _islink = staticmethod(os.path.islink)
    _remove = staticmethod(os.remove)
    _rmdir = staticmethod(os.rmdir)
    import warnings as _warnings
    _warn = _warnings.warn

    def _rmtree(self, path):
        for name in self._listdir(path):
            fullname = self._path_join(path, name)
            try:
                isdir = self._isdir(fullname) and not self._islink(fullname)
            except OSError:
                isdir = False
            if isdir:
                self._rmtree(fullname)
            else:
                try:
                    self._remove(fullname)
                except OSError:
                    pass
        try:
            self._rmdir(path)
        except OSError:
            pass


if __name__ == '__main__':
    main()


  
