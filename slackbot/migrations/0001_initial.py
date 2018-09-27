# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import model_utils.fields
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PBotLog',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', model_utils.fields.AutoCreatedField(editable=False, verbose_name='created', default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(editable=False, verbose_name='modified', default=django.utils.timezone.now)),
                ('request_user', models.CharField(blank=True, max_length=64, verbose_name='요청한 사람', null=True)),
                ('message', models.CharField(blank=True, max_length=1024, verbose_name='요청 메시지', null=True)),
            ],
            options={
                'verbose_name_plural': '호출 로그',
                'db_table': 'pbot_log',
                'verbose_name': '호출 로그',
            },
        ),
        migrations.CreateModel(
            name='PBotWhitelistEmail',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', model_utils.fields.AutoCreatedField(editable=False, verbose_name='created', default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(editable=False, verbose_name='modified', default=django.utils.timezone.now)),
                ('email', models.EmailField(verbose_name='요청 가능한 메일', max_length=254)),
            ],
            options={
                'verbose_name_plural': '사용 가능한 이메일',
                'db_table': 'pbot_whitelist_email',
                'verbose_name': '사용 가능한 이메일',
            },
        ),
        migrations.CreateModel(
            name='PBotWhitelistStats',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created', model_utils.fields.AutoCreatedField(editable=False, verbose_name='created', default=django.utils.timezone.now)),
                ('modified', model_utils.fields.AutoLastModifiedField(editable=False, verbose_name='modified', default=django.utils.timezone.now)),
                ('stats_name', models.CharField(unique=True, verbose_name='통계 이름', max_length=64)),
            ],
            options={
                'verbose_name_plural': '화이트리스트 통계',
                'db_table': 'pbot_whitelist_stats',
                'verbose_name': '화이트리스트 통계',
            },
        ),
        migrations.AddField(
            model_name='pbotwhitelistemail',
            name='stats',
            field=models.ForeignKey(to='slackbot.PBotWhitelistStats', verbose_name='통계 이름', on_delete=models.CASCADE),
        ),
    ]
