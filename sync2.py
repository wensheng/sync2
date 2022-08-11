# Wensheng Wang @2017

# run pep8 with:
#   "flake8 --max-line-length=100 sync2.py"

import sys
import os
import shutil
import filecmp
import hashlib
import threading

import wx

STOP_ON_ERROR = False  # we don't stop on error
# Button definitions

# Define notification event for thread completion
EVT_RESULT_ID = wx.NewIdRef(count=1)


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def EVT_RESULT(win, func):
    """Define Result Event."""
    win.Connect(-1, -1, EVT_RESULT_ID, func)


class ResultEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, data):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_RESULT_ID)
        self.data = data


def get_fhash(filename):
    key = hashlib.sha1()
    with open(filename, mode='rb') as f:
        key.update(f.read(1048576))
    return key.hexdigest()


class WorkerThread(threading.Thread):
    """Worker Thread Class."""
    def __init__(self, notify_window):
        """Init Worker Thread Class."""
        threading.Thread.__init__(self)
        self._notify_window = notify_window
        self._want_abort = 0
        # This starts the thread running on creation, but you could
        # also make the GUI thread responsible for calling this
        self.new2dirs = []
        self.new1dirs = []
        self.same_name_diff_stats = []
        self.logFile = open("log.txt", 'w')
        self.start()

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread. Simulation of
        # a long process (well, 10s here) as a simple loop - you will
        # need to structure your processing so that you periodically
        # peek at the abort variable
        number_of_files = 0
        first_len = len(self._notify_window.firstFolder)
        second_len = len(self._notify_window.secondFolder)
        if self._notify_window.curDirection in (0, 2):
            # A -> B
            for root, dirs, files in os.walk(self._notify_window.firstFolder):
                for d in dirs:
                    src_dir = os.path.join(root, d)
                    dir_name = src_dir[first_len + 1:]
                    target_dir = os.path.join(self._notify_window.secondFolder, dir_name)
                    if not os.path.isdir(target_dir):
                        try:
                            os.makedirs(target_dir, exist_ok=True)
                            self.new2dirs.append((src_dir, target_dir))
                        except (PermissionError, FileNotFoundError):
                            self.logFile.write("Error creating %s in %s\n" % (
                                               dir_name, self._notify_window.secondFolder))
                            if STOP_ON_ERROR:
                                wx.PostEvent(self._notify_window, ResultEvent({'s': 0}))
                                return

                for f in files:
                    file_dir = root[first_len + 1:]
                    src_file = os.path.join(root, f)
                    dest_file = os.path.join(self._notify_window.secondFolder, file_dir, f)
                    if os.path.isfile(dest_file):
                        if not filecmp.cmp(src_file, dest_file):
                            # files are different
                            self.same_name_diff_stats.append(os.path.join(file_dir, f))
                            try:
                                fsize = os.path.getsize(src_file)
                            except OSError:
                                continue
                            if fsize > 100000000:
                                # for size > 100MB, report it's being copied
                                wx.PostEvent(self._notify_window, ResultEvent({'s': 2,
                                                                               'n': number_of_files,
                                                                               'f': src_file}))
                            try:
                                # save filename in folder 1 as filename.1 in folder 2
                                shutil.copy2(src_file, "%s.1" % dest_file)
                                self.logFile.write("conflict: %s and %s\n" % (src_file, dest_file))
                                number_of_files += 1
                            except (PermissionError, FileNotFoundError):
                                self.logFile.write("Error copy %s to %s\n" % (src_file, dest_file))
                                if STOP_ON_ERROR:
                                    wx.PostEvent(self._notify_window, ResultEvent({'s': 0}))
                                    return
                    else:
                        try:
                            fsize = os.path.getsize(src_file)
                        except OSError:
                            continue
                        if fsize > 100000000:
                            # for size > 100MB, report it's being copied
                            wx.PostEvent(self._notify_window, ResultEvent({'s': 2,
                                                                           'n': number_of_files,
                                                                           'f': src_file}))
                        try:
                            shutil.copy2(src_file, dest_file)
                            number_of_files += 1
                        except (PermissionError, FileNotFoundError):
                            self.logFile.write("Error copy %s to %s\n" % (src_file, dest_file))
                            if STOP_ON_ERROR:
                                wx.PostEvent(self._notify_window, ResultEvent({'s': 0}))
                                return

                    if number_of_files % 10 == 0:
                        if self._want_abort:
                            wx.PostEvent(self._notify_window, ResultEvent({'s': 1}))
                            return
                        wx.PostEvent(self._notify_window,
                                     ResultEvent({'s': 2,
                                                  'n': number_of_files,
                                                  'f': os.path.join(root, f)}))

            # newly create dir has same metadata(ie. last modified) as original
            for pair in self.new2dirs:
                shutil.copystat(pair[0], pair[1])

        if self._notify_window.curDirection in (1, 2):
            # B -> A
            for root, dirs, files in os.walk(self._notify_window.secondFolder):
                for d in dirs:
                    src_dir = os.path.join(root, d)
                    dir_name = src_dir[second_len + 1:]
                    target_dir = os.path.join(self._notify_window.firstFolder, dir_name)
                    if not os.path.isdir(target_dir):
                        try:
                            os.makedirs(target_dir, exist_ok=True)
                            self.new1dirs.append((src_dir, target_dir))
                        except (PermissionError, FileNotFoundError):
                            self.logFile.write("Error creating %s in %s\n" % (
                                               dir_name, self._notify_window.secondFolder))
                            if STOP_ON_ERROR:
                                wx.PostEvent(self._notify_window, ResultEvent({'s': 0}))
                                return

                for f in files:
                    file_dir = root[second_len + 1:]
                    src_file = os.path.join(root, f)
                    # skip those copied from 1st to 2nd and those already compared
                    dest_file = os.path.join(self._notify_window.firstFolder, file_dir, f)
                    if not os.path.isfile(dest_file):
                        try:
                            fsize = os.path.getsize(src_file)
                        except OSError:
                            continue
                        if fsize > 100000000:
                            # for size > 100MB, report it's being copied
                            wx.PostEvent(self._notify_window, ResultEvent({'s': 2,
                                                                           'n': number_of_files,
                                                                           'f': src_file}))
                        try:
                            shutil.copy2(src_file, dest_file)
                            number_of_files += 1
                        except (PermissionError, FileNotFoundError):
                            self.logFile.write("Error copy %s to %s\n" % (src_file, dest_file))
                            wx.PostEvent(self._notify_window, ResultEvent({'s': 0}))
                            return

                    if number_of_files % 10 == 0:
                        if self._want_abort:
                            wx.PostEvent(self._notify_window, ResultEvent({'s': 1}))
                            return
                        wx.PostEvent(self._notify_window,
                                     ResultEvent({'s': 2,
                                                  'n': number_of_files,
                                                  'f': os.path.join(root, f)}))

            for f in self.same_name_diff_stats:
                src_file = os.path.join(self._notify_window.secondFolder, f)
                dest_file = os.path.join(self._notify_window.firstFolder, f)
                try:
                    # save filename in folder 2 as filename.2 in folder 1
                    shutil.copy2(src_file, "%s.2" % dest_file)
                    number_of_files += 1
                except (PermissionError, FileNotFoundError):
                    self.logFile.write("Error copy %s to %s.2\n" % (src_file, dest_file))
                    if STOP_ON_ERROR:
                        wx.PostEvent(self._notify_window, ResultEvent({'s': 0}))
                        return

                number_of_files += 1

            for pair in self.new1dirs:
                shutil.copystat(pair[0], pair[1])

        self.logFile.close()
        wx.PostEvent(self._notify_window, ResultEvent({'n': number_of_files, 's': 3}))

    def abort(self):
        """abort worker thread."""
        # Method for use by main thread to signal an abort
        self._want_abort = 1


class MyFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, size=(550, 300),
                          style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER)
        self.worker = None
        self.firstFolder = ""
        self.secondFolder = ""
        self.curDirection = 0  # down

        self.deleted = 0  # 0:ready 1:in progress 2:done
        self.SetBackgroundColour('white')

        icon = wx.Icon()
        icon.CopyFromBitmap(wx.Bitmap(resource_path("icon.ico"), wx.BITMAP_TYPE_ICO))
        self.SetIcon(icon)

        panel = wx.Panel(self, -1)
        title = wx.StaticText(panel, -1, "sync2", pos=(230, 20))
        title.SetFont(wx.Font(24, wx.DECORATIVE, wx.ITALIC, wx.BOLD))

        self.firstButton = wx.Button(panel, id=1, label='Folder A', size=(85, 28), pos=(5, 80))
        self.Bind(wx.EVT_BUTTON, self.OnFirst, id=1)
        self.txt1 = wx.TextCtrl(panel, size=(430, 30), pos=(95, 80), style=wx.TE_READONLY)

        self.upArrowSVG = wx.Bitmap('arrow-up.png')
        wx.Bitmap.Rescale(self.upArrowSVG, (32,32))
        self.downArrowSVG = wx.Bitmap('arrow-down.png')
        wx.Bitmap.Rescale(self.downArrowSVG, (32, 32))
        self.upDownArrowSVG = wx.Bitmap('arrows-up-down.png')
        wx.Bitmap.Rescale(self.upDownArrowSVG, (32, 32))
        wx.StaticText(panel, -1, "Click to change ->", pos=(70, 130))
        self.dirButton = wx.Button(panel, id=5, label='', pos=(200, 120), size=(33, 33), name='direction')
        self.dirButton.SetBitmap(self.downArrowSVG)
        self.dirText = wx.StaticText(panel, -1, "Folder A will be sync'ed to folder B", pos=(260, 130))
        self.Bind(wx.EVT_BUTTON, self.onDirButton, id=5)

        self.secondButton = wx.Button(panel, id=2, label='Folder B', size=(85, 28), pos=(5, 160))
        self.Bind(wx.EVT_BUTTON, self.OnSecond, id=2)
        self.txt2 = wx.TextCtrl(panel, size=(430, 30), pos=(95, 160), style=wx.TE_READONLY)

        self.doButton = wx.Button(panel, 3, 'SYNC!', (230, 210))
        self.Bind(wx.EVT_BUTTON, self.DoIt, id=3)
        self.txt3 = wx.TextCtrl(panel,
                                size=(515, 50),
                                pos=(10, 240),
                                style=wx.TE_READONLY | wx.TE_WORDWRAP | wx.TE_MULTILINE | wx.BORDER_NONE)
        self.txt3.SetValue("")

        # Set up event handler for any worker thread results
        EVT_RESULT(self, self.OnResult)

    def OnResult(self, event):
        # PostEvent data['s']:
        #     1: cancel
        #     2: processing
        #     3: done
        #     0: error  (should never happen because we dont stop on error)
        if event.data['s'] == 1:
            self.txt3.SetValue('Deleting task canceled.')
            self.worker = None
            self.doButton.SetLabel("SYNC!")
        elif event.data['s'] == 2:
            self.txt3.SetValue('copying %s\n%d files copied.' %
                               (event.data['f'], event.data['n']))
        elif event.data['s'] == 3:
            self.txt3.SetValue("Done! %d files were copied. The 2 folders are sync'ed" %
                               event.data['n'])
            self.worker = None
            self.doButton.SetLabel("SYNC!")
            self.doButton.Disable()
        else:
            # Process results here
            self.txt3.SetValue('Error! Aborted.')
            self.worker = None

    def ResetDoButton(self):
        self.doButton.Enable()
        self.deleted = 0

    def OnFirst(self, event):
        dlg = wx.DirDialog(self,
                           message="Select 1st folder",
                           defaultPath=wx.GetHomeDir(),
                           style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            firstFolder = dlg.GetPath()
            if self.firstFolder != firstFolder:
                self.firstFolder = firstFolder
                self.ResetDoButton()
            self.txt1.SetValue(self.firstFolder)
        dlg.Destroy()

    def OnSecond(self, event):
        dlg = wx.DirDialog(self, "Select 2nd folder", style=wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            secondFolder = dlg.GetPath()
            if self.secondFolder != secondFolder:
                self.secondFolder = secondFolder
                self.ResetDoButton()
            self.txt2.SetValue(self.secondFolder)
        dlg.Destroy()

    def onDirButton(self, event):
        if self.curDirection == 0:
            self.curDirection = 1
            self.dirButton.SetBitmap(self.upArrowSVG)
            self.dirText.SetLabel("Folder B will be sync'ed to folder A")
        elif self.curDirection == 1:
            self.curDirection = 2
            self.dirButton.SetBitmap(self.upDownArrowSVG)
            self.dirText.SetLabel("Folder A and B will be sync'ed")
        else:
            self.curDirection = 0
            self.dirButton.SetBitmap(self.downArrowSVG)
            self.dirText.SetLabel("Folder A will be sync'ed to folder B")

    def DoIt(self, event):
        if self.deleted == 0:
            if self.firstFolder == "" or self.secondFolder == "":
                self.txt3.SetValue("folders can not be empty!")
                return
            if self.firstFolder == self.secondFolder:
                self.txt3.SetValue("folders can not be the same!")
                return
            if self.firstFolder in self.secondFolder or self.secondFolder in self.firstFolder:
                self.txt3.SetValue("one folder can NOT be subfolder of the other")
                return

            self.deleted = 1
            self.doButton.SetLabel("Cancel")
            self.worker = WorkerThread(self)

        elif self.deleted == 1:
            self.txt3.SetValue("Canceling ...")
            self.deleted = 0
            self.worker.abort()


class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame(None, -1, 'sync2')
        frame.Show(True)
        frame.Centre()
        return True


if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
