# Generated by Django 3.0.6 on 2020-05-13 13:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MetaGrab', '0036_auto_20200511_1208'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='report_reason',
            field=models.TextField(default='', max_length=100),
            preserve_default=False,
        ),
    ]
