﻿from PySide.QtGui import *
from PySide.QtCore import *
import sys, os
from db import Nikki
import configparser
import time
import logging

# from config tile
titlefont = QFont('SimSun')
titlefont.setBold(True)
titlefont.setPixelSize(12)
datefont = QFont('Segoe UI')
datefont.setPixelSize(12)
dfontm = QFontMetrics(datefont)
textfont = QFont('SimSun')  # WenQuanYi Micro Hei
textfont.setPixelSize(13)
txfontm = QFontMetrics(textfont)
defaultfont = QFont()
defaultfont.setPixelSize(12)
previewlines = 4

if os.sep not in sys.argv[0]:
    path = ''
else:
    path = os.path.split(sys.argv[0])[0] + os.sep


class CintaEntryDelegate(QStyledItemDelegate):
    "CintaNotes like delegate for Entry"
    def __init__(self):
        "calculate first"
        super(CintaEntryDelegate, self).__init__()

        self.tr_h = titlefont.pixelSize() + 11
        
        leading = txfontm.leading() if txfontm.leading()>=0 else 0
        self.text_h = (txfontm.height()+leading) * previewlines
        self.dico_w, self.dico_h = 8, 7
        self.dico_y = self.tr_h // 2 - 3
        # for displaying text
        self.qtd = NText()
        self.qtd.setDefaultFont(textfont)
        self.qtd.setUndoRedoEnabled(False)
        self.qtd.setDocumentMargin(0)

    def paint(self, painter, option, index):
        x, y, w= option.rect.x()+1, option.rect.y(), option.rect.width()-3
        row = index.data()

        selected = bool(option.state & QStyle.State_Selected)
        areafocused = bool(option.state & QStyle.State_Active)
        is_current = bool(option.state&QStyle.State_HasFocus) and areafocused
        
        mainrect = QRect(x, y, w, self.height)
        painter.setPen(QColor(180, 180, 180))
        painter.setBrush(QColor(255, 255, 255))
        painter.drawRect(mainrect)

        # titlerect and title
        painter.setFont(titlefont)
        titlerect = QRect(x+1, y+1, w-1, self.tr_h)
        painter.setPen(Qt.NoPen)
        if selected:
            painter.setBrush(QColor(251, 225, 184) if areafocused \
                             else QColor(251, 230, 195))
        else:
            painter.setBrush(QColor(254, 250, 244))
        painter.drawRect(titlerect)
        painter.setPen(QColor(150, 118, 64) if selected
                       else QColor(121, 107, 85))
        painter.drawText(x+8, y+1, w-100, self.tr_h,
                         Qt.AlignLeft|Qt.AlignVCenter, row['title'])

        # border change
        if selected:
            imainrect = QRect(x+1, y+1, w-2, self.height-2)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QColor(183, 161, 135) if is_current
                           else QColor(180, 180, 180))
            painter.drawRect(mainrect)
            painter.setPen(QColor(172, 158, 134))
            painter.drawRect(imainrect)

            if is_current:
                pen = QPen()
                pen.setDashPattern([1,1,1,1,1,1])
                pen.setColor(QColor(23, 7, 121))
                painter.setPen(pen)
                painter.drawRect(mainrect)
                
                pen.setDashPattern([1,1,1,1])
                pen.setColor(QColor(93, 73, 57))
                painter.setPen(pen)
                painter.drawRect(imainrect)

        # date with icon
        painter.setFont(datefont)
        date_w = dfontm.width(row['created'])
        date_x = w-date_w-9
        painter.drawText(date_x, y+1, date_w, self.tr_h,
                         Qt.AlignVCenter, row['created'])
        painter.setBrush(Qt.NoBrush)
        dico = QRect(date_x-self.dico_w-4,
                     y+self.dico_y, self.dico_w, self.dico_h)
        painter.setPen(QColor(208,186,149) if selected
                       else QColor(198,198,198))
        painter.drawRoundedRect(dico, 1, 1)
        dicop_x = date_x-self.dico_h/2 - 4
        dicocenter_y = y + self.dico_y + 4
        painter.setPen(QColor(191,173,143))
        painter.drawLine(dicop_x, y+self.dico_y+2, dicop_x, dicocenter_y)
        painter.drawLine(dicop_x, dicocenter_y, dicop_x+2, dicocenter_y)

        # text
        painter.setPen(QColor(0,0,0))
        painter.save()
        self.qtd.setText(row['text'], row['plaintext'], row['id'])
        self.qtd.setTextWidth(w-22)
        painter.translate(x+12, y+self.tr_h+self.tag_h+2)
        self.qtd.drawContents(painter, QRectF(0, 0, w-21, self.text_h))
        painter.restore()

        # tags
        if self.tag_h:
            painter.setPen(QColor(161, 151, 136))
            painter.setFont(defaultfont)
            painter.drawText(x+16, y+self.tr_h+3, 
                             200, 30, Qt.AlignLeft, row['tags'])

    def sizeHint(self, option, index):
        self.tag_h = 20 if index.data()['tags'] else 0
        self.height = self.tag_h + self.text_h + self.tr_h + 10
        
        return QSize(-1, self.height+1)


