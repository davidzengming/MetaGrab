# Generated by Django 2.0.13 on 2020-01-22 16:51

from django.db import migrations
import django_mysql.models


class Migration(migrations.Migration):

    dependencies = [
        ('MetaGrab', '0032_game_next_expansion_release_date'),
    ]

    operations = [
        migrations.RenameField(
            model_name='comment',
            old_name='content',
            new_name='content_string',
        ),
        migrations.RenameField(
            model_name='thread',
            old_name='content',
            new_name='content_string',
        ),
        migrations.AddField(
            model_name='comment',
            name='content_attributes',
            field=django_mysql.models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='thread',
            name='content_attributes',
            field=django_mysql.models.JSONField(default=dict),
        ),
    ]