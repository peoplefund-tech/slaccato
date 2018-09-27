from django.db import models
from model_utils.models import TimeStampedModel


class PBotLog(TimeStampedModel):
    """P Bot 호출 기록을 저장해 두는 모델이다.

    """
    request_user = models.CharField(verbose_name='요청한 사람', max_length=64, null=True, blank=True)
    message = models.CharField(verbose_name='요청 메시지', max_length=1024, null=True, blank=True)
    archived_path = models.CharField(verbose_name='아카이브 경로', max_length=1024, null=True, blank=True)

    class Meta:
        db_table = 'pbot_log'
        verbose_name = verbose_name_plural = '호출 로그'

    def __str__(self):
        return '{}: {}'.format(self.request_user, self.message)


class PBotWhitelistStats(TimeStampedModel):
    """stats, stats_csv 명령에서 사용할 수 있는 통계 중 화이트리스트로 운영하는 통계 목록이다.

    """
    stats_name = models.CharField(verbose_name='통계 이름', max_length=64, unique=True)

    class Meta:
        db_table = 'pbot_whitelist_stats'
        verbose_name = verbose_name_plural = '화이트리스트 통계'

    def __str__(self):
        return self.stats_name


class PBotWhitelistEmail(TimeStampedModel):
    """PBotWhitelistStats 모델에 등록된 화이트리스트 통계에서 사용 가능한 메일을 지정하는 모델이다.

    """
    email = models.EmailField(verbose_name='요청 가능한 메일')
    stats = models.ForeignKey(PBotWhitelistStats, verbose_name='통계 이름', on_delete=models.CASCADE)

    class Meta:
        db_table = 'pbot_whitelist_email'
        verbose_name = verbose_name_plural = '사용 가능한 이메일'

    def __str__(self):
        return self.email


"""
# 0001
BEGIN;
CREATE TABLE `pbot_log` (`id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY, `created` datetime(6) NOT NULL, `modified` datetime(6) NOT NULL, `request_user` varchar(64) NULL, `message` varchar(1024) NULL);
CREATE TABLE `pbot_whitelist_email` (`id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY, `created` datetime(6) NOT NULL, `modified` datetime(6) NOT NULL, `email` varchar(254) NOT NULL);
CREATE TABLE `pbot_whitelist_stats` (`id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY, `created` datetime(6) NOT NULL, `modified` datetime(6) NOT NULL, `stats_name` varchar(64) NOT NULL UNIQUE);
ALTER TABLE `pbot_whitelist_email` ADD COLUMN `stats_id` integer NOT NULL;
ALTER TABLE `pbot_whitelist_email` ALTER COLUMN `stats_id` DROP DEFAULT;
CREATE INDEX `pbot_whitelist_email_764e54b1` ON `pbot_whitelist_email` (`stats_id`);
ALTER TABLE `pbot_whitelist_email` ADD CONSTRAINT `pbot_whitel_stats_id_5f131af31b28c356_fk_pbot_whitelist_stats_id` FOREIGN KEY (`stats_id`) REFERENCES `pbot_whitelist_stats` (`id`);

COMMIT;

# 0002
BEGIN;
ALTER TABLE `pbot_log` ADD COLUMN `archived_path` varchar(64) NULL;

COMMIT;

# 0003
BEGIN;
ALTER TABLE `pbot_log` MODIFY `archived_path` varchar(1024) NULL;

COMMIT;
"""  # noqa
