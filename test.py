import logging
from sys import stdout

from slaccato import (
    SlackBot,
    SlackMethod,
)

logger = logging.getLogger(__name__)

logger.setLevel(4)
logger.addHandler(logging.StreamHandler(stdout))


class TestResponse(SlackMethod):

    @property
    def execution_words(self):
        return ['test', 'ping']

    @property
    def help_text(self):
        return '*{}*: Test me.'.format('/'.join(self.execution_words))

    def response(self, channel, thread_ts, user_command, request_user):
        response = '<@{}> pong!'.format(request_user)

        return channel, thread_ts, response


slack_bot = SlackBot(
    slack_bot_token='SLACK_BOT_TOKEN',
    slack_bot_name='SLACK_BOT_NAME',
    logger=logger,
)


slack_bot.add_method(TestResponse)

slack_bot.run()
