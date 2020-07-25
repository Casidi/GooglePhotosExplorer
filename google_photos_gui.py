import os, time
import wx
from wx.lib.agw import ultimatelistctrl as ULC
import mygoogle as mg
import threading

class MainWin(wx.Frame):
    def __init__(self, parent, title):
        super(MainWin, self).__init__(parent, title=title, size=(700, 300))
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

        # self.service = mg.Create_Service(mg.CLIENT_SECRET_FILE, mg.API_NAME, mg.API_VERSION, mg.SCOPES)
        # self.sync_from_remote()

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

        self.log = wx.TextCtrl(panel, wx.ID_ANY, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        wx.Log.SetActiveTarget(wx.LogTextCtrl(self.log))

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

        self.work_queue_lock = threading.Lock()
        self.enqueue_work('hello src', '>>', 'hello dst')

        self.work_thread = threading.Thread(target=self.worker_func)
        self.work_thread.start()

        hbox.Add(left_vbox, 3, wx.EXPAND)
        hbox.Add(middle_vbox, 1, wx.CENTER)
        hbox.Add(self.remote_list, 3, wx.EXPAND)
        top_vbox.Add(sizer=hbox, proportion=2, flag=wx.EXPAND)
        top_vbox.Add(window=self.work_queue_list, proportion=1, flag=wx.EXPAND)
        top_vbox.Add(window=self.log, proportion=1, flag=wx.EXPAND)
        panel.SetSizer(top_vbox)
        panel.Fit()
        self.Centre()
        self.SetIcon(wx.Icon('google-photos.ico'))

        self.Show(True)

    def worker_func(self):
        while True:
            if self.work_queue_list.GetItemCount() > 0:
                self.work_queue_lock.acquire()
                self.work_queue_lock.release()
                item = self.work_queue_list.GetItem(0, 3)
                progress = item.GetWindow()
                for i in range(0, 101, 20):
                    progress.SetValue(i)
                    time.sleep(1)
                
                self.work_queue_list.DeleteItem(0)

    def is_img_dir(self, path):
        if not os.path.isdir(path):
            return False

        for i in os.listdir(path):
            if i.lower().endswith('.jpg') or i.lower().endswith('.cr2'):
                return True

        return False

    def sync_from_remote(self):
        # wx.LogMessage('Sync..')
        albums = mg.list_albums(self.service)
        self.remote_list.DeleteAllItems()
        for album in albums:
            index = self.remote_list.InsertItem(0, album['title'])
            self.remote_list.SetItem(index, 1, '')

    def enqueue_work(self, src, direction, dst):
        #get lock here
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

    def on_to_remote(self, event):
        index = self.local_list.GetFirstSelected()
        selected = []
        while index != -1:
            selected.append(self.local_list.GetItemText(index, 1))
            index = self.local_list.GetNextSelected(index)
        wx.LogMessage(str(selected))

        for folder in selected:
            wx.LogMessage(f'Enqueuing {folder}')
            self.enqueue_work(os.path.join(self.select_local_dir.Path, folder), '>>', folder)
            # mg.upload_folder_as_album(self.service, folder)
        # wx.LogMessage('Sync..')
        # self.sync_from_remote()
        # wx.LogMessage('Done')

    def on_set_local_dir(self, event):
        for i in os.listdir(event.Path):
            if self.is_img_dir(os.path.join(event.Path, i)):
                index = self.local_list.InsertItem(0, 'V')
            else:
                index = self.local_list.InsertItem(0, '')
            self.local_list.SetItem(index, 1, i)
            if os.path.isdir(i):
                self.local_list.SetItem(index, 2, str(len(os.listdir(i))))

ex = wx.App()
MainWin(None, 'Google Photo GUI')
ex.MainLoop()
