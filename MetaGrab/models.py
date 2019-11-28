from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now
from django.db.models import F

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
    upvotes = models.IntegerField(default=1)
    downvotes = models.IntegerField(default=0)
    content = models.TextField(max_length = 40000)

    num_childs = models.IntegerField(default = 0)
    num_subtree_nodes = models.IntegerField(default = 0)

class Thread(Votable):
    TYPE_UPDATE = 0
    TYPE_DISCUSSION = 1
    TYPE_MEME = 2
    TYPE_CHOICES = (
        (TYPE_UPDATE, 0),
        (TYPE_DISCUSSION, 1),
        (TYPE_MEME, 2),
    )

    flair = models.IntegerField(
        choices=TYPE_CHOICES,
        default=TYPE_DISCUSSION,
    )
    title = models.TextField(max_length = 200)
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE)
    image_url = models.URLField(default=None)

    @classmethod
    def create(cls, flair, title, content, author, forum, image_url):
        thread = cls.objects.create(flair=flair, title=title, content=content, author=author, forum=forum, image_url=image_url)
        return thread

    def increment_upvotes(self):
        self.upvotes = F('upvotes') + 1
        self.save()
        self.refresh_from_db()
        return self

    def switch_increment_upvotes(self):
        self.upvotes = F('upvotes') + 1
        self.downvotes = F('downvotes') - 1
        self.save()
        self.refresh_from_db()
        return self

    def increment_downvotes(self):
        self.downvotes = F('downvotes') + 1
        self.save()
        self.refresh_from_db()
        return self

    def decrement_upvotes(self):
        self.upvotes = F('upvotes') - 1
        self.save()
        self.refresh_from_db()
        return self

    def decrement_downvotes(self):
        self.downvotes = F('downvotes') - 1
        self.save()
        self.refresh_from_db()
        return self

    def switch_increment_downvotes(self):
        self.upvotes = F('upvotes') - 1
        self.downvotes = F('downvotes') + 1
        self.save()
        self.refresh_from_db()
        return self

    def __str__(self):
        return self.title

class Comment(Votable):
    parent_thread = models.ForeignKey(Thread, on_delete=models.CASCADE, null=True, blank=True)
    parent_post = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    
    @classmethod
    def create(cls, parent_thread, parent_post, content, author):
        comment = cls.objects.create(parent_thread=parent_thread, parent_post=parent_post, content=content, author=author)
        return comment

    def increment_upvotes(self):
        self.upvotes = F('upvotes') + 1
        self.save()
        self.refresh_from_db()
        return self

    def switch_increment_upvotes(self):
        self.upvotes = F('upvotes') + 1
        self.downvotes = F('downvotes') - 1
        self.save()
        self.refresh_from_db()
        return self

    def increment_downvotes(self):
        self.downvotes = F('downvotes') + 1
        self.save()
        self.refresh_from_db()
        return self

    def decrement_upvotes(self):
        self.upvotes = F('upvotes') - 1
        self.save()
        self.refresh_from_db()
        return self

    def decrement_downvotes(self):
        self.downvotes = F('downvotes') - 1
        self.save()
        self.refresh_from_db()
        return self

    def switch_increment_downvotes(self):
        self.upvotes = F('upvotes') - 1
        self.downvotes = F('downvotes') + 1
        self.save()
        self.refresh_from_db()
        return self

    def __str__(self):
        return self.content

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

class Vote(models.Model):
    created = models.DateTimeField(default=now, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    is_positive = models.BooleanField(blank=False)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)

    @classmethod
    def create(cls, user, is_positive, thread, comment):
        vote = cls.objects.create(user=user, is_positive=is_positive, thread=thread, comment=comment)
        return vote

    @classmethod
    def delete_thread_vote(cls, vote_id):
        vote = cls.objects.get(pk=vote_id)

        thread = vote.thread
        if vote.is_positive:
            thread.decrement_upvotes()
        else:
            thread.decrement_downvotes()
        cls.objects.get(pk=vote_id).delete()
        return thread

    @classmethod
    def delete_comment_vote(cls, vote_id):
        vote = cls.objects.get(pk=vote_id)
        comment = vote.comment
        if vote.is_positive:
            comment.decrement_upvotes()
        else:
            comment.decrement_downvotes()
        cls.objects.get(pk=vote_id).delete()
        return comment

    def switch_vote_comment(self):
        if self.is_positive == True:
            self.comment.switch_increment_downvotes()
        else:
            self.comment.switch_increment_upvotes()
        self.is_positive = not self.is_positive
        self.save()
        return self.comment

    def switch_vote_thread(self):
        if self.is_positive == True:
            self.thread.switch_increment_downvotes()
        else:
            self.thread.switch_increment_upvotes()
        self.is_positive = not self.is_positive
        self.save()
        return self.thread

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
def increment_subtree_counts(sender, instance, created, **kwargs):
    if created:
        post = instance
        if post.parent_post:
            post.parent_post.num_childs = F('num_childs') + 1
            post.parent_post.save()
            post.parent_post.refresh_from_db()
        else:
            post.parent_thread.num_childs = F('num_childs') + 1
            post.parent_thread.save()
            post.parent_thread.refresh_from_db()

        post = instance
        while post.parent_post:
            post = post.parent_post
            post.num_subtree_nodes = F('num_subtree_nodes') + 1
            post.save()

        post.parent_thread.num_subtree_nodes = F('num_subtree_nodes') + 1
        post.parent_thread.save()