
from .models import Game, Genre, Developer, Forum, Thread, User, UserProfile, Group, Comment
from .serializers import GameSerializer, GenreSerializer, ThreadSerializer, ForumSerializer, DeveloperSerializer, \
    UserSerializer, UserProfileSerializer, GroupSerializer, CommentSerializer
from django_redis import get_redis_connection
from datetime import datetime, timedelta
from math import log
from time import mktime
import pytz, collections
from django_redis import get_redis_connection

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
        "created": convert_date_to_unix(game.release_date),
    }
    return data

def transform_thread_to_redis_object(thread):
    data = {
	    "id": thread.id,
	    "flair": thread.flair,
	    "title": thread.title,
	    "forum": thread.forum.id,
	    "num_childs": thread.num_childs,
        "num_subtree_nodes": thread.num_subtree_nodes,
	    "author": thread.author.id,
	    "upvotes": thread.upvotes,
	    "downvotes": thread.downvotes,
	    "content": thread.content,
	    "created": convert_datetime_to_unix(thread.created),
        "num_childs": thread.num_childs,
        "num_subtree_nodes": thread.num_subtree_nodes,
        "image_url": thread.image_url,
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
        "parent_thread": comment.parent_thread.id if comment.parent_thread != None else "",
        "parent_post": comment.parent_post.id if comment.parent_post != None else "",
        "num_childs": comment.num_childs,
        "num_subtree_nodes": comment.num_subtree_nodes,
    }

    return data

def transform_vote_to_redis_object(vote):
    data = {
        "id": vote.id,
        "created:": convert_datetime_to_unix(vote.created),
        "thread": vote.thread.id if vote.thread != None else "",
        "comment": vote.comment.id if vote.comment != None else "",
        "is_positive": "1" if vote.is_positive else "0",
    }

    return data

def redis_insert_games_bulk(games):
    for game in games:
        redis_insert_game(game)

def redis_insert_threads_bulk(threads):
    for thread in threads:
        redis_insert_thread(thread)

def redis_insert_comments_bulk(comments):
    for comment in comments:
        redis_insert_comment_choose(comment, True)

def redis_insert_comment_choose(comment, is_new):
    if comment.parent_thread != None:
        redis_insert_comment(comment, comment.parent_thread.id, is_new)
    else:
        redis_insert_child_comment(comment, is_new)

def redis_insert_votes_bulk(votes):
    for vote in votes:
        redis_insert_vote(vote)

def redis_insert_vote(vote):
    conn = get_redis_connection('default')
    redis_vote_object = transform_vote_to_redis_object(vote)
    conn.hmset("vote:" + str(vote.id), redis_vote_object)

    if vote.thread:
        conn.hset("vote:user:" + str(vote.user.id), "thread:" + str(vote.thread.id), str(vote.id))
    else:
        conn.hset("vote:user:" + str(vote.user.id), "comment:" + str(vote.comment.id), str(vote.id))

def redis_delete_vote(vote_id, user_id, is_thread, obj_id):
    conn = get_redis_connection('default')
    conn.delete("vote:" + str(vote_id))

    if is_thread:
        conn.hdel("vote:user:" + str(user_id), "thread:" + str(obj_id))
    else:
        conn.hdel("vote:user:" + str(user_id), "comment:" + str(obj_id))
    return

def redis_insert_game(game):
    conn = get_redis_connection('default')
    redis_game_object = transform_game_to_redis_object(game)
    conn.hmset("game:" + str(game.id), redis_game_object)

def redis_insert_thread(new_thread):
    redis_thread_object = transform_thread_to_redis_object(new_thread)
    conn = get_redis_connection('default')

    conn.hmset("thread:" + str(new_thread.id), redis_thread_object)
    conn.zadd("game:" + str(new_thread.forum.id) + ".ranking", {"thread:" + str(new_thread.id): hot(redis_thread_object["upvotes"], redis_thread_object["downvotes"], epoch_seconds(redis_thread_object["created"]))})

