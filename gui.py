import tkinter as tk
from tkinter import messagebox
from tkinter import font as tkFont
import filter_emails
import json, os, sys, shutil, threading

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

class Window():
    def __init__(self):
        if getattr(sys, 'frozen', None):
            self.basedir = sys._MEIPASS
        else:
            self.basedir = os.path.dirname(__file__)
        self.root = tk.Tk()
        #self.root.geometry('450x600')
        self.root.title('Email Blocker v0.3.0 - By Crozzers')

        dk = {'side':'top', 'fill':'x', 'expand':True, 'anchor':'nw'}

        self.credentials_frame = tk.LabelFrame(self.root, text='Your credentials')
        self.credentials_frame.pack(**dk)

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
        self.load_settings_check = tk.Checkbutton(self.actions_frame, text='Load your saved settings at startup', variable=self.load_settings_at_launch)
        self.load_settings_check.pack(pady=(0, 10), **dk)
        WrappingLabel(self.actions_frame,text='NOTICE: I offer no warranty of any kind with this program', bg='red').pack(**dk)
        self.run_button = tk.Button(self.actions_frame, text='Run', command=lambda:quick_thread(self.run), relief='groove')
        self.run_button.pack(pady=(5, 10), **dk)

        self.run_at_startup_buton1 = tk.Button(self.actions_frame, text='Save these settings to run at startup', command=lambda:quick_thread(self.run_at_startup, 0), relief='groove')
        self.run_at_startup_buton1.pack(pady=5, **dk)
        self.run_at_startup_buton2 = tk.Button(self.actions_frame, text='Remove startup tasks', command=lambda:quick_thread(self.run_at_startup, 1), relief='groove')
        self.run_at_startup_buton2.pack(pady=(0, 10), **dk)

        self.output_label = WrappingLabel(self.root)
        self.output_label.pack(**dk)

        self.load_settings()
    def show_password(self, *args):
        if self.password_input['show']=='*':
            self.password_input.config(show='')
        else:
            self.password_input.config(show='*')
    def run(self):
        try:
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
    def save_settings(self):
        msg_box = messagebox.askyesno(
            title='IMPORTANT',
            message='Your data will be stored in PLAIN text, no encryption and absolutely no security. Do you still wish to proceed?',
            icon='warning'
        )
        if msg_box==True:
            email, password, sender, load_at_startup = self.get_config()
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
            filepath = os.path.join(self.basedir, 'settings.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            self.output(f'Settings saved!', 'green')
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
        path = os.path.join(os.path.expanduser('~'), 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/').replace('\\','/')
        exepath = path+'EmailBlockerLite/EmailBlockerLite.exe'
        frompath = 'EmailBlockerLite'
        if not os.path.isdir(frompath):
            if os.path.isdir('EmailBlocker/'+frompath):
                frompath = 'EmailBlocker/'+frompath
            else:
                self.output('Cannot create startup task: cannot find EmailBlockerLite', 'red')
                return
        
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
                self.output('Copying EmailBlockerLite to AppData folder')
                if not os.path.isdir(path+'EmailBlockerLite'):
                    shutil.copytree(frompath, path+'EmailBlockerLite')
                if not os.path.isfile(exepath):
                    shutil.rmtree(path+'EmailBlockerLite')
                    shutil.copytree(frompath, path+'EmailBlockerLite')
                
                self.output('Writing batch file in shell:startup dir')
                with open(path+'Startup/EmailBlocker.bat', 'w', encoding='utf-8') as f:
                    f.write(
                        f'@echo off\nstart "EmailBlocker" "{exepath}" "{email}" "{password}" "{sender}"'
                    )
                self.output('Startup task created!', 'green')
            except Exception as e:
                self.output(f'Failed to create startup task: {e}', 'red')
        else:
            if os.path.isdir(path+'EmailBlockerLite'):
                shutil.rmtree(path+'EmailBlockerLite')
            if os.path.isfile(path+'Startup/EmailBlocker.bat'):
                os.remove(path+'Startup/EmailBlocker.bat')
            self.output('Startup tasks removed!', 'green')
        self.run_at_startup_buton1.config(state=tk.NORMAL)
        self.run_at_startup_buton2.config(state=tk.NORMAL)
    def output(self, text, colour='white', **kwargs):
        self.output_label.config(text=text, bg=colour, **kwargs)
        self.output_label.update()

if __name__=='__main__':
    window = Window()
    window.root.mainloop()