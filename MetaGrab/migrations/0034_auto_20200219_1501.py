# Generated by Django 2.0.13 on 2020-02-19 20:01

from django.db import migrations
import django_mysql.models


class Migration(migrations.Migration):

    dependencies = [
        ('MetaGrab', '0033_auto_20200122_1151'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='thread',
            name='image_url',
        ),
        migrations.AddField(
            model_name='thread',
            name='image_urls',
            field=django_mysql.models.JSONField(default=dict),
        ),
    ]
