import os, time
import threading
import wx
from wx.lib.agw import ultimatelistctrl as ULC
import mygoogle as mg

class MainWin(wx.Frame):
    def __init__(self, parent, title):
        super(MainWin, self).__init__(parent, title=title, size=(700, 400))

        self.statusbar = self.CreateStatusBar(1)
        self.statusbar.SetStatusText('Ready')

        panel = wx.Panel(self)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        top_vbox = wx.BoxSizer(wx.VERTICAL)

        self.local_list = wx.ListCtrl(panel, -1, style=wx.LC_REPORT)
        self.local_list.InsertColumn(0, 'Is img dir', width=20)
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

        self.select_local_dir = wx.DirPickerCtrl(panel)
        self.select_local_dir.Bind(wx.EVT_DIRPICKER_CHANGED, self.on_set_local_dir)
        left_vbox = wx.BoxSizer(wx.VERTICAL)
        left_vbox.Add(self.select_local_dir, 0, wx.EXPAND)
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
        self.work_queue_list = ULC.UltimateListCtrl(panel, agwStyle=agw_style)
        self.work_queue_list.InsertColumnInfo(0, gen_column_header("Local"))
        self.work_queue_list.InsertColumnInfo(1, gen_column_header("Direction"))
        self.work_queue_list.InsertColumnInfo(2, gen_column_header("Remote"))
        self.work_queue_list.InsertColumnInfo(3, gen_column_header("Progress"))
        self.work_queue_list.SetColumnWidth(0, 200)
        self.work_queue_list.SetColumnWidth(1, 70)
        self.work_queue_list.SetColumnWidth(2, 200)
        self.work_queue_list.SetColumnWidth(3, 100)

        self.work_thread = threading.Thread(target=self.worker_func)
        self.work_queue_lock = threading.Lock()

        hbox.Add(left_vbox, 3, wx.EXPAND)
        hbox.Add(middle_vbox, 1, wx.CENTER)
        hbox.Add(right_vbox, 3, wx.EXPAND)
        top_vbox.Add(sizer=hbox, proportion=2, flag=wx.EXPAND)
        top_vbox.Add(window=self.work_queue_list, proportion=1, flag=wx.EXPAND)
        panel.SetSizer(top_vbox)
        panel.Fit()
        self.Centre()
        self.SetIcon(wx.Icon('google-photos.ico'))

        self.Show(True)

    #TODO: handle exceptions like upload failures
    def worker_func(self):
        while self.work_queue_list.GetItemCount() > 0:
            self.work_queue_lock.acquire()
            self.work_queue_lock.release()

            item = self.work_queue_list.GetItem(0, 3)
            progress = item.GetWindow()

            src_item = self.work_queue_list.GetItem(0, 0)
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
            
            self.work_queue_list.DeleteItem(0)

        self.sync_from_remote()

    def is_img(self, path):
        return path.lower().endswith('.jpg') or path.lower().endswith('.cr2')

    def is_img_dir(self, path):
        if not os.path.isdir(path):
            return False

        for i in os.listdir(path):
            if not self.is_img(i):
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
        self.work_queue_list.InsertStringItem(index, src)
        self.work_queue_list.SetStringItem(index, 1, direction)
        self.work_queue_list.SetStringItem(index, 2, dst)
        item = self.work_queue_list.GetItem(index, 3)
        gauge = wx.Gauge(self.work_queue_list, range=100, size=(
            100, -1), style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        item.SetWindow(gauge)
        self.work_queue_list.SetItem(item)
        self.work_queue_lock.release()

        if not self.work_thread.is_alive():
            self.work_thread = threading.Thread(target=self.worker_func)
            self.work_thread.start()

    def on_connect_remote(self, event):
        self.statusbar.SetStatusText('Connecting...')
        self.service = mg.Create_Service(mg.CLIENT_SECRET_FILE, mg.API_NAME, mg.API_VERSION, mg.SCOPES)
        self.statusbar.SetStatusText('Synchronizing...')
        self.sync_from_remote()
        self.statusbar.SetStatusText('')

    def on_to_remote(self, event):
        index = self.local_list.GetFirstSelected()
        selected = []
        while index != -1:
            if self.local_list.GetItemText(index, 0) == 'V':
                selected.append(self.local_list.GetItemText(index, 1))
            index = self.local_list.GetNextSelected(index)

        for folder in selected:
            self.enqueue_work(os.path.join(self.select_local_dir.Path, folder), '>>', folder)

    def on_set_local_dir(self, event):
        self.local_list.DeleteAllItems()
        for i in os.listdir(event.Path):
            if self.is_img_dir(os.path.join(event.Path, i)):
                index = self.local_list.InsertItem(0, 'V')
            else:
                index = self.local_list.InsertItem(0, '')
            self.local_list.SetItem(index, 1, i)
            if os.path.isdir(i):
                self.local_list.SetItem(index, 2, str(len(os.listdir(i))))

ex = wx.App()
MainWin(None, 'Google Photo Explorer')
ex.MainLoop()
