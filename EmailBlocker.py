import sys, os
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'packages'))
import argparse, threading, json, shutil, zipfile
import urllib.request
from packaging import version
from time import sleep
import filter_emails

def output(item, *args, **kwargs):
    global window
    try:
        if 'window' in globals():
            globals()['window'].output(item, *args, **kwargs)
        else:
            gui.Window.instance.output(item, *args, **kwargs)
    except:
        print(item)

def get_settings():
    if 'emailblocker_settings' in globals().keys():
        return globals()['emailblocker_settings']
    else:
        try:
            with open(os.path.join(os.path.dirname(__file__), 'settings.json'), 'r', encoding='utf-8') as f:
                settings = json.load(f)
            # some compatibility for older settings files
            if 'filters' not in settings.keys():
                settings['filters'] = []
            if 'blocked_emails' in settings.keys():
                for email in settings['blocked_emails']:
                    settings['filters'].append(
                        {
                            'search': email,
                            'from': True,
                            'cc': False,
                            'bcc': False,
                            'subject': False,
                            'body': False,
                            'all_match': True,
                            'exact_match': True
                        }
                    )
                del(settings['blocked_emails'])
        except:
            settings = {
                'user_email': '',
                'user_password': '',
                'load_settings_on_launch': True,
                'filters': []
            }
        globals()['emailblocker_settings'] = settings
        return settings

def set_settings(settings):
    globals()['emailblocker_settings'] = settings

def save_settings(settings=get_settings(), file=os.path.join(os.path.dirname(__file__), 'settings.json')):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)
    globals()['emailblocker_settings'] = settings

def quick_thread(target, *args, autostart=True, **kwargs):
    t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    if autostart:
        t.start()
    return t

def makeHTTPRequest(url):
    try:
        with urllib.request.urlopen(url) as url:
            http=url.getcode()
            try:
                data=url.read().decode()
            except:
                data=None
        return http,data
    except urllib.error.URLError:
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

