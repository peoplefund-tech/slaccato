from slackbot.bot_core import SlackMethod


class DefaultResponse(SlackMethod):

    @property
    def execution_words(self):
        return ['할수없음']

    @property
    def help_text(self):
        return None

    def response(self, channel, user_command, exception=None, pbot_log_pk=None):
        if not exception:
            response = '\n'.join([
                '제가 처리할 수 없는 명령을 하셨군요. ㅠㅠ',
                '제가 처리할 수 있는 명령을 알아보시려면, [헬프]나 [help]라고 요청해주세요!',
            ])

        else:
            response = '\n'.join([
                '앗, 명령을 처리하는 중 오류가 발생했어요. 아래 오류를 처리할 수 있게 저를 도와주세요!',
                '```{}```'.format(exception),
            ])
        return channel, response
