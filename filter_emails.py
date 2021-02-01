#coding: utf-8
import imaplib, re

'''
Simple script that delete emails from a given sender
params:
-username: Gmail username
-pw: gmail pw
-label: If you have a label that holds the emails, specify here
-sender: the target sender you want to delete
usage: python delete_emails.py username='giovaneliberato@gmail.com' pw='bla' label='e-commerce' sender='spam@some-ecommerce.com'
see http://stackoverflow.com/a/5366205 for mode details
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