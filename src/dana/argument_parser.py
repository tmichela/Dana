from argparse import ArgumentParser, RawDescriptionHelpFormatter
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
parser_meeting = subparsers.add_parser(
    'meeting', help='Manage meeting reminders', formatter_class=RawDescriptionHelpFormatter)

meeting_subparsers = parser_meeting.add_subparsers(dest='meeting_command', help='Meeting command')
parser_meeting_add = meeting_subparsers.add_parser('add', help='Add a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_remove = meeting_subparsers.add_parser('remove', help='Remove a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_list = meeting_subparsers.add_parser('list', help='List all meetings', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_info = meeting_subparsers.add_parser('info', help='Get info about a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_edit = meeting_subparsers.add_parser('edit', help='Edit a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_reschedule = meeting_subparsers.add_parser('reschedule', help='Change the scheduled time of a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_add_participant = meeting_subparsers.add_parser('add_participant', help='Add a participant to a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_remove_participant = meeting_subparsers.add_parser('remove_participant', help='Remove a participant from a meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_pause = meeting_subparsers.add_parser('pause', help='Pause meeting', formatter_class=RawDescriptionHelpFormatter)
parser_meeting_resume = meeting_subparsers.add_parser('resume', help='Resume a paused meeting', formatter_class=RawDescriptionHelpFormatter)

parser_meeting_add.add_argument('name', nargs='+', help='Meeting name')
parser_meeting_add.add_argument('--description', '-d', type=str, nargs='+', help='Description')
parser_meeting_add.add_argument('--start', '-s', type=str, required=True, help='Start time')
parser_meeting_add.add_argument('--end', '-e', type=str, help='End time')
parser_meeting_add.add_argument('--url', '-u', type=str, help='Room url')
parser_meeting_add.add_argument('--participants', '-p', nargs='+', required=True, help='Participants')
parser_meeting_add.add_argument('--optional', '-o', nargs='+', help='Optional participants')
sched_help=('Schedule for meeting repetition. Must contain week days and time of day, e.g. '
          '"wed 8:00", "mon,tue,fri 10:00" or "tue-sat 12:00". Add an additional "/n" after '
          'the week days to repeat the schedule every n week. e.g. "mon-fri/3 10:00" will '
          'schedule a meeting every day from Monday through Friday at 10:00 every 3 weeks. '
          'Days and time must be separated by a empty space')
parser_meeting_add.add_argument('--schedule', '-sc', nargs=2, action='append', metavar=('DAYS', 'HH:MM'), help=sched_help)

parser_meeting_remove.add_argument('name', nargs='+', help='Name of the meeting to remove')
parser_meeting_info.add_argument('name', nargs='+', help='Name of the meeting to get info about')
parser_meeting_edit.add_argument('name', nargs='+', help='Name of the meeting to edit')
parser_meeting_edit.add_argument('--arg', '-a', action='append', nargs=2, metavar=('KEY', 'VALUE'), required=True, help='key/value of the property to change')

parser_meeting_reschedule.add_argument('name', help='Name of the meeting to change the schedule for')
parser_meeting_reschedule.add_argument('--schedule', '-sc', nargs=2, action='append', metavar=('DAYS', 'HH:MM'), required=True, help=sched_help)

parser_meeting_add_participant.add_argument('name', nargs='+', help='Name of the meeting')
parser_meeting_add_participant.add_argument('--participants', '-p', nargs='+', help='Participant to add')
parser_meeting_add_participant.add_argument('--optional', '-o', action='store_true', default=False, help='Participants are optional')
parser_meeting_remove_participant.add_argument('name', nargs='+', help='Name of the meeting')
parser_meeting_remove_participant.add_argument('--participants', '-p', nargs='+', help='Participant to remove')

parser_meeting_pause.add_argument('name', nargs='+', help='Name of the meeting')
parser_meeting_resume.add_argument('name', nargs='+', help='Name of the meeting')


# calendar subcommand
parser_meeting = subparsers.add_parser(
    'calendar', help='Show calendar', formatter_class=RawDescriptionHelpFormatter)
parser_meeting.add_argument('year', type=int, default=None, help='Year. Default value is the current year.')
parser_meeting.add_argument('month', type=int, default=None, help='Month. Default value is the current month.')
parser_meeting.add_argument('--start_sunday', default=False, action='store_true', help='Start weeks from Sunday.')


# reminders subcommand
# TODO

# chat subcommand
# TODO


def parse_arguments(args):
    if not args or args[0].lower() == 'help':
        return None, parser.format_help()

    try:
        out = StringIO()
        with redirect_stdout(out):
            args = parser.parse_args(args)
    except Exception as ex:
        return None, str(ex)
    else:
        return args, out.getvalue()


def print_help(sub_command=None):
    if sub_command is None:
        return parser.format_help()
    return parser.parse_args([f'sub_command', '--help'])
