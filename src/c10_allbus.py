#!/usr/bin/env python

"""usage: c10-allbus <src> <dst> [-b] [options]

Switch 1553 format 1 messages to indicate the same bus (A or B).

Options:
    -b           Use the B bus instead of A (default).
    -f, --force  Overwrite existing dst file if present.
"""

import os
import sys

from docopt import docopt

from common import FileProgress, C10


def main(args=[]):
    args = docopt(__doc__, args)

    if os.path.exists(args['<dst>']) and not args['--force']:
        print('Destination file exists. Use --force to overwrite it.')
        raise SystemExit

    with open(args['<dst>'], 'wb') as out, \
            FileProgress(args['<src>']) as progress:
        for packet in C10(args['<src>']):

            raw = bytes(packet)
            progress.update(len(raw))

            # Write non-1553 out as-is.
            if packet.data_type != 0x19:
                out.write(raw)
                continue

            # Write out packet header secondary if applicable) and CSDW.
            offset = 28
            # TODO: make this consistent between python and c libraries
            if getattr(packet, 'secondary_header', None) or getattr(
                    packet, 'flags', 0) & (1 << 7):
                offset += 12
            out.write(raw[:offset])

            # Walk through messages and update bus ID as needed.
            for msg in packet:
                msg.bus = int(args['-b'])

                # TODO: replace this when we reimplement Item.bytes in
                # pychapter10
                try:
                    packed = bytes(msg)
                except TypeError:
                    packed = msg.pack()
                out.write(packed)
                offset += len(packed)

            # Write filler.
            for i in range(packet.packet_length - offset):
                out.write(b'0')


if __name__ == '__main__':
    main(sys.argv)
