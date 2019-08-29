import importlib
import logging
import signal
import sys
import traceback
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from datetime import datetime
from logging.handlers import WatchedFileHandler

from slackclient import SlackClient


"""
Slack API list: https://api.slack.com/bot-users#api_usage
"""


class SlackMethod:
    """
    Base Class of User's command.
    """

    @property
    def execution_words(self):
        """This method should be able to return list(str).

        Returns
            list(str): The keywords to execute the method `response`.
        """
        raise NotImplementedError()

    @property
    def help_text(self):
        """This method should able to return the description, guide for this command.

        Returns:
            (str): Description, guide for this command.
        """
        raise NotImplementedError()

    def response(self, channel, thread_ts, user_command, request_user):
        """This method should be able to return a str response

        Args:
            channel (str): Channel with requested user
            thread_ts (str): Thread requested from user
            user_command (str): Text received from user
            request_user (dict): Requested user.
            
        Returns:
            (str): Target channel
            (str): Target thread or None
            (str|list): Message to send
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


class DefaultMethod(SlackMethod):

    @property
    def execution_words(self):
        return ['OMG']

    @property
    def help_text(self):
        return None

    def response(self, channel, thread_ts, user_command, request_user, exception=None):
        if not exception:
            response = '\n'.join([
                'Wrong command!',
                'Type `help` or `list` to show list of available commands.',
            ])

        else:
            response = '\n'.join([
                "Oops, Some error occurred."
                '```{}```'.format(exception),
            ])
        return channel, thread_ts, response


class SlackBot(object):

    BOT_ID = None
    AT_BOT = '<@{}>'

    help_text = None
    slack_methods = None

    @property
    def _slack_client(self):
        if self.__slack_client:
            return self.__slack_client
        self.__slack_client = SlackClient(self.slack_bot_token)
        return self.__slack_client
    __slack_client = None

    def __init__(self,
                 slack_bot_token,
                 slack_bot_name,
                 logger=logging.getLogger(__name__),
                 pid_file_timeout=5,
                 polling_interval_milliseconds=None,
                 exception_callback=None,
                 default_method=DefaultMethod):

        self.logger = logger
        self.kill_now = False
        self.futures = []

        self.pidfile_timeout = pid_file_timeout

        self.polling_interval_milliseconds = polling_interval_milliseconds

        self.slack_bot_token = slack_bot_token
        self.slack_bot_name = slack_bot_name

        self.exception_callback = load_function(exception_callback) if exception_callback else None

        self.BOT_ID = self.get_bot_id()
        if not self.BOT_ID:
            raise Exception("Could not find bot user with the name {}.".format(self.slack_bot_name))
        self.AT_BOT = self.AT_BOT.format(self.BOT_ID)
        self.slack_methods = self._load_default_methods(default_method)

    def get_bot_id(self):
        api_call = self._slack_client.api_call("users.list")
        if api_call.get('ok'):
            # retrieve all users so we can find our bot
            members = api_call.get('members')

            for member in members:
                if 'name' in member and member.get('name') == self.slack_bot_name:
                    self.logger.debug("Member data:{}".format(member))
                    self.logger.info("Bot ID for '{}' is {}.".format(member['name'], member.get('id')))

                    return member.get('id')

        return None

    def _load_default_methods(self, default_method):
        slack_methods = dict()

        # add a slack method to return help message
        slack_methods['HelpText'] = {
            'class_name': 'HelpText',
            'triggers': ['help', 'list'],
            'help_text': None,
            'response': self.get_help_text,
        }

        # add a slack method executed when user type a wrong commands.
        wrong_input = default_method()
        slack_methods['WrongInput'] = {
            'class_name': 'WrongInput',
            'triggers': wrong_input.execution_words,
            'help_text': None,
            'response': wrong_input.response
        }

        return slack_methods

    def add_method(self, slack_method):
        if issubclass(slack_method, SlackMethod):
            instance = slack_method()

            if not isinstance(instance.execution_words, list):
                raise Exception("{}.execution_words returns not a list type value. "
                                "it must returns list.".format(slack_method.__name__))

            if slack_method in self.slack_methods:
                raise Exception("Class name [{}] is used in two or more classes. "
                                "It must be unique.".format(slack_method.__name__))

            self.slack_methods[slack_method.__name__] = {
                'class_name': slack_method.__name__,
                'triggers': instance.execution_words,
                'help_text': instance.help_text,
                'response': instance.response,
            }

    def get_help_text(self, channel, thread_ts, user_command, request_user):
        if self.help_text:
            return channel, self.help_text

        def _get_help_text(slack_method):
            return '\n\t{}'.format(slack_method[1]['help_text'])

        self.logger.debug(str(self.slack_methods))
        help_text_list = list(map(
            _get_help_text,
            filter(
                lambda x: isinstance(x[1]['help_text'], str),
                self.slack_methods.items()
            )
        ))
        help_text_list.insert(0, '*Available commands*:\n')
        self.help_text = ''.join(help_text_list)

        return channel, thread_ts, self.help_text

    def run(self):
        # Set signal handler up.
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.start()
        self.logger.info('SlackBot is completely exited.')

    def exit_gracefully(self, signum, frame):
        if signum in (signal.SIGINT, signal.SIGTERM):
            self.logger.info('Received termination signal. Prepare to exit...')

            if 1 <= len(self.futures):
                for f in as_completed(self.futures):
                    self.logger.debug("Result of some future: {}".format(f.result()))

            self.kill_now = True

        else:
            self.logger.info('Received signal {}, but there is no process for this signal.'.format(signum))

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
                channel, thread_ts, command, user = self._parse_slack_output(self._slack_client.rtm_read())

                if channel and command and user:
                    self._handle_command(channel, thread_ts, command, user)

            except KeyboardInterrupt:
                e = sys.exc_info()[1]

                raise e

            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                error_traceback = 'Exception traceback: {}'.format(
                    ''.join(
                        str(entry) for entry in traceback.format_tb(exc_traceback, limit=20)
                    )
                )
                self.logger.exception("Caught exception when handle command loop. exception: {}".format(e))
                self.logger.exception(error_traceback)

                if self.exception_callback:
                    self.exception_callback(e)

                self.exit_gracefully(signal.SIGTERM, None)

            if self.polling_interval_milliseconds is not None:
                time.sleep(self.polling_interval_milliseconds / 1000)

    def _parse_slack_output(self, slack_rtm_output):
        """
            The Slack Real Time Messaging API is an events firehose.
            this parsing function returns None unless a message is
            directed at the Bot, based on its ID.
        Args:
            slack_rtm_output:

        Returns:
            channel (str): Channel with requested user.
            text (str): Received message from user.
            user (str): Mention of user who triggered command.
        """
        output_list = slack_rtm_output

        if output_list and len(output_list) > 0:
            for output in output_list:
                if not isinstance(output, dict):
                    return None, None, None, None

                if 'channel' not in output:
                    return None, None, None, None

                if output['type'] != 'message':
                    return None, None, None, None

                if 'text' in output and self.AT_BOT in output['text']:
                    # return text after the @ mention, whitespace removed
                    # self.logger.debug('SlackRUMOutput:{}'.format(output))
                    user = self._slack_client.server.users[output['user']]

                    self.logger.info(str(output))

                    return (
                        output.get('channel'),
                        output.get('thread_ts', None),
                        output['text'].split(self.AT_BOT)[1].strip(),
                        '{}'.format(user.name),
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

        return None, None, None, None

    def _handle_command(self, channel, thread_ts, command, request_user):
        """
            Receives commands directed at the bot and determines if they
            are valid commands. If so, then acts on the commands. If not,
            returns back what it needs for clarification.
        Args:
            channel:
            thread_ts:
            command:
            request_user:

        Returns:

        """
        with ThreadPoolExecutor(max_workers=5) as executor:
            params = {
                'callback': self._slack_client.api_call,
                'channel': channel,
                'thread_ts': thread_ts,
                'func': self._get_command_function(command),
                'user_command': command,
                'request_user': request_user
            }

            future = executor.submit(self._command_executor, **params)
            self.futures.append(future)

    def _command_executor(self, callback, channel, func, user_command, request_user, thread_ts=None):
        try:
            channel, thread_ts, response = func(channel, thread_ts, user_command, request_user=request_user)

        except Exception as e:
            self.logger.error('An error occurred in a {} function. exception:{}'.format(func, e))

            trace_formatted = traceback.format_exc()
            extra_data = {
                'callback': callback,
                'channel': channel,
                'func': func,
                'user_command': user_command,
                'user': request_user,
                'thread_ts': thread_ts,
            }
            extra_data_formatted = '\n'.join('{}: {}'.format(k, v) for k, v in extra_data.items())
            error_message = '{}\n{}\n{}'.format(trace_formatted, '-' * 70, extra_data_formatted)

            self.logger.error(error_message)

            channel, response = self.slack_methods['WrongInput']['response'](channel, user_command,
                                                                             exception=error_message)

        post_message_args = {'channel': channel, 'thread_ts': thread_ts, 'as_user': True}

        if isinstance(response, list):
            post_message_args['blocks'] = response

        else:
            post_message_args['text'] = str(response)

        callback("chat.postMessage", **post_message_args)

        return

    def _get_command_function(self, command):
        for method_name in self.slack_methods:
            slack_method = self.slack_methods[method_name]

            for trigger in slack_method['triggers']:
                if isinstance(trigger, str) and str(command).strip().split(' ')[0].strip() == str(trigger).strip():
                    return self.slack_methods[method_name]['response']

        return self.slack_methods['WrongInput']['response']
