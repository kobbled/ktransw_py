#
# Copyright (c) 2016, G.A. vd. Hoorn
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

from __future__ import print_function

import os
import sys
import time
import argparse
import subprocess
import logging
import re
import yaml
from shutil import copyfile

KTRANSW_VERSION='0.2.3'
KTRANS_BIN_NAME='ktrans.exe'
GPP_BIN_NAME='gpp.exe'
_OS_EX_DATAERR=65
KL_SUFFIX = '.kl'
PCODE_SUFFIX = '.pc'

FILE_MANIFEST = '.man_log'

DATA_TYPES = ('karel', 'src', 'test')
EXT_MAP = {
      '.kl' : {'conversion' : '.pc'},
      '.vr' : {'conversion' : '.vr'},
      '.ftx' : {'conversion' : '.tx'},
      '.utx' : {'conversion' : '.tx'}
    }

#store files to run through ktrans
kl_files = []
#list to hold class injection points
class_injections = []
#list to store header injections
header_injections = []

def main():

    description=("Version {0}\n\n"
        "A wrapper around Fanuc Robotics' command-line Karel translator ({1})\n"
        "that adds a C-like preprocessor, support for multiple include directories,\n"
        "conditional compilation, include guards, macros and more."
            .format(KTRANSW_VERSION, KTRANS_BIN_NAME))

    epilog=("Example invocation:\n\n  ktransw /IC:\\foo\\bar\\include "
        "/IC:\\baz\\include C:\\my_prog.kl /config robot.ini\n\nAll arguments "
        "using forward-slash notation (except '/I') are passed on\nto ktrans.")

    parser = argparse.ArgumentParser(prog='ktransw', description=description,
        epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
        help='Print (lots of) debug information')
    parser.add_argument('-q', '--quiet', action='store_true', dest='quiet',
        help='Print nothing, except when ktrans encounters an error')
    parser.add_argument('-d', '--dry-run', action='store_true', dest='dry_run',
        help='Do nothing, except checking parameters')

    parser.add_argument('-E', action='store_true', dest='output_ppd_source',
        help="Preprocess only; do not translate")
    parser.add_argument('-M', action='store_true', dest='dep_output',
        help='Output GCC compatible dependency file')
    parser.add_argument('-MM', action='store_true', dest='ignore_syshdrs',
        help="Like '-M', but don't include system headers")
    parser.add_argument('-MT', type=str, dest='dep_target', metavar='target',
        help="Change the target of the rule emitted by dependency generation "
            "(default: base name of source, with object extension (.pc))")
    parser.add_argument('-MF', type=str, dest='dep_fname', metavar='file',
        help="When used with -M or -MM, specifies a file to write the "
            "dependencies to.")
    parser.add_argument('-MG', action='store_true', dest='ignore_missing_hdrs',
        help="Assume missing header files are generated files and add them "
            "to the dependency list without raising an error")
    parser.add_argument('-MP', action='store_true', dest='add_phony_tgt_for_deps',
        help="Add a phony target for each dependency to support renaming "
            "dependencies without having to update the Makefile to match")

    parser.add_argument('-k', '--keep-build-dir', action='store_true',
        dest='keep_buildd', help="Don't delete the temporary build directory "
            "on exit")
    parser.add_argument('--ktrans', type=str, dest='ktrans_path', metavar='PATH',
        help="Location of ktrans (by default ktransw assumes it's on the "
            "Windows PATH)")
    parser.add_argument('--gpp', type=str, dest='gpp_path', metavar='PATH',
        help="Location of gpp (by default ktransw assumes it's on the "
            "Windows PATH)")
    parser.add_argument('-I', action='append', type=str, dest='include_dirs',
        metavar='PATH', default=[], help='Include paths (multiple allowed)')
    parser.add_argument('-D', action='append', type=str, dest='user_macros',
        metavar='PATH', default=[], help='Define user macros from cmd')
    parser.add_argument('ktrans_args', type=str, nargs='*', metavar='ARG',
        help="Arguments to pass on to ktrans. Use normal (forward-slash) "
        "notation here")

    # support forward-slash arg notation for include dirs
    for i in range(1, len(sys.argv)):
        if sys.argv[i].startswith('/I'):
            sys.argv[i] = sys.argv[i].replace('/I', '-I', 1)
        if sys.argv[i].startswith('/D'):
            sys.argv[i] = sys.argv[i].replace('/D', '-D', 1)
    args = parser.parse_args()

    # configure the logger
    FMT='%(levelname)-8s | %(message)s'
    logging.basicConfig(format=FMT, level=logging.INFO)
    logger = logging.getLogger('ktransw')
    if args.verbose:
        logger.setLevel(logging.DEBUG)


    logger.debug("Ktrans Wrapper v{0}".format(KTRANSW_VERSION))


    # we expect ktrans to be on the path. If it's not, user should have
    # provided an alternative location
    ktrans_path = os.path.abspath(args.ktrans_path) if args.ktrans_path else KTRANS_BIN_NAME
    logger.debug("Setting ktrans path to: {0}".format(ktrans_path))

    # we expect gpp to be on the path. If it's not, user should have
    # provided an alternative location
    gpp_path = os.path.abspath(args.gpp_path) if args.gpp_path else GPP_BIN_NAME
    logger.debug("Setting gpp path to: {0}".format(gpp_path))


    # bit of a kludge, but we assume:
    #
    #  1. ktrans args always start with a forward-slash
    #  2. things starting with a 'V' or 'v' are core version identifiers
    #  3. everything else is a (potentially relative) path
    #
    # everything in category 3 is made absolute.
    for i in range(0, len(args.ktrans_args)):
        if (args.ktrans_args[i][0] != '/') and (args.ktrans_args[i][0] != 'V') and (args.ktrans_args[i][0] != 'v'):
            args.ktrans_args[i] = os.path.abspath(args.ktrans_args[i])

    logger.debug("Parsed args:")
    for key, val in vars(args).items():
        if type(val) == list:
            logger.debug("  {0}:".format(key))
            for item in val:
                logger.debug("    {0}".format(item))
        else:
            logger.debug("  {0}: {1}".format(key, val))


    # extract args which refer to KAREL sources: we can just search for
    # arguments with '.kl' in it, as ktrans only considers files with that
    # extension.
    pre_gpp_files = []
    for arg in args.ktrans_args:
      if arg.endswith(KL_SUFFIX):
        pre_gpp_files.append(arg)


    # avoid running a build if we don't need it
    needs_build = len(pre_gpp_files) > 0
    logger.debug("{0} a build".format("Needs" if needs_build else "Doesn't need"))

    if not needs_build:
        ktrans_cmdline = [ktrans_path]
        ktrans_cmdline.extend(args.ktrans_args)

        sys.stdout.write("KTRANSW V{}, Copyright (C) 2016 G.A. vd. Hoorn\n"
            .format(KTRANSW_VERSION))
        ktrans_ret = subprocess.call(ktrans_cmdline)

        logger.debug("End of ktrans, ret: {0}".format(ktrans_ret))
        sys.exit(ktrans_ret)

    # assume there's only one input source file (or: we ignore all others)
    kl_file = pre_gpp_files[0]

    # checks done, can now proceed to actual pre-processing / translation ..
    # .. but only if not requested to do a dry-run
    if args.dry_run:
        logger.debug("Not calling ktrans or gpp: dry run requested")
        sys.exit(0)

    # create temporary directory to store preprocessed file in. We
    # avoid problems with temporary files (via NamedTemporaryFile fi) being
    # not readable by other processes in this way.
    with TemporaryDirectory(prefix='ktransw-', suffix='-buildd', do_clean=(not args.keep_buildd)) as dname:
        # unfortunately we need to create a temporary file to store the
        # preprocessed KAREL source in, as ktrans doesn't support reading
        # from stdin.

        # TODO: see if ktrans will read from a named pipe ('\\.\pipe\temp.kl')


        #final pass through filename
        fname = os.path.join(dname, os.path.basename(kl_file))

        #process files and class objects through recursive gpp process
        make_classes(kl_file, fname, dname, args, logger)

        # pre-processing done

        base_source_name = ''
        target = ''
        # see if we need to output dependency info
        if (args.dep_output or args.ignore_syshdrs):
            # use original filename for logging
            logger.debug("Dependency output for {0}".format(kl_file))

            # but scan the GPP output for include markers
            incs = get_includes_from_file(fname)
            logger.debug("Found {0} includes".format(len(incs)))

            # target name we use is 'base source file name + .pc', OR the name
            # provided as a command line arg
            base_source_name = os.path.basename(os.path.splitext(kl_file)[0])
            target = args.dep_target or (base_source_name + PCODE_SUFFIX)

            # resolve all relative includes to their respective include directories
            deps = []
            for hdr in incs:
                if args.ignore_syshdrs and is_system_header(hdr):
                    logger.debug("Ignoring system header '{0}'".format(hdr))
                    continue

                # all non-absolute paths are headers we need to find first
                hdr_path = hdr
                if not os.path.isabs(hdr_path):
                    try:
                        hdr_dir = find_hdr_in_incdirs(hdr_path, args.include_dirs)

                        # make relative header absolute by prefixing it with the
                        # location we found it in
                        hdr_path = os.path.join(hdr_dir, hdr_path)
                        logger.debug("Found {0} in '{1}'".format(hdr, hdr_dir))

                    except ValueError as e:
                        if not args.ignore_missing_hdrs:
                            # we were not asked to ignore this, so exit with an error
                            sys.stderr.write("ktransw: fatal error: {0}: No such file or directory\n".format(hdr))
                            sys.exit(_OS_EX_DATAERR)

                logger.debug("Adding {0} to dependencies".format(hdr_path))
                deps.append(hdr_path)

            # escape spaces as ninja does not like those
            for i in range(0, len(deps)):
                deps[i] = deps[i].replace(' ', '\\ ')
            target = target.replace(' ', '\\ ')

            # write out dependency rules
            dep_lines = '{0}: {1}\n'.format(target, ' '.join(['{}'.format(dep) for dep in deps]))

            # and some phony targets if user requested that
            if args.add_phony_tgt_for_deps:
                dep_lines += '\n'.join([dep + ':' for dep in deps]) + '\n'

            # write out dependency file
            if args.dep_fname:
                with open(args.dep_fname, 'w') as outf:
                    outf.write(dep_lines)
            # or to stdout
            else:
                sys.stdout.write(dep_lines)

        #store files and classes in manifest
        write_manifest(FILE_MANIFEST, [os.path.split(f)[-1] for f in kl_files], os.path.split(kl_file)[-1])

        # output only pre-processed source if user asked for that
        if args.output_ppd_source:
            for i in range(0, len(kl_files)):
                copyfile(dname + '\\' + os.path.basename(kl_files[i]), os.path.basename(kl_files[i]))
            sys.exit(0)

        for i in range(0, len(kl_files)):
          ret_code = run_ktrans(kl_files[i], args, logger)
        
        sys.exit(ret_code)


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