class Entry(QListWidgetItem):
    def __init__(self, row, parent=None):
        super(Entry, self).__init__(parent)
        self.setData(2, row)


class Nlist(QListWidget):
    def __init__(self):
        super(Nlist, self).__init__()
        self.editors = []

        self.setSelectionMode(self.ExtendedSelection)
        self.itemDoubleClicked.connect(self.starteditor)
        
        self.setItemDelegate(CintaEntryDelegate())
        self.setStyleSheet('QListWidget{background-color:rgb(174,176,189); \
                           border: solid 0px}')
        
        # Context Menu
        self.editAct = QAction('Edit', self,
                                shortcut=QKeySequence('Return'),
                                triggered=self.starteditor)
        self.addAction(self.editAct)  # make shortcut working anytime
        self.delAct = QAction('Delete', self, shortcut=QKeySequence('Delete'),
                              triggered=self.delNikki)
        self.addAction(self.delAct)
        self.newAct = QAction('New Nikki', self, shortcut=QKeySequence.New,
                              triggered=self.newNikki)
        self.addAction(self.newAct)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction(self.editAct)
        menu.addAction(self.delAct)
        menu.addSeparator()
        menu.addAction(self.newAct)
        
        selcount = len(self.selectedItems())
        self.editAct.setDisabled(True if (selcount>1 or selcount==0)
                                 else False)
        menu.popup(event.globalPos())

    def starteditor(self, item=None, new=False):
        if not new:
            # called by doubleclick event or contextmenu
            self.curtitem = item if item else self.selectedItems()[0] 
            row = self.curtitem.data(2)
            editor = Editwindow(row)
        else:
            editor = Editwindow(None, True)

        self.editors.append(editor)
        center = self.mapToGlobal(self.geometry().center())
        w, h = (int(i) for i in settings.value('Editor/size', (500, 400)))
        editor.setGeometry(center.x()-w/2, center.y()-h/2, w, h)

        editor.show()

    def delNikki(self):
        msgbox = QMessageBox(QMessageBox.NoIcon,
                             'Confirm',
                             'Delete it?',
                             QMessageBox.Yes|QMessageBox.Cancel,
                             parent=self)
        msgbox.setDefaultButton(QMessageBox.Cancel)
        ret = msgbox.exec_()

        if ret == QMessageBox.Yes:
            for i in self.selectedItems():
                nikki.delete(i.data(2)['id'])
                self.takeItem(self.row(i))
            nikki.commit()

    def newNikki(self):
        self.starteditor(None, True)

    def load(self):
        order = settings.value('Nlist/sortorder', 'created')
        for e in nikki.sorted(order):
            Entry(e, nlist)
        
        self.setCurrentRow(0)

    def refresh(self, id):
        "Reload after nikki in Nlist changed"
        logging.info('Nikki List reloading')
        self.clear()
        order='created'
        for e in nikki.sorted(order):
            if e['id'] == id:
                rownum = self.count()
            Entry(e, nlist)
            
        self.setCurrentRow(rownum)

    def destroyEditor(self, editor):
        self.editors.remove(editor)


