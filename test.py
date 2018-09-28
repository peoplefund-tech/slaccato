from slack_methods.test import TestResponse
from core import SlackBot


slack_bot = SlackBot(
    slack_bot_token='SLACK_BOT_TOKEN',
    slack_bot_name='SLACK_BOT_NAME'
)

slack_bot.add_method(TestResponse)

slack_bot.run()
