# Generated by Django 2.2.2 on 2019-06-24 13:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('MetaGrab', '0002_auto_20190622_1031'),
    ]

    operations = [
        migrations.CreateModel(
            name='Thread',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('content', models.CharField(max_length=200)),
                ('forum', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MetaGrab.Forum')),
            ],
        ),
        migrations.DeleteModel(
            name='Threads',
        ),
    ]
