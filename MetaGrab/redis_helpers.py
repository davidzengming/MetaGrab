
from .models import Game, Genre, Developer, Forum, Thread, User, UserProfile, Group, Comment, CommentSecondary
from .serializers import GameSerializer, GenreSerializer, ThreadSerializer, ForumSerializer, DeveloperSerializer, \
    UserSerializer, UserProfileSerializer, GroupSerializer, CommentSerializer, CommentSecondarySerializer
from django_redis import get_redis_connection
from datetime import datetime, timedelta
from math import log
from time import mktime
import pytz

epoch_seconds_1970 = datetime(1970, 1, 1, 0, 0).timestamp()
tz = pytz.timezone('America/Toronto')

def convert_datetime_to_unix(date):
    return date.timestamp()

def convert_date_to_unix(date):
    return int(mktime(date.timetuple()))

def score(ups, downs):
    return ups - downs

def epoch_seconds(date_seconds):
    return date_seconds - epoch_seconds_1970

def hot(ups, downs, date_seconds):
    s = score(ups, downs)
    order = log(max(abs(s), 1), 10)
    sign = 1 if s > 0 else -1 if s < 0 else 0
    seconds = epoch_seconds(date_seconds) - (1567363566)  # 1567363566 is Sept 1, 2019
    return round(sign * order + seconds / 21600, 7)  # 10x upvotes to match 21600 = 6 hours


def transform_game_to_redis_object(game):
    data = {
        "id": game.id,
        "name": game.name,
        "created": convert_date_to_unix(game.release_date)
    }
    return data

def transform_thread_to_redis_object(thread):
    data = {
	    "id": thread.id,
	    "flair": thread.flair,
	    "title": thread.title,
	    "forum": thread.forum.id,
	    "num_comments": thread.num_comments,
	    "author": thread.author.id,
	    "upvotes": thread.upvotes,
	    "downvotes": thread.downvotes,
	    "content": thread.content,
	    "created": convert_datetime_to_unix(thread.created)
    }

    return data

def transform_comment_to_redis_object(comment):
    data = {
        "id": comment.id,
        "upvotes": comment.upvotes,
        "downvotes": comment.downvotes,
        "created": convert_datetime_to_unix(comment.created),
        "content": comment.content,
        "author": comment.author.id,
        "parent_thread": comment.parent_thread.id
    }

    return data

def transform_sec_comment_to_redis_object(comment):
    data = {
        "id": comment.id,
        "upvotes": comment.upvotes,
        "downvotes": comment.downvotes,
        "created": convert_datetime_to_unix(comment.created),
        "content": comment.content,
        "author": comment.author.id,
        "parent_post": comment.parent_post.id
    }
    return data

def redis_thread_serializer(thread_response):
	decoded_response = {}
	for key, val in thread_response.items():
		if key.decode() != "created":
		    decoded_response[key.decode()] = val.decode()
		else:
		    decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz)

		if key.decode() in {"id", "author", "num_comments", "upvotes", "downvotes"}:
		    decoded_response[key.decode()] = int(val.decode())

		# forum field in json response is nested, additional O(1) retrieve call required
		if key.decode() == "forum":
		    forum = Forum.objects.get(pk=int(val.decode()))
		    serializer = ForumSerializer(forum, many=False)
		    decoded_response[key.decode()] = serializer.data
	return decoded_response

def redis_comment_serializer(comment_response):
    decoded_response = {}
    for key, val in comment_response.items():
        if key.decode() != "created":
            decoded_response[key.decode()] = val.decode()
        else:
            decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz)

        if key.decode() in {"id", "author", "num_comments", "upvotes", "downvotes", "parent_thread", "parent_post"}:
            decoded_response[key.decode()] = int(val.decode())

    return decoded_response