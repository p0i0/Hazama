﻿import sqlite3
import sys, os
import richtagparser
import logging


# template used to format txt file
default_tpl = '''***{0[title]}***
[Created: {0[created]}, Modified: {0[modified]}]

{0[text]}\n\n\n\n'''


class Nikki:
    '''This class hold a SQLite3 database,handling save/read/import/export.

    Each Table's function:
    Nikki: All diary saved here.(every one has all data except format/tag info).
    Nikki_Tags: Connecting tags to diary.
    Tags: All tags' body saved here.
    TextFormat: Connecting format info to diary.Format info itself also saved here.
    

    '''
    def __str__(self):
        return '%s nikki in database' % self.count()

    def __init__(self, dbpath):
        self.conn = sqlite3.connect(dbpath)

        self.conn.execute('CREATE TABLE IF NOT EXISTS Tags'
                          '(id INTEGER PRIMARY KEY, name TEXT NOT NULL ' 'UNIQUE)')
        self.conn.execute('CREATE TABLE IF NOT EXISTS Nikki'
                          '(id INTEGER PRIMARY KEY, created TEXT NOT NULL '
                          'UNIQUE, modified TEXT NOT NULL, plaintext INTEGER,'
                          'text TEXT NOT NULL, title TEXT)')
        self.conn.execute('CREATE TABLE IF NOT EXISTS Nikki_Tags'
                          '(nikkiid INTEGER NOT NULL, tagid INTEGER NOT NULL,'
                          'PRIMARY KEY(nikkiid, tagid))')
        self.conn.execute('CREATE TABLE IF NOT EXISTS TextFormat'
                          '(nikkiid INTEGER, start INTEGER, '
                          'length INTEGER, type INTEGER)')
        self.conn.execute('CREATE TRIGGER IF NOT EXISTS autodeltag AFTER '
                          'DELETE ON Nikki_Tags BEGIN   DELETE FROM Tags '
                          'WHERE (SELECT COUNT(*) FROM Nikki_Tags WHERE '
                          'Nikki_Tags.tagid=Tags.id)==0;  END')

    def __getitem__(self, id):
        L = self.conn.execute('SELECT * FROM Nikki '
                              'WHERE id = ?', (id,)).fetchone()
        if not L:
            raise IndexError('id is not in database')
        tags = self.conn.execute('SELECT tagid FROM Nikki_Tags WHERE '
                                 'nikkiid = ?', (id,))
        taglst = [self.gettag(i[0]) for i in tags]
        tagstr = ' '.join(taglst) + ' ' if len(taglst)>=1 else ''

        return {'id': L[0], 'created': L[1], 'modified': L[2],
                'plaintext': L[3], 'text': L[4], 'title': L[5], 'tags': tagstr}

    def importXml(self, xmlpath):
        "Import CintaNotes/Hazama XML file,will not appear in main program."
        def trans_date(datetime):
            d, t = datetime.split('T')
            return (d[:4] + '/' + d[4:6] + '/' + d[6:] + ' '   # date
                     + t[:2] + ':' + t[2:4])                    # time

        import xml.etree.ElementTree as ET
        
        tree = ET.parse(xmlpath)
        root = tree.getroot()
        Hxml = True if 'nikkichou' in str(root) else False
        
        if Hxml:
            startindex = 2
        else:  # CintaNotes XML
            startindex = 1 if root.find('tags') else 0

        # save tags into Tags Table.its index is always 0 in root
        if root.find('tags'):
            for t in root[0]:
                tag = (t.attrib['name'],)
                try:
                    self.conn.execute('INSERT INTO Tags VALUES(NULL,?)', tag)
                except Exception:
                    logging.warning('Failed adding tag: %s' % tag)
            self.commit()

        id = self.getnewid()  # the first column in Nikki Table
        index = startindex
        for i in range(startindex, len(root)):
            nikki = root[i].attrib
            text = root[i].text if root[i].text else ' '
            plain = int(nikki.get('plainText', 0))
            # import formats if nikki has rich text
            if not plain:
                if not Hxml:
                    parser = richtagparser.RichTagParser(strict=False)
                    parser.myfeed(id, text, self.conn)
                    text = parser.getstriped()
                else:
                    for f in root[1]:
                        if int(f.attrib['index']) == index:
                            values = (id, f.attrib['start'],
                                      f.attrib['length'], f.attrib['type'])
                            self.conn.execute('INSERT INTO TextFormat VALUES '
                                              '(?,?,?,?)', values)
            # import nikki itself into Nikki Table
            if Hxml:
                created, modified = nikki['created'], nikki['modified']
            else:
                created, modified = (trans_date(nikki['created']),
                                     trans_date(nikki['modified']))
                if created==modified:
                    modified = ''
            values = (created, modified, plain, text, nikki['title'])
            self.conn.execute('INSERT INTO Nikki VALUES(NULL,?,?,?,?,?)',
                              values)
            # import tags if nikki has
            if nikki['tags']:
                for tag in nikki['tags'].split():
                    values = (id, self.conn.execute('SELECT id FROM '
                              'Tags WHERE name=?', (tag,)).fetchone()[0])
                    self.conn.execute('INSERT INTO Nikki_Tags VALUES(?,?)',
                                      values)
                                      
            id += 1
            index += 1

        self.commit()

    def exportXml(self, xmlpath):
        "Export XML file,will not appear in main program."
        import xml.etree.ElementTree as ET

        root = ET.Element('nikkichou')
        tags = ET.SubElement(root, 'tags')
        reachedTags = set()
        formats = ET.SubElement(root, 'formats')

        for e in enumerate(self.sorted('created'), 2):
            index, n = e  # index just connect a rich nikki to its formats
            nikki = ET.SubElement(root, 'nikki')
            for attr in ['title', 'created', 'modified', 'tags']:
                nikki.set(attr, n[attr])
            nikki.set('plainText', str(n['plaintext']))
            nikki.text = n['text']
            # save reatched tags to set
            if n['tags']:
                for t in n['tags'].split(): reachedTags.add((t))
            # save format if current nikki has
            if not n['plaintext']:
                for r in self.getformat(n['id']):
                    format = ET.SubElement(formats, 'format')
                    for i in enumerate(['start','length','type']):
                        format.set('index', str(index))
                        format.set(i[1], str(r[i[0]]))

        for t in reachedTags:
            tag = ET.SubElement(tags, 'tag')
            tag.set('name', t)

        tree = ET.ElementTree(root)
        tree.write(xmlpath, encoding='utf-8')

    def exporttxt(self, txtpath, hazamapath=None, selected=None):
        '''Export to TXT file using template(string format).
        When selected is a list contains nikki data,only export diary in list.'''
        file = open(txtpath, 'w', encoding='utf-8')
        try:
            with open(hazamapath+'template.txt', encoding='utf-8') as f:
                tpl = f.read()
        except OSError:
            tpl = default_tpl
        for n in (self.sorted('created', False) if selected is None
                   else selected):
            file.write(tpl.format(n))
        file.close()

    def sorted(self, orderby, reverse=True, *, tagid=None, search=None):
        if tagid and (search is None):  # only fetch nikki whose tagid matchs
            where = ('WHERE id IN (SELECT nikkiid FROM Nikki_Tags WHERE '
                     'tagid=%i) ') % tagid
        elif search and (tagid is None):
            where = ('WHERE created LIKE "%%%s%%" OR text LIKE "%%%s%%" '
                     'OR title LIKE "%%%s%%"') % ((search,)*3)
        elif search and tagid:
            where = ('WHERE (id IN (SELECT nikkiid FROM Nikki_Tags WHERE '
                     'tagid=%i)) AND (created LIKE "%%%s%%" OR '
                     'text LIKE "%%%s%%" OR title LIKE "%%%s%%")' %
                     ((tagid,) + (search,)*3))
        else:
            where = ''

        if orderby == 'length':
            orderby = 'LENGTH(text)'
        cmd = ('SELECT * FROM Nikki ' + where + 'ORDER BY ' +
               orderby + (' DESC' if reverse else ''))
        for L in self.conn.execute(cmd):
            tags = self.conn.execute('SELECT tagid FROM Nikki_Tags WHERE '
                                     'nikkiid = ?', (L[0],))

            taglst = [self.gettag(i[0]) for i in tags]
            tagstr = ' '.join(taglst) + ' ' if len(taglst)>=1 else ''
            yield {'id': L[0], 'created': L[1], 'modified': L[2],
                   'plaintext': L[3], 'text': L[4], 'title': L[5],
                   'tags': tagstr}

    def delete(self, id):
        self.conn.execute('DELETE FROM Nikki WHERE id = ?', (id,))
        try:
            self.conn.execute('DELETE FROM Nikki_Tags WHERE '
                              'nikkiid=?', (id,))
        except Exception:
            logging.warning('Faild deleting Nikki (ID: %s)' % id)
        else:
            logging.info('Nikki deleted (ID: %s)' % id)
            self.commit()

    def commit(self):
        self.conn.commit()

    def count(self):
        return self.conn.execute('SELECT COUNT(id) FROM Nikki').fetchone()[0]

    def gettag(self, tagid=None, *, getcount=False):
        if tagid:   # get tags by id
            return self.conn.execute('SELECT name FROM Tags WHERE '
                                      'id = ?', (tagid,)).fetchone()[0]
        else:   # get all tags
            if getcount:    # get with counts.used in TList
                result = self.conn.execute('SELECT Tags.id,Tags.name,(SELECT '
                'COUNT(*) FROM Nikki_Tags WHERE Nikki_Tags.tagid=Tags.id) '
                'FROM Tags ORDER BY Tags.name')

                return result
            else:         # get without counts.used in tag completer
                result = self.conn.execute('SELECT name FROM Tags')
                return [n[0] for n in result]

    def getformat(self, id):
        return self.conn.execute('SELECT start,length,type FROM TextFormat '
                                  'WHERE nikkiid=?', (id,))

    def save(self, id, created, modified, html, title, tags):
        new = not bool(id)  # new is True if current nikki is new one
        if new:
            id = self.getnewid()

        parser = richtagparser.NTextParser(strict=False)
        parser.myfeed(id, html, self.conn)  # format process done here
        text = parser.getstriped()
        plain = parser.plain

        values = ((None, created, modified, plain, text, title) if new else
                  (created, modified, plain, text, title, id))
        cmd = ('INSERT INTO Nikki VALUES(?,?,?,?,?,?)' if new else
               'UPDATE Nikki SET created=?, modified=?, plaintext=?, '
               'text=?, title=? WHERE id=?')
        try:
            self.conn.execute(cmd, values)
        except Exception:
            logging.warning('Failed saving Nikki (ID: %s)' % id)
            return
        else:
            logging.info('Nikki saved (ID: %s)' % id)

        # tags processing
        if tags is not None:  # tags modified
            if not new:  # if diary isn't new,delete its tags first
                self.conn.execute('DELETE FROM Nikki_Tags WHERE nikkiid=?',
                                  (id,))
            for t in tags:
                try:
                    self.conn.execute('INSERT INTO Tags VALUES(NULL,?)', (t,))
                    self.commit()
                except Exception:
                    pass
                values = (id, self.conn.execute('SELECT id FROM Tags WHERE '
                                                'name=?', (t,)).fetchone()[0])
                self.conn.execute('INSERT INTO Nikki_Tags VALUES(?,?)',
                                  values)
        
        self.commit()
        return id

    def getnewid(self):
        maxid = self.conn.execute('SELECT max(id) FROM Nikki').fetchone()[0]
        return (maxid+1 if maxid else 1)


if __name__ == '__main__':
    path = os.path.split(__file__)[0] + os.sep
    n = Nikki(path+'nikkichou.db')
    #n.importXml(path+'out.xml')
