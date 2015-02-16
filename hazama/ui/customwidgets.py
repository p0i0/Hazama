from PySide.QtCore import *
from PySide.QtGui import *
from ui import setStdEditMenuIcons
from ui.customobjects import TextFormatter, NTextDocument


class QLineEditWithMenuIcon(QLineEdit):
    """A QLineEdit with system theme icons in context-menu"""
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        setStdEditMenuIcons(menu)
        menu.exec_(event.globalPos())
        menu.deleteLater()


class NDocumentLabel(QFrame):
    """Simple widget to draw QTextDocument. sizeHint will always related
    to fixed number of lines set. If font fallback happen, it may look bad."""

    def __init__(self, parent=None, lines=None, **kwargs):
        super(NDocumentLabel, self).__init__(parent, **kwargs)
        self._lines = self._heightHint = None
        self.doc = NTextDocument(self)
        self.doc.setDocumentMargin(0)
        self.doc.setUndoRedoEnabled(False)
        self.setLines(lines if lines else 4)

    def setFont(self, f):
        self.doc.setDefaultFont(f)
        super(NDocumentLabel, self).setFont(f)
        self.setLines(self._lines)  # refresh size hint

    def setText(self, text, formats):
        self.doc.setText(text, formats)
        # delete exceed lines here using QTextCursor will slow down

    def setLines(self, lines):
        self._lines = lines
        self.doc.setText('\n' * (lines - 1), None)
        self._heightHint = int(self.doc.size().height())
        self.updateGeometry()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.contentsRect()
        painter.translate(rect.topLeft())
        rect.moveTo(0, 0)  # become clip rect
        self.doc.drawContentsPalette(painter, rect, self.palette())

    def resizeEvent(self, event):
        self.doc.setTextWidth(self.contentsRect().width())
        super(NDocumentLabel, self).resizeEvent(event)

    def sizeHint(self):
        __, top, __, bottom = self.getContentsMargins()
        return QSize(-1, self._heightHint + top + bottom)