class StartupTask:
    pjoin = os.path.join
    isdir = os.path.isdir
    isfile = os.path.isfile
    pydir = os.path.dirname(sys.executable)
    appdata_dir = pjoin(os.path.expanduser('~'), 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/')
    startup_dir = pjoin(appdata_dir, 'Startup').replace('\\','/')
    appdata_dir = pjoin(appdata_dir, 'EmailBlockerLite').replace('\\','/')
    basedir = os.path.dirname(__file__)
    def create():
        appdata_dir = StartupTask.appdata_dir
        startup_dir = StartupTask.startup_dir
        pjoin = StartupTask.pjoin
        isdir = StartupTask.isdir
        isfile = StartupTask.isfile
        pydir = StartupTask.pydir
        basedir = StartupTask.basedir

        if not isfile(pjoin(os.path.dirname(__file__), 'EmailBlockerLite.py')):
            output('Cannot create startup task: cannot find EmailBlockerLite.py', 'red')
            return

        try:
            config = get_settings()
            if not filter_emails.email_valid(config['user_email']):
                output('Cannot create startup task: Invalid email address', 'red')
                return
            if config['user_password']=='':
                output('Cannot create startup task: Invalid password', 'red')
                return

            output('Removing old startup task')
            if isdir(appdata_dir):
                shutil.rmtree(appdata_dir)
            output('Copying Python interpreter to AppData folder')
            os.mkdir(appdata_dir)
            shutil.copytree(pydir, pjoin(appdata_dir, 'py_interp'))

            output('Copying EmailBlockerLite to AppData folder')
            shutil.copyfile(pjoin(basedir, 'EmailBlockerLite.py'), pjoin(appdata_dir, 'EmailBlockerLite.py'))
            shutil.copyfile(pjoin(basedir, 'filter_emails.py'), pjoin(appdata_dir, 'filter_emails.py'))
            save_settings(config, file=os.path.join(appdata_dir, 'settings.json'))

            output('Writing batch file in shell:startup dir')
            paths = [pjoin(appdata_dir, "py_interp/python.exe"), pjoin(appdata_dir, "EmailBlockerLite.py")]
            paths = [i.replace('\\','/') for i in paths]
            with open(pjoin(startup_dir, 'EmailBlocker.bat'), 'w', encoding='utf-8') as f:
                f.write(
                    f'@echo off\nstart "EmailBlocker" "{paths[0]}" "{paths[1]}" -f'
                )
            output('Startup task created!', 'green')
        except Exception as e:
            import traceback
            traceback.print_exc()
            output(f'Failed to create startup task: {e}', 'red')
    def destroy():
        appdata_dir = StartupTask.appdata_dir
        startup_dir = StartupTask.startup_dir
        pjoin = StartupTask.pjoin
        isdir = StartupTask.isdir
        isfile = StartupTask.isfile

        try:
            if isdir(appdata_dir):
                shutil.rmtree(appdata_dir)
            if isfile(pjoin(startup_dir, 'EmailBlocker.bat')):
                os.remove(pjoin(startup_dir, 'EmailBlocker.bat'))
            output('Startup tasks removed!', 'green')
        except Exception as e:
            output(f'Failed to remove startup task: {e}')
    def repair():
        appdata_dir = StartupTask.appdata_dir
        startup_dir = StartupTask.startup_dir
        pjoin = StartupTask.pjoin
        isdir = StartupTask.isdir
        isfile = StartupTask.isfile

        try:
            if isdir(appdata_dir) and isfile(pjoin(startup_dir, 'EmailBlocker.bat')):
                ver = None
                with open(pjoin(appdata_dir, 'EmailBlockerLite.py'), 'r', encoding='utf-8') as f:
                    for line in f.readlines():
                        if line.replace(' ','').startswith('__version__='):
                            ver = version.Version(line.replace(' ','').replace('__version__=', '').replace('\'', ''))
                            break
                if ver==None:
                    output('Failed to update startup tasks: Could not detect version of the task', 'orange')
                elif ver<version.Version(__version__):
                    output('Updating startup tasks')
                    # remove startup tasks
                    StartupTask.destroy()
                    # add them back
                    StartupTask.create()
                    output('Startup tasks updated', 'green')
            elif isdir(appdata_dir) or isfile(pjoin(startup_dir, 'EmailBlocker.bat')):
                # if only one is detected then it's likely that the other was deleted
                # or that it's a startup task from a different program
                # if the latter is the case we really do NOT want to go and muck that up
                # so we ask the user what to do so if something goes wrong we can blame them :)
                output('Invalid startup tasks detected', 'orange')
                try:
                    msg_box = gui.messagebox.askyesno(
                        title='Invalid startup tasks',
                        message='An invalid startup task was detected. Would you like to repair it?'
                    )
                except:
                    while True:
                        inp = input('An invalid startup task was detected. Would you like to repair it? (y/n)')
                        if inp.lower()=='y':
                            msg_box = True
                            break
                        elif inp.lower()=='n':
                            msg_box = False
                            break
                        else:
                            print('Invalid respone\n')
                if msg_box:
                    # remove startup tasks
                    StartupTask.destroy()
                    # add them back
                    StartupTask.create()
                    output('Startup task repaired', 'green')

        except Exception as e:
            output(f'Failed to update startup tasks: {e}', 'red')

def run():
    try:
        config = get_settings()

        if not filter_emails.email_valid(config['user_email']):
            output(f'Cannot filter emails: Invalid email address', 'red')
            return
        if config['user_password']=='':
            output(f'Cannot filter emails: Invalid password', 'red')
            return

        with filter_emails.Server() as server:
            output(f'Logging into GMAIL with user {config["user_email"]}')
            try:
                server.login(config['user_email'], config['user_password'])
            except Exception as e:
                output(f'Failed to log in: {e}', 'red')
                return

            output(f'Selecting inbox')
            server.select_label('inbox')

            email_ids = []
            for filter in config['filters']:
                output(f'Searching for emails that match "{filter["search"]}"')
                email_ids+=server.search(
                    filter['search'], **filter
                )

            output(f'Found {len(email_ids)} email{"s" if len(email_ids)>1 or len(email_ids)==0 else ""}')

            if len(email_ids)>0:
                for i in range(len(email_ids)):
                    output(f'Sending {len(email_ids)} email{"s" if len(email_ids)>1 else ""} to the bin ({i+1}/{len(email_ids)})')
                    server.delete_email(email_ids[i])

        output(f'Done! Removed {len(email_ids)} email{"s" if len(email_ids)>1 or len(email_ids)==0 else ""}', 'green')
    except Exception as e:
        output(f'Failed: {e}', 'red')

def check_for_update():
    output('Checking')
    url = 'https://github.com/Crozzers/EmailBlocker/blob/master/EmailBlocker.py?raw=true'
    ret = makeHTTPRequest(url)
    if ret==False:
        output('Error: Failed to reach GitHub servers', 'red')
    else:
        http, data = ret
        if http!=200:
            output(f'Error: GitHub servers returned code: {http}', 'red')
        else:
            data = data.split('\n')
            ver = None
            for line in data:
                if line.replace(' ','').startswith('__version__='):
                    ver = line.replace(' ','').replace('__version__=', '').replace('\'','')
                    break
            if ver==None:
                output('Failed to detect latest version', 'red')
            else:
                if version.Version(ver)>version.Version(__version__):
                    try:
                        msg_box = gui.messagebox.askyesno(
                            title='Update Available',
                            message='Would you like to download and install the latest update?'
                        )
                    except:
                        while True:
                            inp = input('Would you like to download and install the latest update? (y/n)')
                            if inp.lower()=='y':
                                msg_box = True
                                break
                            elif inp.lower()=='n':
                                msg_box = False
                                break
                            else:
                                print('Invalid respone\n')
                    if msg_box==True:
                        try:
                            pjoin = os.path.join
                            basedir = basedir = os.path.dirname(__file__)
                            dest = pjoin(basedir, f'EmailBlocker-{ver}.zip')
                            # start the download while we deal with any old downloads kicking about
                            downloader = Download('https://github.com/Crozzers/EmailBlocker/archive/master.zip', dest)
                            downloader.download()

                            def unzip(downloader, dest):
                                while not downloader.finished():
                                    sleep(1)
                                sleep(1)
                                with zipfile.ZipFile(dest) as f:
                                    f.extractall(basedir)

                            output('Moving old update files')
                            if os.path.isdir('EmailBlocker-master') or os.path.isfile('EmailBlocker-master'):
                                os.rename('EmailBlocker-master', 'EmailBlocker-master-old')

                            # unzip in the background while we deal with removing all the old files
                            unzip_thread = quick_thread(unzip, downloader, dest)

                            output('Removing old update files')
                            if os.path.isdir('EmailBlocker-master-old'):
                                shutil.rmtree('EmailBlocker-master-old')
                            elif os.path.isfile('EmailBlocker-master-old'):
                                os.remove('EmailBlocker-master-old')

                            while not downloader.started():
                                output('Waiting for download to start')
                                sleep(1)
                            while not downloader.finished():
                                tmp = downloader.progress()
                                if downloader.length!=None:
                                    output(f'Downloading update ({tmp[1]}/{conv_file_size(downloader.length)})')
                                sleep(0.05)
                            sleep(1)

                            output('Unzipping update')
                            while unzip_thread.is_alive():
                                sleep(1)
                            os.remove(dest)

                            up_dir = pjoin(basedir, 'EmailBlocker-master')
                            for item in os.listdir(up_dir):
                                src = pjoin(up_dir, item)
                                dst = pjoin(basedir, item)
                                # only do files because the python embed directory and TCL library shouldn't need to be updated
                                if os.path.isfile(src) :
                                    output(f'Updating {item}')
                                    if os.path.isfile(dst):
                                        os.remove(dst)
                                    shutil.copyfile(src, dst)

                            output('Update completed! Please restart the program', 'green')
                        except Exception as e:
                            output(f'Failed to download update: {e}', 'red')
                else:
                    output('No updates are available')

def validate_filter(filter: dict, sub=False):
    for i in (('search', ''), ('from', False), ('cc', False), ('bcc', False), ('subject', False), ('body', False), ('all_match', True), ('exact_match', True)):
        if i[0] not in filter.keys():
            filter[i[0]] = i[1]
        elif type(filter[i[0]])!=type(i[1]):
            raise TypeError(f'filter key "{i[0]}" contains invalid type {type(filter[i[0]])}, expected {type(i[1])}')
        else:
            pass
    if sub:
        # only allow the sub-filtering to go 1 level deep
        if 'sub_filters' in filter.keys():
            del(filter['sub_filters'])
    else:
        if 'sub_filters' not in filter.keys() or type(filter['sub_filters'])!=list:
            filter['sub_filters'] = []
        else:
            sub_filters = []
            for sub_filter in filter['sub_filters']:
                sub_filters.append(validate_filter(sub_filter, sub=True))
            filter['sub_filters'] = sub_filters
    return filter

def validate_config(config:dict):
    for i in ('user_email', 'user_password', 'filters'):
        if i not in config.keys():
            raise Exception(f'Invalid configuration. Missing key: {i}')
    if not filter_emails.email_valid(config['user_email']):
        raise ValueError('Invalid user email')
    if config['user_password']=='':
        raise ValueError('Invalid password')
    filters = []
    for filter in config['filters']:
        filters.append(validate_filter(filter))
    config['filters'] = filters
    return config

os.environ['TCL_LIBRARY'] = os.path.join(os.path.dirname(__file__), 'tcl/tcl8.6')
__version__='0.6.0-dev'

# import this here once eveything is set up
import gui

if __name__=='__main__':
    if len(sys.argv)==1:
        global window
        window = gui.Window()
        # we do this because the global variable dissapears
        # I don't know where, I don't know how. It just does
        gui.Window.instance = window
        window.root.mainloop()
    else:
        parser = argparse.ArgumentParser(description='Deletes annoying emails from people you can\'t block')

        parser.add_argument('-f', '--file', action='store_true', help='Load filter settings from stored settings.json file (If specified all other args are ignored)')
        parser.add_argument('--email', required=False, type=str, help='Your email address')
        parser.add_argument('--password', required=False, type=str, help='Your password')
        parser.add_argument('--filter', required=False, type=str, help='The string to filter out (seperate multiple values with commas)')
        parser.add_argument('--sender', action='store_true', help='Filter by sender')
        parser.add_argument('--cc', action='store_true', help='Filter by CC')
        parser.add_argument('--bcc', action='store_true', help='Filter by BCC')
        parser.add_argument('--subject', action='store_true', help='Filter by subject')
        parser.add_argument('--body', action='store_true', help='Filter by contents of body')
        parser.add_argument('--no-exact-match', action='store_true', help='Filter if the field contains the search term even if the two don\'t completely match')
        parser.add_argument('--no-all-match', action='store_true', help='The query doesn\'t have to appear in ALL specified fields, just one of them')

        args = parser.parse_args()

        if args.file:
            try:
                with open(os.path.join(os.path.dirname(__file__), 'settings.json'), 'r', encoding='utf-8') as f:
                    config = validate_config(json.load(f))
            except Exception as e:
                print(f'Failed to load settings.json: {e}')
                sys.exit(1)
        else:
            if any(getattr(args, i)==None for i in ('email', 'password', 'filter')):
                print('--email, --password and --filter arguments are required')
                sys.exit(1)
            elif all(getattr(args, i)==False for i in ('sender', 'cc', 'bcc', 'subject', 'body')):
                print('At least one category to filter by is required')
                sys.exit(1)
            else:
                config = {
                    'user_email': args.email,
                    'user_password': args.password,
                    'filters': []
                }
                filters = []
                for i in args.filter.split(','):
                    config['filters'].append(
                        {
                            'search': i,
                            'from': args.sender,
                            'cc': args.cc,
                            'bcc': args.bcc,
                            'subject': args.subject,
                            'body': args.body,
                            'all_match': not args.no_all_match, # we do NOT args.no_all_match because the default choice is "use ALL matches" and if "not all matches" is True, we need to invert it
                            'exact_match': not args.no_exact_match # same here
                        }
                    )
                try:
                    config = validate_config(config)
                except Exception as e:
                    print(f'Failed to parse config: {e}')
                    sys.exit(1)
        set_settings(config)
        run()