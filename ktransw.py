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
    KTRANSW_VERSION='0.0.1'
    KTRANS_BIN_NAME='ktrans.exe'

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
    parser.add_argument('-d', '--dry-run', action='store_true', dest='dry_run',
        help='Do everything except copying files and starting ktrans')
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

    # avoid creating a build dir if we don't need it
    # TODO: this is brittle: ktrans.exe does not require source files to have
    #       an '.kl' extension at all.
    needs_buildd = '.kl' in ktrans_cmdlargs
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
        ktrans_ret = subprocess.call(ktrans_cmdline, cwd=build_dir)
    #else:
        #logger.debug("Not calling ktrans: dry run requested")

    #logger.debug("End of ktrans. Ret: {0}".format(ktrans_ret))

    if not args.keep_buildd:
        #logger.debug("Removing temporary build dir")
        shutil.rmtree(build_dir)

    # let caller know what ktrans did
    sys.exit(ktrans_ret)


if __name__ == '__main__':
    main()
