# Generated by Django 3.0.6 on 2020-07-02 19:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MetaGrab', '0038_auto_20200513_1319'),
    ]

    operations = [
        migrations.AddField(
            model_name='genre',
            name='long_name',
            field=models.CharField(default='Test Genre Name', max_length=100),
            preserve_default=False,
        ),
    ]