def redis_increment_tree_count_by_comment_id(new_comment_id):
    conn = get_redis_connection('default')  

    def find_parent(find_parent_new__comment_id):
        parent_thread_id = conn.hget("comment:" + str(find_parent_new__comment_id), "parent_thread").decode()
        parent_post_id = conn.hget("comment:" + str(find_parent_new__comment_id), "parent_post").decode()
        parent_thread_id = parent_thread_id if parent_thread_id != "" else None
        parent_post_id = parent_post_id if parent_post_id != "" else None
        return parent_thread_id, parent_post_id

    parent_thread_id, parent_post_id = find_parent(new_comment_id)
    if parent_thread_id:
        conn.hincrby("thread:" + str(parent_thread_id), "num_childs", 1)
    else:
        conn.hincrby("comment:" + str(parent_post_id), "num_childs", 1)

    while parent_thread_id or parent_post_id:
        if parent_thread_id:
            conn.hincrby("thread:" + str(parent_thread_id), "num_subtree_nodes", 1)
            break
        else:
            conn.hincrby("comment:" + str(parent_post_id), "num_subtree_nodes", 1)
            parent_thread_id, parent_post_id = find_parent(parent_post_id)
    return

def redis_insert_comment(new_comment, thread_id, is_new):
    redis_comment_object = transform_comment_to_redis_object(new_comment)
    conn = get_redis_connection('default')
    conn.hmset("comment:" + str(new_comment.id), redis_comment_object)
    conn.zadd("thread:" + str(thread_id) + ".ranking", {"comment:" + str(new_comment.id): epoch_seconds(redis_comment_object["created"])})
    if is_new:
        redis_increment_tree_count_by_comment_id(new_comment.id)

def redis_insert_child_comment(new_secondary_comment, is_new):
    parent_comment = new_secondary_comment.parent_post
    redis_comment_object = transform_comment_to_redis_object(new_secondary_comment)

    conn = get_redis_connection('default')
    conn.hmset("comment:" + str(new_secondary_comment.id), redis_comment_object)
    conn.zadd("comment:" + str(parent_comment.id) + ".ranking",
                  {"comment:" + str(new_secondary_comment.id): epoch_seconds(redis_comment_object["created"])})
    
    if is_new:
        redis_increment_tree_count_by_comment_id(new_secondary_comment.id)

def redis_thread_serializer(thread_response):
	decoded_response = {}
	for key, val in thread_response.items():
		if key.decode() != "created":
		    decoded_response[key.decode()] = val.decode()
		else:
		    decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz)

		if key.decode() in {"id", "author", "num_childs", "num_subtree_nodes", "upvotes", "downvotes", "flair"}:
		    decoded_response[key.decode()] = int(val.decode())

		# forum field in json response is nested, additional O(1) retrieve call required
		if key.decode() == "forum":
		    forum = Forum.objects.get(pk=int(val.decode()))
		    serializer = ForumSerializer(forum, many=False)
		    decoded_response[key.decode()] = serializer.data
	return decoded_response

def redis_vote_serializer(vote_response):
    decoded_response = {}
    for key, val in vote_response.items():
        if key.decode() != "created":
            decoded_response[key.decode()] = val.decode()
        else:
            decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz)

        if key.decode() in {"id", "thread", "comment", "user"}:
            if val.decode() != "":
                decoded_response[key.decode()] = int(val.decode())
            else:
                decoded_response[key.decode()] = None

        if key.decode() in {"is_positive"}:
            decoded_response[key.decode()] = val.decode() in {"1", "True"}

    return decoded_response


def redis_comment_serializer(comment_response):
    decoded_response = {}
    for key, val in comment_response.items():
        if key.decode() != "created":
            decoded_response[key.decode()] = val.decode()
        else:
            decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz)

        if key.decode() in {"id", "author", "num_childs", "num_subtree_nodes", "upvotes", "downvotes"}:
            decoded_response[key.decode()] = int(val.decode())
        elif key.decode() in {"parent_thread", "parent_post"}:
            if val.decode() == "":
                decoded_response[key.decode()] = None
            else:
                decoded_response[key.decode()] = int(val.decode())

    return decoded_response

def redis_get_threads_by_game_id(game_id, start, count, user_id):
    conn = get_redis_connection('default')
    encoded_threads = conn.zrevrange("game:" + str(game_id) + ".ranking", start, start + count - 1)
    serializer, vote_serializer = [], []
    has_next_page = (start + count - 1) < conn.zcard("game:" + str(game_id) + ".ranking")

    for encoded_thread in encoded_threads:
        decoded_thread = encoded_thread.decode()
        response = conn.hgetall(decoded_thread)
        serializer.append(redis_thread_serializer(response))

        vote_id_response = conn.hget("vote:user:" + str(user_id), "thread:" + str(decoded_thread.split(":")[1]))
        if vote_id_response != None:
            vote_response = conn.hgetall("vote:" + vote_id_response.decode())
            vote_serializer.append(redis_vote_serializer(vote_response))
        
    return serializer, has_next_page, vote_serializer

