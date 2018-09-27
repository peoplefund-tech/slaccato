import importlib
import inspect
import logging
import signal
import sys
import time
import traceback
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime
from logging.handlers import WatchedFileHandler
from os import listdir
from os.path import (
    isfile,
    join,
)

from django.conf import settings
from slackclient import SlackClient

import slackbot

from .models import PBotLog


"""
Slack API list: https://api.slack.com/bot-users#api_usage
"""


class SlackMethod:
    """
    Base Class of User's command.
    """

    @property
    def execution_words(self):
        """특정 명령을 실행할 수 있는 명령어를 반환한다.

        Returns:
            list(str): 이 명령을 실행할 수 있는 단어의 리스트이다. 부합하는 명령이 들어오면, `response` 함수를 실행한다.
        """
        raise NotImplementedError()

    @property
    def help_text(self):
        """명령을 설명하는 문자열을 반환한다.

        Returns:
            (str): 이 명령의 설명이다.
        """
        raise NotImplementedError()

    def response(self, channel, user_command, pbot_log_pk=None):
        """명령이 실행되는 함수이다.

        Args:
            channel (str): 메시지를 받은 채널이다.
            user_command (str): 유저에게 받은 메시지이다.
            pbot_log_pk (int): PBot Log Primary Key이다.

        Returns:
            (str): 답을 전송할 채널이다.
            (str): 답변 메시지이다.

        """
        raise NotImplementedError()


def load_function(func):
    if hasattr(func, '__call__'):
        func = func
    elif isinstance(func, str):
        module_string, func_name = func.split(':')
        module = importlib.import_module(module_string)
        func = getattr(module, func_name)
    else:
        raise TypeError("A type of \"func\" argument is must function or str. "
                        "When put str, it must be full name of function. "
                        "e.g.: func=\"moduleA.moduleB:function_name\"")
    return func


class SlackBotLogFormatter(logging.Formatter):
    converter = datetime.fromtimestamp

    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            s = ct.strftime(datefmt)
        else:
            t = ct.strftime("%Y-%m-%d %H:%M:%S")
            s = "%s,%06d" % (t, record.msecs)
        return s


