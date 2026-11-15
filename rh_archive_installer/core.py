"""Logique de l'installateur : analyse d'une archive, installation, désinstallation.

Rien ici ne dépend de Qt : tout est testable en ligne de commande.
"""
from __future__ import annotations

import configparser
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from .i18n import _

ICON_NAME = ".rh-icon"          # copie de l'icône, rangée dans le dossier de l'application
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

# (identifiant freedesktop, français, English)
CATEGORIES = (
    ("Utility", "Utilitaires", "Utilities"),
    ("Network", "Internet", "Internet"),
    ("Development", "Développement", "Development"),
    ("Game", "Jeux", "Games"),
    ("Graphics", "Graphisme", "Graphics"),
    ("AudioVideo", "Son et vidéo", "Audio & video"),
    ("Office", "Bureautique", "Office"),
    ("Education", "Éducation", "Education"),
    ("Science", "Sciences", "Science"),
    ("System", "Système", "System"),
)

ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tbz", ".tar")


# --------------------------------------------------------------------------------------
# Chemins
# --------------------------------------------------------------------------------------


def home() -> Path:
    return Path(os.path.expanduser("~"))


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or home() / ".local" / "share")


def cache_home() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or home() / ".cache") / "rh-archive-installer"


def manifests_dir() -> Path:
    return data_home() / "rh-archive-installer" / "installed"


def log_file() -> Path:
    return cache_home() / "journal.log"


def assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


@dataclass(frozen=True)
class Layout:
    install_dir: Path
    bin_link: Path
    desktop_file: Path


def layout(scope: str, app_id: str) -> Layout:
    """Emplacements finaux d'une application pour une portée donnée."""
    if scope == "system":
        return Layout(Path("/opt") / app_id, Path("/usr/local/bin") / app_id,
                      Path("/usr/share/applications") / f"{app_id}.desktop")
    return Layout(home() / ".local" / "opt" / app_id, home() / ".local" / "bin" / app_id,
                  data_home() / "applications" / f"{app_id}.desktop")


def desktop_dir() -> Path:
    """Dossier « Bureau » de l'utilisateur (XDG), éventuellement traduit."""
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or home() / ".config") / "user-dirs.dirs"
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            m = re.match(r'\s*XDG_DESKTOP_DIR\s*=\s*"?([^"]+)"?\s*$', line)
            if m:
                p = Path(m.group(1).replace("$HOME", str(home())))
                if p.is_absolute():
                    return p
    except OSError:
        pass
    for name in ("Desktop", "Bureau"):
        if (home() / name).is_dir():
            return home() / name
    return home() / "Desktop"


# --------------------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------------------


def format_size(n: float) -> str:
    units = ("o", "Ko", "Mo", "Go") if _lang_is_fr() else ("B", "KB", "MB", "GB")
    for u in units[:-1]:
        if n < 1024:
            return f"{n:.0f} {u}" if u == units[0] else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} {units[-1]}"


def _lang_is_fr() -> bool:
    from . import i18n
    return i18n.get_lang() == "fr"


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def run_host(args: list[str], timeout: float = 120) -> tuple[int, str]:
    """Lance une commande de l'hôte ; renvoie (code, sortie)."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, f"{args[0]}: introuvable"
    except subprocess.TimeoutExpired:
        return 124, f"{args[0]}: délai dépassé"


def make_id(name: str) -> str:
    """Identifiant technique sûr (a-z, 0-9, « . _ - ») dérivé d'un nom."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9._-]+", "-", s.lower()).strip("-._")
    s = re.sub(r"-{2,}", "-", s)[:64].strip("-._")
    return s if ID_RE.match(s or "") else "app"


_NOISE = {"linux", "linux64", "linux32", "x86", "x64", "x86_64", "amd64", "i386", "i686", "64bit", "64-bit",
          "glibc", "generic", "portable", "bin", "binary", "release", "stable", "static", "gnu", "musl", "arm64",
          "aarch64", "setup", "installer", "unix", "universal"}


