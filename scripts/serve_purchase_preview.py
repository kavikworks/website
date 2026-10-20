"""Start the explicit loopback-only fake-purchase demonstration."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview.purchase.server import main

if __name__ == "__main__":
    main()
