import tkinter as tk
from tkinter import font as tkFont
from tkinter import messagebox
import EmailBlocker
from EmailBlocker import __version__, filter_emails, output, quick_thread, get_settings, set_settings, save_settings
import os
import time

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
    def __init__(self, container, *args, autobind=True, **kwargs):
        self.__parent = tk.Frame(container, *args, **kwargs)
        self.__canvas = tk.Canvas(self.__parent)
        self.__scrollbar = tk.Scrollbar(self.__parent, orient="vertical", command=self.__canvas.yview)
        super().__init__(self.__canvas, *args, **kwargs)

        for i in dir(self.__parent):
            if i.startswith(('winfo', 'pack', 'place', 'grid')):
                setattr(self, 'scroll_'+i, getattr(self, i))
                setattr(self, i, getattr(self.__parent, i))
        for i in dir(self.__canvas):
            if i.startswith(('yview', 'xview')):
                setattr(self, i, getattr(self.__canvas, i))

        self.bind("<Configure>",self.__config)
        self.autobind = autobind

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
        if self.autobind:
            if super().winfo_reqheight()<self.winfo_height():
                self.children_unbind_scroll()
                self.__canvas.yview_moveto(0)
            else:
                self.children_bind_scroll()
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
                amount = 1 if amount.delta<0 else -1
            else:#linux
                amount = 1 if amount.num==4 else -1
        self.__canvas.yview_scroll(amount, 'units')
    def children_bind_scroll(self):
        children = self.__get_all_children()
        children.append(self.__canvas)
        if os.name=='nt':
            for child in children:
                child.bind_all('<MouseWheel>', self.scroll)
        else:#linux
            for child in children:
                child.bind_all('<4>', self.scroll)
                child.bind_all('<5>', self.scroll)
    def children_unbind_scroll(self):
        children = self.__get_all_children()
        children.append(self.__canvas)
        if os.name=='nt':
            for child in children:
                child.unbind_all('<MouseWheel>')
        else:#linux
            for child in children:
                child.unbind_all('<4>')
                child.unbind_all('<5>')

