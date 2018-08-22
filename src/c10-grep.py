#!/usr/bin/env python

"""usage: c10-grep <value> <path>... [options]

Search Chapter 10 files/directories for "<value>" based on user input.
Use "*" for value to see all data at that address.

Options:
    -c CHANNEL, --channel CHANNEL  Channel ID
    --cmd CMDWORD                  1553 Command word
    -b BUS, --bus BUS              Message bus[es] to search (defaults to all)
    -w WORD, --word-offset WORD    Word offset within message [default: 0]
    -m MASK, --mask=MASK           Value mask
    -o OUTFILE, --output OUTFILE   Print results to file
    -f, --force                    Overwrite existing output file
    -x                             Utilize multiprocessing via dask (works, \
but progress reporting is a little exciting)
"""

from __future__ import print_function
from functools import partial
import os
import struct
import sys

from i106 import C10
from dask.delayed import delayed
from docopt import docopt
from tqdm import tqdm
import dask.bag as db

from common import get_time, FileProgress


def swap_word(word):
    return struct.unpack('<H', struct.pack('>H', word))[0]


def search(path, args, i=None):
    """Search file "path" based on parameters from "args"."""

    outfile = sys.stdout
    if args.get('--output'):
        outfile = open(args.get('--output'), 'a')

    outfile.write(path + '\n')

    last_time = None
    with FileProgress(
            filename=path,
            desc='    ' + os.path.basename(path),
            ascii=False,
            position=i) as progress:

        if outfile == sys.stdout:
            progress.close()

        for packet in C10(path):

            progress.update(packet.packet_length)

            if packet.data_type == 0x11:
                last_time = packet

            # Match channel
            if (args.get('--channel') or packet.channel_id) != \
                    packet.channel_id:
                continue

            # Iterate over messages if applicable
            for msg in packet:

                # 1553 format 1
                if packet.data_type == 0x19:
                    cmd = msg[0]

                    # Match command word
                    if args.get('--cmd') and args.get('--cmd') != cmd:
                        continue

                    value = msg[args.get('--word-offset')]

                    if args.get('--mask') is not None:
                        value &= args.get('--mask')

                    if args.get('<value>') == '*':
                        print(hex(value))
                    elif value == args.get('<value>'):
                        outfile.write((' ' * 4) + str(get_time(
                            msg.rtc, last_time)) + '\n')

                # Arinc 429 format 0
                elif packet.data_type == 0x38:
                    print(repr(msg))

    if outfile != sys.stdout:
        outfile.close()


if __name__ == '__main__':
    args = docopt(__doc__)

    # Validate int/hex inputs.
    for opt in ('--channel', '--word-offset', '--cmd', '<value>', '--mask',
                '--bus'):
        if args.get(opt):
            if opt == '<value>' and args[opt] == '*':
                continue
            try:
                if args[opt].lower().startswith('0x'):
                    args[opt] = int(args[opt], 16)
                else:
                    args[opt] = int(args[opt])
            except ValueError:
                print('Invalid value "%s" for %s' % (args[opt], opt))
                raise SystemExit

    if args.get('--output') and os.path.exists(args.get('--output')):
        if args.get('--force'):
            with open(args.get('--output'), 'w') as f:
                f.write('')
        else:
            print('Output file exists, use -f to overwrite.')
            raise SystemExit

    # Describe the search parameters.
    value_repr = args.get('<value>')
    if isinstance(value_repr, int):
        value_repr = hex(value_repr)
    print('Searching for %s' % value_repr, end='')
    if args.get('--channel'):
        print('in channel #%s' % args.get('--channel'), end='')
    if args.get('--cmd'):
        print('with command word %s' % hex(args.get('--cmd')), end='')
    if args.get('--word-offset'):
        print('at word %s' % args.get('--word-offset'), end='')
    if args.get('--mask'):
        print('with mask %s' % hex(args.get('--mask')), end='')

    files = []
    for path in args.get('<path>'):
        path = os.path.abspath(path)
        if os.path.isdir(path):
            for dirname, dirnames, filenames in os.walk(path):
                for f in filenames:
                    if os.path.splitext(f)[1].lower() in ('.c10', '.ch10'):
                        files.append(os.path.join(dirname, f))
        else:
            files.append(path)

    print('in %s files...' % len(files))
    task = partial(search, args=args)
    if args.get('-x'):
        bag = db.from_delayed([
            delayed(task)(f, i=i) for i, f in enumerate(files)])
        bag.compute()
    else:
        files = tqdm(
            files,
            desc='Overall',
            unit='files',
            dynamic_ncols=True,
            leave=False)
        if not args.get('--output'):
            files.close()
        for f in files:
            task(f)
    print('\nfinished')
