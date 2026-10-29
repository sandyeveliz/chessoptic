"""Allow `python -m chessoptic`."""

import sys

from chessoptic.cli import main

if __name__ == "__main__":
    sys.exit(main())