def redis_get_comments_by_thread_id(thread_id, start, count):
    conn = get_redis_connection('default')
    encoded_comments = conn.zrevrange("thread:" + str(thread_id) + ".ranking", start, start + count - 1)
    serializer = []

    for encoded_comment in encoded_comments:
        response = conn.hgetall(encoded_comment.decode())
        serializer.append(redis_comment_serializer(response))
    return serializer

def redis_get_comments_by_parent_comment_id(parent_comment_id, start, count):
    conn = get_redis_connection('default')
    encoded_comments = conn.zrevrange("comment:" + str(parent_comment_id) + ".ranking", start, start + count - 1)
    serializer = []

    for encoded_comment in encoded_comments:
        response = conn.hgetall(encoded_comment.decode())
        serializer.append(redis_comment_seiralizer(response))
    return serializer

def redis_get_tree_by_parent_comments_id(roots, size, next_page_start, count, parent_comment_id, user_id):
    conn = get_redis_connection('default')
    queue = collections.deque(roots[::-1])
    comments_to_be_added = []
    votes_to_be_added = []

    next_page_more_comments = conn.zrevrange("comment:" + str(parent_comment_id) + ".ranking", next_page_start + count, next_page_start + 2 * count - 1)

    while queue and size > 0:
        node = queue.pop()
        response = conn.hgetall("comment:" + str(node))
        comments_to_be_added.append(redis_comment_serializer(response))

        vote_id_response = conn.hget("vote:user:" + str(user_id), "comment:" + str(node))
        if vote_id_response != None:
            vote_response = conn.hgetall("vote:" + vote_id.decode())
            votes_to_be_added.append(redis_vote_serializer(vote_response))

        size -= 1
        if size == 0:
            break

        nested_encoded_comments = conn.zrevrange("comment:" + str(node) + ".ranking", 0, count - 1)
        for encoded_comment in nested_encoded_comments:
            _, comment_id = encoded_comment.decode().split(":")
            queue.appendleft(comment_id)

    more_comments_response = [redis_comment_serializer(conn.hgetall("comment:" + str(node))) for node in list(reversed(queue))]
    next_page_more_comments_response = [redis_comment_serializer(conn.hgetall(encoded_comment.decode())) for encoded_comment in next_page_more_comments]
    return comments_to_be_added, more_comments_response + next_page_more_comments_response, votes_to_be_added

def redis_get_tree_by_parent_thread_id(roots, size, next_page_start, count, parent_thread_id, user_id):
    conn = get_redis_connection('default')
    queue = []
    comments_to_be_added = []
    next_page_more_comments = []
    votes_to_be_added = []

    if next_page_start == 0:
        queue = collections.deque([int(encoded_comment.decode().split(":")[1]) for encoded_comment in conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", 0, count - 1)])
        next_page_more_comments = conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", count, count * 2 - 1)
    else:
        queue = collections.deque(roots[::-1])
        next_page_more_comments = conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", next_page_start + count, next_page_start + 2 * count - 1)

    while queue and size > 0:
        node = queue.pop()
        response = conn.hgetall("comment:" + str(node))
        comments_to_be_added.append(redis_comment_serializer(response))

        vote_id_response = conn.hget("vote:user:" + str(user_id), "comment:" + str(node))
        if vote_id_response != None:
            vote_response = conn.hgetall("vote:" + vote_id_response.decode())
            votes_to_be_added.append(redis_vote_serializer(vote_response))
        
        size -= 1
        if size == 0:
            break

        nested_encoded_comments = conn.zrevrange("comment:" + str(node) + ".ranking", 0, count - 1)
        for encoded_comment in nested_encoded_comments:
            _, comment_id = encoded_comment.decode().split(":")
            queue.appendleft(comment_id)

    more_comments_response = [redis_comment_serializer(conn.hgetall("comment:" + str(node))) for node in list(reversed(queue))]
    next_page_more_comments_response = [redis_comment_serializer(conn.hgetall(encoded_comment.decode())) for encoded_comment in next_page_more_comments]
    return comments_to_be_added, more_comments_response + next_page_more_comments_response, votes_to_be_added

def flush_redis():
    conn = get_redis_connection('default')
    conn.flushall()