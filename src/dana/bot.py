from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from argument_parser import parse_arguments, print_help
from commands.meetings import MeetingBot
from commands.calendar import make_calendar
from commands.pick import pick_user

# key in the zulip cache where meeting information is stored
# TODO make it configurable from an env variable or a configuration file
CACHE_PATH = 'meeting-1'


class Dana:
    """Dana is the Zulip bot, used by the Data Analysis group at the EuXFEL
    """

    def initialize(self, bot_handler):
        self.meetings = MeetingBot(bot_handler, CACHE_PATH)

    def handle_message(self, message, bot_handler):
        print(message)
        args_list = message['content'].split()
        
        if not args_list:
            bot_handler.send_reply(message, print_help())
            return

        args, output = parse_arguments(args_list)

        if output:
            bot_handler.send_reply(message, f'```text\n{output}\n```')
            return

        if args is None:
            print(output)
            bot_handler.send_reply(message, print_help())
            return

        if args.command == 'meeting' and args.meeting_command is not None:
            arguments = dict(args.__dict__)
            arguments.pop('meeting_command')
            arguments.pop('command')
            arguments['sender_full_name'] = message['sender_full_name']

            print(arguments)
            print(args.meeting_command, type(args.meeting_command))
            res = self.meetings.execute(args.meeting_command, **arguments)
            print(res)
            bot_handler.send_reply(message, res)

        elif args.command == 'calendar':
            try:
                res = make_calendar(args.year, args.month, args.start_sunday)
            except Exception as ex:
                print(ex)
                res = str(ex)
            bot_handler.send_reply(message, res)
        
        elif args.command == 'pick':
            res = pick_user(message, bot_handler._client)
            bot_handler.send_reply(message, res)

        else:
            print(args)
            bot_handler.send_reply(message, print_help(args.command if hasattr(args, 'command') else None))

    def usage(self, bot='@-mention-bot'):
        return f"""Hi! I'm {bot}! You can type `help` or `[command] --help` for more information on my commands."""


handler_class = Dana


if __name__ == '__main__':
    pass
