import logging
import os
import uuid
from datetime import datetime
from logging.handlers import WatchedFileHandler

from django.conf import settings
from django.core.management.base import BaseCommand

from django_sqs.daemonize import CustomDaemonRunner
from django_sqs.management.commands.runreceiver_daemon import pid_exists
from inapi.setting.base import Environments
from pfapi.storage import Storage
from slackbot.bot_core import SlackBot
from slackbot.models import PBotLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """This is a script to run PBot as a daemon.

    # 로컬 테스트하기
    슬랙은 기본적으로 동일 ID의 봇은 하나의 프로세스만 띄워놔야 하는 구조이다.
    만약 2개 이상의 프로세스를 띄우는 경우 각각이 메시지를 받아가서 응답을 보내기 때문에 동일한 응답이 2개 이상 보내지기 때문이다.
    따라서 테스트용도로 사용하기 위해 pf-operation 팀 쪽에 pbotd 라는 이름으로 봇을 하나 만들어두었고,
    로컬에서 테스트 할 때는 이 봇을 사용하면 된다.
    .env의 SLACK_BOT_TOKEN 과 SLACK_BOT_NAME 을 pf-operation 팀의 것으로 설정하고
    아래와 같이 실행하면 pf-operation 팀 쪽의 pbotd 에 해당하는 프로세스가 만들어진다.

    $ cd /path/to/inapi
    $ . .env/bin/activate
    (ENV)$ python manage.py slackbot start

    # 로그 보기
    (ENV)$ tail -f logs/slack_bot_output.log

    # 실행 종료
    (ENV)$ python manage.py slackbot stop

    """

    def add_arguments(self, parser):
        parser.add_argument(dest='action', metavar='ACTION', action='store',
                            help='[start|restart|stop]')
        parser.add_argument('-d', '--daemonize',
                            dest='daemonize', type=bool, default=False,
                            help="Fork into background as a daemon. "
                                 "You can set this up at django\'s settings file: "
                                 "SLACK_BOT_DAEMONIZE=[True|False].")
        parser.add_argument('-l', '--output-log-path',
                            dest='output_log_path', type=str, default=None,
                            help="Standard output log file. "
                                 "You can set this up at django\'s settings file: "
                                 "SLACK_BOT_OUTPUT_LOG_PATH=[OUTPUT_LOG_FILE_PATH].")
        parser.add_argument('-e', '--error-log-path',
                            dest='error_log_path', type=str, default=None,
                            help="Standard error log file."
                                 "You can set this up at django\'s settings file: "
                                 "SLACK_BOT_ERROR_LOG_PATH=[ERROR_LOG_FILE_PATH].")
        parser.add_argument('-p', '--pid-file-path',
                            dest='pid_file_path', type=str, default=None,
                            help="Store process ID in a file"
                                 "You can set this up at django\'s settings file: "
                                 "SLACK_BOT_PID_FILE_PATH=[PID_FILE_PATH].")

    def handle(self, *args, **options):
        action = options['action']
        if action not in ('start', 'restart', 'stop'):
            raise Exception('%s is not supported action.' % str(action))

        daemonize = options.get('daemonize')
        if not daemonize:
            daemonize = getattr(settings, 'SLACK_BOT_DAEMONIZE', None)

        pid_file_path = options.get('pid_file_path')
        if not pid_file_path:
            pid_file_path = getattr(settings, 'SLACK_BOT_PID_FILE_PATH', 'slack_bot.pid')

        output_log_path = options.get('output_log_path')
        if not output_log_path:
            output_log_path = getattr(settings, 'SLACK_BOT_OUTPUT_LOG_PATH', 'slack_bot_output.log')

        error_log_path = options.get('error_log_path')
        if not error_log_path:
            error_log_path = getattr(settings, 'SLACK_BOT_ERROR_LOG_PATH', 'slack_bot_output.log')

        exception_callback = options.get('exception_callback')
        if not exception_callback:
            exception_callback = getattr(settings, 'SLACK_BOT_EXCEPTION_CALLBACK', None)

        # Set logger up.
        if not logger.handlers:
            formatter = logging.Formatter(
                fmt='[SlackBot %(levelname)s %(asctime)s %(module)s %(process)d %(thread)d] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S')
            handler = WatchedFileHandler(output_log_path)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            logger.info('Set new logger up.')
        else:
            logger.info('Use logger already set up.')

        # Close the DB connection now and let Django reopen it when it
        # is needed again.  The goal is to make sure that every
        # process gets its own connection
        from django.db import connection
        connection.close()

        if 'start' == action and os.path.isfile(pid_file_path):
            with open(pid_file_path, 'r') as pid_file:
                for pid in pid_file:
                    try:
                        pid = int(pid.rstrip('\n'))
                    except (AttributeError, ValueError):
                        pid = -1
                    logger.info('PID file exists already, so checking whether PID(%d) is running.' % pid)
                    if pid_exists(pid):
                        logger.info('PID(%d) is already running, so exit this process.' % pid)
                        return

        slack_bot = SlackBot(
            std_out_path=output_log_path,
            std_err_path=error_log_path,
            pid_file_path=pid_file_path,
            exception_callback=exception_callback)
        if daemonize:
            logger.debug('Initiating daemon runner for SlackBot...')
            runner = CustomDaemonRunner(slack_bot, (__name__, action))
            logger.debug('Initiated daemon runner for SlackBot...')
            logger.info('{} daemon for SlackBot...'.format(action))
            runner.do_action()
        else:
            logger.info('This is not a daemonized process. Use first queue.')
            slack_bot.start()
        logger.info('Exit process for SlackBot.')

        return


def backup_to_s3(request_type, extension, pbot_log_pk, result_file_path):
    """QA, PRODUCTION 환경에서 PBot으로 추출한 데이터를 S3에도 올려 백업한다.

        Args:
            request_type (str): 요청 Type. Example: 'stats/bi/mg_유저정보', '담보채권_거래내역', etc...
            extension (str): 확장자. Example: 'zip', 'xlsx'
            pbot_log_pk (int): PBot 로깅을 하면서 생성된 PBotLog의 PK
            result_file_path (str): 업로드할 파일의 경로
        """
    # QA, PRODUCTION 환경이 아닌경우 저장하지 않는다.
    if os.environ.get('DJANGO_SETTINGS_MODULE') not in (Environments.QA, Environments.PRODUCTION):
        logger.debug('The data is not requested from QA or Development')
        return

    # 로또에 당첨될 만한 확률로 UUID 값이 겹치는 경우가 있을 수 있다. 이 경우도 고려해주자.
    while True:
        key = 'pbot/{0}/{1}_{2}.{3}'.format(
            request_type, datetime.now().strftime('%Y%m%d_%H%M%S'), str(uuid.uuid4()), extension)
        if not PBotLog.objects.filter(archived_path=key).exists():
            break

    log = PBotLog.objects.get(pk=pbot_log_pk)
    log.archived_path = key
    log.save()
    Storage().s3bucket.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=open(result_file_path, 'rb'),
        ServerSideEncryption='AES256',
        StorageClass='STANDARD_IA',
    )
