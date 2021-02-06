import argparse, sys, os, json
sys.path.append(os.path.dirname(__file__))
import imaplib, re
import filter_emails

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
        for i in (('search', ''), ('from', False), ('cc', False), ('bcc', False), ('subject', False), ('body', False), ('all_match', True), ('exact_match', True)):
            if i[0] not in filter.keys():
                filter[i[0]] = i[1]
            elif type(filter[i[0]])!=type(i[1]):
                raise TypeError(f'filter key "{i[0]}" contains invalid type {type(filter[i[0]])}, expected {type(i[1])}')
            else:
                pass
        filters.append(filter)
    config['filters'] = filters
    return config

__version__ = '0.5.0-dev'
__author__='Crozzers'

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Deletes annoying emails from people you can\'t block')

    parser.add_argument('-f', '--file', action='store_true', help='Load filter settings from stored settings.json file')
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


    with filter_emails.Server() as server:
        print(f'Logging into GMAIL with user {config["user_email"]}')
        try:
            server.login(config['user_email'], config['user_password'])
        except Exception as e:
            print(f'Failed to log in: {e}')
            sys.exit(1)


        print('Selecting the inbox as the target')
        server.select_label('inbox')

        email_ids = []
        for filter in config['filters']:
            print(f'Searching for emails that match "{filter["search"]}"')
            email_ids+=server.search(
                filter['search'],
                from_ = filter['from'],
                cc=filter['cc'],
                bcc=filter['bcc'],
                subject=filter['subject'],
                body=filter['body'],
                all_match=filter['all_match'],
                exact_match=filter['exact_match']
            )

        print(f'Found {len(email_ids)} email{"s" if len(email_ids)>1 or len(email_ids)==0 else ""}')

        if len(email_ids)>0:
            for i in range(len(email_ids)):
                print(f'Sending {len(email_ids)} email{"s" if len(email_ids)>1 else ""} to the bin ({i+1}/{len(email_ids)})')
                server.delete_email(email_ids[i])

        print('Done!')