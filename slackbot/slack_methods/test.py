from slackbot.bot_core import SlackMethod


class TestResponse(SlackMethod):

    @property
    def execution_words(self):
        return ['테스트', 'test', 'ping']

    @property
    def help_text(self):
        return '*{}*: 저를 테스트해보실 수 있는 명령이에요.'.format('/'.join(self.execution_words))

    def response(self, channel, user_command, pbot_log_pk=None):
        response = '피봇을 테스트해주셨군요! 저는 잘 살아있어요!!!'
        return channel, response