class Editwindow(QWidget):
    createdModified = False
    def __init__(self, row=None, new=False):
        super(Editwindow, self).__init__()

        self.setMinimumSize(350,200)
        self.setWindowTitle("Editor")

        self.titleeditor = QLineEdit(self)
        self.titleeditor.setFont(titlefont)
        self.tageditor = QLineEdit(self)
        self.tageditor.setFont(defaultfont)
        # Load data
        if not new:  # existing nikki
            self.id = row['id']
            self.created = row['created']
            self.modified = row['modified']
            self.titleeditor.setText(row['title'])
            self.tageditor.setText(row['tags'])
            self.editor = Editor(row['text'],
                                 row['plaintext'],
                                 row['id'],
                                 parent=self)
        else:
            self.modified = self.created = self.id = None
            self.editor = Editor(parent=self)
        # set up tageditor 
        completer = TagCompleter(nikki.gettag(), self)
        self.tageditor.setCompleter(completer)
        
        self.title_h = self.titleeditor.sizeHint().height()
        self.tageditor_h = self.tageditor.sizeHint().height()
        self.box = QDialogButtonBox(QDialogButtonBox.Save | \
                                    QDialogButtonBox.Cancel,
                                    parent=self)
        self.box.accepted.connect(self.close)
        self.box.rejected.connect(self.hide)
        self.box_w, self.box_h = self.box.sizeHint().toTuple()
        # title and created,modified,tags
        # self.d_created = NDate(self.created, self)
        # self.d_created.move(50, 330)
        # self.d_created.dateTimeChanged.connect(self.setCreatedModified)
        
            
    def closeEvent(self, event):
        event.accept()
        if (self.editor.document().isModified() or \
        self.titleeditor.isModified() or self.createdModified or \
        self.tageditor.isModified()):
            realid = self.saveNikki()
            nlist.refresh(realid)
        settings.setValue('Editor/size', self.size().toTuple())
        nlist.destroyEditor(self)

    def saveNikki(self):
        if not self.created:  # new nikki
            self.created = time.strftime('%Y/%m/%d %H:%M')
            modified = self.created
        else:
            modified = time.strftime('%Y/%m/%d %H:%M')
        tags = self.tageditor.text().split()
        # realid: id returned by database
        realid = nikki.save(self.id, self.created, modified,
                            self.editor.toHtml(), self.titleeditor.text(),
                            tags)
        return realid
    # def setCreatedModified(self):
        # self.created = self.d_created.toString()
        # self.createdModified = True

    def paintEvent(self, event):
        w, h = self.size().toTuple()
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(247, 241, 231))  # 199,199,233
        daterect = QRect(0, h-self.box_h-20, w, self.box_h+20)
        painter.drawRect(daterect)
        
        painter.setBrush(QColor(249,245,238))  # 77,199,145
        painter.drawRect(0, h-self.box_h-70, w, 50)
        
        painter.setPen(QColor(115,115,115))
        painter.setFont(datefont)
        date = '   Created:%s\n   Modified:%s' % (self.created, self.modified)
        painter.drawText(daterect,Qt.AlignVCenter, date)

    def resizeEvent(self, event):
        w, h = event.size().toTuple()
        # from buttom to top
        box_x, box_y = w-self.box_w-10, h-self.box_h-10
        self.box.move(box_x, box_y)
        self.tageditor.setGeometry(20, box_y-35, w-40, self.tageditor_h)
        self.editor.setGeometry(0, self.title_h, w, box_y-60)
        self.titleeditor.resize(w, self.title_h)

    def showEvent(self, event):
        self.editor.setFocus()
        self.editor.moveCursor(QTextCursor.End)


