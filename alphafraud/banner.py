"""CLI styling -- stdlib-only (no pyfiglet/rich dependency) so the banner and colored
status lines work on whatever bare python3 runs `init`, before the managed venv exists.

Respects NO_COLOR (https://no-color.org) and auto-disables on a non-tty (piped output,
log redirection, journald under systemd) so scripted/service use stays clean.

The palette matches the marcdeller.com brand tokens used across ChemSage / BoltzMaker
and the web app's :root CSS custom properties, so terminal and HTML read as one product.
"""

import os
import sys

_NO_COLOR = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()


def _c(code: str) -> str:
    return "" if _NO_COLOR else code


_RESET = _c("\x1b[0m")
_BOLD = _c("\x1b[1m")
_DIM = _c("\x1b[2m")
# marcdeller.com brand palette (see alphafraud/static/brand.css :root).
_BLUE = _c("\x1b[38;2;30;115;190m")    # #1e73be -- primary
_CYAN = _c("\x1b[38;2;74;159;212m")    # #4a9fd4 -- primary-light
_AMBER = _c("\x1b[38;2;252;185;0m")    # #fcb900 -- accent
_GREEN = _c("\x1b[38;2;0;208;132m")    # #00d084 -- accent-green
_RED = _c("\x1b[38;2;214;39;40m")

# Plain-text banner (also embedded verbatim as a <pre> in the web header, so keep it
# ASCII-only and stable -- the brand palette is applied there via CSS, here via ANSI).
BANNER_ART = r"""
    ___    __      __          ______                     __
   /   |  / /___  / /_  ____ _/ ____/________ ___  ______/ /
  / /| | / / __ \/ __ \/ __ `/ /_  / ___/ __ `/ / / / __  /
 / ___ |/ / /_/ / / / / /_/ / __/ / /  / /_/ / /_/ / /_/ /
/_/  |_/_/ .___/_/ /_/\__,_/_/   /_/   \__,_/\__,_/\__,_/
        /_/
"""

_TAGLINE = "new PDB depositions vs. their blind AlphaFold predictions"


def print_banner() -> None:
    """Print the AlphaFraud banner. Collapses to a bare word when color is disabled."""
    if _NO_COLOR:
        print("AlphaFraud")
        return
    print()
    for line in BANNER_ART.strip("\n").splitlines():
        print(f"{_BOLD}{_BLUE}{line}{_RESET}")
    print(f"  {_DIM}{_TAGLINE}{_RESET}")
    print()


def ok(msg: str) -> None:
    print(f"{_GREEN}✓{_RESET} {msg}")


def info(msg: str) -> None:
    print(f"{_BLUE}ℹ{_RESET} {msg}")


def step(msg: str) -> None:
    print(f"{_CYAN}→{_RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{_AMBER}⚠{_RESET} {msg}")


def err(msg: str) -> None:
    print(f"{_RED}✗{_RESET} {msg}")
