"""Main List and TagList, and their delegates.
"""
import logging
import random
from collections import OrderedDict
from PySide.QtGui import *
from PySide.QtCore import *
from hazama.ui import font, datetimeTrans, scaleRatio, makeQIcon
from hazama.ui.editor import Editor
from hazama.ui.customobjects import NTextDocument, MultiSortFilterProxyModel
from hazama.ui.customwidgets import NElideLabel, NDocumentLabel
from hazama.ui.listmodel import NikkiModel
from hazama.config import settings, nikki


class NListDelegate(QStyledItemDelegate):
    """ItemDelegate of old theme 'one-pixel-rect' for NList, Using 'traditional'
    painting method compared to colorful theme."""
    def __init__(self):
        super().__init__()  # don't pass parent because of mem problem
        # To avoid some font has much more space at top and bottom, we use ascent instead
        # of height, and add it with a small number.
        magic = int(4 * scaleRatio)
        self.title_h = max(font.title_m.ascent(), font.datetime_m.ascent()) + magic
        self.titleArea_h = self.title_h + 4
        self.text_h = font.text_m.lineSpacing() * settings['Main'].getint('previewLines')
        self.tagPath_h = font.default_m.ascent() + magic
        self.tag_h = self.tagPath_h + 4
        self.dt_w = font.datetime_m.width(datetimeTrans('2000-01-01 00:00')) + 40
        self.all_h = None  # updated in sizeHint before each item being painting
        # doc is used to draw text(diary's body)
        self.doc = NTextDocument()
        self.doc.setDefaultFont(font.text)
        self.doc.setUndoRedoEnabled(False)
        self.doc.setDocumentMargin(0)
        self.doc.documentLayout().setPaintDevice(QWidget())  # refer actual list will cause segfault
        # setup colors
        self.c_text = Qt.black
        self.c_bg = QColor(255, 236, 176)
        self.c_border = QColor(214, 172, 41)
        self.c_inActBg = QColor(255, 236, 176, 40)
        self.c_gray = QColor(93, 73, 57)

    def paint(self, painter, option, index):
        x, y, w = option.rect.x(), option.rect.y(), option.rect.width()-1
        row = index.row()
        dt, text, title, tags, formats = (index.sibling(row, i).data()
                                          for i in range(1, 6))
        selected = bool(option.state & QStyle.State_Selected)
        active = bool(option.state & QStyle.State_Active)
        # draw border and background
        painter.setPen(self.c_border)
        painter.setBrush(self.c_bg if selected and active else
                         self.c_inActBg)
        painter.drawRect(x+1, y, w-2, self.all_h)  # outer border
        if selected:  # draw inner border
            pen = QPen()
            pen.setStyle(Qt.DashLine)
            pen.setColor(self.c_gray)
            painter.setPen(pen)
            painter.drawRect(x+2, y+1, w-4, self.all_h-2)
        # draw datetime and title
        painter.setPen(self.c_gray)
        painter.drawLine(x+10, y+self.titleArea_h, x+w-10, y+self.titleArea_h)
        painter.setPen(self.c_text)
        painter.setFont(font.datetime)
        painter.drawText(x+14, y+self.titleArea_h-self.title_h, self.dt_w, self.title_h,
                         Qt.AlignVCenter, datetimeTrans(dt))
        if title:
            painter.setFont(font.title)
            title_w = w - self.dt_w - 13
            title = font.title_m.elidedText(title, Qt.ElideRight, title_w)
            painter.drawText(x+self.dt_w, y+self.titleArea_h-self.title_h, title_w, self.title_h,
                             Qt.AlignVCenter | Qt.AlignRight, title)
        # draw text
        self.doc.setText(text, formats)
        self.doc.setTextWidth(w-26)
        painter.translate(x+14, y+self.titleArea_h+2)
        self.doc.drawContentsColor(painter, QRect(0, 0, w-26, self.text_h), self.c_text)
        painter.resetTransform()
        # draw tags
        if tags:
            painter.setPen(self.c_gray)
            painter.setFont(font.default)
            painter.translate(x + 15, y+self.titleArea_h+6+self.text_h)
            real_x, max_x = x+15, w-10
            for t in tags.split():
                oneTag_w = font.default_m.width(t) + 4
                real_x += oneTag_w + 15
                if real_x > max_x: break
                tagPath = QPainterPath()
                tagPath.moveTo(8, 0)
                tagPath.lineTo(8+oneTag_w, 0)
                tagPath.lineTo(8+oneTag_w, self.tagPath_h)
                tagPath.lineTo(8, self.tagPath_h)
                tagPath.lineTo(0, self.tagPath_h/2)
                tagPath.closeSubpath()
                painter.drawPath(tagPath)
                painter.drawText(8, 0, oneTag_w, self.tagPath_h, Qt.AlignCenter, t)
                painter.translate(oneTag_w+15, 0)  # translate by offset
            else:
                painter.resetTransform()
                return
            # too many tags
            painter.setPen(Qt.DotLine)
            painter.drawLine(-4, self.tagPath_h/2, 2, self.tagPath_h/2)
            painter.resetTransform()

    def sizeHint(self, option, index):
        tag_h = self.tag_h if index.sibling(index.row(), 4).data() else 0
        self.all_h = self.titleArea_h + 2 + self.text_h + tag_h + 6
        return QSize(-1, self.all_h+3)  # 3 is spacing between entries


