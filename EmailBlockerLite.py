import argparse, sys
import filter_emails

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Automatically deletes annoying emails from people you can\'t block')

    parser.add_argument('email', type=str, help='Your email address')
    parser.add_argument('password', type=str, help='Your password')
    parser.add_argument('sender', type=str, help='The email of the person you want to block')

    args = parser.parse_args()

    print(f'Logging into GMAIL with user {args.email}')
    connection_message, server = filter_emails.login(args.email, args.password)
    print(connection_message)

    print('Selecting the inbox as the target')
    filter_emails.select_label(server, 'inbox')

    if ',' in args.sender:
        args.sender = args.sender.split(',')
    else:
        args.sender = [args.sender]
    while True:
        email_ids = []
        for sender in args.sender:
            if sender!='' and filter_emails.email_valid(sender):
                print(f'Searching inbox for emails from {sender}')
                email_ids+=filter_emails.get_emails(server, sender)
            else:
                print(f'Skipped invalid email: {sender}')
        if email_ids==[]:
            break
        print(f'Found {len(email_ids)} email{"s" if len(email_ids)>1 else ""}')

        if len(email_ids)>0:
            for i in range(len(email_ids)):
                print(f'Sending {len(email_ids)} email{"s" if len(email_ids)>1 else ""} to the bin ({i+1}/{len(email_ids)})')
                filter_emails.move_email(server, email_ids[i], filter_emails.TRASH)

    print('Done!')