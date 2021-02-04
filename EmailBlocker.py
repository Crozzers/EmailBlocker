import argparse, sys, os
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'packages'))
import filter_emails

os.environ['TCL_LIBRARY'] = os.path.join(os.path.dirname(__file__), 'tcl/tcl8.6')

__version__='0.5.0-dev'

if __name__=='__main__':
    if len(sys.argv)==1:
        import gui
        window = gui.Window()
        window.root.mainloop()
    else:
        parser = argparse.ArgumentParser(description='Deletes annoying emails from people you can\'t block')

        parser.add_argument('email', type=str, help='Your email address')
        parser.add_argument('password', type=str, help='Your password')
        parser.add_argument('sender', type=str, help='The email of the person you want to block')

        args = parser.parse_args()

        with filter_emails.Server() as server:
            print(f'Logging into GMAIL with user {args.email}')
            server.login(args.email, args.password)

            print('Selecting the inbox as the target')
            server.select_label('inbox')

            if ',' in args.sender:
                args.sender = args.sender.split(',')
            else:
                args.sender = [args.sender]
            while True:
                emails = []
                for sender in args.sender:
                    if sender!='' and filter_emails.email_valid(sender):
                        print(f'Searching inbox for emails from {sender}')
                        emails+=server.get_email_by_sender(sender)
                    else:
                        print(f'Skipped invalid email: {sender}')
                print(f'Found {len(emails)} email{"s" if len(emails)>1 else ""}')
                if emails==[]:
                    break

                for i in range(len(emails)):
                    print(f'Sending {len(emails)} email{"s" if len(emails)>1 else ""} to the bin ({i+1}/{len(emails)})')
                    server.delete_email(emails[i]['id'])

            print('Done!')