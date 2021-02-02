import imaplib, re

'''
Created with inspiration from github user Giovane Liberato
https://gist.github.com/giovaneliberato/b3ebce305262888633c1
'''

def email_valid(email):
    return re.fullmatch(r'[^@]+@[^@]+\.[^@]+', email)

def login(username, password):
    server = imaplib.IMAP4_SSL('imap.gmail.com')
    connection_message = server.login(username, password)
    return connection_message, server

def select_label(server, label = 'inbox'):
    server.select(label)

def get_emails(server, sender):
    result_status, email_ids = server.search(None, f'(FROM "{sender}")')
    email_ids = email_ids[0].split()
    return email_ids

def move_email(server, email_id, destination):
    server.store(email_id, '+X-GM-LABELS', destination)
    server.expunge()

# define some constants
TRASH = '\\Trash'