# Generated by Django 2.2.2 on 2019-06-22 15:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Developer',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='Forum',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
            ],
        ),
        migrations.CreateModel(
            name='Genre',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='Threads',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('forum', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MetaGrab.Forum')),
            ],
        ),
        migrations.CreateModel(
            name='Game',
            fields=[
                ('id', models.IntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('release_date', models.DateTimeField()),
                ('last_updated', models.DateTimeField()),
                ('developer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MetaGrab.Developer')),
                ('genre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='MetaGrab.Genre')),
            ],
        ),
        migrations.AddField(
            model_name='forum',
            name='game',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='MetaGrab.Game'),
        ),
    ]
