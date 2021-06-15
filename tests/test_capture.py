
from tempfile import NamedTemporaryFile
import os

import pytest

from c10_tools.capture import main


@pytest.fixture
def args():
    with NamedTemporaryFile() as out:
        yield {'<infile>': pytest.PCAP,
               '<outfile>': out.name,
               '-f': True,
               '-q': True,
               '-t': None}


def test_overwrite(args):
    main(args)
    assert os.stat(args['<outfile>']).st_size == 1552


def test_checks_exists(args):
    args['-f'] = False
    assert os.path.exists(args['<outfile>'])
    with open(args['<outfile>'], 'w+b'), pytest.raises(SystemExit):
        main(args)


def test_tmats(args):
    args['-t'] = pytest.TMATS
    main(args)
    with open(args['<outfile>'], 'rb') as f:
        assert f.read(6351)[28:] == open(pytest.TMATS, 'rb').read()