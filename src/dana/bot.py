from multiprocessing.sharedctypes import Value
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from argument_parser import parse_arguments
from commands.meetings import MeetingBot


class Dana:
    """Dana is the Zulip bot, used by the Data Analysis group at the EuXFEL
    """

    def initialize(self, bot_handler):
        self.meetings = MeetingBot(bot_handler)
    #     self.init_storage(bot_handler)

    # def init_storage(self, bot_handler):
    #     for store in ['meeting', 'reminder']:
    #         if not bot_handler.storage.contains(store):
    #             bot_handler.storage.put(store, [])

    def handle_message(self, message, bot_handler):
        print(message)
        args, output = parse_arguments(message['content'].split())
        if output:
            bot_handler.send_reply(message, f'```text\n{output}\n```')

        if args is None:
            print(output)
            return

        if args.command == 'meeting':
            arguments = dict(args.__dict__)
            arguments.pop('meeting_command')
            arguments.pop('command')
            getattr(self.meetings, args.meeting_command)(**arguments)

        # if args:
        #     print(args)
        #     print(args.command)
        #     print(args.repeat)

    def usage(self, bot='@-mention-bot'):
        return f"""Hi! I'm {bot}!"""


handler_class = Dana


if __name__ == '__main__':
    pass