class FilterManager(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        self.top_bar = []
        a = 0
        # the '' at the end makes the small square of space above the delete buttons grey too
        for i in ('Search Term', 'Label', 'From', 'CC', 'BCC', 'Subject', 'Body', 'Search must be present\nin ALL fields', 'Must match the\nsearch exactly', ''):
            self.top_bar.append(tk.Label(self, text=i, bg='#808080', anchor='nw', height=2))
            self.top_bar[-1].grid(row=0, column = a, sticky='nesw')
            a+=1

        self.grid_columnconfigure(0, weight=1)

        #self._init()
    def _format_filter(self, filter, sub=False):
        if type(filter)==tuple:
            if len(filter)==10:
                search, from_, cc, bcc, subject, body, label, all_match, exact_match, sub_filters = filter
            else:
                search, from_, cc, bcc, subject, body, all_match, exact_match = filter
                label = None
                sub_filters = None
            filter = {
                'search': search,
                'from': from_,
                'cc': cc,
                'bcc': bcc,
                'subject': subject,
                'body': body,
                'label': label,
                'all_match': all_match,
                'exact_match': exact_match,
                'sub_filters': sub_filters
            }
            if filter['sub_filters'] == None:
                del(filter['sub_filters'])
            if filter['label'] == None:
                del(filter['label'])
        if filter == None:
            filter = {}
        if type(filter)==dict:
            filter = EmailBlocker.validate_filter(filter, sub=sub)
        return filter
    def _create(self, item, focus=False, sub=False):
        row = None
        configs = (50, 'nesw')
        major_rows = {}
        minor_rows = []
        taken = []
        for i in self.rows():
            taken.append(i)
            info = self.get_row(i)
            if info!=False:
                if 'sub_filters' in info.keys():
                    major_rows[i] = info
                else:
                    minor_rows.append(i)

        if sub:
            current = self.focus_get()
            try:
                if '!filtermanager.!' in str(current):
                    # find the "main rule" by finding the nearest 10
                    nearest_major = current.grid_info()['row']
                    if nearest_major%10!=0:
                        nearest_major = nearest_major - (nearest_major%10)
                    # check if max number of sub-filters exceeded
                    if len(major_rows[nearest_major]['sub_filters'])>=9:
                        output('Can have maximum of 9 sub-rules', 'orange')
                        return
                    # find nearest empty row
                    for i in range(1, 10):
                        if nearest_major+i not in minor_rows:
                            row = nearest_major+i
                            break
            except:
                pass
            configs = (35, 'nes')
        else:
            row = (len(major_rows)*10)+10
            while row in taken:
                row += 10
            # leave the first 10 rows reserved because I don't want to deal with them
            # the labels at the top are packed to row 1 and I don't want to offset
            # all my calculations by 1 because that's ugly

        e = tk.Entry(self, bd=1, width=configs[0])
        e.insert(0, item['search'])
        e.grid(row=row, column=0, sticky=configs[1])
        if focus:
            e.focus()
        row = e.grid_info()['row']

        if not sub:
            f = tk.Entry(self, bd=1, width=int(configs[0]/2), name=f'labelr{row}c{1}')
            f.insert(0, item['label'])
            f.grid(row=row, column=1, sticky='nesw')

        a = 2
        ret = []
        for i in (item['from'], item['cc'], item['bcc'], item['subject'], item['body'], item['all_match'], item['exact_match']):
            cb = tk.Checkbutton(self, bd=0, name=f'checkbuttonr{row}c{a}')
            cb.variable = tk.BooleanVar()
            cb.config(variable = cb.variable)
            cb.grid(row=row, column=a, sticky='nesw')
            if i:
                cb.select()
            ret.append(cb)
            a+=1
        tk.Button(self, text='Delete', relief='groove', command=lambda:self.remove_row(row)).grid(row=row, column=a, sticky='nesw')

        if type(self.master) == ScrollableFrame:
            if all(row>=i for i in self.rows()):
                quick_thread(lambda:[time.sleep(0.1),self.master.yview_moveto(1)])

        return e, *ret
    def remove_row(self, row, update=True):
        try:
            r = self.get_row(row)
            for w in self.grid_slaves(row=row):
                w.grid_remove()
                w.grid_forget()
                w.destroy()

            if r!=False:
                if 'sub_filters' in r.keys():
                    for i in range(len(r['sub_filters'])):
                        self.remove_row(row+i+1, update=False)

            if update:
                self.update_colours()

        except tk.TclError:
            pass
    def add_row(self, value=None, sub=False):
        if value!=None:
            value = self._format_filter(value)
            self._create(value)
        else:
            try:
                candidates = []
                if sub:
                    nearest_major = self.focus_get()
                    if '!filtermanager.!' in str(nearest_major):
                        nearest_major = nearest_major.grid_info()['row']
                    else:
                        nearest_major = self.rows()[0]
                    nearest_major = nearest_major - (nearest_major % 10)
                    candidates = list(range(nearest_major+1, nearest_major+10))
                else:
                    for r in self.rows():
                        if r%10==0:
                            candidates.append(r)

                for r in candidates:
                    row = self.get_row(r)
                    if row!=False and row['search'] == '':
                        for w in self.grid_slaves(r):
                            if type(w)==tk.Entry and 'label' not in w._name:
                                w.focus()
                                return
                # if there are no un-filled entries then create one
                self._create(self._format_filter(None), focus=True, sub=sub)
            except IndexError:
                # if there are no un-filled entries then create one
                self._create(self._format_filter(None), focus=True, sub=sub)
        self.update_colours()
    def load_filters(self):
        for i in self.grid_slaves():
            if i not in self.top_bar:
                i.destroy()

        for i in get_settings()['filters']:
            self._create(self._format_filter(i))
            if 'sub_filters' in i.keys():
                for sub in i['sub_filters']:
                    self._create(self._format_filter(sub), sub=True)
        self.update_colours()
    def get_filters(self):
        config = []

        for row in self.rows():
            if row%10==0:
                setting = self.get_row(row)
                if setting!={} and not setting['search']=='':
                    config.append(self._format_filter(setting))
        return config
    def rows(self):
        rows = []
        for i in range(10, self.grid_size()[1]):
            if len(self.grid_slaves(row=i))>0:
                rows.append(i)
        return rows
    def get_row(self, row):
        names = ('from', 'cc', 'bcc', 'subject', 'body', 'all_match', 'exact_match')
        setting = {}
        if row<0:
            row = self.rows()[row]

        for widget in self.grid_slaves(row=row):
            if type(widget) == tk.Entry and 'label' not in widget._name:
                setting['search'] = widget.get()
                if widget.grid_info()['row']%10==0:
                    sub_filters = []
                    for i in range(1, 10):
                        tmp = self.get_row(row=widget.grid_info()['row']+i)
                        if tmp!=False and 'sub_filters' not in tmp.keys():
                            sub_filters.append(tmp)
                    setting['sub_filters'] = sub_filters
            elif type(widget) == tk.Entry and 'label' in widget._name:
                setting['label'] = widget.get()
            elif f'checkbutton' in widget._name:
                name = int(widget._name[-1])
                setting[names[name-2]] = widget.variable.get()

        if setting=={}:
            return False
        elif 'sub_filters' not in setting.keys():
            return self._format_filter(setting, sub=True)
        else:
            return self._format_filter(setting)
    def update_colours(self):
        a=0
        for i in range(10, self.grid_size()[1]):
            bg='white'
            if a%10==0 or a==0:
                if (a/10)%2==0 or a//10 == 1:
                    bg='#d9d9d9'
            elif a%2==0:
                bg = '#d9d9d9'

            if len(self.grid_slaves(row=i))>0:
                for w in self.grid_slaves(row=i):
                    if w['bg']!=bg:
                        w.config(bg=bg)
                        w.update()
                a+=1

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
        tk.Button(self.blocking_frame, text='Add blocking rule', command=lambda:[self.filter_manager.add_row(), tmp.children_bind_scroll()], relief='groove').pack(**dk)
        tk.Button(self.blocking_frame, text='Add blocking sub-rule', command=lambda:[self.filter_manager.add_row(sub=True),tmp.children_bind_scroll()], relief='groove').pack(**dk)

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

def scrollable_popup_yn(msg, title=''):
    class tmp_vars():
        yes = False
        no = False
    p = tk.Toplevel()
    p.title(title)
    s = ScrollableFrame(p)
    s.pack(side='top', fill='both', expand=True)
    if type(msg) == str:
        msg = [msg]
    for m in msg:
        tk.Label(s, text=m, anchor='w', justify='left').pack(side='top', fill='both', expand=True)
    tmp = tk.Frame(p)
    tmp.pack(side='bottom')

    vars = tmp_vars()
    tk.Button(tmp, text='Accept', command=lambda:setattr(vars, 'yes', True), height=3).pack(side='left')
    tk.Button(tmp, text='Deny', command=lambda:setattr(vars, 'no', True), height=3).pack(side='right')

    while vars.yes == False and vars.no == False:
        time.sleep(0.1)
    p.destroy()
    return vars.yes

if __name__=='__main__':
    global window
    window = Window()
    # see EmailBlocker.py for why we do this
    window.instance = window
    window.root.mainloop()