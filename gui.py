import tkinter as tk
from tkinter import font as tkFont
from tkinter import messagebox
import json, shutil, threading
from EmailBlocker import __version__, sys, os, filter_emails
import urllib.request
from packaging import version
from time import sleep
import zipfile

def quick_thread(target, *args, autostart=True, **kwargs):
    t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    if autostart:
        t.start()
    return t

class WrappingLabel(tk.Label):
    def __init__(self, container, autowrap=True, maxheight=None, **kwargs):
        '''
        Tkinter compatible Label type widget that automatically wraps the text inside of it

        Args:
            container: the widget to place the label onto
            autowrap (bool): if the widget should automatically wrap the text
            kwargs (dict): passed directly to the initialization of a `tkinter.Label`
        '''
        super().__init__(container, **kwargs)
        self.autowrap = autowrap
        self.maxheight = maxheight
        if self.autowrap:
            super().bind('<Configure>', self.wrap_text)
    def wrap_text(self, *args):
        '''
        Performs the text-wrapping operation

        Args:
            args (tuple): ignored
        '''
        if not self.winfo_ismapped():
            return
        super().unbind('<Configure>')
        self.update_idletasks()
        font = tkFont.Font(font=self['font'])
        text = self['text']
        font_width = font.measure('0')

        if self.winfo_width() < len(text)*font_width:
            maxlen = self.winfo_width()
            try:
                maxheight = int((len(text)/(min(self.winfo_reqwidth(), self.winfo_width())//font_width))+0.7)
                maxheight = max(1, maxheight)
                if self.maxheight!=None:
                    maxheight = min(maxheight, self.maxheight)
                maxheight+=text.count('\n')
                self.config(wraplength=maxlen, height=maxheight)
            except ZeroDivisionError:
                pass
        elif self.winfo_width() > len(text)*font_width:
            self.config(height=1, wraplength=(len(text)*font_width)+5)

        self.update_idletasks()
        if self.autowrap:
            super().bind('<Configure>', self.wrap_text)
    def config(self, *args, **kwargs):
        if 'maxheight' in kwargs.keys():
            self.maxheight = kwargs['maxheight']
            del(kwargs['maxheight'])

        ret = super().config(*args, **kwargs)

        if ('text' in kwargs.keys() or 'font' in kwargs.keys()) and self.autowrap:
            self.wrap_text()
        return ret
    def destroy(self, *args, **kwargs):
        self.unbind_all('<Configure>')
        super().destroy(*args, **kwargs)

def makeHTTPRequest(url):
    try:
        with urllib.request.urlopen(url) as url:
            http=url.getcode()
            try:
                data=url.read().decode()
            except:
                data=None
        return http,data
    except urllib.error.URLError as e:
        return False

def conv_file_size(size):
    size = size/1024#convert bytes to kb
    suffix="KB"
    if size/1024>=1:#1Mb or larger
        size=size/1024
        suffix="MB"
        if size/1024>=1:#1Gb or larger
            size=size/1024
            suffix="GB"
    size=str(size)
    if "." in size:
        size=size[:size.index(".")+3]
    return size+suffix

def get_file_size(file, raw=True):
    if raw:
        return os.path.getsize(file)
    else:
        size=os.path.getsize(file)
        return conv_file_size(size)

class Download():
    def __init__(self,url,destination):
        self.url = url
        self.destination = destination
        if os.path.isdir(self.destination):
            self.destination = os.path.join(self.destination, os.path.basename(url))
        self.is_started = False
        self.is_finished = False
        self.is_cancelled = False
        self.length = None
    def __download(self):
        def listener(self, *args):
            if self.is_cancelled:
                raise Exception('Download cancelled')
        try:
            tmp = urllib.request.urlopen(self.url)
            try:
                self.length = int(tmp.info()['Content-Length'])
            except:
                sleep(0.5)
                tmp = urllib.request.urlopen(self.url)
                try:
                    self.length = int(tmp.info()['Content-Length'])
                except:
                    self.length = 0
            self.is_started=True
            urllib.request.urlretrieve(self.url,self.destination, reporthook=lambda *args:listener(self, *args))
        except Exception as e:
            if str(e) != 'Download cancelled':
                raise e
        else:
            self.is_finished=True
    def download(self):
        quick_thread(self.__download)
    def cancel(self):
        self.is_cancelled = True
        os.remove(self.destination)
    def progress(self):
        if not os.path.isfile(self.destination):
            return None
        else:
            return get_file_size(self.destination), get_file_size(self.destination, False)
    def started(self):
        return self.is_started
    def finished(self):
        return self.is_finished
    def cancelled(self):
        return self.is_cancelled

class Window():
    def __init__(self):
        self.basedir = os.path.dirname(__file__)
        self.running = False
        self.root = tk.Tk()
        self.root.title(f'EmailBlocker v{__version__} - By Crozzers')

        dk = {'side':'top', 'fill':'x', 'expand':True, 'anchor':'nw'}

        # create top menu toolbar
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        upmenu = tk.Menu(self.menubar)
        upmenu.add_command(label='Check for updates', command=lambda:quick_thread(self.check_for_update))
        self.menubar.add_cascade(label='Options', menu=upmenu)

        self.credentials_frame = tk.LabelFrame(self.root, text='Your credentials')
        self.credentials_frame.pack(pady=(5,0), **dk)

        WrappingLabel(self.credentials_frame, text='Your email address:', anchor='w').pack(pady=10, **dk)
        self.email_input = tk.Entry(self.credentials_frame)
        self.email_input.pack(**dk)

        WrappingLabel(self.credentials_frame, text='Your password:', anchor='w').pack(pady=10, **dk)
        self.password_input = tk.Entry(self.credentials_frame, show='*')
        self.password_input.pack(**dk)
        tk.Checkbutton(self.credentials_frame, command=self.show_password, text='Show password', anchor='w').pack(**dk)

        self.blocking_frame = tk.LabelFrame(self.root, text='Blocking Settings')
        self.blocking_frame.pack(pady=(10,0), **dk)

        WrappingLabel(self.blocking_frame, text='Email addresses to block (one address per line):', anchor='w').pack(pady=10, **dk)
        self.email_block_input = tk.Text(self.blocking_frame, height=10)
        self.email_block_input.pack(**dk)

        self.actions_frame = tk.Frame(self.root)
        self.actions_frame.pack(pady=15, **dk)
        tk.Button(self.actions_frame, text='Save these settings', command=self.save_settings, relief='groove').pack(pady=(5,2), **dk)
        tk.Button(self.actions_frame, text='Load saved settings', command=lambda:self.load_settings(True), relief='groove').pack(pady=(0,5), **dk)
        self.load_settings_at_launch = tk.BooleanVar()
        self.load_settings_check = tk.Checkbutton(self.actions_frame, text='Load your saved settings on launch', variable=self.load_settings_at_launch, command=lambda:self.save_settings(1))
        self.load_settings_check.pack(pady=(0, 10), **dk)
        WrappingLabel(self.actions_frame,text='NOTICE: I offer no warranty of any kind with this program', bg='red').pack(**dk)
        self.run_button = tk.Button(self.actions_frame, text='Run', command=lambda:quick_thread(self.run), relief='groove')
        self.run_button.pack(pady=(5, 10), **dk)

        if os.name=='nt':
            self.run_at_startup_buton1 = tk.Button(self.actions_frame, text='Save these settings to run at startup', command=lambda:quick_thread(self.run_at_startup, 0), relief='groove')
            self.run_at_startup_buton1.pack(pady=5, **dk)
            self.run_at_startup_buton2 = tk.Button(self.actions_frame, text='Remove startup tasks', command=lambda:quick_thread(self.run_at_startup, 1), relief='groove')
            self.run_at_startup_buton2.pack(pady=(0, 10), **dk)

        self.output_label = WrappingLabel(self.root)
        self.output_label.pack(**dk)

        self.load_settings()
        # check if tasks need to be updated and if so, update them
        self.run_at_startup(2)
    def show_password(self, *args):
        if self.password_input['show']=='*':
            self.password_input.config(show='')
        else:
            self.password_input.config(show='*')
    def run(self):
        try:
            self.running=True
            self.run_button.config(state=tk.DISABLED)
            email, password, sender, load_at_startup = self.get_config()
            if email==False:
                self.output(f'Cannot filter emails: Invalid email address', 'red')
                return
            if password=='':
                self.output(f'Cannot filter emails: Invalid password', 'red')
                return
            if not sender:
                self.output(f'Cannot filter emails: Invalid blocking list', 'red')
                return
            folder='inbox'
            
            self.output(f'Logging into GMAIL with user {email}')
            connection_message, server = filter_emails.login(email, password)
            self.output(connection_message)

            self.output(f'Selecting {folder}')
            filter_emails.select_label(server, folder)

            while True:
                self.output(f'Searching {folder} for emails{" from "+sender if len(sender)==0 else ""}')
                email_ids = []
                for s in sender:
                    if filter_emails.email_valid(s):
                        email_ids+=filter_emails.get_emails(server, s)
                    else:
                        self.output(f'Skipped invalid email address: {s}')
                if email_ids==[]:
                    break
                self.output(f'Found {len(email_ids)} email{"s" if len(email_ids)>1 else ""}')

                if len(email_ids)>0:
                    for i in range(len(email_ids)):
                        self.output(f'Sending {len(email_ids)} email{"s" if len(email_ids)>1 else ""} to the bin ({i+1}/{len(email_ids)})')
                        filter_emails.move_email(server, email_ids[i], filter_emails.TRASH)

            self.output('Done!', 'green')
        except Exception as e:
            self.output(f'Failed: {e}', 'red')
        finally:
            self.run_button.config(state=tk.NORMAL)
            self.running=False
    def save_settings(self, mode=None):
        filepath = os.path.join(self.basedir, 'settings.json')
        email, password, sender, load_at_startup = self.get_config()
        if mode==None:
            msg_box = messagebox.askyesno(
                title='IMPORTANT',
                message='Your data will be stored in PLAIN text, no encryption and absolutely no security. Do you still wish to proceed?',
                icon='warning'
            )
            if msg_box==True:
                if email==False:
                    self.output(f'Cannot save settings: Invalid email address', 'red')
                    return
                if password=='':
                    self.output(f'Cannot save settings: Invalid password', 'red')
                    return
                if not sender:
                    self.output(f'Cannot save settings: Invalid blocking list', 'red')
                    return
                data = {
                    'user_email': email,
                    'user_password': password,
                    'blocked_emails': sender,
                    'load_settings_on_launch': load_at_startup
                }
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                self.output(f'Settings saved!', 'green')
        else:
            # just saving the 'load on lauch' checkbox
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            except:
                settings = {}
            settings['load_settings_on_launch'] = load_at_startup
            with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(settings, f)
    def load_settings(self, override=False):
        try:
            filepath = os.path.join(self.basedir, 'settings.json')
            if os.path.isfile(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                if settings['load_settings_on_launch'] or override:
                    try:
                        self.email_input.delete(0, tk.END)
                        self.email_input.insert(0, settings['user_email'])
                    except:pass
                    try:
                        self.password_input.delete(0, tk.END)
                        self.password_input.insert(0, settings['user_password'])
                    except:pass
                    try:
                        self.email_block_input.delete('1.0', tk.END)
                        self.email_block_input.insert('1.0', '\n'.join([i for i in settings['blocked_emails'] if filter_emails.email_valid(i)]))
                    except:pass
                    if settings['load_settings_on_launch']:
                        self.load_settings_check.select()
                    if override:
                        self.output('Settings loaded', 'green')
        except Exception as e:
            self.output(f'Failed to load your settings: {e}', 'red')
            pass
    def get_config(self):
        email = self.email_input.get()
        if not filter_emails.email_valid(email):
            email = False
        password = self.password_input.get()
        sender = self.email_block_input.get('1.0', 'end-1c').split('\n')
        while '' in sender:
            sender.remove('')
        sender = [i for i in sender if filter_emails.email_valid(i)]
        load_at_startup = self.load_settings_at_launch.get()
        return email, password, sender, load_at_startup
    def run_at_startup(self, mode):
        self.run_at_startup_buton1.config(state=tk.DISABLED)
        self.run_at_startup_buton2.config(state=tk.DISABLED)
        pjoin = os.path.join
        isdir = os.path.isdir
        isfile = os.path.isfile

        appdata_dir = pjoin(os.path.expanduser('~'), 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/')
        startup_dir = pjoin(appdata_dir, 'Startup').replace('\\','/')
        appdata_dir = pjoin(appdata_dir, 'EmailBlockerLite').replace('\\','/')
        if not isfile(pjoin(self.basedir, 'EmailBlockerLite.py')):
            self.output('Cannot create startup task: cannot find EmailBlockerLite.py', 'red')
            return
        pydir = os.path.dirname(sys.executable)

        if mode==0:
            try:
                email, password, sender, load_at_startup = self.get_config()
                if email==False:
                    self.output('Cannot create startup task: Invalid email address', 'red')
                    return
                if password=='':
                    self.output('Cannot create startup task: Invalid password', 'red')
                    return
                if not sender:
                    self.output('Cannot create startup task: Invalid blocking list', 'red')
                    return
                sender = ','.join(sender)

                self.output('Removing old startup task')
                if isdir(appdata_dir):
                    shutil.rmtree(appdata_dir)
                self.output('Copying Python interpreter to AppData folder')
                os.mkdir(appdata_dir)
                shutil.copytree(pydir, pjoin(appdata_dir, 'py_interp'))

                self.output('Copying EmailBlockerLite to AppData folder')
                shutil.copyfile(pjoin(self.basedir, 'EmailBlockerLite.py'), pjoin(appdata_dir, 'EmailBlockerLite.py'))
                
                self.output('Writing batch file in shell:startup dir')
                with open(pjoin(startup_dir, 'EmailBlocker.bat'), 'w', encoding='utf-8') as f:
                    f.write(
                        f'@echo off\nstart "EmailBlocker" "{pjoin(appdata_dir, "py_interp/python.exe")}" "{pjoin(appdata_dir, "EmailBlockerLite.py")}" "{email}" "{password}" "{sender}"'
                    )
                self.output('Startup task created!', 'green')
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.output(f'Failed to create startup task: {e}', 'red')
        elif mode==1:
            if isdir(appdata_dir):
                shutil.rmtree(appdata_dir)
            if isfile(pjoin(startup_dir, 'EmailBlocker.bat')):
                os.remove(pjoin(startup_dir, 'EmailBlocker.bat'))
            self.output('Startup tasks removed!', 'green')
        elif mode==2:
            try:
                if isdir(appdata_dir) and isfile(pjoin(startup_dir, 'EmailBlocker.bat')):
                    ver = None
                    with open(pjoin(appdata_dir, 'EmailBlockerLite.py'), 'r', encoding='utf-8') as f:
                        for line in f.readlines():
                            if line.replace(' ','').startswith('__version__='):
                                ver = version.Version(line.replace(' ','').replace('__version__=', '').replace('\'', ''))
                                break
                    if ver==None:
                        self.output('Failed to update startup tasks: Could not detect version of the task', 'orange')
                    elif ver<version.Version(__version__):
                        self.output('Updating startup tasks')
                        # remove startup tasks
                        self.run_at_startup(1)
                        # add them back
                        self.run_at_startup(0)
                        self.output('Startup tasks updated', 'green')
                elif isdir(appdata_dir) or isfile(pjoin(startup_dir, 'EmailBlocker.bat')):
                    # if only one is detected then it's likely that the other was deleted
                    # or that it's a startup task from a different program
                    # if the latter is the case we really do NOT want to go and muck that up
                    # so we ask the user what to do so if something goes wrong we can blame them :)
                    self.output('Invalid startup tasks detected', 'orange')
                    msg_box = messagebox.askyesno(
                        title='Invalid startup tasks',
                        message='An invalid startup task was detected. Would you like to repair it?'
                    )
                    if msg_box:
                        self.run_at_startup(0)
                        self.run_at_startup(1)
                        self.output('Startup task repaired', 'green')

            except Exception as e:
                self.output(f'Failed to update startup tasks: {e}', 'red')
        else:
            pass
        self.run_at_startup_buton1.config(state=tk.NORMAL)
        self.run_at_startup_buton2.config(state=tk.NORMAL)
    def output(self, text, colour='white', **kwargs):
        self.output_label.config(text=text, bg=colour, **kwargs)
        self.output_label.update()
    def check_for_update(self):
        self.run_button.config(state=tk.DISABLED)
        self.output('Checking')
        url = 'https://github.com/Crozzers/EmailBlocker/blob/master/EmailBlocker.py?raw=true'
        ret = makeHTTPRequest(url)
        if ret==False:
            self.output('Error: Failed to reach GitHub servers', 'red')
        else:
            http, data = ret
            if http!=200:
                self.output(f'Error: GitHub servers returned code: {http}', 'red')
            else:
                data = data.split('\n')
                ver = None
                for line in data:
                    if line.replace(' ','').startswith('__version__='):
                        ver = line.replace(' ','').replace('__version__=', '').replace('\'','')
                        break
                if ver==None:
                    self.output('Failed to detect latest version', 'red')
                else:
                    if version.Version(ver)>version.Version(__version__) or True:
                        # the "or True" is here for testing purposes
                        msg_box = messagebox.askyesno(
                            title='Update Available',
                            message='Would you like to download and install the latest update?'
                        )
                        if msg_box==True:
                            try:
                                pjoin = os.path.join
                                dest = pjoin(self.basedir, f'EmailBlocker-{ver}.zip')
                                # start the download while we deal with any old downloads kicking about
                                downloader = Download('https://github.com/Crozzers/EmailBlocker/archive/master.zip', dest)
                                downloader.download()

                                def unzip(downloader, dest):
                                    while not downloader.finished():
                                        sleep(1)
                                    sleep(1)
                                    with zipfile.ZipFile(dest) as f:
                                        f.extractall(self.basedir)

                                self.output('Disabling buttons')
                                for b in self.actions_frame.winfo_children():
                                    if type(b) in (tk.Button, tk.Checkbutton):
                                        b.config(state=tk.DISABLED)

                                self.output('Moving old update files')
                                if os.path.isdir('EmailBlocker-master') or os.path.isfile('EmailBlocker-master'):
                                    os.rename('EmailBlocker-master', 'EmailBlocker-master-old')

                                # unzip in the background while we deal with removing all the old files
                                unzip_thread = quick_thread(unzip, downloader, dest)

                                self.output('Removing old update files')
                                if os.path.isdir('EmailBlocker-master-old'):
                                    shutil.rmtree('EmailBlocker-master-old')
                                elif os.path.isfile('EmailBlocker-master-old'):
                                    os.remove('EmailBlocker-master-old')

                                while not downloader.started():
                                    self.output('Waiting for download to start')
                                    sleep(1)
                                while not downloader.finished():
                                    tmp = downloader.progress()
                                    if downloader.length!=None:
                                       self.output(f'Downloading update ({tmp[1]}/{conv_file_size(downloader.length)})')
                                    sleep(0.05)
                                sleep(1)

                                self.output('Unzipping update')
                                while unzip_thread.is_alive():
                                    sleep(1)
                                os.remove(dest)

                                self.output('Waiting for running jobs to complete')
                                while self.running:
                                    sleep(1)

                                up_dir = pjoin(self.basedir, 'EmailBlocker-master')
                                for item in os.listdir(up_dir):
                                    src = pjoin(up_dir, item)
                                    dst = pjoin(self.basedir, item)
                                    # only do files because the python embed directory and TCL library shouldn't need to be updated
                                    if os.path.isfile(src) :
                                       self.output(f'Updating {item}')
                                       if os.path.isfile(dst):
                                           os.remove(dst)
                                       shutil.copyfile(src, dst)

                                self.output('Update completed! Please restart the program', 'green')
                            except Exception as e:
                                self.output(f'Failed to download update: {e}', 'red')
                            finally:
                                for b in self.actions_frame.winfo_children():
                                    if type(b) in (tk.Button, tk.Checkbutton):
                                        b.config(state=tk.NORMAL)
                    else:
                        self.output('No updates are available')

if __name__=='__main__':
    window = Window()
    window.root.mainloop()