def run_gpp(inpt, outpt, args, logger):
    gpp_path = os.path.abspath(args.gpp_path) if args.gpp_path else GPP_BIN_NAME
    # do actual pre-processing
    logger.debug("Starting pre-processing of {}".format(inpt))

    # setup command line for gpp
    gpp_cmdline = setup_gpp_cline(gpp_path, inpt, outpt, args.include_dirs, args.user_macros)
    # TODO: why do we need to do this ourselves? gpp doesn't run
    #       correctly if we don't, but it shouldn't matter?
    gpp_cmdline = ' '.join(gpp_cmdline)

    # invoke gpp and save output
    logger.debug("Starting gpp as: '{0}'".format(gpp_cmdline))
    gpp_proc = subprocess.Popen(gpp_cmdline, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    (pstdout, pstderr) = gpp_proc.communicate()

    logger.debug("End of gpp, ret: {0}".format(gpp_proc.returncode))

    # make sure to relay errors in case there are any, even if we're quiet
    if (gpp_proc.returncode != 0):
        sys.stderr.write(
            "{}\n"
            "Translation terminated\n".format(pstderr))

        # TODO: this is not very nice, as it essentially merges the set of
        # possible exit codes of gpp with those of ktrans (and gpp's are
        # positive, while ktrans' are negative ..)
        sys.exit(gpp_proc.returncode)

def run_ktrans(inpt, args, logger):
    ktrans_path = os.path.abspath(args.ktrans_path) if args.ktrans_path else KTRANS_BIN_NAME
    run_files = [arg for arg in args.ktrans_args if arg.endswith(KL_SUFFIX)]
    # quote all paths as they may potentially contain spaces and ktrans
    # (or the shell really) can't handle that
    # ** hack arguments to insert the requested input file into the ktrans arguments
    ktrans_args = []
    for i in range(0, len(args.ktrans_args)):
        if (args.ktrans_args[i] == run_files[0]):
            ktrans_args.append('"{0}"'.format(inpt))
        elif (args.ktrans_args[i][0] != '/') and (args.ktrans_args[i][0] != 'V') and (args.ktrans_args[i][0] != 'v'):
            ktrans_args.append('"{0}"'.format(args.ktrans_args[i]))
        else:
            ktrans_args.append('{0}'.format(args.ktrans_args[i]))

    # setup ktrans command line args
    ktrans_cmdline = ['"{0}"'.format(ktrans_path)]
    ktrans_cmdline.extend(ktrans_args)
    ktrans_cmdline = ' '.join(ktrans_cmdline)

    logger.debug("Starting ktrans as: '{}'".format(ktrans_cmdline))
    # NOTE: we remap stderr to stdout as ktrans doesn't use those
    # consistently (ie: uses stderr when it should use stdout and
    # vice versa)
    ktrans_proc = subprocess.Popen(ktrans_cmdline, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    (pstdout, _) = ktrans_proc.communicate()

    # let caller know how we did
    logger.debug("End of ktrans, ret: {0}".format(ktrans_proc.returncode))

    # print ktrans output only on error or if we're not quiet
    if (ktrans_proc.returncode != 0) or (not args.quiet) or args.verbose:
        # TODO: we loose stdout/stderr interleaving here
        # TODO: the error messages refer to lines in the temporary,
        # preprocessed KAREL source file, not the original one.
        sys.stdout.write(pstdout.decode('utf-8').replace(os.path.dirname(inpt), os.path.dirname(run_files[0])) + '\n')

    return ktrans_proc.returncode


def make_classes(fil, output_file, folder, args, logger):
    #search for class instantiations

    #classes_file = os.path.join(dname, 'obj-' + os.path.basename(kl_file))
    #pre_file = os.path.join(dname, 'pre-' + os.path.basename(kl_file))
    #pass2_file = os.path.join(dname, 'pass2-' + os.path.basename(kl_file))
    #fname = os.path.join(dname, os.path.basename(kl_file))

    #classes = search_for_classes(kl_file, classes_file)

    #run through 1st pass to reveal any %class directives
    pre_file = os.path.join(folder, 'pre-' + os.path.basename(fil))
    run_gpp(fil, pre_file, args, logger)
    remove_blank_lines(pre_file)

    #add to list of class injections
    classes = search_for_classes(pre_file, pre_file)
    class_injections.extend(classes)

    #find any selective include declarations and replace them
    #with function declarations
    search_for_selective_include(pre_file, args.include_dirs)

    # do first pass
    pass1_file = os.path.join(folder, 'pass1-' + os.path.basename(fil))
    logger.debug("Storing preprocessed KAREL source at: {}".format(pass1_file))

    run_gpp(pre_file, pass1_file, args, logger)
    remove_blank_lines(pass1_file)

    if len(classes) > 0:
      #if classes is found create object files do 2nd pass
      for obj in classes:
        #make object file and preprocess
        obj_file = os.path.join(folder, os.path.basename('obj-'+obj[1]+".kl"))
        obj_processed = os.path.join(folder, os.path.basename(obj[1]+".kl"))
        #make header inclusion and preprocess
        header_injections.append(os.path.join(folder, os.path.basename('pre-'+obj[1]+".klh")))

        #create object file
        create_object(obj, obj_file)
        #create header file for object
        create_object_hdr(obj, header_injections[-1])

        # recursively loop through object files
        make_classes(obj_file, obj_processed, folder, args, logger)

    #insert header inclusions back into original karel file
    insert_headers(pass1_file, header_injections, class_injections)
    #evaluate injections
    pass2_file = os.path.join(folder, 'pass2-' + os.path.basename(fil))
    run_gpp(pass1_file, pass2_file, args, logger)
    #remove leftover "`" characters from kransw_macros
    # *** see docstring for details
    remove_char(pass2_file, "`")
    #do final gpp pass
    run_gpp(pass2_file, output_file, args, logger)
    remove_blank_lines(output_file)

    #append processed file to ktrans list
    kl_files.append(output_file)



def search_for_classes(inpt, outpt):
    # match %class name('class.klc','class.klh',<'class.klt'>)
    pattern = r"(?:\%class\s*)(\w+)\s*\(\s*'(\w+.\w+)'(?:\s*,\s*'(\w+.\w+)')(?:\s*,\s*'(\w+.\w+)')*\s*\)"
    objects =[]
    with open(inpt, 'r+') as inf:
      lines = inf.readlines()
      k = 1
      for i in range(len(lines)):
        m = re.match(pattern, lines[i])
        if m:
          #make a list in the format (index, object_name, class_file, header_file, type_name, type_file)
          obj = []
          obj.append(k)
          for j in range(1,m.lastindex+1):
            obj.append(m.group(j))
          objects.append(obj)
          
          #replace line with include marker for later insersion
          lines[i] = "-- INCLUDE_MARKER {0}:{1}:1\n".format(k,m.group(1))
          k += 1
    
    with open(outpt, 'w') as inf:
        inf.seek(0)
        inf.write(''.join(lines))
        inf.truncate()

    return objects

def create_object(obj, fname):
    with open(fname,"w+") as f:
      #define a class_name for the .klc file to evaluate
      f.write(r"%defeval class_name {0}".format(obj[1]) + '\n')
      #define a type_name for the .klc file to evaluate if it exists
      if len(obj) > 4:
        f.write(r"%include {0}".format(obj[4]) + '\n')
      #call the class '.klc' file
      f.write(r"%include {0}".format(obj[2]) + '\n')

def create_object_hdr(obj, fname):
    with open(fname,"w+") as f:
      f.write(r"%defeval class_name {0}".format(obj[1]) + '\n')
      if len(obj) > 4:
        f.write(r"%include {0}".format(obj[4]) + '\n')
      #process header file
      f.write(r"%include {0}".format(obj[3]) + '\n')

def insert_headers(fname, header_injections, objects):
    pattern = r"(?:--\s*INCLUDE_MARKER\s*(\d+)\:({0})+\:1)".format('|'.join([obj[1] for obj in objects]))

    with open(fname,"r+") as f:
      lines = f.readlines()
      for i in range(len(lines)):
        m = re.match(pattern, lines[i])
        if m:
          for obj in objects:
            if str(obj[0]) == m.group(1) and obj[1] == m.group(2):
              #find associating header file
              fle = [hdr for hdr in header_injections if (m.group(2) in os.path.basename(hdr))][0]
              if not fle:
                raise Exception('header file {0} was not created'.format(m.group(2)))
              with open(fle,"r") as h:
                inclusion = h.read()
              #include header into main file
              lines[i] = inclusion
              break

      #write back into file
      f.seek(0)
      f.write(''.join(lines))
      f.truncate()


def remove_char(fname, char):
    """ (HACK) this is for defining a user defined %define name at time of compilation
      couldn't figure out how to process this in a single function: 
      ```
      %mode push
      %mode quote "$"
      %define alias foo
      %define func bar
      %defeval declare $%define alias func$
      %mode pop
      declare
      ```
      you cannot nest "%mode quote "$"" in "%mode string QQQ "`" "`" "\\""
      making is seemingly impossible to do this in one line

      current solution is to use %mode nostring "`" to evaluate the expression
      ```
        %defeval TEMP0 `%define alias func^`
        TEMP0
      ```
      However this still leaves `` around the %define, hence removing the character
      and incorperating another gpp pass. might have conflicts on choice of nostring
      character. 
    
    """

    with open(fname, 'r+') as f:
      data = f.read()
      data = data.replace(char, "")
      #write back into file
      f.seek(0)
      f.write(data)
      f.truncate()

def findWholeWord(w):
    """return if only full words are found, or a word with a preceeding '_'
    """
    return re.compile(r'(?:\b|_)({0})(?:\b)'.format(w), flags=re.IGNORECASE).search

def isLineCont(prog, idx, out_string):
    """function makes sure to absorb line continutations for parsing
       out routine defintions in header files (i.e. look at def search_for_selective_include)
    """
    line = prog[idx].rstrip()
    if line[-1] == '&':
      out_string += prog[idx+1]
      if idx+1 <= len(prog):
        isLineCont(prog, idx+1, out_string)
    
    return out_string
    


def search_for_selective_include(inpt, include_dirs):
    """search for selective includes '%from header.klh %import func1, func2'
       Then find an look through header file for selective header declartions
    """
    # match %from header.klh %import func1, func2
    pattern = r"(?:\%from\s*)([a-zA-Z_.0-9]*)(?:\s*\%import\s*)(\w+,?(\s*\w+,?)*)"
    #selective include dictionary
    sinc_dictionary = {}

    with open(inpt,"r+") as f:
      lines = f.readlines()
      for i in range(len(lines)):
        m = re.match(pattern, lines[i])
        if m:
          #find file in include directories
          head_file = ''
          for head_dir in include_dirs:
            if os.path.exists(head_dir + '\\' + m.group(1)):
              head_file = head_dir + '\\' + m.group(1)
              break
          
          if head_file:
            #start insersion string
            insert_string = '%include namespace.m' + '\n'

            #split specified functions into list
            fs = m.group(2).replace(" ", "")
            funcs = fs.split(',')

            #go through header file and pick out sepecified
            #function declarations
            with open(head_file,'r') as f_head:
              h_line = f_head.readlines()
              for j in range(len(h_line)):
                #look for namespace delarations
                if any(nspace in h_line[j] for nspace in ['%define prog_name', '%define prog_name_alias']):
                  insert_string += h_line[j]
                #look for function declarations
                #make sure only full words match
                if any(findWholeWord(func)(h_line[j]) for func in funcs):
                  insert_string += h_line[j]
                  insert_string = isLineCont(h_line, j, insert_string)

            
            #replace line in input file with the insert_string
            #holding the function declarations
            lines[i] = insert_string
          else:
            raise Exception('{0} was not found in any include directory.'.format(m.group(1)))
      
      #write back into file
      f.seek(0)
      f.write(''.join(lines))
      f.truncate()

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
      file_list = None
      with open(manifest, 'r') as man:
        # ..todo:: issue with opening .man_log file concurrently numerous times through
        #          ninja throwing "AttributeError: 'NoneType' object has no attribute 'keys'"
        #          something is blocking while trying to open .man_log. The looping solution
        #          below is an intermediary patch.
        while file_list is None:
          file_list = yaml.safe_load(man)
          time.sleep(0.1)
    
        vals = {}
        found = False
        for key in file_list.keys():
          if isinstance(file_list[key], dict) and (key in DATA_TYPES):
            sub_dict = file_list[key]
            if parent in sub_dict.keys():
              #retrieve list
              vals = set(sub_dict[parent])
              vals.update(set(children))
              file_list[key][parent] = list(vals)
              found = True

        #insert into dictionary if parent not in manifest
        if found == False:
          file_list['karel'] = {}
          vals = set(children)
          file_list['karel'][parent] = list(vals)

      #save back to yaml file
      with open(manifest, 'w') as man:
        yaml.dump(file_list, man)
        man.close()


GPP_OP_ENTER='1'
GPP_OP_EXIT='2'
def scan_for_inc_stmts(text):
    matches = re.findall(r'^-- INCLUDE_MARKER (\d+):(\S+):(\d+|)', text.decode('utf-8'), re.MULTILINE)
    incs = []
    for (line_nr, fpath, op) in matches:
        if (op == GPP_OP_ENTER) and (fpath not in incs):
            incs.append(fpath)
    return incs


def is_system_header(header):
    # TODO: this is only a list of 'system headers' for V7.70-1
    return header in [
        "iosetup.kl",
        "kldctptx.kl",
        "kldcutil.kl",
        "klersys.kl",
        "klerxmlf.kl",
        "klevaxdf.kl",
        "klevccdf.kl",
        "klevkeys.kl",
        "klevkmsk.kl",
        "klevksp.kl",
        "klevtpe.kl",
        "klevutil.kl",
        "kliosop.kl",
        "kliotyps.kl",
        "kliouop.kl",
        "klrdread.kl",
        "klrdutil.kl",
        "kluifdir.kl",
        "passcons.kl",
        "ppedef.kl",
        "runform.kl",
        "sledef.kl"
    ]


def find_hdr_in_incdirs(header, include_dirs):
    for include_dir in include_dirs:
        if os.path.exists(os.path.join(include_dir, header)):
            return include_dir
    raise ValueError()


def setup_gpp_cline(gpp_exe, src_file, dest_file, include_dirs, macro_strs):
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

    # add user defined macros if defined from cmd line
    if macro_strs:
      gpp_cmdline.extend(['-D{0}'.format(d) for d in macro_strs])
    
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
