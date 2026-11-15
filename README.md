# République Hagridienne — Archive Installer · Installeur d'archives

**[English](#english)** · **[Français](#français)**

---

## English

A graphical installer for software downloaded as a `.tar.gz` archive. It extracts the archive, adds the software to your applications menu, and optionally puts a shortcut on your desktop — in French or English, with the neon look of the République Hagridienne Plasma theme.

Built with Python 3 and PySide6 (Qt). Linux x86_64.

### Features

- Supports `.tar.gz`, `.tgz`, `.tar.xz`, `.tar.bz2` and `.tar` (drag and drop, or *Browse…*).
- Asks the questions that matter:
  - **Install for whom?** Just you (`~/.local/opt`, no password) or all users (`/opt`, administrator password through `pkexec`).
  - **Which file is the executable?** Automatic detection, sorted from most to least likely (ELF programs, scripts, AppImages; libraries, sandboxes and updaters are demoted). A checkbox shows every file in the archive.
  - **Desktop shortcut?** Yes or no.
  - Display name, menu category, and "runs in a terminal".
- Creates a `.desktop` menu entry, a command in your `PATH`, and uses the icon found in the archive (or a default star).
- Strips the archive's single top-level folder, and reuses `Name`, `Comment`, `Categories` and `Terminal` from a bundled `.desktop` file if there is one.
- Uninstalls what it installed (*Installed applications…* button).
- French and English; the language is detected from your system and can be changed on the first page.

### Download and run

Download the AppImage from the Releases page, then:

```sh
chmod +x rh_archive_installer_1_0_x86_64.AppImage
./rh_archive_installer_1_0_x86_64.AppImage                     # opens the wizard
./rh_archive_installer_1_0_x86_64.AppImage my-app-1.2.tar.gz   # opens it with an archive
./rh_archive_installer_1_0_x86_64.AppImage --lang en           # force the language (fr or en)
```

Without FUSE, run it with `--appimage-extract-and-run`.

**Requirements:** a recent Linux desktop (X11 or Wayland). "All users" mode needs `pkexec` (polkit) and a running authentication agent, which KDE Plasma provides.

### Where things go

| | Just me | All users |
|---|---|---|
| Application | `~/.local/opt/<id>/` | `/opt/<id>/` |
| Command | `~/.local/bin/<id>` | `/usr/local/bin/<id>` |
| Menu entry | `~/.local/share/applications/<id>.desktop` | `/usr/share/applications/<id>.desktop` |
| Desktop shortcut | your desktop folder (both modes; in "all users" mode, for your account only) | |

The list of installed applications is kept in `~/.local/share/rh-archive-installer/installed/` and the log in `~/.cache/rh-archive-installer/journal.log`.

### Safety

- The archive is read once without being extracted for analysis; extraction uses Python's `data` filter, so absolute paths, `..` and links pointing outside the destination are refused.
- Names are reduced to a safe identifier (`a-z`, `0-9`, `.`, `_`, `-`) and every path is quoted before it reaches a shell or a `.desktop` file.
- Uninstalling recomputes paths from the identifier; it never trusts paths stored in the manifest.
- It installs software you downloaded: **only install archives you trust**.

### Run from source

```sh
pip install PySide6
python3 -m rh_archive_installer [archive.tar.gz] [--lang fr|en]
```

### Build the AppImage

`build.sh` reuses an existing AppImage that already contains Python 3.12 and PySide6 (for example the theme installer's) and swaps in this application.

```sh
# requires: squashfs-tools (unsquashfs, mksquashfs) and python3
./build.sh base.AppImage rh_archive_installer_1_0_x86_64.AppImage
```

### Project layout

```
rh_archive_installer/
  core.py      archive analysis, install, uninstall (no Qt)
  gui.py       PySide6 wizard and stylesheet
  i18n.py      language selection
  catalog.py   French → English translations
  assets/      star logo, icon, Orbitron and VT323 fonts
packaging/     AppRun, launcher, .desktop for the AppImage
build.sh
```

To add a language, add its code in `i18n.py` and a table in `catalog.py` (the French text is the key).

### License

Code: [MIT](LICENSE) (English text is authoritative; a French courtesy translation is included in the same file) © 2026 Soviet_Hagrid.

Third-party components: the **Orbitron** and **VT323** fonts are under the SIL Open Font License 1.1 (texts in `rh_archive_installer/assets/fonts/`). The AppImage also bundles Python (PSF License) and PySide6/Qt (LGPLv3), which keep their own licenses. The MIT license covers this project's own code and assets only.

---

## Français

Un installateur graphique pour les logiciels téléchargés en archive `.tar.gz`. Il extrait l'archive, ajoute le logiciel au menu des applications et, si tu le souhaites, place un raccourci sur le bureau — en français ou en anglais, avec le style néon du thème Plasma République Hagridienne.

Écrit en Python 3 avec PySide6 (Qt). Linux x86_64.

### Fonctionnalités

- Prend en charge `.tar.gz`, `.tgz`, `.tar.xz`, `.tar.bz2` et `.tar` (glisser-déposer ou *Parcourir…*).
- Pose les questions utiles :
  - **Pour qui installer ?** Toi seulement (`~/.local/opt`, sans mot de passe) ou tous les utilisateurs (`/opt`, mot de passe administrateur via `pkexec`).
  - **Quel est l'exécutable ?** Détection automatique, triée du plus probable au moins probable (programmes ELF, scripts, AppImages ; les bibliothèques, bacs à sable et mises à jour sont rétrogradés). Une case affiche tous les fichiers de l'archive.
  - **Raccourci sur le bureau ?** Oui ou non.
  - Nom affiché, catégorie du menu et « s'utilise dans un terminal ».
- Crée l'entrée de menu `.desktop`, une commande dans le `PATH` et utilise l'icône trouvée dans l'archive (ou une étoile par défaut).
- Retire le dossier racine unique de l'archive et reprend `Name`, `Comment`, `Categories` et `Terminal` d'un fichier `.desktop` inclus, s'il y en a un.
- Désinstalle ce qu'il a installé (bouton *Applications installées…*).
- Français et anglais ; la langue est détectée d'après le système et modifiable sur la première page.

### Télécharger et lancer

Télécharge l'AppImage depuis la page Releases, puis :

```sh
chmod +x rh_archive_installer_1_0_x86_64.AppImage
./rh_archive_installer_1_0_x86_64.AppImage                     # ouvre l'assistant
./rh_archive_installer_1_0_x86_64.AppImage mon-logiciel-1.2.tar.gz   # l'ouvre avec une archive
./rh_archive_installer_1_0_x86_64.AppImage --lang fr           # force la langue (fr ou en)
```

Sans FUSE, lance-le avec `--appimage-extract-and-run`.

**Prérequis :** un bureau Linux récent (X11 ou Wayland). Le mode « tous les utilisateurs » demande `pkexec` (polkit) et un agent d'authentification actif, ce que fournit KDE Plasma.

### Où vont les fichiers

| | Moi seulement | Tous les utilisateurs |
|---|---|---|
| Application | `~/.local/opt/<id>/` | `/opt/<id>/` |
| Commande | `~/.local/bin/<id>` | `/usr/local/bin/<id>` |
| Entrée de menu | `~/.local/share/applications/<id>.desktop` | `/usr/share/applications/<id>.desktop` |
| Raccourci du bureau | ton dossier Bureau (dans les deux modes ; en mode « tous », pour ton compte seulement) | |

La liste des applications installées est conservée dans `~/.local/share/rh-archive-installer/installed/` et le journal dans `~/.cache/rh-archive-installer/journal.log`.

### Sécurité

- L'archive est lue une première fois sans extraction pour l'analyser ; l'extraction utilise le filtre `data` de Python, qui refuse les chemins absolus, les `..` et les liens pointant hors de la destination.
- Les noms sont réduits à un identifiant sûr (`a-z`, `0-9`, `.`, `_`, `-`) et chaque chemin est protégé avant d'atteindre un shell ou un fichier `.desktop`.
- La désinstallation recalcule les chemins à partir de l'identifiant ; elle ne fait jamais confiance aux chemins du manifeste.
- Il installe des logiciels que tu as téléchargés : **n'installe que des archives de confiance**.

### Lancer depuis les sources

```sh
pip install PySide6
python3 -m rh_archive_installer [archive.tar.gz] [--lang fr|en]
```

### Construire l'AppImage

`build.sh` réutilise un AppImage existant qui contient déjà Python 3.12 et PySide6 (par exemple celui de l'installeur du thème) et y remplace l'application.

```sh
# nécessite : squashfs-tools (unsquashfs, mksquashfs) et python3
./build.sh base.AppImage rh_archive_installer_1_0_x86_64.AppImage
```

### Structure du projet

```
rh_archive_installer/
  core.py      analyse, installation, désinstallation (sans Qt)
  gui.py       assistant PySide6 et feuille de style
  i18n.py      choix de la langue
  catalog.py   traductions français → anglais
  assets/      logo étoile, icône, polices Orbitron et VT323
packaging/     AppRun, lanceur, .desktop de l'AppImage
build.sh
```

Pour ajouter une langue : son code dans `i18n.py` et une table dans `catalog.py` (le texte français sert de clé).

### Licence

Code : [MIT](LICENSE) (le texte anglais fait foi ; une traduction française de courtoisie figure dans le même fichier) © 2026 Soviet_Hagrid.

Composants tiers : les polices **Orbitron** et **VT323** sont sous licence SIL Open Font 1.1 (textes dans `rh_archive_installer/assets/fonts/`). L'AppImage embarque aussi Python (licence PSF) et PySide6/Qt (LGPLv3), qui gardent leurs propres licences. La licence MIT ne couvre que le code et les ressources propres à ce projet.
