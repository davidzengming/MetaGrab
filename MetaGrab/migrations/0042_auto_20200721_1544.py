# Generated by Django 3.0.6 on 2020-07-21 20:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('MetaGrab', '0041_auto_20200716_1432'),
    ]

    operations = [
        migrations.AlterField(
            model_name='game',
            name='icon',
            field=models.URLField(default='https://images2.alphacoders.com/474/thumb-1920-474206.jpg', max_length=500),
        ),
    ]
