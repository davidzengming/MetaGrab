from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now

# Create your models here.
class Developer(models.Model):
    name = models.CharField(max_length = 100)
    created = models.DateTimeField(default=now, editable=False)

    def __str__(self):
        return self.name

class Genre(models.Model):
    name = models.CharField(max_length = 100)
    created = models.DateTimeField(default=now, editable=False)

    def __str__(self):
        return self.name

class Game(models.Model):
    created = models.DateTimeField(default=now, editable=False)
    name = models.CharField(max_length = 100)
    release_date = models.DateField()
    developer = models.ForeignKey(Developer, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    last_updated = models.DateField()
    icon = models.URLField(default="https://images2.alphacoders.com/474/thumb-1920-474206.jpg")

    def __str__(self):
        return self.name

class Forum(models.Model):
    created = models.DateTimeField(default=now, editable=False)
    game = models.OneToOneField(Game, on_delete=models.CASCADE)
    def __str__(self):
        return self.game.name

class Votable(models.Model):
    class Meta:
        abstract = True

    created = models.DateTimeField(default=now, editable=False)
    author = models.ForeignKey(User, on_delete=models.PROTECT)
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    content = models.TextField(max_length = 40000)

    num_childs = models.IntegerField(default = 0)
    num_subtree_nodes = models.IntegerField(default = 0)

class Thread(Votable):
    TYPE_UPDATE = 'update'
    TYPE_DISCUSSION = 'discussion'
    TYPE_MEME = 'meme'
    TYPE_CHOICES = (
        (TYPE_UPDATE, 'Update'),
        (TYPE_DISCUSSION, 'Discussion'),
        (TYPE_MEME, 'Meme'),
    )

    flair = models.CharField(
        max_length = 20,
        choices=TYPE_CHOICES,
        default=TYPE_DISCUSSION,
    )
    title = models.TextField(max_length = 200)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE)

    @classmethod
    def create(cls, flair, title, content, author, forum):
        thread = cls.objects.create(flair=flair, title=title, content=content, author=author, forum=forum)
        return thread

    def __str__(self):
        return self.title

class UserProfile(models.Model):
    created = models.DateTimeField(default=now, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    followed_games = models.ManyToManyField(Game)

    def find_followed_games(self):
        return self.followed_games

    def follow_game(self, game):
        self.followed_games.add(game)
        self.save()
        return

    def unfollow_game(self, game):
        self.followed_games.remove(game)
        self.save()
        return

    def __str__(self):
        return "__all__"

def get_first_name(self):
    return self.first_name

User.add_to_class("__str__", get_first_name)

class Comment(Votable):
    parent_thread = models.ForeignKey(Thread, on_delete=models.CASCADE, null=True, blank=True)
    parent_post = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    @classmethod
    def create(cls, parent_thread, parent_post, content, author):
        comment = cls.objects.create(parent_thread=parent_thread, parent_post=parent_post, content=content, author=author)
        return comment

    def __str__(self):
        return self.content

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()

@receiver(post_save, sender=Game)
def create_forum(sender, instance, created, **kwargs):
    if created:
        Forum.objects.create(game=instance)

@receiver(post_save, sender=Game)
def save_forum(sender, instance, **kwargs):
    instance.forum.save()

@receiver(post_save, sender=Comment)
def create_comment(sender, instance, created, **kwargs):
    if created:
        post = instance
        if post.parent_post:
            post.parent_post.num_childs += 1
            post.parent_post.save()
        else:
            post.parent_thread.num_childs += 1
            post.parent_thread.save()

        post = instance
        while post.parent_post:
            post = post.parent_post
            post.num_subtree_nodes += 1
            post.save()

        post.parent_thread.num_subtree_nodes += 1
        post.parent_thread.save()