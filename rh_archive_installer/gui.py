"""Assistant graphique (PySide6) aux couleurs du thème République Hagridienne."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFontDatabase, QIcon
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import core, i18n
from .i18n import _
from .version import APP_VERSION

ARROW = (core.assets_dir() / "arrow-down.svg").as_posix()
NIGHT, PANEL, TEXT = "#020818", "#0a1628", "#cce0ff"
CYAN, PINK, GOLD, LIME, SEL = "#00f5ff", "#ff00cc", "#ffd700", "#00ff88", "#d400a8"
MUTED = "#8aa0c8"

QSS = f"""
* {{ color: {TEXT}; font-size: 11pt; }}
QWidget#root, QStackedWidget, QWidget#page, QDialog, QFileDialog {{ background: {PANEL}; }}
QFrame#sidebar {{ background: {NIGHT}; border-right: 2px solid {CYAN}; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ color: {CYAN}; font-family: Orbitron; font-size: 19pt; font-weight: bold; }}
QLabel#h2 {{ color: {GOLD}; font-family: Orbitron; font-size: 12pt; font-weight: bold; }}
QLabel#brand {{ color: {CYAN}; font-family: Orbitron; font-size: 12pt; font-weight: bold; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#step {{ color: {MUTED}; padding: 5px 8px; }}
QLabel#stepOn {{ color: {NIGHT}; background: {CYAN}; padding: 5px 8px; font-weight: bold; }}
QLabel#stepDone {{ color: {LIME}; padding: 5px 8px; }}
QPushButton {{ background: {PANEL}; border: 2px solid {CYAN}; color: {CYAN}; padding: 7px 20px; }}
QPushButton:hover {{ border-color: {PINK}; color: {PINK}; }}
QPushButton:disabled {{ border-color: #2a3b5c; color: #4d5f80; }}
QPushButton#primary {{ background: {CYAN}; color: {NIGHT}; font-weight: bold; }}
QPushButton#primary:hover {{ background: {PINK}; border-color: {PINK}; color: white; }}
QPushButton#primary:disabled {{ background: #1b2c48; border-color: #2a3b5c; color: #4d5f80; }}
QPushButton#link {{ border: none; color: {MUTED}; padding: 2px 4px; text-decoration: underline; }}
QPushButton#link:hover {{ color: {PINK}; }}
QFrame#card {{ background: {NIGHT}; border: 2px solid #2a3b5c; }}
QFrame#card[sel="true"] {{ border-color: {PINK}; }}
QFrame#card[off="true"] {{ border-color: #14233f; }}
QFrame#card QLabel, QFrame#card QRadioButton {{ background: transparent; }}
QFrame#drop {{ background: {NIGHT}; border: 2px dashed {CYAN}; }}
QFrame#drop[hot="true"] {{ border-color: {PINK}; background: #14102c; }}
QFrame#drop QLabel {{ background: transparent; }}
QListWidget {{ background: {NIGHT}; border: 2px solid {CYAN}; outline: none; }}
QListWidget::item {{ padding: 6px 4px; border-bottom: 1px solid #14233f; }}
QListWidget::item:selected {{ background: {SEL}; color: white; }}
QLineEdit, QComboBox {{ background: {NIGHT}; border: 2px solid #2a3b5c; padding: 6px 8px; selection-background-color: {SEL}; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {CYAN}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{ARROW}"); width: 14px; height: 10px; }}
QAbstractItemView {{ background: {NIGHT}; border: 2px solid {CYAN}; selection-background-color: {SEL}; selection-color: white; outline: none; }}
QHeaderView::section {{ background: {NIGHT}; color: {CYAN}; border: none; padding: 4px; }}
QCheckBox, QRadioButton {{ spacing: 9px; background: transparent; }}
QListWidget::indicator {{ width: 14px; height: 14px; border: 2px solid {CYAN}; background: {NIGHT}; margin-left: 4px; }}
QListWidget::indicator:checked {{ background: {CYAN}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 14px; height: 14px; border: 2px solid {CYAN}; background: {NIGHT}; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ background: {CYAN}; border-color: {CYAN}; }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ border-color: #2a3b5c; }}
QProgressBar {{ border: 2px solid {CYAN}; background: {NIGHT}; height: 16px; text-align: center; color: {TEXT}; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {CYAN}, stop:1 {PINK}); }}
QPlainTextEdit, QTextBrowser {{ background: {NIGHT}; border: 2px solid #2a3b5c; font-family: VT323, monospace; font-size: 13pt; }}
QScrollBar:vertical {{ background: {NIGHT}; width: 12px; }}
QScrollBar::handle:vertical {{ background: #2a3b5c; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {NIGHT}; color: {TEXT}; border: 1px solid {CYAN}; }}
QMessageBox {{ background: {PANEL}; }}
"""

ARCHIVE_FILTER = "Archives (*.tar.gz *.tgz *.tar.xz *.txz *.tar.bz2 *.tbz2 *.tar);;* (*)"


# --------------------------------------------------------------------------------------
# Tâches en arrière-plan
# --------------------------------------------------------------------------------------


class Worker(QObject):
    log = Signal(str, str)
    progress = Signal(float, str)
    done = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        rep = core.Reporter(log=lambda m, lv="info": self.log.emit(m, lv),
                            progress=lambda f, t="": self.progress.emit(f, t))
        try:
            res = self.fn(rep)
        except Exception as exc:  # noqa: BLE001
            rep.log(str(exc) if isinstance(exc, core.InstallError) else f"Erreur inattendue : {exc}", "error")
            res = exc
        self.done.emit(res)


class Relay(QObject):
    """Vit dans le thread principal : les signaux du worker y arrivent en file d'attente,
    de sorte que l'interface n'est jamais touchée depuis un autre thread."""

    def __init__(self, parent, on_log, on_progress, on_done):
        super().__init__(parent)
        self._l, self._p, self._d = on_log, on_progress, on_done

    @Slot(str, str)
    def log(self, msg, level):
        if self._l:
            self._l(msg, level)

    @Slot(float, str)
    def progress(self, frac, text):
        if self._p:
            self._p(frac, text)

    @Slot(object)
    def done(self, res):
        if self._d:
            self._d(res)


class Card(QFrame):
    """Carte cliquable contenant un bouton radio, un titre et un texte."""

    def __init__(self, title: str, text: str, badge: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.radio = QRadioButton(title)
        self.radio.setStyleSheet(f"font-family: Orbitron; font-weight: bold; font-size: 12pt; color: {CYAN};")
        self.body = QLabel(text)
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setStyleSheet(f"color: {TEXT}; padding-left: 26px;")
        top = QHBoxLayout()
        top.addWidget(self.radio, 1)
        if badge:
            b = QLabel(badge)
            b.setStyleSheet(f"background: {GOLD}; color: {NIGHT}; font-weight: bold; padding: 2px 8px;")
            top.addWidget(b)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(6)
        lay.addLayout(top)
        lay.addWidget(self.body)
        fx = QGraphicsDropShadowEffect(self)
        fx.setBlurRadius(0)
        fx.setOffset(5, 5)
        fx.setColor(QColor(PINK))
        fx.setEnabled(False)
        self.setGraphicsEffect(fx)
        self.radio.toggled.connect(self._sync)

    def _sync(self, on: bool):
        self.setProperty("sel", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.graphicsEffect().setEnabled(on)

    def set_available(self, ok: bool):
        self.radio.setEnabled(ok)
        self.setEnabled(ok)
        self.setProperty("off", "false" if ok else "true")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, _e):
        if self.radio.isEnabled():
            self.radio.setChecked(True)


def _label(text="", name="", wrap=True) -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    lb.setTextFormat(Qt.TextFormat.RichText)
    return lb


def _page() -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    w.setObjectName("page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(32, 28, 32, 12)
    lay.setSpacing(12)
    return w, lay


def _dot(ok: bool | None) -> str:
    color = LIME if ok else (GOLD if ok is None else PINK)
    return f'<span style="color:{color}">●</span>'


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def star_path() -> Path:
    return core.assets_dir() / "star.svg"


# --------------------------------------------------------------------------------------
# Fenêtre principale
# --------------------------------------------------------------------------------------


class Wizard(QWidget):
    PAGE_BUILDERS = (("archive", "_p_archive"), ("scope", "_p_scope"), ("exe", "_p_exe"), ("integ", "_p_integ"),
                     ("summary", "_p_summary"), ("progress", "_p_progress"), ("finish", "_p_finish"),
                     ("uninst", "_p_uninst"), ("uninst_done", "_p_uninst_done"))

    def __init__(self, lang: str = "fr", archive: str | None = None):
        super().__init__()
        i18n.set_lang(lang)
        self.setObjectName("root")
        self.setAcceptDrops(True)
        self.setWindowTitle(_("Installeur d’archives — République Hagridienne"))
        self.resize(980, 680)
        self.setMinimumSize(900, 640)
        self.flow = "install"
        self.info: core.ArchiveInfo | None = None
        self.archive_path = ""
        self.scope = "user"
        self.exe_rel = ""
        self.want_shortcut = False
        self.result: core.InstallResult | None = None
        self.uninst_name = ""
        self._busy = False
        self._analyzing = False
        self._threads: list[QThread] = []
        self._exe_for = None
        self._integ_for = None
        self.key = "lang"

        self._build_sidebar()
        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {"lang": self._p_lang()}
        self.stack.addWidget(self.pages["lang"])
        self._build_pages()

        self.btn_back = QPushButton(_("Retour"))
        self.btn_next = QPushButton(_("Suivant"))
        self.btn_next.setObjectName("primary")
        self.btn_quit = QPushButton(_("Quitter"))
        self.btn_back.clicked.connect(self.go_back)
        self.btn_next.clicked.connect(self.go_next)
        self.btn_quit.clicked.connect(self.close)
        bar = QHBoxLayout()
        bar.setContentsMargins(32, 6, 32, 18)
        bar.setSpacing(12)
        bar.addWidget(self.btn_quit)
        bar.addStretch(1)
        bar.addWidget(self.btn_back)
        bar.addWidget(self.btn_next)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self.stack, 1)
        right.addLayout(bar)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.sidebar)
        root.addLayout(right, 1)

        self.go("lang")
        if archive:
            QTimer.singleShot(0, lambda: self.load_archive(archive))

    # ---- langue ---------------------------------------------------------------------
    def _build_pages(self):
        """(Re)crée toutes les pages, sauf celle de la langue, dans la langue courante."""
        for key, _b in self.PAGE_BUILDERS:
            old = self.pages.pop(key, None)
            if old is not None:
                self.stack.removeWidget(old)
                old.setParent(None)
                old.deleteLater()
        for key, builder in self.PAGE_BUILDERS:
            self.pages[key] = getattr(self, builder)()
            self.stack.addWidget(self.pages[key])
        self._built_lang = i18n.get_lang()
        self._exe_for = None
        self._integ_for = None
        if self.info is not None:
            self._render_info()

    def _p_lang(self):
        w, lay = _page()
        lay.addWidget(_label("Langue · Language", "h1"))
        lay.addWidget(_label("Choisissez la langue de l’assistant · Choose the language of the installer", "muted"))
        lay.addSpacing(8)
        greeting = {"fr": "Bienvenue dans le futur !", "en": "Welcome to the future!"}
        grp = QButtonGroup(self)
        self.lang_cards: dict[str, Card] = {}
        for code, name in i18n.LANGS:
            card = Card(name, greeting[code])
            grp.addButton(card.radio)
            self.lang_cards[code] = card
            lay.addWidget(card)
        self.lang_cards[i18n.get_lang()].radio.setChecked(True)
        for code, card in self.lang_cards.items():
            card.radio.toggled.connect(lambda on, c=code: on and self._on_lang(c))
        lay.addStretch(1)
        return w

    def _on_lang(self, code: str):
        """Changement immédiat des textes communs (boutons, barre latérale, titre)."""
        i18n.set_lang(code)
        self.setWindowTitle(_("Installeur d’archives — République Hagridienne"))
        self.btn_back.setText(_("Retour"))
        self.btn_quit.setText(_("Quitter"))
        if self.key == "lang":
            self.btn_next.setText(_("Suivant"))
        self.sub_label.setText(_("Installeur d’archives"))
        self.ver_label.setText(_("Version {v}", v=APP_VERSION))
        self._refresh_steps()

    def _apply_language(self):
        if self._built_lang != i18n.get_lang():
            self._build_pages()

    # ---- barre latérale -------------------------------------------------------------
    def _build_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(250)
        lay = QVBoxLayout(self.sidebar)
        lay.setContentsMargins(18, 26, 18, 18)
        lay.setSpacing(4)
        if star_path().exists():
            sv = QSvgWidget(str(star_path()))
            sv.setFixedSize(84, 84)
            sv.setStyleSheet("background: transparent;")
            lay.addWidget(sv, 0, Qt.AlignmentFlag.AlignHCenter)
        brand = _label("RÉPUBLIQUE<br>HAGRIDIENNE", "brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(brand)
        self.sub_label = _label(_("Installeur d’archives"), "muted")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.sub_label)
        lay.addSpacing(22)
        self.step_box = QVBoxLayout()
        self.step_box.setSpacing(2)
        lay.addLayout(self.step_box)
        lay.addStretch(1)
        self.ver_label = _label(_("Version {v}", v=APP_VERSION), "muted")
        lay.addWidget(self.ver_label)

    def label_for(self, key: str) -> str:
        return {"lang": _("Langue"), "archive": _("Archive"), "scope": _("Portée"), "exe": _("Exécutable"),
                "integ": _("Intégration"), "summary": _("Récapitulatif"), "progress": _("Progression"),
                "finish": _("Terminé"), "uninst": _("Désinstallation"), "uninst_done": _("Terminé")}[key]

    def steps(self) -> list[str]:
        if self.flow == "uninstall":
            return ["uninst", "progress", "uninst_done"]
        return ["lang", "archive", "scope", "exe", "integ", "summary", "progress", "finish"]

    def _refresh_steps(self):
        while self.step_box.count():
            w = self.step_box.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        order = self.steps()
        cur = order.index(self.key) if self.key in order else 0
        for i, k in enumerate(order):
            lb = QLabel(("✓  " if i < cur else "") + self.label_for(k))
            lb.setObjectName("stepOn" if i == cur else "stepDone" if i < cur else "step")
            self.step_box.addWidget(lb)

    # ---- navigation -----------------------------------------------------------------
    def go(self, key: str):
        self.key = key
        self.stack.setCurrentWidget(self.pages[key])
        self._refresh_steps()
        self.btn_back.setVisible(key in ("archive", "scope", "exe", "integ", "summary", "uninst"))
        self.btn_back.setEnabled(True)
        self.btn_next.setEnabled(True)
        self.btn_next.setText(_("Suivant"))
        self.btn_next.setVisible(True)
        self.btn_quit.setEnabled(not self._busy)
        getattr(self, f"_enter_{key}", lambda: None)()

    def go_next(self):
        if self.key == "failed":
            return self.close()
        if self.key == "finish":
            return self._finish_clicked()
        if self.key == "uninst":
            return self._start_uninstall()
        if self.key == "uninst_done":
            return self.close()
        if self.key == "lang":
            self._apply_language()
        order = self.steps()
        self.go(order[order.index(self.key) + 1])

    def go_back(self):
        if self.key == "failed":
            return self.go("summary")
        if self.key == "uninst":
            self.flow = "install"
            return self.go("archive")
        order = self.steps()
        self.go(order[order.index(self.key) - 1])

    def set_busy(self, busy: bool):
        self._busy = busy
        for b in (self.btn_back, self.btn_next, self.btn_quit):
            b.setEnabled(not busy)

    def run_async(self, fn, on_log=None, on_progress=None, on_done=None):
        th, wk = QThread(self), Worker(fn)
        wk.moveToThread(th)

        def finished(res):
            th.quit()
            th.wait()
            self._threads.remove(th)
            if on_done:
                on_done(res)

        relay = Relay(self, on_log, on_progress, finished)
        th.started.connect(wk.run)
        wk.log.connect(relay.log, Qt.ConnectionType.QueuedConnection)
        wk.progress.connect(relay.progress, Qt.ConnectionType.QueuedConnection)
        wk.done.connect(relay.done, Qt.ConnectionType.QueuedConnection)
        th._keep = (wk, relay)  # références
        self._threads.append(th)
        th.start()

    def closeEvent(self, e):
        if self._busy:
            QMessageBox.information(self, _("Opération en cours"), _("Patientez : l’opération n’est pas terminée."))
            e.ignore()
        else:
            e.accept()

    # ---- glisser-déposer -----------------------------------------------------------
    def dragEnterEvent(self, e):
        if self.key == "archive" and not self._busy and e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drop_hot(True)

    def dragLeaveEvent(self, _e):
        self._drop_hot(False)

    def dropEvent(self, e):
        self._drop_hot(False)
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if urls and self.key == "archive":
            self.load_archive(urls[0])

    def _drop_hot(self, on: bool):
        if hasattr(self, "drop"):
            self.drop.setProperty("hot", "true" if on else "false")
            self.drop.style().unpolish(self.drop)
            self.drop.style().polish(self.drop)

    # ---- page : archive -------------------------------------------------------------
    def _p_archive(self):
        w, lay = _page()
        lay.addWidget(_label(_("Archive à installer"), "h1"))
        lay.addWidget(_label(_(
            "Choisissez une archive de logiciel (.tar.gz, .tgz, .tar.xz, .tar.bz2). L’assistant l’extrait, "
            "ajoute le logiciel au menu des applications et, si vous le souhaitez, au bureau.")))
        self.drop = QFrame()
        self.drop.setObjectName("drop")
        dl = QVBoxLayout(self.drop)
        dl.setContentsMargins(20, 18, 20, 18)
        dl.setSpacing(10)
        t = _label("⭐  " + _("Glissez-déposez une archive ici"), "h2")
        t.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        dl.addWidget(t)
        self.btn_browse = QPushButton(_("Parcourir…"))
        self.btn_browse.clicked.connect(self._browse)
        dl.addWidget(self.btn_browse, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.drop)
        self.info_label = _label("")
        lay.addWidget(self.info_label)
        row = QHBoxLayout()
        self.btn_uninstall = QPushButton(_("Applications installées…"))
        self.btn_uninstall.clicked.connect(lambda: self.start_flow("uninstall"))
        row.addWidget(self.btn_uninstall)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _enter_archive(self):
        self.flow = "install"
        self.btn_next.setEnabled(self.info is not None and not self._analyzing)
        n = len(core.list_installed())
        self.btn_uninstall.setVisible(n > 0)
        if n:
            self.btn_uninstall.setText(_("Applications installées ({n})…", n=n))

    def _browse(self):
        dlg = QFileDialog(self, _("Choisir une archive"))
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
        dlg.setNameFilter(ARCHIVE_FILTER)
        dlg.setDirectory(str(core.home() / "Downloads") if (core.home() / "Downloads").is_dir()
                         else str(core.home() / "Téléchargements") if (core.home() / "Téléchargements").is_dir()
                         else str(core.home()))
        dlg.setStyleSheet(QSS)
        if dlg.exec() and dlg.selectedFiles():
            self.load_archive(dlg.selectedFiles()[0])

    def load_archive(self, path: str):
        self.archive_path = path
        self.info = None
        self._analyzing = True
        self._exe_for = None
        self._integ_for = None
        self.btn_next.setEnabled(False)
        self.info_label.setText(f"{_dot(None)} " + _("Analyse de l’archive en cours…"))
        self.run_async(lambda rep: core.analyze(path), on_done=self._analyzed)

    def _analyzed(self, res):
        self._analyzing = False
        if isinstance(res, Exception):
            self.info = None
            self.info_label.setText(f"{_dot(False)} {_esc(str(res))}")
            self.btn_next.setEnabled(False)
            return
        self.info = res
        self._render_info()
        if self.key == "archive":
            self.btn_next.setEnabled(True)

    def _render_info(self):
        i = self.info
        if i is None or not hasattr(self, "info_label"):
            return
        rows = [f"{_dot(True)} <b>{_esc(Path(i.path).name)}</b>",
                _("{n} fichier(s) · {taille} une fois extraite", n=i.n_files, taille=core.format_size(i.total_size))]
        if i.prefix:
            rows.append(_("Dossier racine de l’archive : <b>{nom}</b> (retiré à l’installation)", nom=_esc(i.prefix)))
        if i.candidates:
            rows.append(_("Exécutable probable : <b>{nom}</b>", nom=_esc(i.candidates[0].rel)))
        else:
            rows.append(f"{_dot(None)} " + _("Aucun exécutable évident : vous pourrez le choisir à l’étape suivante."))
        self.info_label.setText("<br>".join(rows))

    def start_flow(self, flow: str):
        self.flow = flow
        self.go("uninst" if flow == "uninstall" else "archive")

    # ---- page : portée --------------------------------------------------------------
    def _p_scope(self):
        w, lay = _page()
        lay.addWidget(_label(_("Pour qui installer ?"), "h1"))
        lay.addWidget(_label(_("Choisissez qui pourra utiliser ce logiciel.")))
        grp = QButtonGroup(self)
        self.card_user = Card(
            _("Moi seulement"),
            _("Installé dans votre dossier personnel (<b>~/.local/opt</b>). Aucun mot de passe n’est demandé ; "
              "les autres utilisateurs de l’ordinateur ne le verront pas."))
        has_pk = core.which("pkexec") is not None
        self.card_system = Card(
            _("Tous les utilisateurs"),
            _("Installé dans <b>/opt</b>, avec une entrée dans le menu de chacun. Le mot de passe administrateur "
              "sera demandé.") + ("" if has_pk else "<br><span style='color:%s'>" % PINK
                                  + _("Indisponible : pkexec est introuvable sur ce système.") + "</span>"),
            _("Admin"))
        self.card_system.set_available(has_pk)
        for c in (self.card_user, self.card_system):
            grp.addButton(c.radio)
            lay.addWidget(c)
        if self.scope == "system" and has_pk:
            self.card_system.radio.setChecked(True)
        else:
            self.scope = "user"
            self.card_user.radio.setChecked(True)
        self.card_user.radio.toggled.connect(lambda on: on and setattr(self, "scope", "user"))
        self.card_system.radio.toggled.connect(lambda on: on and setattr(self, "scope", "system"))
        lay.addStretch(1)
        return w

    # ---- page : exécutable ----------------------------------------------------------
    def _p_exe(self):
        w, lay = _page()
        lay.addWidget(_label(_("Quel est le fichier exécutable ?"), "h1"))
        lay.addWidget(_label(_("C’est le fichier qui lance le logiciel. La liste est triée du plus probable au "
                               "moins probable ; vérifiez le premier choix.")))
        self.exe_list = QListWidget()
        self.exe_list.currentItemChanged.connect(self._exe_changed)
        self.exe_list.itemDoubleClicked.connect(lambda _i: self.btn_next.isEnabled() and self.go_next())
        lay.addWidget(self.exe_list, 1)
        self.cb_all = QCheckBox(_("Afficher tous les fichiers de l’archive"))
        self.cb_all.toggled.connect(lambda _on: self._fill_exe(keep=True))
        lay.addWidget(self.cb_all)
        self.exe_detail = _label("", "muted")
        lay.addWidget(self.exe_detail)
        return w

    def _enter_exe(self):
        if self._exe_for is not self.info:
            self._exe_for = self.info
            self.cb_all.blockSignals(True)
            self.cb_all.setChecked(not (self.info and self.info.candidates))
            self.cb_all.blockSignals(False)
            self._fill_exe(keep=False)
        self.btn_next.setEnabled(self.exe_list.currentItem() is not None)

    def _fill_exe(self, keep: bool):
        i = self.info
        if i is None:
            return
        prev = self.exe_rel if keep else ""
        self.exe_list.blockSignals(True)
        self.exe_list.clear()
        items = i.all_files[:5000] if self.cb_all.isChecked() else i.candidates
        kinds = {"elf": _("programme"), "script": _("script"), "appimage": "AppImage", "other": _("fichier")}
        sel = None
        for c in items:
            it = QListWidgetItem(f"{c.rel}    ·  {kinds[c.kind]}  ·  {core.format_size(c.size)}")
            it.setData(Qt.ItemDataRole.UserRole, c.rel)
            self.exe_list.addItem(it)
            if prev and c.rel == prev:
                sel = it
        self.exe_list.blockSignals(False)
        if sel is None and self.exe_list.count():
            sel = self.exe_list.item(0)
        if sel is not None:
            self.exe_list.setCurrentItem(sel)
        else:
            self.exe_rel = ""
            self.exe_detail.setText("")
        if self.key == "exe":
            self.btn_next.setEnabled(sel is not None)

    def _exe_changed(self, cur, _prev):
        if cur is None:
            return
        self.exe_rel = cur.data(Qt.ItemDataRole.UserRole)
        self.exe_detail.setText(_("Sera lancé : <b>{nom}</b>", nom=_esc(self.exe_rel)))
        if self.key == "exe":
            self.btn_next.setEnabled(True)

    # ---- page : intégration ---------------------------------------------------------
    def _p_integ(self):
        w, lay = _page()
        lay.addWidget(_label(_("Intégration"), "h1"))
        lay.addWidget(_label(_("Le logiciel sera ajouté au menu des applications. Vérifiez son nom et sa catégorie.")))
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.ed_name = QLineEdit()
        self.ed_name.setMaxLength(80)
        self.cb_cat = QComboBox()
        fr = i18n.get_lang() == "fr"
        for cid, lfr, len_ in core.CATEGORIES:
            self.cb_cat.addItem(lfr if fr else len_, cid)
        self.cb_term = QCheckBox(_("Ce logiciel s’utilise dans un terminal"))
        form.addRow(_label(_("Nom affiché"), "muted"), self.ed_name)
        form.addRow(_label(_("Catégorie du menu"), "muted"), self.cb_cat)
        form.addRow("", self.cb_term)
        lay.addLayout(form)
        lay.addSpacing(6)
        lay.addWidget(_label(_("Mettre un raccourci sur le bureau ?"), "h2"))
        grp = QButtonGroup(self)
        self.card_desk_yes = Card(_("Oui"), _("Une icône du logiciel sera ajoutée sur votre bureau."))
        self.card_desk_no = Card(_("Non"), _("Le logiciel restera accessible depuis le menu des applications."))
        for c in (self.card_desk_yes, self.card_desk_no):
            grp.addButton(c.radio)
            lay.addWidget(c)
        (self.card_desk_yes if self.want_shortcut else self.card_desk_no).radio.setChecked(True)
        self.card_desk_yes.radio.toggled.connect(lambda on: setattr(self, "want_shortcut", on))
        self.ed_name.textChanged.connect(self._integ_valid)
        lay.addStretch(1)
        return w

    def _enter_integ(self):
        if self._integ_for is not self.info and self.info is not None:
            self._integ_for = self.info
            meta = self.info.meta
            self.ed_name.setText((meta.get("Name") or self.info.suggested_name).strip())
            cats = [c for c in (meta.get("Categories", "")).split(";") if c]
            idx = next((self.cb_cat.findData(c) for c in cats if self.cb_cat.findData(c) >= 0), -1)
            self.cb_cat.setCurrentIndex(idx if idx >= 0 else 0)
            self.cb_term.setChecked(meta.get("Terminal", "").lower() == "true")
        self._integ_valid()

    def _integ_valid(self):
        if self.key == "integ":
            self.btn_next.setEnabled(bool(core.make_id(self.ed_name.text().strip())) and bool(self.ed_name.text().strip()))

    # ---- page : récapitulatif -------------------------------------------------------
    def _p_summary(self):
        w, lay = _page()
        lay.addWidget(_label(_("Récapitulatif"), "h1"))
        self.sum_label = _label("")
        lay.addWidget(self.sum_label)
        self.sum_warn = _label("")
        lay.addWidget(self.sum_warn)
        lay.addStretch(1)
        return w

    def options(self) -> core.Options:
        name = self.ed_name.text().strip()
        return core.Options(scope=self.scope, exe_rel=self.exe_rel, name=name, app_id=core.make_id(name),
                            category=self.cb_cat.currentData() or "Utility", terminal=self.cb_term.isChecked(),
                            desktop_shortcut=self.want_shortcut)

    def _enter_summary(self):
        o = self.options()
        lay = core.layout(o.scope, o.app_id)
        yes, no = _("Oui"), _("Non")
        rows = [
            (_("Archive"), _esc(Path(self.archive_path).name)),
            (_("Nom"), _esc(o.name)),
            (_("Pour"), _("Tous les utilisateurs") if o.scope == "system" else _("Moi seulement")),
            (_("Dossier"), _esc(str(lay.install_dir))),
            (_("Exécutable"), _esc(o.exe_rel)),
            (_("Commande"), _esc(lay.bin_link.name)),
            (_("Menu des applications"), yes),
            (_("Raccourci sur le bureau"), yes if o.desktop_shortcut else no),
        ]
        self.sum_label.setText("<table cellspacing='8'>" + "".join(
            f"<tr><td style='color:{MUTED}'>{k}</td><td style='color:{CYAN}'><b>{v}</b></td></tr>" for k, v in rows)
            + "</table>")
        warns = []
        if core.get_installed(o.app_id):
            warns.append(f"{_dot(None)} " + _("« {nom} » est déjà installé : il sera remplacé.", nom=_esc(o.name)))
        if o.scope == "system":
            warns.append(f"{_dot(None)} " + _("Une fenêtre vous demandera le mot de passe administrateur."))
            if o.desktop_shortcut:
                warns.append(f"{_dot(None)} " + _("Le raccourci du bureau ne sera créé que pour votre compte."))
        self.sum_warn.setText("<br>".join(warns))
        self.btn_next.setText(_("Installer"))

    # ---- page : progression ---------------------------------------------------------
    def _p_progress(self):
        w, lay = _page()
        self.prog_title = _label(_("Installation…"), "h1")
        lay.addWidget(self.prog_title)
        self.prog_step = _label("")
        lay.addWidget(self.prog_step)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 1000)
        lay.addWidget(self.prog_bar)
        self.prog_log = QPlainTextEdit()
        self.prog_log.setReadOnly(True)
        lay.addWidget(self.prog_log, 1)
        return w

    def _append_log(self, msg: str, level: str):
        prefix = {"warn": "! ", "error": "✗ "}.get(level, "")
        self.prog_log.appendPlainText(prefix + msg)

    def _on_progress(self, frac: float, text: str):
        self.prog_bar.setValue(int(frac * 1000))
        if text:
            self.prog_step.setText(text)

    def _enter_progress(self):
        self.btn_back.hide()
        self.btn_next.setEnabled(False)
        self.prog_log.clear()
        self.prog_bar.setValue(0)
        self.set_busy(True)
        if self.flow == "uninstall":
            return
        self.prog_title.setText(_("Installation en cours…"))
        info, opts = self.info, self.options()
        self.run_async(lambda rep: core.install(info, opts, rep), on_log=self._append_log,
                       on_progress=self._on_progress, on_done=self._install_done)

    def _install_done(self, res):
        self.set_busy(False)
        self.btn_back.hide()
        if isinstance(res, Exception):
            self.result = None
            self.prog_title.setText(_("Échec de l’installation"))
            self.prog_step.setText(f"{_dot(False)} {_esc(str(res))}")
            self.btn_next.setText(_("Fermer"))
            self.btn_next.setEnabled(True)
            self.btn_back.setText(_("Retour"))
            self.btn_back.show()
            self.key = "failed"
            return
        self.result = res
        self.go("finish")

    # ---- page : terminé -------------------------------------------------------------
    def _p_finish(self):
        w, lay = _page()
        self.fin_title = _label(_("Installation terminée") + " ⭐", "h1")
        lay.addWidget(self.fin_title)
        self.fin_info = _label("")
        lay.addWidget(self.fin_info)
        self.cb_launch = QCheckBox("")
        self.cb_launch.setChecked(True)
        lay.addWidget(self.cb_launch)
        lay.addSpacing(6)
        row = QHBoxLayout()
        self.btn_again = QPushButton(_("Installer une autre archive"))
        self.btn_again.clicked.connect(self._again)
        row.addWidget(self.btn_again)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _enter_finish(self):
        r = self.result
        self.btn_back.hide()
        self.btn_next.setText(_("Terminer"))
        if r is None:
            return
        rows = [f"{_dot(True)} " + _("« {nom} » est installé.", nom=_esc(r.name)),
                f"{_dot(True)} " + _("Il se trouve dans le menu des applications (recherchez « {nom} »).", nom=_esc(r.name))]
        if r.shortcut:
            rows.append(f"{_dot(True)} " + _("Un raccourci a été ajouté sur le bureau."))
        rows.append(f"<span style='color:{MUTED}'>" + _("Dossier : {nom}", nom=_esc(r.install_dir)) + "</span>")
        self.fin_info.setText("<br>".join(rows))
        self.cb_launch.setText(_("Lancer « {nom} » maintenant", nom=r.name))
        self.cb_launch.setChecked(True)

    def _again(self):
        self.info = None
        self.archive_path = ""
        self.info_label.setText("")
        self.go("archive")
        self.btn_next.setEnabled(False)

    def _finish_clicked(self):
        if self.result and self.cb_launch.isChecked():
            try:
                core.launch(self.result.exe)
            except OSError as exc:
                QMessageBox.warning(self, _("Lancement impossible"), str(exc))
                return
        self.close()

    # ---- désinstallation ------------------------------------------------------------
    def _p_uninst(self):
        w, lay = _page()
        lay.addWidget(_label(_("Applications installées"), "h1"))
        lay.addWidget(_label(_("Choisissez une application installée par cet assistant pour la supprimer.")))
        self.un_list = QListWidget()
        self.un_list.currentItemChanged.connect(lambda cur, _p: self.btn_next.setEnabled(cur is not None))
        lay.addWidget(self.un_list, 1)
        return w

    def _enter_uninst(self):
        self.btn_next.setText(_("Désinstaller"))
        self.un_list.clear()
        for d in core.list_installed():
            scope = _("tous les utilisateurs") if d["scope"] == "system" else _("utilisateur")
            it = QListWidgetItem(f"{d['name']}    ·  {scope}  ·  {d['install_dir']}")
            it.setData(Qt.ItemDataRole.UserRole, d["id"])
            it.setData(Qt.ItemDataRole.UserRole + 1, d["name"])
            self.un_list.addItem(it)
        if self.un_list.count():
            self.un_list.setCurrentRow(0)
        self.btn_next.setEnabled(self.un_list.count() > 0)

    def _start_uninstall(self):
        it = self.un_list.currentItem()
        if it is None:
            return
        app_id, name = it.data(Qt.ItemDataRole.UserRole), it.data(Qt.ItemDataRole.UserRole + 1)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(_("Confirmer"))
        box.setText(_("Supprimer « {nom} » et ses fichiers ?", nom=name))
        yes = box.addButton(_("Désinstaller"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(_("Annuler"), QMessageBox.ButtonRole.RejectRole)
        box.setStyleSheet(QSS)
        box.exec()
        if box.clickedButton() is not yes:
            return
        self.uninst_name = name
        self.go("progress")
        self.prog_title.setText(_("Désinstallation en cours…"))
        self.run_async(lambda rep: core.uninstall(app_id, rep), on_log=self._append_log,
                       on_progress=self._on_progress, on_done=self._uninstall_done)

    def _uninstall_done(self, res):
        self.set_busy(False)
        self.btn_back.hide()
        self.uninst_ok = not isinstance(res, Exception)
        self.uninst_msg = str(res) if isinstance(res, Exception) else ""
        self.go("uninst_done")

    def _p_uninst_done(self):
        w, lay = _page()
        self.ud_title = _label("", "h1")
        lay.addWidget(self.ud_title)
        self.ud_info = _label("")
        lay.addWidget(self.ud_info)
        lay.addStretch(1)
        return w

    def _enter_uninst_done(self):
        self.btn_back.hide()
        self.btn_next.setText(_("Fermer"))
        if getattr(self, "uninst_ok", False):
            self.ud_title.setText(_("Désinstallation terminée"))
            self.ud_info.setText(f"{_dot(True)} " + _("« {nom} » a été supprimé.", nom=_esc(self.uninst_name)))
        else:
            self.ud_title.setText(_("Échec de la désinstallation"))
            self.ud_info.setText(f"{_dot(False)} {_esc(getattr(self, 'uninst_msg', ''))}")


# --------------------------------------------------------------------------------------


def _load_fonts():
    d = core.assets_dir() / "fonts"
    for f in d.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


def make_app() -> QApplication:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Installeur d’archives République Hagridienne")
    app.setDesktopFileName("rh-archive-installer")   # associe la fenêtre à l'icône sous Wayland
    ico = core.assets_dir() / "rh-archive-installer.png"
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))
    _load_fonts()
    app.setStyleSheet(QSS)
    return app


def main(lang: str = "fr", archive: str | None = None) -> int:
    app = make_app()
    w = Wizard(lang, archive)
    w.show()
    return app.exec()


def selftest(lang: str = "fr") -> int:
    """Construit la fenêtre et quitte : sert à vérifier un AppImage sans écran."""
    app = make_app()
    w = Wizard(lang)
    w.show()
    QTimer.singleShot(400, app.quit)
    app.exec()
    print("selftest OK")
    return 0
