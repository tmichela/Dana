from multiprocessing.sharedctypes import Value
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from argument_parser import parse_arguments


class Dana:
    """Dana is the Zulip bot, used by the Data Analysis group at the EuXFEL
    """

    def initialize(self, bot_handler):
        self.init_storage(bot_handler)

    def init_storage(self, bot_handler):
        for store in ['meeting', 'reminder']:
            if not bot_handler.storage.contains(store):
                bot_handler.storage.put(store, [])

    def handle_message(self, message, bot_handler):
        args, output = parse_arguments(message['content'].split())
        if output:
            bot_handler.send_reply(message, f'```text\n{output}\n```')

        if args:
            print(args)
            print(args.command)
            print(args.repeat)

    def usage(self, bot='@-mention-bot'):
        return f"""Hi! I'm {bot}!"""


handler_class = Dana


if __name__ == '__main__':
    pass