def guess_name(filename: str) -> str:
    """« my-app_1.4.2_linux_x86_64.tar.gz » → « My App »."""
    base = Path(filename).name
    low = base.lower()
    for suf in ARCHIVE_SUFFIXES:
        if low.endswith(suf):
            base = base[: -len(suf)]
            break
    tokens = [t for t in re.split(r"[-_ ]+", base) if t]
    kept: list[str] = []
    for i, t in enumerate(tokens):
        tl = t.lower()
        if i > 0 and (re.match(r"^v?\d[\w.+~]*$", tl) or tl in _NOISE):
            continue
        kept.append(t)
    name = " ".join(kept) or base
    return " ".join(w[:1].upper() + w[1:] if w.islower() else w for w in name.split())


def desktop_escape(text: str) -> str:
    """Valeur de chaîne d'un fichier .desktop (pas de retour à la ligne ni de caractère de contrôle)."""
    text = "".join(c for c in text if c == "\t" or c >= " ")
    return text.replace("\\", "\\\\")


def exec_quote(path: str) -> str:
    """Chemin utilisable dans la clé Exec= (spécification freedesktop)."""
    p = path.replace("%", "%%")
    if re.fullmatch(r"[A-Za-z0-9_./+:@%-]+", p):
        return p
    for ch in ("\\", '"', "`", "$"):
        p = p.replace(ch, "\\" + ch)
    return '"' + p.replace("\\", "\\\\") + '"'


# --------------------------------------------------------------------------------------
# Journal et progression
# --------------------------------------------------------------------------------------


class Reporter:
    """Reçoit journal et progression ; écrit aussi dans le fichier journal."""

    def __init__(self, log: Optional[Callable[[str, str], None]] = None,
                 progress: Optional[Callable[[float, str], None]] = None):
        self._log, self._progress = log, progress
        self.warnings: list[str] = []
        try:
            log_file().parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def log(self, msg: str, level: str = "info") -> None:
        if level == "warn":
            self.warnings.append(msg)
        try:
            with open(log_file(), "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{level}] {msg}\n")
        except OSError:
            pass
        if self._log:
            self._log(msg, level)

    def progress(self, frac: float, text: str = "") -> None:
        if self._progress:
            self._progress(max(0.0, min(1.0, frac)), text)


class InstallError(Exception):
    pass


# --------------------------------------------------------------------------------------
# Analyse de l'archive
# --------------------------------------------------------------------------------------


@dataclass
class Candidate:
    rel: str            # chemin relatif dans l'application (préfixe commun retiré)
    size: int
    kind: str           # elf | script | appimage | other
    score: int = 0
    exec_bit: bool = False


@dataclass
class ArchiveInfo:
    path: str
    prefix: str = ""                 # dossier racine unique de l'archive, retiré à l'installation
    total_size: int = 0
    n_files: int = 0
    candidates: list[Candidate] = field(default_factory=list)
    all_files: list[Candidate] = field(default_factory=list)
    suggested_name: str = ""
    icon_rel: str = ""
    meta: dict = field(default_factory=dict)       # Name / Comment / Categories / Terminal d'un .desktop inclus


_BAD_DIRS = {"lib", "lib32", "lib64", "libs", "share", "include", "doc", "docs", "man", "locale", "plugins",
             "modules", "resources", "site-packages", "python", "node_modules", "test", "tests", "examples",
             "dist-packages", "libexec", "etc", "licenses"}
_BAD_NAMES = ("sandbox", "crash", "updater", "uninstall", "helper", "minidump", "ldd", "pingsender", "gtk-update",
              "chrome_", "xdg-", "install", "setup-", "configure", "build", "test")
_NOT_EXEC_SUFFIX = (".so", ".a", ".o", ".dll", ".txt", ".md", ".png", ".svg", ".json", ".xml", ".html", ".css",
                    ".js", ".pak", ".dat", ".bin.sig", ".pyc", ".h", ".qml", ".ttf", ".otf", ".conf", ".ini",
                    ".desktop", ".rules", ".license", ".log", ".yml", ".yaml", ".toml", ".gz", ".zip", ".mo")
_ICON_SUFFIX = (".png", ".svg", ".xpm")


def _norm(name: str) -> str:
    n = name.replace("\\", "/")
    while n.startswith("./"):
        n = n[2:]
    return n.strip("/")


def _safe_name(n: str) -> bool:
    if not n or n.startswith("/"):
        return False
    return ".." not in PurePosixPath(n).parts


def _is_so(name: str) -> bool:
    return bool(re.search(r"\.so(\.\d+)*$", name))


