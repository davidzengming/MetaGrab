# Generated by Django 3.0.6 on 2020-05-13 18:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MetaGrab', '0037_report_report_reason'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='blacklisted_user_profiles',
            field=models.ManyToManyField(to='MetaGrab.UserProfile'),
        ),
    ]