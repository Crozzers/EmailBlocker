import imaplib, re
from email.parser import HeaderParser

'''
Created with inspiration from github user Giovane Liberato
https://gist.github.com/giovaneliberato/b3ebce305262888633c1
'''

class Server():
    TRASH = '\\Trash'
    def __init__(self, url='imap.gmail.com'):
        self.server = imaplib.IMAP4_SSL(url)
    def __enter__(self):
        return self
    def login(self, username, password):
        self.server.login(username, password)
    def select_label(self, label='inbox'):
        self.server.select(label)
    def get_email_ids_by_sender(self, sender):
        if not email_valid(sender):
            raise ValueError('Invalid email address')
        _, email_ids = self.server.search(None, f'(FROM "{sender}")')
        email_ids = email_ids[0].split()
        return email_ids
    def get_email_by_sender(self, sender):
        ids = self.get_email_ids_by_sender(sender)
        emails = []
        for email_id in ids:
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
        self.server.close()

def email_valid(email):
    return re.fullmatch(r'[^@]+@[^@]+\.[^@]+', email)