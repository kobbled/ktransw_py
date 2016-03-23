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

import os
import sys
import argparse
import subprocess
#import logging



def main():
    KTRANSW_VERSION='0.1.0'
    KTRANS_BIN_NAME='ktrans.exe'
    _OS_EX_DATAERR=65

    description=("Version {0}\n\n"
        "A wrapper around Fanuc Robotics' command-line Karel translator "
        "({1})\nthat fakes support for multiple include paths by running {1} "
        "from a\ntemporary directory containing a copy of the contents of the "
        "specified\ninclude paths.".format(KTRANSW_VERSION, KTRANS_BIN_NAME))

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
        help='Do everything except copying files and starting ktrans')

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

    parser.add_argument('-k', '--keep-build-dir', action='store_true',
        dest='keep_buildd', help="Don't delete the temporary build directory "
        "on exit")
    parser.add_argument('--ktrans', type=str, dest='ktrans_path', metavar='PATH',
        help="Location of ktrans (by default ktransw assumes it's on the "
            "Windows PATH)")
    parser.add_argument('-I', action='append', type=str, dest='include_dirs',
        metavar='PATH', default=[], help='Include paths (multiple allowed)')
    parser.add_argument('ktrans_args', type=str, nargs='*', metavar='ARG',
        help="Arguments to pass on to ktrans. Use normal (forward-slash) "
        "notation here")

    # support forward-slash arg notation for include dirs
    for i in range(1, len(sys.argv)):
        if sys.argv[i].startswith('/I'):
            sys.argv[i] = sys.argv[i].replace('/I', '-I', 1)
    args = parser.parse_args()

    KL_SUFFIX = '.kl'
    PCODE_SUFFIX = '.pc'

    # configure the logger
    #FMT='%(levelname)-8s | %(message)s'
    #logging.basicConfig(format=FMT, level=logging.INFO)
    #logger = logging.getLogger('ktransw')
    #if args.verbose:
    #    logger.setLevel(logging.DEBUG)


    #logger.debug("Ktrans Wrapper v{0}".format(KTRANSW_VERSION))

    # we expect ktrans to be on the path. If it's not, user should have
    # provided an alternative location
    ktrans_path = KTRANS_BIN_NAME
    if args.ktrans_path:
        ktrans_path = os.path.abspath(args.ktrans_path)
    #logger.debug("Setting ktrans path to: {0}".format(ktrans_path))


    # bit of a kludge, but we assume:
    #
    #  1. args always start with a forward-slash
    #  2. things starting with a 'V' or 'v' are core version identifiers
    #  3. everything else is a (potentially relative) path
    #
    # everything in category 3 is made absolute.
    for i in range(0, len(args.ktrans_args)):
        if (args.ktrans_args[i][0] != '/') and (args.ktrans_args[i][0] != 'V') and (args.ktrans_args[i][0] != 'v'):
            args.ktrans_args[i] = os.path.abspath(args.ktrans_args[i])

    #logger.debug("Parsed args:")
    #for key, val in vars(args).iteritems():
    #    if type(val) == list:
    #        logger.debug("  {0}:".format(key))
    #        for item in val:
    #            logger.debug("    {0}".format(item))
    #    else:
    #        logger.debug("  {0}: {1}".format(key, val))


    # generate full command line to pass to subprocess
    ktrans_cmdlargs = ' '.join(args.ktrans_args)
    ktrans_cmdline = "{0} {1}".format(ktrans_path, ktrans_cmdlargs)


    # see if we just need to output dependency info
    if (args.dep_output or args.ignore_syshdrs) and (KL_SUFFIX in ktrans_cmdlargs):
        # assume there's only one input source file (or: we ignore all others)
        kl_file = [arg for arg in args.ktrans_args if arg.endswith('.kl')][0]
        #logger.debug("Dependency output for {0}".format(kl_file))

        incs = get_includes(kl_file)
        #logger.debug("Found {0} includes".format(len(incs)))

        # make sure everything ends in the right suffix
        for i in range(0, len(incs)):
            if not incs[i].endswith(KL_SUFFIX):
                incs[i] = incs[i] + KL_SUFFIX

        # target name we use is 'base source file name + .pc', OR the name
        # provided as a command line arg
        target = os.path.basename(os.path.splitext(kl_file)[0]) + PCODE_SUFFIX
        if args.dep_target:
            target = args.dep_target

        # resolve all relative includes to their respective include directories
        deps = []
        for hdr in incs:
            if args.ignore_syshdrs and is_system_header(hdr):
                #logger.debug("Ignoring system header '{0}'".format(hdr))
                continue

            # all non-absolute paths are headers we need to find first
            hdr_path = hdr
            if not os.path.isabs(hdr_path):
                try:
                    hdr_dir = find_hdr_in_incdirs(hdr_path, args.include_dirs)

                    # make relative headers absolute by prefixing it with the
                    # location we found it in
                    hdr_path = os.path.join(hdr_dir, hdr_path)
                    #logger.debug("Found {0} in '{1}'".format(hdr, hdr_dir))

                except ValueError, e:
                    if not args.ignore_missing_hdrs:
                        # we were not asked to ignore this, so exit with an error
                        sys.stderr.write("fatal error: {0}: No such file or directory\n".format(hdr))
                        sys.exit(_OS_EX_DATAERR)

            #logger.debug("Adding {0} to dependencies".format(hdr_path))
            deps.append(hdr_path)

        dep_lines = "{0} : {1}\n".format(target, ' \\\n\t'.join([dep for dep in deps]))

        # write out dependency file
        if args.dep_fname:
            with open(args.dep_fname, 'w') as outf:
                outf.write(dep_lines)
        # or to stdout
        else:
            sys.stdout.write(dep_lines)

        # done
        sys.exit(0)


    # avoid creating a build dir if we don't need it
    # TODO: this is brittle: ktrans.exe does not require source files to have
    #       an '.kl' extension at all.
    needs_buildd = KL_SUFFIX in ktrans_cmdlargs
    #logger.debug("{0} a build dir".format("Needs" if needs_buildd else "Doesn't need"))

    # if we're not translating anything, exit early
    if not needs_buildd:
        ktrans_ret = subprocess.call(ktrans_cmdline, cwd=os.path.abspath(os.getcwd()))
        #logger.debug("End of ktrans. Ret: {0}".format(ktrans_ret))
        sys.exit(ktrans_ret)


    # we are, so setup build directory
    # TODO: probably want to use some kind of context management here. See:
    #   http://stackoverflow.com/a/33288373
    import tempfile
    import shutil

    build_dir = tempfile.mkdtemp(prefix='ktransw-', suffix='-buildd')
    #logger.debug("Using temp build dir: {0}".format(build_dir))

    # copy contents of include dirs to it
    seen = []
    for include_dir in args.include_dirs:
        # silently ignore non-existent paths
        if not os.path.exists(include_dir):
            #logger.debug("Include path {0} does not exist, ignoring".format(include_dir))
            continue

        # avoid copying dirs with the same name
        # TODO: should we merge them instead? Probably slower.
        if include_dir in seen:
            #logger.debug("Skipping (already copied): {0}".format(include_dir))
            continue
        seen.append(include_dir)

        # find out which dirs are sub dirs of the include path
        # TODO: we only copy sub directories of 'include_dir' here. Should files
        #       also be copied?
        subdirs = [d for d in os.listdir(include_dir) if os.path.isdir(os.path.join(include_dir, d))]
        #logger.debug("Found {0} subdir(s) in {1}".format(len(subdirs), include_dir))

        # copy all of those subdirs to the build dir
        for subdir in subdirs:
            src = os.path.join(include_dir, subdir)
            dst = os.path.join(build_dir, subdir)

            #logger.debug("Copying {0} to {1}".format(src, dst))
            if not args.dry_run:
                shutil.copytree(src=src, dst=dst)


    #logger.debug("Starting ktrans with args: '{0}'".format(ktrans_cmdlargs))

    ktrans_ret = 0
    if not args.dry_run:
        # save ktrans output ..
        process = subprocess.Popen(ktrans_cmdline, cwd=build_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (pstdout, _) = process.communicate()
        ktrans_ret = process.returncode

        # .. but print only on error or if we're not quiet
        if (ktrans_ret < 0) or not args.quiet or args.verbose:
            # TODO: we loose stdout/stderr interleaving here
            sys.stdout.write(pstdout)
    #else:
        #logger.debug("Not calling ktrans: dry run requested")

    #logger.debug("End of ktrans. Ret: {0}".format(ktrans_ret))

    if not args.keep_buildd:
        #logger.debug("Removing temporary build dir")
        shutil.rmtree(build_dir)

    # let caller know what ktrans did
    sys.exit(ktrans_ret)


def get_includes(fname):
    import re
    with open(fname, 'r') as fd:
        source = fd.read()
        matches = re.findall(r'^%INCLUDE (.*)$', source, re.MULTILINE)
        return matches or []


def is_system_header(header):
    # list of 'system headers' for V7.70-1
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


if __name__ == '__main__':
    main()
