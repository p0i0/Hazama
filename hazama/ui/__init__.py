from PySide.QtGui import QApplication, QIcon, QFont, QFontMetrics, QMessageBox
from PySide.QtCore import QLocale, QTranslator, QLibraryInfo, QDateTime, QFile, QIODevice
from config import settings
from ui import rc
import sys
import os
import time
import logging


locale = None
timeFmt = dateFmt = datetimeFmt = None


def datetimeTrans(s, forceDateOnly=False):
    """Convert datetime in database format to locale one"""
    dt = QDateTime.fromString(s, 'yyyy-MM-dd HH:mm')
    return locale.toString(dt, dateFmt if forceDateOnly else datetimeFmt)


def currentDatetime():
    """Return current datetime in database format"""
    return time.strftime('%Y-%m-%d %H:%M')


def readRcTextFile(path):
    """Read whole text file from qt resources system"""
    f = QFile(path)
    if not f.open(QFile.ReadOnly | QFile.Text):
        raise Exception('read rc text failed')
    text = str(f.readAll())
    f.close()
    return text


def setTranslationLocale():
    lang = settings['Main'].get('lang', 'en')
    logging.info('set translation(%s)', lang)
    global _trans, _transQt  # avoid being collected
    _trans = QTranslator()
    _trans.load(lang, 'lang/')
    _transQt = QTranslator()
    ret = _transQt.load('qt_' + lang,
                        QLibraryInfo.location(QLibraryInfo.TranslationsPath))
    if not ret:  # frozen
        _transQt.load('qt_'+lang, 'lang/')
    for i in [_trans, _transQt]: app.installTranslator(i)
    sysLocale = QLocale.system()
    # special case: application language is different from system's
    global locale, timeFmt, dateFmt, datetimeFmt
    locale = sysLocale if lang == sysLocale.name() else QLocale(lang)
    QLocale.setDefault(locale)
    timeFmt = settings['Main'].get('timeFormat')
    dateFmt = settings['Main'].get('dateFormat', locale.dateFormat())
    datetimeFmt = (dateFmt + ' ' + timeFmt) if timeFmt else dateFmt


def showDbError(hint=''):
    """Show information about database error.
    :param hint: error message to show
    """
    QMessageBox.critical(
        None,
        app.translate('Errors', 'Failed to access database'),
        app.translate('Errors', 'SQLite3: %s.\n\nPlease check database path(have permission?). '
                      'If it\'s corrupt, you may have to recover this file by hand or restore '
                      'from backups.') % hint)


def setStdEditMenuIcons(menu):
    """Add system theme icons to QLineEdit and QTextEdit context-menu
    :param menu: QMenu generated by createStandardContextMenu
    """
    (undo, redo, __, cut, copy, paste, delete, __, sel, *__) = menu.actions()
    undo.setIcon(QIcon.fromTheme('edit-undo'))
    redo.setIcon(QIcon.fromTheme('edit-redo'))
    cut.setIcon(QIcon.fromTheme('edit-cut'))
    copy.setIcon(QIcon.fromTheme('edit-copy'))
    paste.setIcon(QIcon.fromTheme('edit-paste'))
    delete.setIcon(QIcon.fromTheme('edit-delete'))
    sel.setIcon(QIcon.fromTheme('edit-select-all'))


def setStyleSheet():
    """If -stylesheet not in sys.argv, append custom.qss(if exists) to default one and
    load it. Otherwise load the one in sys.argv"""
    if '-stylesheet' in sys.argv:
        logging.info('override default StyleSheet by command line arg')
    else:
        ss = [readRcTextFile(':/default.qss')]
        # append theme part
        theme = settings['Main'].get('theme')
        if theme == 'colorful':
            ss.append(readRcTextFile(':/theme.colorful.qss'))
        # load custom
        if os.path.isfile('custom.qss'):
            logging.info('set custom StyleSheet')
            with open('custom.qss', encoding='utf-8') as f:
                ss.append(f.read())

        app.setStyleSheet(''.join(ss))


class Fonts:
    """Manage all fonts used in application"""
    def __init__(self):
        self.title = QFont()
        self.date = QFont()
        self.text = QFont()
        self.default = app.font()
        self.default_m = QFontMetrics(self.default)
        self.title_m = self.date_m = self.date_m = None

    def load(self):
        self.title.fromString(settings['Font'].get('title'))
        self.title_m = QFontMetrics(self.title)
        self.date.fromString(settings['Font'].get('datetime'))
        self.date_m = QFontMetrics(self.date)
        self.text.fromString(settings['Font'].get('text'))
        if settings['Font'].get('default'):
            self.default.fromString(settings['Font'].get('default'))
            self.default_m = QFontMetrics(self.default)
            app.setFont(self.default)


# setup application icon
app = QApplication(sys.argv)
appIcon = QIcon(':/appicon16.png')
appIcon.addFile(':/appicon32.png')
appIcon.addFile(':/appicon48.png')
appIcon.addFile(':/appicon64.png')
app.setWindowIcon(appIcon)
# setup fonts after qApp created
font = Fonts()
font.load()

setTranslationLocale()
setStyleSheet()
