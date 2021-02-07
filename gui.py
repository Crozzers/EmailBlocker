import tkinter as tk
from tkinter import font as tkFont
from tkinter import messagebox
import EmailBlocker
from EmailBlocker import __version__, filter_emails, output, quick_thread, get_settings, set_settings, save_settings
import os

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

class ScrollableFrame(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        self.__parent = tk.Frame(container, *args, **kwargs)
        self.__canvas = tk.Canvas(self.__parent)
        self.__scrollbar = tk.Scrollbar(self.__parent, orient="vertical", command=self.__canvas.yview)
        super().__init__(self.__canvas, *args, **kwargs)

        for i in dir(self.__parent):
            if i.startswith(('winfo', 'pack', 'place', 'grid')):
                setattr(self, 'scroll_'+i, getattr(self, i))
                setattr(self, i, getattr(self.__parent, i))

        self.bind("<Configure>",self.__config)

        self.__canvas.create_window((0, 0), window=self, anchor="nw")
        self.__canvas.configure(yscrollcommand=self.__scrollbar.set)

        self.__canvas.pack(side="left", fill="both", expand=True)
        self.__scrollbar.pack(side="right", fill="y")
    def config(self, *args, **kwargs):
        self.__canvas.config(*args, **kwargs)
        self.__parent.config(*args, **kwargs)
        super().config(*args,**kwargs)
    def __config(self, event):
        self.__canvas.configure(scrollregion=self.__canvas.bbox("all"))
        self.__canvas.configure(yscrollcommand=self.__scrollbar.set)
        children = self.__get_all_children()
        children.append(self.__canvas)
        if os.name=='nt':
            for child in children:
                child.bind_all('<MouseWheel>', self.scroll)
        else:#linux
            for child in children:
                child.bind_all('<4>', self.scroll)
                child.bind_all('<5>', self.scroll)
        self.__canvas.config(width = super().winfo_reqwidth())
    def __get_all_children(self, *args):
        if len(args)==0:
            children=self
        else:
            children=args[0]
        re=[]
        if type(children)!=list:
            re=children.winfo_children()
            children=children.winfo_children()
        if type(children)==list:
            for i in children:
                if type(i)==tk.Frame:
                    re+=self.__get_all_children(i.winfo_children())+[i]
                else:
                    re+=[i]
        else:
            re+=[children]
        return list(set(re))
    def scroll(self, amount):
        if type(amount)==tk.Event:
            if os.name=='nt':
                if amount.delta<0:
                    amount = 1
                else:
                    amount = -1
            else:#linux
                if amount.num==4:
                    amount = -1
                else:
                    amount = 1
        self.__canvas.yview_scroll(amount, 'units')

class FilterManager(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        self.top_bar = []
        a = 0
        # the '' at the end makes the small square of space above the delete buttons grey too
        for i in ('Search Term', 'From', 'CC', 'BCC', 'Subject', 'Body', 'Search must be present\nin ALL fields', 'Must match the\nsearch exactly', ''):
            self.top_bar.append(tk.Label(self, text=i, bg='#808080', anchor='nw', height=2))
            self.top_bar[-1].grid(row=0, column = a, sticky='nesw')
            a+=1

        self.grid_columnconfigure(0, weight=1)

        #self._init()
    def _format_filter(self, filter):
        if type(filter)==tuple:
            search, from_, cc, bcc, subject, body, all_match, exact_match = filter
            filter = {
                'search': search,
                'from': from_,
                'cc': cc,
                'bcc': bcc,
                'subject': subject,
                'body': body,
                'all_match': all_match,
                'exact_match': exact_match
            }
        if filter == None:
            filter = {}
        if type(filter)==dict:
            if 'search' not in filter.keys() or type(filter['search'])!=str:
                filter['search'] = ''
            for i in ('from', 'cc', 'bcc', 'subject', 'body', 'all_match', 'exact_match'):
                if i not in filter.keys():
                    if 'match' in i: # because all_match and exact_match should default to True
                        filter[i] = True
                    else:
                        filter[i] = False
                elif type(filter[i])==int:
                    filter[i] = bool(filter[i])
                elif type(filter[i])==bool:
                    pass
                else:
                    if 'match' in i: # because all_match and exact_match should default to True
                        filter[i] = True
                    else:
                        filter[i] = False
        return filter
    def _create(self, item, focus=False):
        e = tk.Entry(self, bd=1, width=50)
        e.insert(0, item['search'])
        e.grid(column=0, sticky='nesw')
        if focus:
            e.focus()
        bg='white'
        if e.grid_info()['row']%2==0:
            bg = '#d9d9d9'
        e.config(bg=bg)

        row = e.grid_info()['row']
        a = 1
        ret = []
        for i in (item['from'], item['cc'], item['bcc'], item['subject'], item['body'], item['all_match'], item['exact_match']):
            cb = tk.Checkbutton(self, bg=bg, bd=0, name=f'checkbuttonr{row}c{a}')
            cb.variable = tk.BooleanVar()
            cb.config(variable = cb.variable)
            cb.grid(row=row, column=a, sticky='nesw')
            if i:
                cb.select()
            ret.append(cb)
            a+=1
        tk.Button(self, text='Delete', relief='groove', command=lambda:self.remove_row(row)).grid(row=row, column=a, sticky='nesw')
        return e, *ret
    def remove_row(self, row):
        for w in self.grid_slaves(row=row):
            w.grid_remove()
            w.grid_forget()
            w.destroy()

        a=0
        for i in range(1, self.grid_size()[1]):
            # the order of the background swapping is reversed here because look up and behold!
            # this loop starts on an ODD number. The others start at 0
            bg='#d9d9d9'
            if a%2==0:
                bg = 'white'
            if len(self.grid_slaves(row=i))>0:
                for w in self.grid_slaves(row=i):
                    w.config(bg=bg)
                    w.update()
                a+=1
    def add_row(self, value=None):
        if value!=None:
            value = self._format_filter(value)
            self._create(value)
        else:
            try:
                rows = self.rows()
                for r in rows:
                    row = self.get_row(r)
                    if row['search'] == '' and all(row[k]==False for k,v in row.items() if 'match' not in k and type(v)==bool):
                        # if theres an un-filled entry then focus on that instead of adding more rows
                        for i in self.grid_slaves(row=r):
                            if type(i)==tk.Entry:
                                i.focus()
                                return
                # if there are no un-filled entries then create one
                self._create(self._format_filter(None), focus=True)
            except IndexError:
                # if there are no un-filled entries then create one
                self._create(self._format_filter(None), focus=True)
    def load_filters(self):
        for i in self.grid_slaves():
            if i not in self.top_bar:
                i.destroy()

        for i in get_settings()['filters']:
            self._create(self._format_filter(i))
    def get_filters(self):
        config = []

        for row in self.rows():
            setting = self.get_row(row)
            if setting!={} and not(setting['search']=='' and all(i==0 for i in setting.values() if type(i)==int)):
                config.append(self._format_filter(setting))
        return config
    def rows(self):
        rows = []
        for i in range(1, self.grid_size()[1]):
            if len(self.grid_slaves(row=i))>0:
                rows.append(i)
        return rows
    def get_row(self, row):
        names = ('from', 'cc', 'bcc', 'subject', 'body', 'all_match', 'exact_match')
        setting = {}
        if row<0:
            row = self.rows()[row]
        for widget in self.grid_slaves(row=row):
            if type(widget)==tk.Entry:
                setting['search'] = widget.get()
            elif f'checkbutton' in widget._name:
                name = int(widget._name[-1])
                setting[names[name-1]] = widget.variable.get()
        return self._format_filter(setting)

class Window():
    def __init__(self):
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

        tmp = ScrollableFrame(self.blocking_frame, bd=0, highlightthickness=0)
        tmp.pack(side='top', fill='both', expand=True)

        self.filter_manager = FilterManager(tmp, bd=0, highlightthickness=0)
        self.filter_manager.pack(**dk)
        #self.filter_manager.pack(side='top', fill='both', expand=True)
        tk.Button(self.blocking_frame, text='Add blocking rule', command = self.filter_manager.add_row, relief='groove').pack(**dk)

        self.actions_frame = tk.Frame(self.root)
        self.actions_frame.pack(pady=15, **dk)
        tk.Button(self.actions_frame, text='Save these settings', command=self.save_settings, relief='groove').pack(pady=(5,2), **dk)
        tk.Button(self.actions_frame, text='Load saved settings', command=lambda:self.load_settings(), relief='groove').pack(pady=(0,5), **dk)

        self.load_settings_at_launch = tk.BooleanVar()
        self.load_settings_check = tk.Checkbutton(
            self.actions_frame, text='Load your saved settings on launch', variable=self.load_settings_at_launch, command=lambda:self.save_settings(1))
        self.load_settings_check.pack(pady=(0, 10), **dk)
        WrappingLabel(self.actions_frame,text='NOTICE: I offer no warranty of any kind with this program', bg='red').pack(**dk)
        self.run_button = tk.Button(self.actions_frame, text='Run', command=lambda:quick_thread(self.run), relief='groove')
        self.run_button.pack(pady=(5, 10), **dk)

        if os.name=='nt':
            self.run_at_startup_buton1 = tk.Button(self.actions_frame, text='Run the current config when the computer starts', command=lambda:quick_thread(self.StartupTask_create), relief='groove')
            self.run_at_startup_buton1.pack(pady=5, **dk)
            self.run_at_startup_buton2 = tk.Button(self.actions_frame, text='Remove startup tasks', command=lambda:quick_thread(self.StartupTask_destroy), relief='groove')
            self.run_at_startup_buton2.pack(pady=(0, 10), **dk)

        self.output_label = WrappingLabel(self.root)
        self.output_label.pack(**dk)

        if get_settings()['load_settings_on_launch']:
            self.load_settings()
        if len(self.filter_manager.get_filters())==0:
            self.filter_manager.add_row()
        # check if tasks need to be updated and if so, update them
        EmailBlocker.StartupTask.repair()
    def show_password(self, *args):
        if self.password_input['show']=='*':
            self.password_input.config(show='')
        else:
            self.password_input.config(show='*')
    def get_inputs(self):
        email = self.email_input.get()
        password = self.password_input.get()
        load_at_startup = self.load_settings_at_launch.get()
        # do this method of removing duplicates because this call returns dicts
        # and they are not hashable so we can't just do list(set(item))
        filters = []
        for i in self.filter_manager.get_filters():
            if i not in filters:
                filters.append(i)

        return {
            'user_email': email,
            'user_password': password,
            'load_settings_on_launch': load_at_startup,
            'filters': filters
        }
    def output(self, text, colour = 'white'):
        self.output_label.config(text=text, bg=colour)
        self.output_label.update()
    def disable(self, widget):
        if widget=='run':
            self.run_button.config(state=tk.DISABLED)
        elif widget=='startup':
            self.run_at_startup_buton1.config(state=tk.DISABLED)
            self.run_at_startup_buton2.config(state=tk.DISABLED)
        elif widget=='actions_frame':
            for b in self.actions_frame.winfo_children():
                if type(b) in (tk.Button, tk.Checkbutton):
                    b.config(state=tk.DISABLED)
    def enable(self, widget):
        if widget=='run':
            self.run_button.config(state=tk.NORMAL)
        elif widget=='startup':
            self.run_at_startup_buton1.config(state=tk.NORMAL)
            self.run_at_startup_buton2.config(state=tk.NORMAL)
        elif widget=='actions_frame':
            for b in self.actions_frame.winfo_children():
                if type(b) in (tk.Button, tk.Checkbutton):
                    b.config(state=tk.NORMAL)
    def save_settings(self, mode=0):
        if mode==0:
            save_settings(self.get_inputs())
        elif mode==1:
            save_settings(
                {**get_settings(), 'load_settings_on_launch': self.get_inputs()['load_settings_on_launch']}
            )
    def load_settings(self):
        settings = get_settings()

        try:
            self.email_input.delete(0, 'end')
            self.email_input.insert(0, settings['user_email'])
        except:pass

        try:
            self.password_input.delete(0, 'end')
            self.password_input.insert(0, settings['user_password'])
        except:pass

        try:
            if settings['load_settings_on_launch']:
                self.load_settings_check.select()
        except:
            pass

        try:
            # do this method of removing duplicates because this call returns dicts
            # and they are not hashable so we can't just do list(set(item))
            filters = []
            for i in settings['filters']:
                if i not in filters:
                    filters.append(i)
            settings['filters'] = filters
            self.filter_manager.load_filters()
        except:
            pass
    def run(self):
        set_settings(self.get_inputs())
        self.disable('run')
        EmailBlocker.run()
        self.enable('run')
    def StartupTask_create(self):
        set_settings(self.get_inputs())
        self.disable('startup')
        EmailBlocker.StartupTask.create()
        self.enable('startup')
    def StartupTask_destroy(self):
        set_settings(self.get_inputs())
        self.disable('startup')
        EmailBlocker.StartupTask.destroy()
        self.enable('startup')
    def check_for_update(self):
            self.disable('actions_frame')
            EmailBlocker.check_for_update()
            self.enable('actions_frame')

if __name__=='__main__':
    global window
    window = Window()
    # see EmailBlocker.py for why we do this
    window.instance = window
    window.root.mainloop()