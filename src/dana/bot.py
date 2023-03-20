from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from argument_parser import parse_arguments
from commands.meetings import MeetingBot


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
        args, output = parse_arguments(message['content'].split())
        if output:
            bot_handler.send_reply(message, f'```text\n{output}\n```')
            return

        if args is None:
            print(output)
            return

        if args.command == 'meeting' and args.meeting_command is not None:
            arguments = dict(args.__dict__)
            arguments.pop('meeting_command')
            arguments.pop('command')

            print(arguments)
            print(args.meeting_command, type(args.meeting_command))
            # res = getattr(self.meetings, args.meeting_command)(**arguments)
            res = self.meetings.execute(args.meeting_command, **arguments)
            print(res)
            bot_handler.send_reply(message, res)
        else:
            print(args)

    def usage(self, bot='@-mention-bot'):
        return f"""Hi! I'm {bot}!"""


handler_class = Dana


if __name__ == '__main__':
    pass