class NTextEdit(QTextEdit, TextFormatter):
    """The widget used to edit diary contents in Editor window."""
    # spaces auto-indent will recognize
    Spaces = (' ', '\u3000')  # full width space U+3000

    def __init__(self, *args, **kwargs):
        super(NTextEdit, self).__init__(*args, **kwargs)
        self._doc = None
        # setup colors
        prt = self.palette()
        prt.setColor(prt.Highlight, QColor(180, 180, 180))
        prt.setColor(prt.HighlightedText, QColor(0, 0, 0))
        self.setPalette(prt)
        # remove highlight color's alpha to avoid alpha loss in copy&paste.
        # NTextDocument should use this color too.
        hl, bg = self.HlColor, prt.base().color()
        fac = hl.alpha() / 255
        self.HlColor = QColor(round(hl.red()*fac + bg.red()*(1-fac)),
                              round(hl.green()*fac + bg.green()*(1-fac)),
                              round(hl.blue()*fac + bg.blue()*(1-fac)))
        self.autoIndent = False
        self.setTabChangesFocus(True)
        # setup format menu
        onHLAct = lambda: super(NTextEdit, self).setHL(self.hlAct.isChecked())
        onBDAct = lambda: super(NTextEdit, self).setBD(self.bdAct.isChecked())
        onSOAct = lambda: super(NTextEdit, self).setSO(self.soAct.isChecked())
        onULAct = lambda: super(NTextEdit, self).setUL(self.ulAct.isChecked())
        onItaAct = lambda: super(NTextEdit, self).setIta(self.itaAct.isChecked())

        self.subMenu = QMenu(self.tr('Format'), self)
        # shortcuts of format actions only used to display shortcut-hint in menu
        self.hlAct = QAction(QIcon(':/fmt/highlight.png'), self.tr('Highlight'),
                             self, triggered=onHLAct,
                             shortcut=QKeySequence('Ctrl+H'))
        self.bdAct = QAction(QIcon(':/fmt/bold.png'), self.tr('Bold'),
                             self, triggered=onBDAct,
                             shortcut=QKeySequence.Bold)
        self.soAct = QAction(QIcon(':/fmt/strikeout.png'), self.tr('Strike out'),
                             self, triggered=onSOAct,
                             shortcut=QKeySequence('Ctrl+T'))
        self.ulAct = QAction(QIcon(':/fmt/underline.png'), self.tr('Underline'),
                             self, triggered=onULAct,
                             shortcut=QKeySequence.Underline)
        self.itaAct = QAction(QIcon(':/fmt/italic.png'), self.tr('Italic'),
                              self, triggered=onItaAct,
                              shortcut=QKeySequence.Italic)
        self.clrAct = QAction(self.tr('Clear format'), self,
                              shortcut=QKeySequence('Ctrl+D'),
                              triggered=self.clearFormat)
        self.acts = (self.hlAct, self.bdAct, self.soAct, self.ulAct,
                     self.itaAct)  # excluding uncheckable clrAct
        for a in self.acts:
            self.subMenu.addAction(a)
            a.setCheckable(True)
        self.subMenu.addSeparator()
        self.addAction(self.clrAct)
        self.subMenu.addAction(self.clrAct)
        self.key2act = {
            Qt.Key_H: self.hlAct, Qt.Key_B: self.bdAct, Qt.Key_T: self.soAct,
            Qt.Key_U: self.ulAct, Qt.Key_I: self.itaAct}

    def setRichText(self, text, formats):
        doc = NTextDocument(self)  # pass self to let widget hold us
        # inherit settings
        doc.setDefaultFont(self.document().defaultFont())
        doc.setDefaultStyleSheet(self.document().defaultStyleSheet())
        doc.setDefaultCursorMoveStyle(self.document().defaultCursorMoveStyle())
        doc.setDefaultTextOption(self.document().defaultTextOption())

        doc.setHlColor(self.HlColor)
        doc.setText(text, formats)
        self.setDocument(doc)
        self._doc = doc

    def setAutoIndent(self, enabled):
        assert isinstance(enabled, (bool, int))
        self.autoIndent = enabled

    def contextMenuEvent(self, event):
        if self.textCursor().hasSelection():
            self._setFmtActs()
            self.subMenu.setEnabled(True)
        else:
            self.subMenu.setEnabled(False)
        menu = self.createStandardContextMenu()
        setStdEditMenuIcons(menu)
        before = menu.actions()[2]
        menu.insertSeparator(before)
        menu.insertMenu(before, self.subMenu)
        menu.exec_(event.globalPos())
        menu.deleteLater()

    def getRichText(self):
        # getFormats is static method because self.document() will return
        # QTextDocument, not NTextDocument
        return self.toPlainText(), NTextDocument.getFormats(self.document())

    def _setFmtActs(self):
        """Check formats in current selection and check or uncheck actions"""
        fmts = [QTextFormat.BackgroundBrush, QTextFormat.FontWeight,
                QTextFormat.FontStrikeOut,
                QTextFormat.TextUnderlineStyle, QTextFormat.FontItalic]

        cur = self.textCursor()
        start, end = cur.anchor(), cur.position()
        if start > end:
            start, end = end, start
        results = [True] * 5
        for pos in range(end, start, -1):
            cur.setPosition(pos)
            charFmt = cur.charFormat()
            for i, f in enumerate(fmts):
                if results[i] and not charFmt.hasProperty(f):
                    results[i] = False
            if not any(results): break
        for i, c in enumerate(results):
            self.acts[i].setChecked(c)

    def clearFormat(self):
        fmt = QTextCharFormat()
        self.textCursor().setCharFormat(fmt)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ControlModifier and event.key() in self.key2act:
            # set actions before calling format methods
            self._setFmtActs()
            self.key2act[event.key()].trigger()
            event.accept()
        elif event.key() == Qt.Key_Return and self.autoIndent:
            # auto-indent support
            para = self.textCursor().block().text()
            if len(para) > 0 and para[0] in NTextEdit.Spaces:
                space, spaceCount = para[0], 1
                for c in para[1:]:
                    if c != space: break
                    spaceCount += 1
                super(NTextEdit, self).keyPressEvent(event)
                self.textCursor().insertText(space * spaceCount)
            else:
                super(NTextEdit, self).keyPressEvent(event)
            event.accept()
        else:
            super(NTextEdit, self).keyPressEvent(event)

    def insertFromMimeData(self, source):
        """Disable some unsupported types"""
        self.insertHtml(source.html() or source.text())


class NElideLabel(QLabel):
    elideMode = Qt.ElideRight

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.contentsRect()
        t = self.fontMetrics().elidedText(self.text(), self.elideMode, rect.width())
        painter.drawText(rect, self.alignment(), t)

    def minimumSizeHint(self):
        return QSize()  # return invalid size


class DateTimeDialog(QDialog):
    """A dialog that let user change datetime, just like QColorDialog."""
    def __init__(self, dt, displayFmt, parent=None):
        super(DateTimeDialog, self).__init__(parent, Qt.WindowTitleHint)
        self.format = displayFmt
        self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle(self.tr('Edit datetime'))
        self.setMinimumWidth(100)
        self.verticalLayout = QVBoxLayout(self)
        self.dtEdit = QDateTimeEdit(dt, self)
        self.dtEdit.setDisplayFormat(displayFmt)
        self.verticalLayout.addWidget(self.dtEdit)
        self.btnBox = QDialogButtonBox(self)
        self.btnBox.setOrientation(Qt.Horizontal)
        self.btnBox.setStandardButtons(QDialogButtonBox.Ok |
                                       QDialogButtonBox.Cancel)
        self.verticalLayout.addWidget(self.btnBox)
        self.btnBox.accepted.connect(self.accept)
        self.btnBox.rejected.connect(self.reject)

    @staticmethod
    def getDateTime(dt, displayFmt, parent):
        """Show a model datetime dialog, let user change it.
        :param parent: parent widget
        :param dt: datetime to change
        :param displayFmt: the Qt datetime format that used to display
        :return: None if canceled else datetime"""
        dialog = DateTimeDialog(dt, displayFmt, parent)
        ret = dialog.exec_()
        dialog.deleteLater()
        return dialog.dtEdit.dateTime() if ret else None