def analyze(path: str) -> ArchiveInfo:
    """Lit l'archive une seule fois (sans rien extraire) et repère l'exécutable le plus probable."""
    info = ArchiveInfo(path=path)
    info.suggested_name = guess_name(path)
    app_id = make_id(info.suggested_name)
    entries: list[tuple[str, int, int, str, bytes]] = []   # (nom, taille, mode, type, 4 premiers octets)
    tops: set[str] = set()
    dir_names: set[str] = set()
    has_nested = False
    desktop_text = ""
    try:
        with tarfile.open(path, "r:*") as tf:
            read_budget = 6000
            for m in tf:
                n = _norm(m.name)
                if not n or n == "." or not _safe_name(n):
                    continue
                parts = PurePosixPath(n).parts
                tops.add(parts[0])
                if len(parts) > 1:
                    has_nested = True
                if m.isdir():
                    dir_names.add(n)
                    continue
                if not (m.isreg() or m.issym()):
                    continue
                head = b""
                if m.isreg() and m.size > 0:
                    low = n.lower()
                    if (m.mode & 0o111 or "." not in PurePosixPath(n).name
                            or low.endswith((".sh", ".appimage", ".run", ".bin"))) and read_budget > 0:
                        read_budget -= 1
                        f = tf.extractfile(m)
                        if f:
                            head = f.read(4)
                    if low.endswith(".desktop") and not desktop_text and m.size < 65536:
                        f = tf.extractfile(m)
                        if f:
                            desktop_text = f.read().decode("utf-8", "replace")
                entries.append((n, m.size if m.isreg() else 0, m.mode, "l" if m.issym() else "f", head))
    except (tarfile.TarError, EOFError, OSError, ValueError) as exc:
        if isinstance(exc, (tarfile.ReadError, EOFError)):
            raise InstallError(_("Ce fichier n’est pas une archive valide (.tar.gz, .tar.xz, .tar.bz2) ou il est corrompu.")) from exc
        raise InstallError(_("Archive illisible : {err}", err=str(exc).splitlines()[0])) from exc
    if not entries:
        raise InstallError(_("L’archive ne contient aucun fichier."))

    if len(tops) == 1:
        top = next(iter(tops))
        if has_nested or top in dir_names:
            info.prefix = top

    def rel(n: str) -> Optional[str]:
        if info.prefix:
            if n == info.prefix:
                return None
            return n[len(info.prefix) + 1:]
        return n

    stem = re.sub(r"[^a-z0-9]", "", info.suggested_name.lower())
    icons: list[tuple[int, str]] = []
    for n, size, mode, typ, head in entries:
        r = rel(n)
        if not r:
            continue
        info.n_files += 1
        info.total_size += size
        low = r.lower()
        name_low = PurePosixPath(low).name
        kind = ("elf" if head == b"\x7fELF" else "script" if head[:2] == b"#!" else
                "appimage" if low.endswith(".appimage") else "other")
        exec_bit = bool(mode & 0o111)
        cand = Candidate(r, size, kind, 0, exec_bit)
        info.all_files.append(cand)
        if typ == "f" and low.endswith(_ICON_SUFFIX):
            sc = 0
            st = re.sub(r"[^a-z0-9]", "", PurePosixPath(low).stem)
            if st and st == stem:
                sc += 50
            if st in ("icon", "logo", "appicon", "app", "main"):
                sc += 30
            if any(p in ("icons", "pixmaps", "hicolor", "icon") for p in PurePosixPath(low).parts[:-1]):
                sc += 15
            if low.endswith(".svg"):
                sc += 10
            if "symbolic" in low or "tray" in low or "banner" in low or "splash" in low:
                sc -= 60
            sc += min(size // 20000, 20)
            icons.append((sc, r))
        if typ != "f" or name_low.endswith(_NOT_EXEC_SUFFIX) or _is_so(name_low):
            continue
        if not (exec_bit or kind in ("elf", "script", "appimage") or name_low.endswith(".sh")):
            continue
        sc = {"elf": 40, "appimage": 45, "script": 25}.get(kind, 10 if name_low.endswith(".sh") else 0)
        sc += 10 if exec_bit else 0
        parts = PurePosixPath(r).parts
        depth = len(parts) - 1
        if depth == 0:
            sc += 30
        elif parts[0] in ("bin", "usr") and depth <= 2:
            sc += 25
        else:
            sc -= 6 * depth
        if any(p.lower() in _BAD_DIRS for p in parts[:-1]):
            sc -= 40
        nm = re.sub(r"[^a-z0-9]", "", PurePosixPath(name_low).stem)
        if nm and stem and (nm == stem or nm == app_id.replace("-", "")):
            sc += 35
        elif nm and stem and (stem.startswith(nm) or nm.startswith(stem)):
            sc += 15
        if any(b in name_low for b in _BAD_NAMES):
            sc -= 30
        cand.score = sc
        info.candidates.append(cand)
    info.candidates.sort(key=lambda c: (-c.score, c.rel))
    info.candidates = info.candidates[:200]
    info.all_files.sort(key=lambda c: c.rel)

    if desktop_text:
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str  # type: ignore[assignment]
        try:
            cp.read_string(desktop_text)
            sec = cp["Desktop Entry"]
            info.meta = {k: sec.get(k, "") for k in ("Name", "Comment", "Categories", "Terminal", "Icon")}
            wanted = re.sub(r"[^a-z0-9]", "", info.meta.get("Icon", "").lower())
            if wanted:
                icons = [((s + 60) if re.sub(r"[^a-z0-9]", "", PurePosixPath(r.lower()).stem) == wanted else s, r)
                         for s, r in icons]
        except (configparser.Error, KeyError):
            info.meta = {}
    if icons:
        icons.sort(key=lambda t: (-t[0], t[1]))
        if icons[0][0] > -20:
            info.icon_rel = icons[0][1]
    return info


# --------------------------------------------------------------------------------------
# Installation
# --------------------------------------------------------------------------------------


@dataclass
class Options:
    scope: str = "user"                 # user | system
    exe_rel: str = ""
    name: str = ""
    app_id: str = ""
    category: str = "Utility"
    terminal: bool = False
    desktop_shortcut: bool = False
    comment: str = ""


@dataclass
class InstallResult:
    ok: bool
    app_id: str = ""
    name: str = ""
    install_dir: str = ""
    exe: str = ""
    desktop_file: str = ""
    shortcut: str = ""
    error: str = ""


def validate_exe_rel(rel: str) -> str:
    p = PurePosixPath(rel)
    if not rel or p.is_absolute() or ".." in p.parts:
        raise InstallError(_("Chemin de l’exécutable invalide."))
    return str(p)


def build_desktop_entry(opts: Options, install_dir: Path, icon: Path) -> str:
    exe = install_dir / opts.exe_rel
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        f"Name={desktop_escape(opts.name)}",
    ]
    if opts.comment:
        lines.append(f"Comment={desktop_escape(opts.comment)}")
    lines += [
        f"Exec={exec_quote(str(exe))} %F",
        f"Path={desktop_escape(str(exe.parent))}",
        f"Icon={desktop_escape(str(icon))}",
        f"Terminal={'true' if opts.terminal else 'false'}",
        f"Categories={opts.category};",
        "StartupNotify=true",
        "X-RH-ArchiveInstaller=true",
        "",
    ]
    return "\n".join(lines)


