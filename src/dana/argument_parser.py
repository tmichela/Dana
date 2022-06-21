from argparse import ArgumentParser, Action, RawDescriptionHelpFormatter
from collections import namedtuple
from io import StringIO
from contextlib import redirect_stdout


class DanaParser(ArgumentParser):

    def error(self, message):
        print(message)

    def exit(self, status=0, message=None):
        if status:
            print(message)


parser = DanaParser(
    prog='Dana',
    description='Zulip bot for the Data Analysis Group at the EuXFEL',
    exit_on_error=False)
subparsers = parser.add_subparsers(dest='command', help='Command')

# meetings subcommand
Repeat = namedtuple('Repeat', ['number', 'interval'])
class ValidateRepeat(Action):
    def __init__(self, option_strings, dest, default=None, nargs=None, help=None, metavar=None):
        super().__init__(option_strings, dest, nargs=nargs, default=default, help=help, metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        number, interval = values
        number = int(number)
        interval = interval.lower()
        granularity = ('seconds', 'minutes', 'hours', 'days', 'weeks', 'months')
        if interval not in granularity:
            raise ValueError(f'Invalid granularity. Allowed are: {granularity}')
        setattr(namespace, self.dest, Repeat(number, interval))

parser_meeting = subparsers.add_parser(
    'meeting', help='Manage meeting reminders', formatter_class=RawDescriptionHelpFormatter)

meeting_subparsers = parser_meeting.add_subparsers(dest='meeting_command', help='Meeting command')
parser_meeting_add = meeting_subparsers.add_parser('add', help='Add a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_remove = meeting_subparsers.add_parser('remove', help='Remove a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_list = meeting_subparsers.add_parser('list', help='List all meetings', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_info = meeting_subparsers.add_parser('info', help='Get info about a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_edit = meeting_subparsers.add_parser('edit', help='Edit a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_add_participant = meeting_subparsers.add_parser('add_participant', help='Add a participant to a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_remove_participant = meeting_subparsers.add_parser('remove_participant', help='Remove a participant from a meeting', formatter_class=RawDescriptionHelpFormatter)

parser_meeting_add.add_argument('name', nargs='+', help='Meeting name')
parser_meeting_add.add_argument('--description', '-d', type=str, nargs='+', help='Description')
parser_meeting_add.add_argument('--start', '-s', type=str, required=True, help='Start time')
parser_meeting_add.add_argument('--end', '-e', type=str, help='End time')
parser_meeting_add.add_argument('--url', '-u', type=str, help='Room url')
parser_meeting_add.add_argument('--participants', '-p', nargs='+', required=True, help='Participants')
parser_meeting_add.add_argument(
    '--repeat', '-r', nargs=2, metavar=('NUM', 'INTERVAL'), action=ValidateRepeat,
    default=Repeat(7, 'days'), help='Time interval between meeting instances. Default: 7 days')

parser_meeting_remove.add_argument('name', nargs='+', help='Name of the meeting to remove')
parser_meeting_info.add_argument('name', nargs='+', help='Name of the meeting to get info about')
parser_meeting_edit.add_argument('name', nargs='+', help='Name of the meeting to edit')
parser_meeting_edit.add_argument('--arg', '-a', action='append', nargs=2, metavar=('KEY', 'VALUE'), required=True, help='key/value of the property to change')

parser_meeting_add_participant.add_argument('name', nargs='+', help='Name of the meeting')
parser_meeting_add_participant.add_argument('--participants', '-p', nargs='+', help='Participant to add')
parser_meeting_remove_participant.add_argument('name', nargs='+', help='Name of the meeting')
parser_meeting_remove_participant.add_argument('--participants', '-p', nargs='+', help='Participant to remove')

# reminders subcommand
# TODO

# chat subcommand
# TODO


def parse_arguments(args):
    if args[0].lower() == 'help':
        return None, parser.format_help()

    try:
        out = StringIO()
        with redirect_stdout(out):
            args = parser.parse_args(args)
    except Exception as ex:
        return None, str(ex)
    else:
        return args, out.getvalue()