class NListDelegateColorful(QItemDelegate):
    """ItemDelegate of theme 'colorful' for NList. Using widget rendering."""
    class ItemWidget(QFrame):
        """Widget that used to draw an item in ItemDelegate.paint method.
        This widget's height is 'fixed'(two possible height) because delegate's
        sizeHint method is called very often. So font fallback will cause problem.
        """
        def __init__(self, parent=None):
            super().__init__(parent, objectName='NListItem')
            self.heightWithTag = self.heightNoTag = None

            self.title = NElideLabel(self, objectName='NListItemTitle')
            self.title.setFont(font.title)
            self.title.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            self.title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.datetime = QLabel(self, objectName='NListItemDt')
            self.datetime.setFont(font.datetime)
            self.datetime.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

            self.text = NDocumentLabel(self, objectName='NListItemText')
            self.text.setLines(settings['Main'].getint('previewLines'))
            self.text.setFont(font.text)

            self.tag = NElideLabel(self, objectName='NListItemTag')

            # use QToolButton to display icons
            self.datetimeIco = QToolButton(self, objectName='NListItemDtIco')
            minSz = max(font.datetime_m.ascent(), 12*scaleRatio)
            self.datetimeIco.setIconSize(QSize(minSz, minSz))
            self.datetimeIco.setIcon(QIcon(':/calendar.png'))

            self.tagIco = QToolButton(self, objectName='NListItemTagIco')
            minSz = max(font.default_m.ascent(), 12*scaleRatio)
            self.tagIco.setIconSize(QSize(minSz, minSz))
            self.tagIco.setIcon(QIcon(':/tag.png'))

            self._vLayout0 = QVBoxLayout(self)
            self._hLayout0 = QHBoxLayout()
            self._hLayout1 = QHBoxLayout()
            for i in [self._vLayout0, self._hLayout0, self._hLayout1]:
                i.setContentsMargins(0, 0, 0, 0)
                i.setSpacing(0)

            for i in [self.datetimeIco, self.datetime, self.title]:
                self._hLayout0.addWidget(i)
            self._hLayout0.insertSpacing(2, 10)
            for i in [self.tagIco, self.tag]:
                self._hLayout1.addWidget(i)
            self._vLayout0.addLayout(self._hLayout0)
            self._vLayout0.addWidget(self.text)
            self._vLayout0.addLayout(self._hLayout1)

        def refreshStyle(self):
            """Must be called after dynamic property changed"""
            self.style().unpolish(self)
            self.style().polish(self)
            # no need to call self.update here

        def setTexts(self, dt, text, title, tags, formats):
            # Some layout behaviours are full of mystery, even changing order of
            # calls will break the UI
            self.datetime.setText(datetimeTrans(dt))
            # without this width of dt will not be updated (for performance reason?)
            self._hLayout0.activate()
            # width of title area depends on itemW's width
            self.title.setText(
                font.title_m.elidedText(title, Qt.ElideRight, self.title.width()))
            self.text.setText(text, formats)
            if tags:
                tags = ' \u2022 '.join(tags.split())  # use bullet to separate
                self.tag.setText(tags)
            self.tag.setVisible(bool(tags))
            self.tagIco.setVisible(bool(tags))

        def refreshHeightInfo(self):
            self.heightWithTag = self.sizeHint().height()
            self.heightNoTag = self.heightWithTag - self._hLayout1.sizeHint().height()

    def __init__(self):
        super().__init__()
        self._itemW = self.ItemWidget()
        self._itemW.refreshHeightInfo()

    def paint(self, painter, option, index):
        row = index.row()

        self._itemW.resize(option.rect.size())
        self._itemW.setTexts(*(index.sibling(row, i).data() for i in range(1, 6)))
        self._itemW.setProperty('selected', bool(option.state & QStyle.State_Selected))
        self._itemW.setProperty('active', bool(option.state & QStyle.State_Active))
        self._itemW.refreshStyle()

        # don't use offset argument of QWidget.render
        painter.translate(option.rect.topLeft())
        self._itemW.render(painter, QPoint(), renderFlags=QWidget.DrawChildren)
        painter.resetTransform()

    def sizeHint(self, option, index):
        hasTag = bool(index.sibling(index.row(), 4).data())
        return QSize(-1, self._itemW.heightWithTag if hasTag else self._itemW.heightNoTag)


class TListDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.h = font.default_m.height() + 8

    def paint(self, painter, option, index):
        x, y, w = option.rect.x(), option.rect.y(), option.rect.width()
        tag, count = index.data(Qt.DisplayRole), index.data(Qt.UserRole)
        if count is not None:
            count = str(count)
        painter.setFont(font.default)
        selected = bool(option.state & QStyle.State_Selected)
        textArea = QRect(x+4, y, w-8, self.h)
        if index.row() == 0:  # row 0 is always All(clear tag filter)
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(textArea,
                             Qt.AlignVCenter | Qt.AlignLeft,
                             tag)
        else:
            painter.setPen(QColor(209, 109, 63))
            painter.drawLine(x, y, w, y)
            if selected:
                painter.setPen(QColor(181, 61, 0))
                painter.setBrush(QColor(250, 250, 250))
                painter.drawRect(x, y+1, w-1, self.h-2)
            # draw tag
            painter.setPen(QColor(20, 20, 20) if selected else
                           QColor(80, 80, 80))
            tag = font.default_m.elidedText(
                tag, Qt.ElideRight,
                w-12 if count is None else w-font.datetime_m.width(count)-12)
            painter.drawText(textArea, Qt.AlignVCenter | Qt.AlignLeft, tag)
            # draw tag count
            if count is not None:
                painter.setFont(font.datetime)
                painter.drawText(textArea, Qt.AlignVCenter | Qt.AlignRight, count)

    def createEditor(self, parent, option, index):
        # delegate will hold the reference to editor
        editor = QLineEdit(parent, objectName='tagListEdit')
        editor.oldText = index.data()
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        rect.translate(1, 1)
        rect.setWidth(rect.width() - 2)
        rect.setHeight(rect.height() - 1)
        editor.setGeometry(rect)

    def sizeHint(self, option, index):
        return QSize(-1, self.h)