def _extract(info: ArchiveInfo, dest: Path, rep: Reporter, lo: float, hi: float) -> None:
    total = max(info.total_size, 1)
    done = 0
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(info.path, "r:*") as tf:
        for m in tf:
            n = _norm(m.name)
            if not n or n == "." or not _safe_name(n):
                continue
            try:
                tf.extract(m, str(dest), filter="data")
            except (tarfile.FilterError, OSError) as exc:
                rep.log(_("Ignoré : {nom} ({err})", nom=n, err=str(exc).splitlines()[0]), "warn")
                continue
            if m.isreg():
                done += m.size
                rep.progress(lo + (hi - lo) * min(done / total, 1.0), _("Extraction de l’archive…"))


def _sh_script_system_install(stage_app: Path, stage_desktop: Path, lay: Layout, app_id: str, exe_rel: str) -> str:
    q = shlex.quote
    return "\n".join([
        "set -e",
        f"rm -rf -- {q(str(lay.install_dir))}",
        "mkdir -p /opt /usr/local/bin /usr/share/applications",
        f"cp -a -- {q(str(stage_app))} {q(str(lay.install_dir))}",
        f"chown -R root:root {q(str(lay.install_dir))}",
        f"chmod -R a+rX,go-w {q(str(lay.install_dir))}",
        f"ln -sfn {q(str(lay.install_dir / exe_rel))} {q(str(lay.bin_link))}",
        f"install -m 644 {q(str(stage_desktop))} {q(str(lay.desktop_file))}",
        "command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications || true",
        "exit 0",
    ])


