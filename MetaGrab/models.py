from django.db import models
from django_mysql.models import JSONField
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
    long_name = models.CharField(max_length = 100)
    created = models.DateTimeField(default=now, editable=False)

    def __str__(self):
        return self.name

class Game(models.Model):
    created = models.DateTimeField(default=now, editable=False)
    name = models.CharField(max_length = 100)
    release_date = models.DateField()
    next_expansion_release_date = models.DateField(default=None, blank=True, null=True)
    developer = models.ForeignKey(Developer, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    last_updated = models.DateField()
    icon = models.URLField(max_length=500, default="https://images2.alphacoders.com/474/thumb-1920-474206.jpg")
    banner = models.URLField(max_length=500, default="https://res.cloudinary.com/dzengcdn/image/upload/c_fill,g_auto,h_250,w_970/b_rgb:000000,e_gradient_fade,y_-0.50/c_scale,co_rgb:ffffff,fl_relative/v1575913613/dota2_tkcbuh.jpg")

    game_summary = models.TextField(max_length = 40000)

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
    content_string = models.TextField(max_length = 40000)
    content_attributes = JSONField()

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

    image_urls = JSONField()
    image_widths = JSONField()
    image_heights = JSONField()

    is_hidden = models.BooleanField(default=False)

    @classmethod
    def create(cls, flair, title, content_string, content_attributes, author, forum, image_urls, image_widths, image_heights):
        thread = cls.objects.create(flair=flair, title=title, content_string=content_string, content_attributes=content_attributes, author=author, forum=forum, image_urls=image_urls, image_widths=image_widths, image_heights=image_heights)
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
    is_hidden = models.BooleanField(default=False)

    @classmethod
    def create(cls, parent_thread, parent_post, content_string, content_attributes, author):
        comment = cls.objects.create(parent_thread=parent_thread, parent_post=parent_post, content_string=content_string, content_attributes=content_attributes, author=author)
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
        return self.content_string

class Report(models.Model):
    created = models.DateTimeField(default=now, editable=False)
    reportee = models.ForeignKey(User, on_delete=models.CASCADE)
    reported_thread = models.ForeignKey(Thread, on_delete=models.CASCADE, null=True, blank=True)
    reported_post = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)

    report_reason = models.TextField(max_length = 100)

    @classmethod
    def create(cls, reportee, reported_thread, reported_post, report_reason):
        report = cls.objects.create(reportee=reportee, reported_thread=reported_thread, reported_post=reported_post, report_reason=report_reason)


class UserProfile(models.Model):
    created = models.DateTimeField(default=now, editable=False)
    user = models.OneToOneField(User, related_name='userprofile', on_delete=models.CASCADE)
    followed_games = models.ManyToManyField(Game)

    is_banned = models.BooleanField(default=False)
    banned_until = models.DateTimeField(default=now, editable=True)

    blacklisted_user_profiles = models.ManyToManyField("self", symmetrical=False)
    hidden_threads = models.ManyToManyField(Thread)
    hidden_comments = models.ManyToManyField(Comment)

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

    def add_user_to_blacklist(self, user_profile):
        self.blacklisted_user_profiles.add(user_profile)
        self.save()
        return

    def remove_user_from_blacklist(self, user_profile):
        self.blacklisted_user_profiles.remove(user_profile)
        self.save()
        return

    def ban_user(self, ban_expiration_date):
        self.is_banned = True
        self.banned_until = ban_expiration_date
        self.save()
        return

    def unban_user(self):
        self.is_banned = False
        self.save()
        return

    def hide_thread(self, thread):
        self.hidden_threads.add(thread)
        self.save()
        return

    def unhide_thread(self, thread):
        self.hidden_threads.remove(thread)
        self.save()
        return

    def hide_comment(self, comment):
        self.hidden_comments.add(comment)
        self.save()
        return

    def unhide_comment(self, comment):
        self.hidden_comments.remove(comment)
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

    TYPE_DOWNVOTE = -1
    TYPE_UNVOTE = 0
    TYPE_UPVOTE = 1
    TYPE_DIRECTION = (
        (TYPE_DOWNVOTE, -1),
        (TYPE_UNVOTE, 0),
        (TYPE_UPVOTE, 1),
    )

    direction = models.IntegerField(
        choices=TYPE_DIRECTION,
        default=TYPE_UPVOTE,
    )

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)

    @classmethod
    def create(cls, user, direction, thread, comment):
        vote = cls.objects.create(user=user, direction=direction, thread=thread, comment=comment)
        return vote

    @classmethod
    def delete_thread_vote(cls, vote_id):
        vote = cls.objects.get(pk=vote_id)
        thread = vote.thread
        if vote.direction == 1:
            thread.decrement_upvotes()
        elif vote.direction == -1:
            thread.decrement_downvotes()
        else:
            print("Error should not be unvoted.", vote_id)

        vote.direction = 0
        vote.save()
        return thread

    @classmethod
    def delete_comment_vote(cls, vote_id):
        vote = cls.objects.get(pk=vote_id)
        comment = vote.comment
        if vote.direction == 1:
            comment.decrement_upvotes()
        else:
            comment.decrement_downvotes()
        vote.direction = 0
        vote.save()
        return comment

    def set_upvote(self):
        self.direction = 1
        self.save()
        return

    def set_downvote(self):
        self.direction = -1
        self.save()
        return

    def switch_vote_comment(self):
        if self.direction == 1:
            self.comment.switch_increment_downvotes()
        else:
            self.comment.switch_increment_upvotes()

        self.direction *= -1
        self.save()
        return self.comment

    def switch_vote_thread(self):
        if self.direction == 1:
            self.thread.switch_increment_downvotes()
        else:
            self.thread.switch_increment_upvotes()
        self.direction *= -1
        self.save()
        return self.thread

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        new_user = UserProfile.objects.create(user=instance)
        return

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