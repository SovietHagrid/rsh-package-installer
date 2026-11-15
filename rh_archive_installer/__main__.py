"""Point d'entrée : assistant graphique ; un chemin d'archive peut être passé en argument."""
import argparse
import sys

from . import i18n
from .version import APP_VERSION


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rh-archive-installer",
                                 description="Installe un logiciel téléchargé en .tar.gz (menu, bureau, FR/EN).")
    ap.add_argument("archive", nargs="?", help="archive à installer (.tar.gz, .tgz, .tar.xz, .tar.bz2)")
    ap.add_argument("--lang", choices=i18n.CODES, help="langue initiale (fr ou en)")
    ap.add_argument("--selftest", action="store_true", help="construit la fenêtre puis quitte")
    ap.add_argument("--version", action="version", version=f"rh-archive-installer {APP_VERSION}")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    from . import gui
    lang = args.lang or i18n.detect_lang()
    if args.selftest:
        return gui.selftest(lang)
    return gui.main(lang, args.archive)


if __name__ == "__main__":
    sys.exit(main())