def _pkexec(script: str, rep: Reporter) -> None:
    if which("pkexec") is None:
        raise InstallError(_("pkexec est introuvable : l’installation pour tous les utilisateurs est impossible."))
    code, out = run_host(["pkexec", "/bin/sh", "-c", script], timeout=900)
    if code != 0:
        if code in (126, 127) and not out.strip():
            raise InstallError(_("Authentification refusée ou annulée."))
        raise InstallError(_("Échec de l’opération administrateur (code {c}) : {o}", c=code, o=out[-400:]))


def _refresh_caches(rep: Reporter) -> None:
    udd = which("update-desktop-database")
    if udd:
        run_host([udd, str(layout("user", "x").desktop_file.parent)], timeout=60)
    for tool in ("kbuildsycoca6", "kbuildsycoca5"):
        if which(tool):
            run_host([tool], timeout=90)
            break
    if which("xdg-desktop-menu"):
        run_host(["xdg-desktop-menu", "forceupdate"], timeout=60)


def install(info: ArchiveInfo, opts: Options, rep: Reporter) -> InstallResult:
    """Extrait l'archive, intègre l'application au menu et (au choix) au bureau."""
    app_id = opts.app_id
    if not ID_RE.match(app_id):
        raise InstallError(_("Identifiant d’application invalide."))
    exe_rel = validate_exe_rel(opts.exe_rel)
    lay = layout(opts.scope, app_id)
    cache_home().mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="stage-", dir=str(cache_home())))
    try:
        rep.log(_("Lecture de l’archive : {nom}", nom=Path(info.path).name))
        raw = stage / "raw"
        _extract(info, raw, rep, 0.0, 0.62)
        app_dir = raw / info.prefix if info.prefix else raw
        exe_path = app_dir / exe_rel
        if not exe_path.is_file():
            raise InstallError(_("L’exécutable choisi est introuvable dans l’archive : {nom}", nom=exe_rel))
        if not exe_path.resolve().is_relative_to(app_dir.resolve()):
            raise InstallError(_("L’exécutable choisi pointe hors de l’application."))
        staged = stage / "app"
        shutil.move(str(app_dir), str(staged))
        rep.progress(0.66, _("Préparation de l’intégration…"))
        # droits d'exécution
        exe_staged = staged / exe_rel
        exe_staged.chmod(exe_staged.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        rep.log(_("Exécutable : {nom}", nom=exe_rel))
        # icône
        icon_src = staged / info.icon_rel if info.icon_rel else None
        if icon_src is not None and icon_src.is_file() and not icon_src.is_symlink():
            ext = icon_src.suffix.lower()
        else:
            icon_src, ext = assets_dir() / "star.svg", ".svg"
            rep.log(_("Aucune icône trouvée : icône par défaut."))
        icon_dst = staged / f"{ICON_NAME}{ext}"
        shutil.copyfile(icon_src, icon_dst)
        icon_final = lay.install_dir / icon_dst.name
        desktop_text = build_desktop_entry(opts, lay.install_dir, icon_final)
        stage_desktop = stage / f"{app_id}.desktop"
        stage_desktop.write_text(desktop_text, encoding="utf-8")

        rep.progress(0.72, _("Copie vers la destination…"))
        if opts.scope == "system":
            rep.log(_("Droits administrateur requis (fenêtre d’authentification)."))
            _pkexec(_sh_script_system_install(staged, stage_desktop, lay, app_id, exe_rel), rep)
        else:
            for d in (lay.install_dir.parent, lay.bin_link.parent, lay.desktop_file.parent):
                d.mkdir(parents=True, exist_ok=True)
            if lay.install_dir.exists() or lay.install_dir.is_symlink():
                shutil.rmtree(lay.install_dir, ignore_errors=True)
            shutil.move(str(staged), str(lay.install_dir))
            if lay.bin_link.is_symlink() or lay.bin_link.exists():
                lay.bin_link.unlink()
            lay.bin_link.symlink_to(lay.install_dir / exe_rel)
            shutil.copyfile(stage_desktop, lay.desktop_file)
            lay.desktop_file.chmod(0o644)
        rep.log(_("Entrée de menu : {nom}", nom=str(lay.desktop_file)))
        rep.log(_("Commande : {nom}", nom=str(lay.bin_link)))

        shortcut = ""
        if opts.desktop_shortcut:
            rep.progress(0.88, _("Création du raccourci sur le bureau…"))
            dd = desktop_dir()
            dd.mkdir(parents=True, exist_ok=True)
            sc = dd / f"{app_id}.desktop"
            shutil.copyfile(stage_desktop, sc)
            sc.chmod(0o755)
            if which("gio"):
                run_host(["gio", "set", str(sc), "metadata::trusted", "true"], timeout=20)
            shortcut = str(sc)
            rep.log(_("Raccourci sur le bureau : {nom}", nom=shortcut))

        rep.progress(0.93, _("Mise à jour des menus…"))
        _refresh_caches(rep)
        write_manifest(opts, lay, shortcut, info)
        rep.progress(1.0, _("Terminé"))
        return InstallResult(True, app_id, opts.name, str(lay.install_dir), str(lay.install_dir / exe_rel),
                             str(lay.desktop_file), shortcut)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


# --------------------------------------------------------------------------------------
# Applications installées / désinstallation
# --------------------------------------------------------------------------------------


def write_manifest(opts: Options, lay: Layout, shortcut: str, info: ArchiveInfo) -> None:
    manifests_dir().mkdir(parents=True, exist_ok=True)
    data = {
        "id": opts.app_id, "name": opts.name, "scope": opts.scope, "exe": opts.exe_rel,
        "install_dir": str(lay.install_dir), "bin_link": str(lay.bin_link),
        "desktop_file": str(lay.desktop_file), "shortcut": shortcut,
        "archive": Path(info.path).name, "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (manifests_dir() / f"{opts.app_id}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                                         encoding="utf-8")


def list_installed() -> list[dict]:
    out: list[dict] = []
    try:
        files = sorted(manifests_dir().glob("*.json"))
    except OSError:
        return out
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and ID_RE.match(str(d.get("id", ""))) and d.get("scope") in ("user", "system"):
            out.append(d)
    return out


def get_installed(app_id: str) -> Optional[dict]:
    return next((d for d in list_installed() if d["id"] == app_id), None)


def uninstall(app_id: str, rep: Reporter) -> None:
    """Supprime une application installée par cet assistant.

    Les chemins sont recalculés à partir de l'identifiant (jamais lus dans le manifeste),
    donc un manifeste modifié ne peut pas faire supprimer autre chose.
    """
    d = get_installed(app_id)
    if not d:
        raise InstallError(_("Application inconnue : {nom}", nom=app_id))
    lay = layout(d["scope"], app_id)
    rep.progress(0.1, _("Suppression des fichiers…"))
    if d["scope"] == "system":
        q = shlex.quote
        script = "\n".join([
            "set -e",
            f"rm -rf -- {q(str(lay.install_dir))}",
            f"rm -f -- {q(str(lay.bin_link))} {q(str(lay.desktop_file))}",
            "command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications || true",
            "exit 0",
        ])
        rep.log(_("Droits administrateur requis (fenêtre d’authentification)."))
        _pkexec(script, rep)
    else:
        shutil.rmtree(lay.install_dir, ignore_errors=True)
        for p in (lay.bin_link, lay.desktop_file):
            try:
                if p.is_symlink() or p.exists():
                    p.unlink()
            except OSError as exc:
                rep.log(_("Ignoré : {nom} ({err})", nom=str(p), err=str(exc)), "warn")
    rep.log(_("Fichiers supprimés : {nom}", nom=str(lay.install_dir)))
    sc = desktop_dir() / f"{app_id}.desktop"
    try:
        if sc.exists() and "X-RH-ArchiveInstaller=true" in sc.read_text(encoding="utf-8", errors="replace"):
            sc.unlink()
            rep.log(_("Raccourci supprimé : {nom}", nom=str(sc)))
    except OSError:
        pass
    rep.progress(0.8, _("Mise à jour des menus…"))
    _refresh_caches(rep)
    try:
        (manifests_dir() / f"{app_id}.json").unlink()
    except OSError:
        pass
    rep.progress(1.0, _("Terminé"))


def launch(path: str) -> None:
    """Lance l'application installée, détachée de l'installateur."""
    subprocess.Popen([path], cwd=str(Path(path).resolve().parent), start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