class SlackBot(object):

    BOT_ID = None
    AT_BOT = '<@{}>'

    help_text = None
    slack_methods = None

    @property
    def _slack_client(self):
        if self.__slack_client:
            return self.__slack_client
        self.__slack_client = SlackClient(settings.SLACK_BOT_TOKEN)
        return self.__slack_client
    __slack_client = None

    def __init__(self,
                 std_in_path='/dev/null',
                 std_out_path='slack_bot_output.log',
                 std_err_path='slack_bot_output.log',
                 pid_file_path='slack_bot.pid',
                 pid_file_timeout=5,
                 exception_callback=None):

        self.logger = logging.getLogger(slackbot.__name__)
        self.kill_now = False
        self.futures = []

        self.stdin_path = std_in_path
        self.stdout_path = std_out_path
        self.stderr_path = std_err_path
        self.pidfile_path = pid_file_path
        self.pidfile_timeout = pid_file_timeout

        self.exception_callback = load_function(exception_callback) if exception_callback else None

        self.BOT_ID = self.get_bot_id()
        if not self.BOT_ID:
            raise Exception("Could not find bot user with the name {}.".format(settings.SLACK_BOT_NAME))
        self.AT_BOT = self.AT_BOT.format(self.BOT_ID)
        self.slack_methods = self._load_slack_methods()

    def get_bot_id(self):
        api_call = self._slack_client.api_call("users.list")
        if api_call.get('ok'):
            # retrieve all users so we can find our bot
            members = api_call.get('members')
            for member in members:
                if 'name' in member and member.get('name') == settings.SLACK_BOT_NAME:
                    self.logger.debug("Member data:{}".format(member))
                    self.logger.info("Bot ID for '{}' is {}.".format(member['name'], member.get('id')))
                    return member.get('id')
        return None

    def _load_slack_methods(self):
        slack_methods = dict()
        base_path = settings.BASE_DIR + '/slackbot/slack_methods'
        module_names = [f for f in listdir(base_path) if isfile(join(base_path, f))]
        for module_name in module_names:
            if module_name == '__init__.py':
                continue
            imported_module = importlib.import_module('slackbot.slack_methods.{}'.format(module_name.split('.')[0]))
            for cls_name, obj in inspect.getmembers(imported_module, inspect.isclass):
                if 'slackbot.slack_methods' not in obj.__module__:
                    continue
                if issubclass(obj, SlackMethod):
                    instance = obj()
                    if not isinstance(instance.execution_words, list):
                        raise Exception("{}.execution_words returns not a list type value. "
                                        "it must returns list.".format(cls_name))
                    if cls_name in slack_methods:
                        raise Exception("Class name [{}] is used in two or more classes. "
                                        "It must be unique.".format(cls_name))
                    slack_methods[cls_name] = {
                        'class_name': cls_name,
                        'triggers': instance.execution_words,
                        'help_text': instance.help_text,
                        'response': instance.response,
                    }
        # add a slack method to return help message
        slack_methods['HelpText'] = {
            'class_name': 'HelpText',
            'triggers': ['헬프', 'help', '리스트', 'list'],
            'help_text': None,
            'response': self.get_help_text,
        }
        return slack_methods

    def get_help_text(self, channel, user_command, pbot_log_pk=None):
        if self.help_text:
            return channel, self.help_text

        def _get_help_text(slack_method):
            return '\n\t{}'.format(slack_method[1]['help_text'])

        self.logger.debug(str(self.slack_methods))
        help_text_list = list(map(_get_help_text,
                                  filter(lambda x: isinstance(x[1]['help_text'], str), self.slack_methods.items())))
        help_text_list.insert(0, '*My commands*:\n')
        self.help_text = ''.join(help_text_list)
        return channel, self.help_text

    def run(self):
        self.set_logger()

        # Set signal handler up.
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.start()
        self.logger.info('SlackBot is completely exited.')

    def set_logger(self):
        self.logger.handlers = list()

        # Set up logger file handler in daemon process.
        formatter = SlackBotLogFormatter(
            fmt='[SlackBot %(levelname)s %(asctime)s %(module)s %(process)d %(thread)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S.%f'
        )
        handler = WatchedFileHandler(self.stdout_path, encoding='utf8')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)
        self.logger.info('SlackBot starts!')
        self.logger.info('Set new logger up.')
        for h in self.logger.handlers:
            self.logger.debug('Added logging handler: ' + str(h))

        for logger_name in settings.LOGGING.get('loggers'):
            logger = logging.getLogger(logger_name)
            logger_setting = settings.LOGGING.get('loggers').get(logger_name)
            if 'file' in logger_setting.get('handlers'):
                logger.handlers = list()
                logger.addHandler(handler)
                logger.setLevel(logging._nameToLevel.get(logger_setting.get('level', 'DEBUG')))
                self.logger.info('Re-setup for logger [{}] in Django settings.'.format(logger_name))

    def exit_gracefully(self, signum, frame):
        logger = logging.getLogger(slackbot.__name__)
        if signal.SIGTERM == signum:
            logger.info('Received termination signal. Prepare to exit...')
            if 1 <= len(self.futures):
                for f in as_completed(self.futures):
                    self.logger.debug("Result of some future: {}".format(f.result()))
            from django.db import connections
            connections.close_all()
            self.kill_now = True
        else:
            logger.info('Received signal {}, but there is no process for this signal.'.format(signum))

    def start(self):
        if self._slack_client.rtm_connect():
            self.logger.info("SlackBot connected and running!")
            self._handle_command_loop()
        else:
            raise Exception("Connection failed. Invalid Slack token or bot ID?")
        return True

    def _handle_command_loop(self):
        while True:
            if self.kill_now:
                return
            # Max sub processes count is 5.
            if len(self.futures) >= 5:
                for f in as_completed(self.futures):
                    self.logger.info("Result of some future: " + str(f.result()))
                self.futures = list()
            try:
                channel, command, user = self._parse_slack_output(self._slack_client.rtm_read())
                if channel and command:
                    log = PBotLog.objects.create(
                        request_user=user,
                        message=command,
                    )
                    self._handle_command(channel, command, log.pk)
            except KeyboardInterrupt:
                e = sys.exc_info()[1]
                raise e
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                error_traceback = 'Exception traceback: {}'.format(''.join(
                    str(entry) for entry in traceback.format_tb(exc_traceback, limit=20)))
                self.logger.exception("Caught exception when handle command loop. exception:{}".format(e))
                self.logger.exception(error_traceback)
                if self.exception_callback:
                    self.exception_callback(e)
                self.exit_gracefully(signal.SIGTERM, None)
            time.sleep(settings.SLACK_READ_WEB_SOCKET_DELAY)

    def _parse_slack_output(self, slack_rtm_output):
        """
            The Slack Real Time Messaging API is an events firehose.
            this parsing function returns None unless a message is
            directed at the Bot, based on its ID.
        Args:
            slack_rtm_output:

        Returns:
            channel (str): 유저가 말을 건 채널이다.
            text (str): 유저의 대화 내용이다.
            user (str): 사용자 이름과 display name 이다.
        """
        output_list = slack_rtm_output
        if output_list and len(output_list) > 0:
            for output in output_list:
                if not isinstance(output, dict):
                    return None, None, None

                if 'channel' not in output:
                    return None, None, None

                if output['type'] != 'message':
                    return None, None, None

                # Prevent to recursive call.
                if 'user' in output and self.BOT_ID == output['user']:
                    return None, None, None

                if 'text' in output and self.AT_BOT in output['text']:
                    # return text after the @ mention, whitespace removed
                    # self.logger.debug('SlackRUMOutput:{}'.format(output))
                    user = self._slack_client.server.users[output['user']]
                    return (
                        output['channel'],
                        output['text'].split(self.AT_BOT)[1].strip().lower(),
                        '{} (@{})'.format(user.real_name, user.name),
                    )

                # elif 'message' == output['type']:
                    # _response = self._slack_client.api_call('im.list')
                    # if not _response.get('ok'):
                    #     return None, None
                    # self.logger.debug('im.list ok response:{}'.format(_response))
                    # for im in _response['ims']:
                    #     if output['channel'] == im['id']:
                    #         return output['channel'], output['text'].strip().lower()
                    # self.logger.debug('SlackRUMOutput:{}'.format(output))

        return None, None, None

    def _handle_command(self, channel, command, pbot_log_pk):
        """
            Receives commands directed at the bot and determines if they
            are valid commands. If so, then acts on the commands. If not,
            returns back what it needs for clarification.
        Args:
            command:
            channel:

        Returns:

        """
        with ThreadPoolExecutor(max_workers=5) as executor:
            params = {
                'callback': self._slack_client.api_call,
                'channel': channel,
                'func': self._get_command_function(command),
                'user_command': command,
                'pbot_log_pk': pbot_log_pk
            }
            future = executor.submit(self._command_executor, **params)
            self.futures.append(future)

    def _command_executor(self, callback, channel, func, user_command, pbot_log_pk):
        from django.db import connections
        connections.close_all()
        try:
            channel, response = func(channel, user_command, pbot_log_pk=pbot_log_pk)
        except Exception as e:
            self.logger.error('An error occurred in a {} function. exception:{}'.format(func, e))
            error_message = traceback.format_exc() + '\n'
            error_message += '-' * 79 + '\n\n'
            error_message += 'callback:{}, \nchannel:{}, \nfunc:{}, \nuser_command:{}, \npbot_log_pk:{}'.format(
                callback, channel, func, user_command, pbot_log_pk
            )
            self.logger.error(error_message)
            channel, response = self.slack_methods['DefaultResponse']['response'](channel, user_command,
                                                                                  exception=error_message)
        callback("chat.postMessage", channel=channel, text=response, as_user=True)
        return True

    def _get_command_function(self, command):
        for method_name in self.slack_methods:
            slack_method = self.slack_methods[method_name]
            self.logger.debug('{}:{}'.format(method_name, slack_method))
            for trigger in slack_method['triggers']:
                if isinstance(trigger, str) and str(command).strip().split(' ')[0].strip() == str(trigger).strip():
                    return self.slack_methods[method_name]['response']
        return self.slack_methods['DefaultResponse']['response']
