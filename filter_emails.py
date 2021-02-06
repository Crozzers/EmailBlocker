import imaplib, re
from email.parser import HeaderParser

'''
Created with inspiration from github user Giovane Liberato
https://gist.github.com/giovaneliberato/b3ebce305262888633c1
'''

class Server():
    TRASH = '\\Trash'
    def __init__(self, url='imap.gmail.com'):
        '''
        Initialize the server
        '''
        self.logged_in = False
        self.server = imaplib.IMAP4_SSL(url)
    def __enter__(self):
        return self
    def login(self, username, password):
        self.server.login(username, password)
        self.logged_in = True
    def select_label(self, label='inbox'):
        '''
        Select folder to search from
        '''
        self.server.select(label)
    def search(self, query, from_=False, cc=False, bcc=False, subject=False, body=False, all_match=True, exact_match=True):
        '''
        Searches the current label for emails matching the query
        Returns a list of email UIDs
        '''
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

        if all_match:
            lookup = f'({" ".join(lookup)})'
            _, result = self.server.search(None, lookup)
            result = result[0].split()
        else:
            result = []
            for l in lookup:
                _, tmp = self.server.search(None, l)
                result+=tmp[0].split()

        if not exact_match:
            return result

        filtered = []
        emails = self.get_emails_by_id(result)
        for e in emails:
            for i in ('from_', 'cc', 'bcc', 'subject', 'body'):
                # this bit here is just grabbing the variables associated with the above strings
                # which were passed as kwargs and then re-using it as the dict key
                # just coz I couldn't be bothered to type these 5 variable names twice
                # or to do a bunch of if/else statements
                if locals()[i]:
                    if query==e[i.replace('_','')]:
                        filtered.append(e['id'])
                        break

        return filtered
    def get_email_ids(self):
        '''
        Get the UID of every single email in that folder
        '''
        _, ids = self.server.search(None, 'all')
        return ids[0].split()
    def get_emails_by_id(self, id):
        '''
        Get info about an email via ID

        Args:
            id: can be UID or list of UIDs

        Returns:
            list: list of dicts
        '''
        if type(id)!=list:
            id = [id]

        emails = []
        for email_id in id:
            try:
                data = self.server.fetch(email_id, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)] RFC822)')
                parser = HeaderParser()
                head_data = parser.parsestr(data[1][0][1].decode())
                info = {
                    'id': email_id,
                    'from': head_data['from'],
                    'to': head_data['to'],
                    'cc': head_data['cc'],
                    'bcc': head_data['bcc'],
                    'date': head_data['date'],
                    'subject': head_data['subject']
                    }
                # requires some extra parsing to filter out the junk
                boundary = head_data.get_boundary()
                try:
                    body = head_data.get_payload(decode=True).replace('\r\n', '\n').split('--'+boundary)
                except TypeError:
                    body = head_data.get_payload().replace('\r\n', '\n').split('--'+boundary)
                while '' in body:
                    body.remove('')
                plaintext = None
                for section in body:
                    section = section.split('\n')
                    for line in section:
                        if line.startswith('Content-Type: text/plain;'):
                            plaintext = '\n'.join(i for i in section if not i.startswith(('Content-Type: ', 'Content-Transfer-Encoding: ')))
                            break
                    if plaintext!=None:
                        break
                info['body'] = plaintext
                emails.append(info)
            except:
                pass
        return emails
    def delete_email(self, email_id):
        if type(email_id)==dict and 'id' in email_id.keys():
            email_id = email_id['id']
        if type(email_id)!=bytes:
            raise TypeError('email must be bytes id')
        self.server.store(email_id, '+X-GM-LABELS', self.TRASH)
        self.server.expunge()
    def __exit__(self, *args,**kwargs):
        self.close()
    def close(self):
        if self.logged_in:
            self.server.close()
            self.server.logout()
        self.logged_in = False

def email_valid(email):
    return re.fullmatch(r'[^@]+@[^@]+\.[^@]+', email)