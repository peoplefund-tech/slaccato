import logging
from sys import stdout

from slack_methods.test import TestResponse
from slaccato.core import SlackBot

logger = logging.getLogger(__name__)

logger.setLevel(4)
logger.addHandler(logging.StreamHandler(stdout))

slack_bot = SlackBot(
    slack_bot_token='SLACK_BOT_TOKEN',
    slack_bot_name='SLACK_BOT_NAME'
    logger=logger
)

slack_bot.add_method(TestResponse)

slack_bot.run()