class TListDelegateColorful(QItemDelegate):
    """ItemDelegate of theme 'colorful' for TList. Using widget rendering."""
    class ItemWidget(QFrame):
        # almost the same as NListDelegateColorful.ItemWidget
        def __init__(self, parent=None):
            super().__init__(parent, objectName='TListItem')
            self._hLayout = QHBoxLayout(self)
            self._hLayout.setContentsMargins(0, 0, 0, 0)

            self.name = NElideLabel(self, objectName='TListItemName')
            self.name.setAlignment(Qt.AlignRight)
            self.name.elideMode = Qt.ElideLeft
            self.count = QLabel(self, objectName='TListItemCount')
            self.count.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            self._hLayout.addWidget(self.count)
            self._hLayout.addWidget(self.name)

        def refreshStyle(self):
            self.style().unpolish(self)
            self.style().polish(self)

        def setFixedWidth(self, w):
            if w != self.width():
                super().setFixedWidth(w)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._itemW = self.ItemWidget()
        self._itemW.setFixedHeight(self._itemW.sizeHint().height())
        self._countEnabled = settings['Main'].getboolean('tagListCount')
        if not self._countEnabled: self._itemW.count.hide()

    def paint(self, painter, option, index):
        selected = bool(option.state & QStyle.State_Selected)
        active = bool(option.state & QStyle.State_Active)

        self._itemW.name.setText(index.data(Qt.DisplayRole))
        if self._countEnabled:
            countData = index.data(Qt.UserRole)
            self._itemW.count.setText(str(countData) if countData else '')
        self._itemW.setProperty('selected', selected)
        self._itemW.setProperty('active', active)
        self._itemW.refreshStyle()
        self._itemW.setFixedWidth(option.rect.width())

        painter.translate(option.rect.topLeft())
        self._itemW.render(
            painter, QPoint(),
            renderFlags=QWidget.DrawChildren)
        painter.resetTransform()

    def sizeHint(self, option, index):
        return QSize(-1, self._itemW.height())

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent, objectName='tagListEdit')
        editor.setAlignment(self._itemW.name.alignment())
        editor.oldText = index.data()
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class TagList(QListWidget):
    currentTagChanged = Signal(str)  # str is tag-name or ''
    tagNameModified = Signal(str)  # arg: newTagName

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trackList = None  # update in mousePressEvent
        self.setVerticalScrollMode(self.ScrollPerPixel)
        self.setDelegateOfTheme()

        self.setUniformItemSizes(True)
        self.currentItemChanged.connect(self.emitCurrentTagChanged)
        nextFunc = lambda: self.setCurrentRow(
            0 if self.currentRow() == self.count() - 1 else self.currentRow() + 1)
        preFunc = lambda: self.setCurrentRow((self.currentRow() or self.count()) - 1)
        self.nextSc = QShortcut(QKeySequence('Ctrl+Tab'), self, activated=nextFunc)
        self.preSc = QShortcut(QKeySequence('Ctrl+Shift+Tab'), self, activated=preFunc)

    def setDelegateOfTheme(self):
        theme = settings['Main']['theme']
        d = {'colorful': TListDelegateColorful}.get(theme, TListDelegate)
        self.setItemDelegate(d())  # do not pass parent under PySide...
        # force items to be laid again
        self.setSpacing(self.spacing())

    def contextMenuEvent(self, event):
        # ignore "All" item. cursor must over the item
        index = self.indexAt(event.pos())
        if index.row() > 0:
            menu = QMenu()
            menu.addAction(QAction(self.tr('Rename'), menu,
                                   triggered=lambda: self.edit(index)))
            menu.exec_(event.globalPos())
            menu.deleteLater()

    def commitData(self, editor):
        newName = editor.text()
        if editor.isModified() and newName and ' ' not in newName:
            # editor.oldText is set in delegate
            nikki.changetagname(editor.oldText, newName)
            logging.info('tag [%s] changed to [%s]', editor.oldText, newName)
            super().commitData(editor)
            self.tagNameModified.emit(newName)

    def load(self):
        logging.debug('load Tag List')
        QListWidgetItem(self.tr('All'), self)
        self.setCurrentRow(0)
        itemFlag = Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if settings['Main'].getboolean('tagListCount'):
            for name, count in nikki.gettags(getcount=True):
                item = QListWidgetItem(name, self)
                item.setFlags(itemFlag)
                item.setData(Qt.ToolTipRole, name)
                item.setData(Qt.UserRole, count)
        else:
            for name in nikki.gettags(getcount=False):
                item = QListWidgetItem(name, self)
                item.setData(Qt.ToolTipRole, name)
                item.setFlags(itemFlag)

    def reload(self):
        if self.isVisible():
            try:
                currentTag = self.currentItem().data(Qt.DisplayRole)
            except AttributeError:  # no selection
                currentTag = None
            self.clear()
            self.load()
            if currentTag:
                try:
                    item = self.findItems(currentTag, Qt.MatchFixedString)[0]
                except IndexError:
                    item = self.item(0)
                self.setCurrentItem(item)

    def emitCurrentTagChanged(self, currentItem):
        try:
            text = currentItem.data(Qt.DisplayRole)
        except AttributeError:  # no selection
            return
        self.currentTagChanged.emit('' if currentItem is self.item(0) else text)

    # all three events below for drag scroll
    def mousePressEvent(self, event):
        self.trackList = []

    def mouseMoveEvent(self, event):
        if self.trackList is not None:
            self.trackList.append(event.pos().y())
            if len(self.trackList) > 4:
                change = self.trackList[-1] - self.trackList[-2]
                scrollbar = self.verticalScrollBar()
                scrollbar.setValue(scrollbar.value() - change)

    def mouseReleaseEvent(self, event):
        if self.trackList is not None and len(self.trackList) <= 4:  # haven't moved
            pEvent = QMouseEvent(QEvent.MouseButtonPress, event.pos(),
                                 event.globalPos(), Qt.LeftButton,
                                 Qt.LeftButton, Qt.NoModifier)
            QListWidget.mousePressEvent(self, pEvent)
        self.trackList = None


