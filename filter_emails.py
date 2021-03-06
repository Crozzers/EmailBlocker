import imaplib
import re
import base64
from email.parser import HeaderParser

'''
Created with inspiration from github user Giovane Liberato
https://gist.github.com/giovaneliberato/b3ebce305262888633c1
'''


class Server():
    def __init__(self, username=None, password=None, url='imap.gmail.com'):
        '''
        Initialize the server
        If user and password are specified then `self.login` is called

        Args:
            username (str): the email to sign in as
            password (str): the password to sign in with
            url (str): the url of the email server (only imap.gmail.com is supported)
        '''
        self.logged_in = False
        self.labels = None
        self.server = imaplib.IMAP4_SSL(url)
        if username is not None and password is not None:
            self.login(username, password)

    def __enter__(self, username=None, password=None, label='inbox'):
        if username is not None and password is not None:
            self.login(username, password)
            self.select_label(label)
        return self

    def login(self, username, password):
        '''
        Logs a user into the server

        Args:
            username (str): the email to log in as
            password (str): the password to log in with
        '''
        self.server.login(username, password)
        self.logged_in = True

    def select_label(self, label='inbox'):
        '''
        Select folder to search from

        Args:
            label (str): the label to select
        '''
        out = self.server.select(label)
        if out[0] == 'OK':
            return

        all_labels = self.get_labels()
        for k in all_labels.keys():
            if k.lower() == label.lower():
                out = self.server.select(all_labels[k])
                if out[0] == 'OK':
                    return

        raise Exception(out[1].decode())

    def get_labels(self):
        '''
        Gets all the available labels in this users email account

        Returns:
            dict: keys are the "name" of the label (eg: Starred)
                values are the label itself (eg: [Gmail]/Starred)
        '''
        if self.labels is not None:
            return self.labels
        else:
            raw = self.server.list()[1]
            labels = {}
            for r in raw:
                v = r.decode().replace('"', '').split('/', 1)[1].lstrip(' ')
                if v == '[Gmail]':
                    continue
                if v.startswith('[Gmail]/'):
                    k = v.replace('[Gmail]/', '')
                else:
                    k = v
                labels[k] = v
            self.labels = labels
        return labels

    def search(self, query, from_=False, cc=False, bcc=False, subject=False, body=False, all_match=True, exact_match=True, sub_filters=[], **kwargs):
        '''
        Searches the current label for emails matching the query
        If kwargs isn't empty and contains the key 'from' then we override the from_ kwarg with that value.
        If it has the key 'search' then we override query with that
        Mostly just to make it more convenient to dump kwargs into this function via dict unpacking

        Args:
            query (str): what you are searching for
            from_ (bool): check if the sender of the email matches the query
            cc (bool): check if the query matches who was CC'd into the email
            bcc (bool): check if the query matches who was BCC'd into the email
            subject (bool): check if the query matches the subject of the email
            body (bool): check if the query matches the subject of the email
            all_match (bool): whether all selected fields must match the query
            exact_match (bool): whether each field must match the query exactly or not
            sub_filters (list): sub-filters to also match against.
                                Each must be a dict with keys corresponding to this
                                function's kwargs
            kwargs (dict): used to override some other kwargs

        Returns:
            list: list of email UIDs

        Raises:
            Exception: if a valid search query could not be constructed
        '''
        if kwargs != {}:
            if 'from' in kwargs.keys():
                from_ = kwargs['from']
            if 'search' in kwargs.keys():
                query = kwargs['search']

        lookup = []
        if from_:
            lookup.append(f'FROM "{query}"')
        if cc:
            lookup.append(f'CC "{query}"')
        if bcc:
            lookup.append(f'BCC "{query}"')
        if subject:
            lookup.append(f'SUBJECT "{query}"')
        if body:
            lookup.append(f'BODY "{query}"')

        if lookup == []:
            raise Exception('Could not create valid search query from your arguments')

        if all_match:
            lookup = f'({" ".join(lookup)})'
            _, result = self.server.search(None, lookup)
            result = result[0].split()
        else:
            result = []
            for look in lookup:
                _, tmp = self.server.search(None, look)
                result += tmp[0].split()

        if sub_filters == []:
            full_result = result
        else:
            full_result = []
            sub_searches = []
            for sub in sub_filters:
                sub_searches.append(self.search(query, **sub))
            for item in result:
                if all(item in sub for sub in sub_searches):
                    full_result.append(item)

        if not exact_match:
            return full_result

        filtered = []
        emails = self.get_emails_by_id(full_result)
        for e in emails:
            for i in ('from_', 'cc', 'bcc', 'subject', 'body'):
                # this bit here is just grabbing the variables associated with the above strings
                # which were passed as kwargs and then re-using it as the dict key
                # just coz I couldn't be bothered to type these 5 variable names twice
                # or to do a bunch of if/else statements
                if locals()[i]:
                    if i == 'from_':
                        tmp = e[i.replace('_', '')]
                        if query in (tmp['raw'], tmp['email']):
                            filtered.append(e['id'])
                    if query == e[i.replace('_', '')]:
                        filtered.append(e['id'])
                        break

        return filtered

    def get_email_ids(self):
        '''
        Get the UID of every single email in the currently selected label

        Returns:
            list: list of email UIDs
        '''
        _, ids = self.server.search(None, 'all')
        return ids[0].split()

    def __get_emails_by_id(self, id):
        '''
        Internal function to gather info about an email.
        Do not call. Call `self.get_emails_by_id` instead
        '''
        if type(id) != list:
            id = [id]

        for email_id in id:
            try:
                data = self.server.fetch(email_id, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)] RFC822)')
                parser = HeaderParser()
                head_data = parser.parsestr(data[1][0][1].decode())
                info = {
                    'id': email_id,
                    'from': {
                        'raw': head_data['from'],
                        'email': None,
                        'name': None
                    },
                    'to': head_data['to'],
                    'cc': head_data['cc'],
                    'bcc': head_data['bcc'],
                    'date': head_data['date'],
                    'subject': head_data.get('subject')
                }
                if '?utf-8?B?' in info['subject']:
                    # manually decode this because all email protocols are garbage
                    try:
                        subs = []
                        for i in info['subject'].split(' '):
                            if i != '':
                                subs.append(
                                    base64.b64decode(i.replace('?utf-8?B?', '')).decode()
                                )
                        info['subject'] = ''.join(subs)
                    except Exception:
                        pass
                # the "from" of an email is usually returned as "John Smith <johnsmith@gmail.com>"
                # so let's parse that real quick
                from_ = info['from']['raw']
                if email_valid(from_):
                    info['from']['email'] = from_
                else:
                    from_ = from_.split(' ')
                    if from_[-1].startswith('<') and from_[-1].endswith('>'):
                        if email_valid(from_[-1][1:-1]):
                            info['from']['email'] = from_[-1][1:-1]
                            info['from']['name'] = ' '.join(from_[:-1])

                # the body requires some extra parsing to filter out the junk
                boundary = head_data.get_boundary()
                try:
                    body = head_data.get_payload(decode=True).replace('\r\n', '\n').split('--' + boundary)
                except TypeError:
                    body = head_data.get_payload().replace('\r\n', '\n').split('--' + boundary)
                while '' in body:
                    body.remove('')
                plaintext = None
                for section in body:
                    section = section.split('\n')
                    for line in section:
                        if line.startswith('Content-Type: text/plain;'):
                            plaintext = '\n'.join(
                                i for i in section if not i.startswith(
                                    ('Content-Type: ', 'Content-Transfer-Encoding: ')
                                )
                            )
                            break
                    if plaintext is not None:
                        break
                info['body'] = plaintext
                yield info
            except Exception:
                pass

    def get_emails_by_id(self, id, generator=False):
        '''
        Get info about an email via ID

        Args:
            id (bytes): can be email UID or list of email UIDs
            generator (bool): whether to generate these or to return complete list

        Returns:
            list: list of dicts
        '''
        if generator:
            return self.__get_emails_by_id(id)
        else:
            return [i for i in self.__get_emails_by_id(id)]

    def delete_email(self, email_id):
        '''
        Deletes an email

        Args:
            email_id (bytes): an email UID (same type as returned by `self.get_email_ids`)
        '''
        if type(email_id) == dict and 'id' in email_id.keys():
            email_id = email_id['id']
        if type(email_id) != bytes:
            raise TypeError('email must be bytes id')
        self.server.store(email_id, '+X-GM-LABELS', '\\Trash')
        self.server.expunge()

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        '''
        Closes the server and logs the user out
        '''
        if self.logged_in:
            try:
                self.server.close()
            except Exception:
                pass
            self.server.logout()
        self.logged_in = False


def email_valid(email):
    '''
    Checks whether an email is valid using regex

    Args:
        email (str): the email address to validate

    Returns:
        bool
    '''
    return re.fullmatch(EMAIL_REGEX, email)


EMAIL_REGEX = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
