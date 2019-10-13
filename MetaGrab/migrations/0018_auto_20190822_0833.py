# Generated by Django 2.0.13 on 2019-08-22 13:33

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('MetaGrab', '0017_game_icon'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommentSecondary',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('upvotes', models.IntegerField(default=0)),
                ('downvotes', models.IntegerField(default=0)),
                ('content', models.CharField(max_length=200)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RemoveField(
            model_name='comment',
            name='parent_post',
        ),
        migrations.AlterField(
            model_name='comment',
            name='parent_thread',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MetaGrab.Thread'),
        ),
        migrations.AddField(
            model_name='commentsecondary',
            name='parent_post',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MetaGrab.Comment'),
        ),
    ]