class NikkiList(QListView):
    """Main List that display preview of diaries"""
    startLoading = Signal()
    countChanged = Signal()
    tagsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._delegate = None
        # ScrollPerPixel means user can draw scroll bar and move list items pixel by pixel,
        # but mouse wheel still scroll item by item (the number of items scrolled depends on
        # qApp.wheelScrollLines)
        self.setVerticalScrollMode(self.ScrollPerPixel)
        self.setDelegateOfTheme()
        # disable default editor. Editor is implemented in the View
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # setup models
        self.originModel = NikkiModel(self)
        self.modelProxy = MultiSortFilterProxyModel(self)
        self.modelProxy.setSourceModel(self.originModel)
        self.modelProxy.setDynamicSortFilter(True)
        self.modelProxy.addFilter(cols=[4], cs=Qt.CaseSensitive)
        self.modelProxy.addFilter(cols=[1, 2, 3], cs=Qt.CaseInsensitive)
        self.setModel(self.modelProxy)
        self.sort()
        # setup actions
        self.editAct = QAction(self.tr('Edit'), self,
                               triggered=self.startEditor)
        self.delAct = QAction(makeQIcon(':/menu/list-delete.png'),
                              self.tr('Delete'), self,
                              shortcut=QKeySequence.Delete, triggered=self.delNikki)
        self.randAct = QAction(makeQIcon(':/menu/random-big.png'),
                               self.tr('Random'), self,
                               shortcut=QKeySequence(Qt.Key_F7), triggered=self.selectRandomly)
        for i in [self.editAct, self.delAct, self.randAct]: self.addAction(i)
        # setup editors
        self.editors = OrderedDict()  # diaryId => Editor, id of new diary is -1
        self.doubleClicked.connect(self.startEditor)
        self.activated.connect(self.startEditor)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction(self.editAct)
        menu.addAction(self.delAct)
        menu.addSeparator()
        menu.addAction(self.randAct)
        selectionCount = len(self.selectedIndexes())
        self.editAct.setDisabled(selectionCount != 1)
        self.delAct.setDisabled(selectionCount == 0)
        self.randAct.setDisabled(self.modelProxy.rowCount() == 0)
        menu.exec_(event.globalPos())

    def selectRandomly(self):
        randRow = random.randrange(0, self.modelProxy.rowCount())
        self.setCurrentIndex(self.modelProxy.index(randRow, 0))

    def startEditor(self):
        dic = self._getNikkiDict(self.currentIndex())
        id_ = dic['id']
        if id_ in self.editors:
            self.editors[id_].activateWindow()
        else:
            e = Editor(dic)
            self._setEditorStaggerPos(e)
            self.editors[id_] = e
            e.closed.connect(self.closeEditor)
            pre, next = lambda: self._editorMove(-1), lambda: self._editorMove(1)
            e.preSc.activated.connect(pre)
            e.quickPreSc.activated.connect(pre)
            e.nextSc.activated.connect(next)
            e.quickNextSc.activated.connect(next)
            e.show()
            return id_

    def startEditorNew(self):
        if -1 in self.editors:
            self.editors[-1].activateWindow()
        else:
            e = Editor({'id': -1})
            self._setEditorStaggerPos(e)
            self.editors[-1] = e
            e.closed.connect(self.closeEditor)
            e.show()

    def closeEditor(self, id_, needSave):
        """Write editor's data to model and database, and destroy editor"""
        editor = self.editors[id_]
        if needSave:
            qApp.setOverrideCursor(QCursor(Qt.WaitCursor))
            dic = editor.toNikkiDict()
            if not editor.tagModified:  # let database skip heavy tag update operation
                dic['tags'] = None
            else:  # remove duplicate tags
                dic['tags'] = ' '.join(set(dic['tags'].split()))
            row = self.originModel.updateNikki(dic)

            self.clearSelection()
            self.setCurrentIndex(self.modelProxy.mapFromSource(
                self.originModel.index(row, 0)))

            if id_ == -1: self.countChanged.emit()  # new diary
            if editor.tagModified: self.tagsChanged.emit()
            qApp.restoreOverrideCursor()
        editor.deleteLater()
        del self.editors[id_]

    def _setEditorStaggerPos(self, editor):
        if self.editors:
            lastOpenEditor = list(self.editors.values())[-1]
            pos = lastOpenEditor.pos() + QPoint(16, 16) * scaleRatio
            # can't check available screen space because of bug in pyside
            editor.move(pos)

    def load(self):
        self.startLoading.emit()
        self.originModel.loadFromDb()
        self.countChanged.emit()

    def setDelegateOfTheme(self):
        theme = settings['Main']['theme']
        self._delegate = {'colorful': NListDelegateColorful}.get(theme, NListDelegate)()
        self.setItemDelegate(self._delegate)
        # force items to be laid again
        self.setSpacing(self.spacing())

    def reload(self):
        self.originModel.clear()
        self.load()

    def delNikki(self):
        if len(self.selectedIndexes()) == 0:
            return
        msg = QMessageBox(self)
        okBtn = msg.addButton(qApp.translate('Dialog', 'Delete'), QMessageBox.AcceptRole)
        msg.setIcon(QMessageBox.Question)
        msg.addButton(qApp.translate('Dialog', 'Cancel'), QMessageBox.RejectRole)
        msg.setWindowTitle(self.tr('Delete diaries'))
        msg.setText(self.tr('Selected diaries will be deleted permanently!'))
        msg.exec_()
        msg.deleteLater()

        if msg.clickedButton() == okBtn:
            indexes = [self.modelProxy.mapToSource(i)
                       for i in self.selectedIndexes()]
            for i in indexes: nikki.delete(i.data())
            for i in sorted([i.row() for i in indexes], reverse=True):
                self.originModel.removeRow(i)
            self.countChanged.emit()
            self.tagsChanged.emit()  # tags might changed

    def handleExport(self, path, export_all):
        if export_all:
            selected = None
        else:
            selected = [self._getNikkiDict(i) for i in self.selectedIndexes()]
        nikki.exporttxt(path, selected)

    def _getNikkiDict(self, idx):
        """Get a nikki dict with its index in proxy model."""
        return self.originModel.getNikkiDictByRow(self.modelProxy.mapToSource(idx).row())

    def sort(self):
        sortBy = settings['Main']['listSortBy']
        sortByCol = {'datetime': 1, 'title': 3, 'length': 6}.get(sortBy, 1)
        reverse = settings['Main'].getboolean('listReverse')
        self.modelProxy.sort(sortByCol,
                             Qt.DescendingOrder if reverse else Qt.AscendingOrder)

    def _editorMove(self, step):
        if len(self.editors) > 1: return
        _id = list(self.editors.keys())[0]
        editor = self.editors[_id]
        if editor.needSave(): return
        idx = self.modelProxy.match(
            self.modelProxy.index(0, 0), 0, _id, flags=Qt.MatchExactly)
        if len(idx) != 1: return
        row = idx[0].row()  # the row of the caller (Editor) 's diary in proxy model

        if ((step == -1 and row == 0) or
           (step == 1 and row == self.modelProxy.rowCount() - 1)):
            return
        newIdx = self.modelProxy.index(row+step, 0)
        self.clearSelection()
        self.setCurrentIndex(newIdx)
        dic = self._getNikkiDict(newIdx)
        editor.fromNikkiDict(dic)
        self.editors[dic['id']] = self.editors.pop(_id)

    def setFilterBySearchString(self, s):
        self.modelProxy.setFilterPattern(1, s)
        self.countChanged.emit()

    def setFilterByTag(self, s):
        self.modelProxy.setFilterPattern(0, s)
        self.countChanged.emit()

    @Slot(str)
    def refreshFilteredTags(self, newTagName):
        """Refresh items with old tag in current modelProxy after a tag's name
        changed, and replace old tag name in filter"""
        model, modelP = self.originModel, self.modelProxy
        needRefresh = [modelP.mapToSource(modelP.index(i, 0))
                       for i in range(modelP.rowCount())]
        for i in needRefresh:
            diary = nikki[i.data()]
            model.setData(i.sibling(i.row(), 4), diary['tags'])
        self.setFilterByTag(newTagName)