class TagCompleter(QCompleter):
    def __init__(self, tagL, parent=None):
        self.tagL = tagL
        super(TagCompleter, self).__init__(tagL, parent)
        self.setCaseSensitivity(Qt.CaseInsensitive)
    def pathFromIndex(self, index):
        # path is current matched tag.
        path = QCompleter.pathFromIndex(self, index)
        # a list like [tag1, tag2, tag3(maybe a part)]
        L = self.widget().text().split()
        if len(L) > 1:
            path = '%s %s ' % (' '.join(L[:-1]), path)
        else:
            path += ' '
        return path

    def splitPath(self, path):
        # path is tag string like "tag1 tag2 tag3(maybe a part) "
        path = path.split()[-1]
        if path in self.tagL:
            return ' '
        else:
            return [path,]


class Editor(QTextEdit):
    def __init__(self, *values, parent=None):
        super(Editor, self).__init__(parent)
        self.setAcceptRichText(False)
        
        doc = NText()
        doc.setDefaultFont(textfont)
        if values:  # Edit existing nikki
            text, plain, nikkiid = values
            doc.setText(text, plain, nikkiid)
        self.setDocument(doc)
            
        prt = self.palette()
        prt.setColor(prt.Highlight, QColor(180, 180, 180))
        prt.setColor(prt.HighlightedText, QColor(0, 0, 0))
        self.setPalette(prt)

        self.creatacts()
        self.setModified(False)

    def creatacts(self):
        self.submenu = QMenu('Format')
        self.hlAct = QAction('Highlight', self, shortcut=QKeySequence('Ctrl+H'))
        self.soAct = QAction('Strike out', self, shortcut=QKeySequence('Ctrl+-'))
        self.bdAct = QAction('Bold', self, shortcut=QKeySequence('Ctrl+B'))
        self.ulAct = QAction('Underline', self, shortcut=QKeySequence('Ctrl+U'))
        self.itaAct = QAction('Italic', self, shortcut=QKeySequence('Ctrl+I'))

        self.hlAct.triggered.connect(self.setHL)
        self.soAct.triggered.connect(self.setSO)
        self.bdAct.triggered.connect(self.setBD)
        self.ulAct.triggered.connect(self.setUL)
        self.itaAct.triggered.connect(self.setIta)

        for a in (self.hlAct, self.bdAct, self.soAct, self.bdAct,
                  self.ulAct, self.itaAct):
            self.addAction(a)
            self.submenu.addAction(a)
            a.setCheckable(True)

        self.submenu.addSeparator()
        self.clrAct = QAction('Clear format', self,
                              shortcut=QKeySequence('Ctrl+D'))
        self.addAction(self.clrAct)
        self.submenu.addAction(self.clrAct)
        self.clrAct.triggered.connect(self.clearformat)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu(event.globalPos())
        before = menu.actions()[2]
        
        curtfmt = self.currentCharFormat()
        self.hlAct.setChecked(True if curtfmt.background().color() == \
                              QColor(255, 250, 160) else False)
        self.bdAct.setChecked(True if curtfmt.fontWeight() == QFont.Bold \
                              else False)
        self.soAct.setChecked(curtfmt.fontStrikeOut())    
        self.ulAct.setChecked(curtfmt.fontUnderline())   
        self.itaAct.setChecked(curtfmt.fontItalic())
        print(1)
        menu.insertSeparator(before)        
        menu.insertMenu(before, self.submenu)
        menu.exec_(event.globalPos())

    def setHL(self, pre=None):
        if pre:
            hasFormat = False
        else:
            curtfmt = self.currentCharFormat()
            hasFormat = curtfmt.background().color() == \
                        QColor(255, 250, 160)
        fmt = QTextCharFormat()
        fmt.setBackground(QBrush(QColor('white') if hasFormat
                                 else QColor(255, 250, 160)))
        self.textCursor().mergeCharFormat(fmt)

    def setBD(self, pre=None):
        if pre:
            hasFormat = False
        else:
            curtfmt = self.currentCharFormat()
            hasFormat = (curtfmt.fontWeight() == QFont.Bold)
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Normal if hasFormat else QFont.Bold)
        self.textCursor().mergeCharFormat(fmt)

    def setSO(self, pre=None):
        if pre:
            hasFormat = False
        else:
            curtfmt = self.currentCharFormat()
            hasFormat = curtfmt.fontStrikeOut()
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not hasFormat)
        self.textCursor().mergeCharFormat(fmt)

    def setUL(self, pre=None):
        if pre:
            hasFormat = False
        else:
            curtfmt = self.currentCharFormat()
            hasFormat = curtfmt.fontUnderline()
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not hasFormat)
        self.textCursor().mergeCharFormat(fmt)

    def setIta(self, pre=None):
        if pre:
            hasFormat = False
        else:
            curtfmt = self.currentCharFormat()
            hasFormat = curtfmt.fontItalic()
        fmt = QTextCharFormat()
        fmt.setFontItalic(not hasFormat)
        self.textCursor().mergeCharFormat(fmt)

    def clearformat(self):
        fmt = QTextCharFormat()
        self.textCursor().setCharFormat(fmt)


