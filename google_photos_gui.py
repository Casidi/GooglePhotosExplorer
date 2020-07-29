import os, time
import threading
import pathlib
import wx
from wx.lib.agw import ultimatelistctrl as ULC
import mygoogle as mg

class MainWin(wx.Frame):
    def __init__(self, parent, title):
        super(MainWin, self).__init__(parent, title=title, size=(700, 400))
        self.Bind(wx.EVT_MAXIMIZE, self.on_maximize)

        self.statusbar = self.CreateStatusBar(1)
        self.statusbar.SetStatusText('Ready')

        self.splitter = wx.SplitterWindow(self, -1)
        panel = wx.Panel(self.splitter)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.local_list = wx.ListCtrl(panel, -1, style=wx.LC_REPORT)
        self.local_list.InsertColumn(0, 'Uploadable', width=20)
        self.local_list.InsertColumn(1, 'Name', wx.LIST_FORMAT_RIGHT, width=150)
        self.local_list.InsertColumn(2, '# photos', wx.LIST_FORMAT_RIGHT)

        self.remote_list = wx.ListCtrl(panel, -1, style=wx.LC_REPORT)
        self.remote_list.InsertColumn(0, 'Album')
        self.remote_list.InsertColumn(1, '# photos', wx.LIST_FORMAT_RIGHT)

        self.to_remote = wx.Button(panel, wx.ID_ANY, '>>')
        self.to_local = wx.Button(panel, wx.ID_ANY, '<<')
        self.to_remote.Bind(wx.EVT_BUTTON, self.on_to_remote)
        
        middle_vbox = wx.BoxSizer(wx.VERTICAL)
        middle_vbox.Add(self.to_remote, 0, wx.EXPAND|wx.TOP)
        middle_vbox.Add(self.to_local, 1, wx.EXPAND)

        self.local_dir_tree = wx.GenericDirCtrl(panel, style=wx.DIRCTRL_DIR_ONLY)
        self.local_dir_tree.Bind(wx.EVT_DIRCTRL_SELECTIONCHANGED, self.on_set_local_dir)
        self.local_dir_tree.SetPath(str(pathlib.Path().home()))
        left_vbox = wx.BoxSizer(wx.VERTICAL)
        left_vbox.Add(self.local_dir_tree, 1, wx.EXPAND)
        left_vbox.Add(self.local_list, 1, wx.EXPAND)

        self.connect_remote_btn = wx.Button(panel, wx.ID_ANY, 'Connect')
        self.connect_remote_btn.Bind(wx.EVT_BUTTON, self.on_connect_remote)
        right_vbox = wx.BoxSizer(wx.VERTICAL)
        right_vbox.Add(self.connect_remote_btn, 0, wx.EXPAND)
        right_vbox.Add(self.remote_list, 1, wx.EXPAND)

        mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_FORMAT

        def gen_column_header(name, kind=0, mask=mask):
            info = ULC.UltimateListItem()
            info.SetMask(mask)
            #info._format = 0
            info.SetKind(kind)
            info.SetText(name)
            return info

        agw_style = (wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.work_queue_list = ULC.UltimateListCtrl(self.splitter, agwStyle=agw_style)
        self.work_queue_list.InsertColumnInfo(0, gen_column_header("Type"))
        self.work_queue_list.InsertColumnInfo(1, gen_column_header("Local"))
        self.work_queue_list.InsertColumnInfo(2, gen_column_header("Direction"))
        self.work_queue_list.InsertColumnInfo(3, gen_column_header("Remote"))
        self.work_queue_list.InsertColumnInfo(4, gen_column_header("Progress"))
        self.work_queue_list.SetColumnWidth(0, 50)
        self.work_queue_list.SetColumnWidth(1, 200)
        self.work_queue_list.SetColumnWidth(2, 70)
        self.work_queue_list.SetColumnWidth(3, 200)
        self.work_queue_list.SetColumnWidth(4, 100)

        self.work_thread = threading.Thread(target=self.worker_func)
        self.work_queue_lock = threading.Lock()

        hbox.Add(left_vbox, 3, wx.EXPAND)
        hbox.Add(middle_vbox, 1, wx.CENTER)
        hbox.Add(right_vbox, 3, wx.EXPAND)

        panel.SetSizerAndFit(hbox)
        self.splitter.SetSashGravity(0)
        self.splitter.SetMinimumPaneSize(100)
        self.splitter.SplitHorizontally(panel, self.work_queue_list)
        
        self.Centre()
        self.SetIcon(wx.Icon('google-photos.ico'))

        self.service = None

        self.Show(True)

    def get_work_queue_item_by_name(self, index, col_name):
        for i in range(self.work_queue_list.GetColumnCount()):
            if self.work_queue_list.GetColumn(i).GetText() == col_name:
                return self.work_queue_list.GetItem(index, i)

        return None

    #TODO: handle exceptions like upload failures
    def worker_func(self):
        while self.work_queue_list.GetItemCount() > 0:
            self.work_queue_lock.acquire()
            self.work_queue_lock.release()

            item = self.get_work_queue_item_by_name(0, 'Type')
            if item.GetText() == 'Album':
                self.process_album_task()
            elif item.GetText() == 'Image':
                self.process_img_task()

            self.work_queue_lock.acquire()
            self.work_queue_list.DeleteItem(0)
            self.work_queue_lock.release()

        self.sync_from_remote()

    def process_album_task(self):
        item = self.get_work_queue_item_by_name(0, 'Progress')
        progress = item.GetWindow()

        src_item = self.get_work_queue_item_by_name(0, 'Local')
        base_dir = src_item.GetText()
        photo_pathes = []
        for i in os.listdir(base_dir):
            if self.is_img(i):
                photo_pathes.append(os.path.join(base_dir, i))

        album_title = os.path.basename(base_dir)
        album_id = mg.create_album(self.service, album_title)
        upload_tokens = []
        for i in range(len(photo_pathes)):
            upload_tokens.append(mg.upload_img(album_title+'_', photo_pathes[i]))
            progress.SetValue(100*(i+1)/len(photo_pathes))
        mg.batch_create_media(self.service, upload_tokens, album_id)
 
    def process_img_task(self):
        item = self.get_work_queue_item_by_name(0, 'Progress')
        progress = item.GetWindow()

        src_item = self.get_work_queue_item_by_name(0, 'Local')
        photo_pathes = [src_item.GetText()]

        album_title = 'Default'
        album_id = mg.create_album(self.service, album_title)
        upload_tokens = []
        for i in range(len(photo_pathes)):
            upload_tokens.append(mg.upload_img('', photo_pathes[i]))
            progress.SetValue(100*(i+1)/len(photo_pathes))
        mg.batch_create_media(self.service, upload_tokens, album_id)

    def is_img(self, path):
        if not os.path.isfile(path):
            return False

        ext = os.path.splitext(path)[1]
        ext = ext.lower()
        return ext in ('.jpg', '.cr2', '.mp4')

    def is_img_dir(self, path):
        if not os.path.isdir(path):
            return False

        for i in os.listdir(path):
            if not self.is_img(os.path.join(path, i)):
                return False

        return True

    def sync_from_remote(self):
        albums = mg.list_albums(self.service)
        self.remote_list.DeleteAllItems()
        for album in albums:
            index = self.remote_list.InsertItem(0, album['title'])
            self.remote_list.SetItem(index, 1, '')

    def enqueue_work(self, src, direction, dst):
        self.work_queue_lock.acquire()

        index = self.work_queue_list.GetItemCount()

        if self.is_img_dir(src):
            self.work_queue_list.InsertStringItem(index, 'Album')
        elif self.is_img(src):
            self.work_queue_list.InsertStringItem(index, 'Image')
        else:
            self.work_queue_lock.release()
            return

        self.work_queue_list.SetStringItem(index, 1, src)
        self.work_queue_list.SetStringItem(index, 2, direction)
        self.work_queue_list.SetStringItem(index, 3, dst)
        item = self.work_queue_list.GetItem(index, 4)
        gauge = wx.Gauge(self.work_queue_list, range=100, size=(
            100, -1), style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        item.SetWindow(gauge)
        self.work_queue_list.SetItem(item)
        self.work_queue_lock.release()

        if not self.work_thread.is_alive():
            self.work_thread = threading.Thread(target=self.worker_func)
            self.work_thread.start()

    def on_maximize(self, event):
        self.splitter.SetSashPosition(self.Size.y - 200)

    def on_connect_remote(self, event):
        self.statusbar.SetStatusText('Connecting...')
        self.service = mg.Create_Service(mg.CLIENT_SECRET_FILE, mg.API_NAME, mg.API_VERSION, mg.SCOPES)
        self.statusbar.SetStatusText('Synchronizing...')
        self.sync_from_remote()
        self.statusbar.SetStatusText('')

    def on_to_remote(self, event):
        if self.service == None:
            wx.MessageBox('Not connected', 'Info', wx.OK | wx.ICON_INFORMATION)
            return
        if self.local_list.GetFirstSelected() == -1:
            wx.MessageBox('Please select at least one folder', 'Info', wx.OK | wx.ICON_INFORMATION)
            return

        index = self.local_list.GetFirstSelected()
        selected = []
        while index != -1:
            if self.local_list.GetItemText(index, 0) == 'V':
                selected.append(self.local_list.GetItemText(index, 1))
            index = self.local_list.GetNextSelected(index)

        if len(selected) == 0:
            wx.MessageBox('No uploadable item selected', 'Info', wx.OK | wx.ICON_INFORMATION)
            return

        for folder in selected:
            self.enqueue_work(os.path.join(self.local_dir_tree.GetPath(), folder), '>>', folder)

    def on_set_local_dir(self, event):
        path = self.local_dir_tree.GetPath()
        self.local_list.DeleteAllItems()
        for i in os.listdir(path):
            sub_item_path = os.path.join(path, i)
            if self.is_img_dir(sub_item_path) or self.is_img(sub_item_path):
                index = self.local_list.InsertItem(0, 'V')
            else:
                index = self.local_list.InsertItem(0, '')
            self.local_list.SetItem(index, 1, i)
            if os.path.isdir(sub_item_path):
                self.local_list.SetItem(index, 2, str(len(os.listdir(sub_item_path))))

ex = wx.App()
MainWin(None, 'Google Photo Explorer')
ex.MainLoop()