class NText(QTextDocument):
    typedic = {1: 'setBD', 2: 'setHL', 3: 'setIta', 4: 'setSO', 5: 'setUL'}
    def setText(self, text, plain, nikkiid=None):
        self.setPlainText(text)
        if not plain:
            self.cur = QTextCursor(self)
            for r in nikki.getformat(nikkiid):
                self.cur.setPosition(r[0])
                self.cur.setPosition(r[0]+r[1], mode=self.cur.KeepAnchor)
                richfunc = getattr(Editor, self.typedic[r[2]])
                richfunc(self, True)

    def textCursor(self):
        "Make Editor.setXX use NText.cur as textCursor"
        return self.cur


class NDate(QDateTimeEdit):
    fmt = "yyyy/MM/dd HH:mm"
    def __init__(self, string, parent=None):
        dt = QDateTime.fromString(string, self.fmt)
        super(NDate, self).__init__(dt, parent)
        self.setDisplayFormat(self.fmt)
        
    def toString(self):
        return self.dateTime().toString(self.fmt)


class Main(QWidget):
    def __init__(self):
        super(Main, self).__init__()
        self.setMinimumSize(300,200)
        self.restoreGeometry(settings.value("Main/windowGeo"))
        self.setWindowTitle('Hazama Prototype')
        

        global nlist
        nlist = Nlist()
        nlist.load()
        self.menubar = QMenuBar()
        self.menubar.setFont(defaultfont)
        self.menubar.setStyleSheet('QMenuBar::item{padding: 1px 0px}')
        
        self.createActMenu()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(self.menubar)
        layout.addWidget(nlist)
        self.setLayout(layout)

    def createActMenu(self):
        self.newAct = QAction("&New", self,
                shortcut=QKeySequence.New,
                statusTip="Create a new file",
                triggered=nlist.newNikki)

        self.menubar.addMenu("   File   ")
        editMenu = self.menubar.addMenu("   Edit   ")
        editMenu.addAction(self.newAct)

    def closeEvent(self, event):
        settings.setValue("Main/windowGeo", self.saveGeometry())
        event.accept()



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    timee = time.clock()
    settings = QSettings(path+'config.ini', QSettings.IniFormat)
    
    app = QApplication(sys.argv)
    
    nikki = Nikki(path + 'test.db')
    print(nikki)
    m = Main()


    m.show()
    print(round(time.clock()-timee,3))
    sys.exit(app.exec_())
