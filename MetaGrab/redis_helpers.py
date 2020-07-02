
from .models import Game, Genre, Developer, Forum, Thread, User, UserProfile, Group, Comment
from .serializers import GameSerializer, GenreSerializer, ThreadSerializer, ForumSerializer, DeveloperSerializer, \
	UserSerializer, UserProfileSerializer, GroupSerializer, CommentSerializer
from django_redis import get_redis_connection
from datetime import datetime, timedelta
from math import log
from time import mktime
import pytz, collections
from django_redis import get_redis_connection
import json
import time
from . import redis_sub_operations

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
	sign = 1 if s > 0 else -1 if s < 0 else 0
	order = log(max(abs(s), 1), 10)
	seconds = epoch_seconds(date_seconds) - (1567363566)  # 1567363566 is Sept 1, 2019
	return round(sign * order + seconds / 21600, 7)  # 10x upvotes to match 21600 = 6 hours

def transform_game_to_redis_object(game):
	data = {
		"id": game.id,
		"name": game.name,
		"created": convert_datetime_to_unix(game.created),
		"release_date": convert_date_to_unix(game.release_date),
		"next_expansion_release_date": convert_date_to_unix(game.next_expansion_release_date) if game.next_expansion_release_date else "",
		"banner": game.banner,
		"icon": game.icon,
		"developer": game.developer.id,
		"genre": game.genre.id,
		"last_updated": convert_date_to_unix(game.last_updated),
		"game_summary": game.game_summary,
	}
	return data

def transform_developer_to_redis_object(developer):
	data = {
		"id": developer.id,
		"created": convert_datetime_to_unix(developer.created),
		"name": developer.name
	}
	return data

def transform_genre_to_redis_object(genre):
	data = {
		"id": genre.id,
		"created": convert_datetime_to_unix(genre.created),
		"name": genre.name,
		"long_name": genre.long_name
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
		"content_string": thread.content_string,
		"content_attributes": json.dumps(thread.content_attributes),
		"created": convert_datetime_to_unix(thread.created),
		"num_childs": thread.num_childs,
		"num_subtree_nodes": thread.num_subtree_nodes,
		"image_urls": json.dumps(thread.image_urls),
		"is_hidden": "1" if thread.is_hidden == True else "0",
	}

	return data

def transform_comment_to_redis_object(comment):
	data = {
		"id": comment.id,
		"upvotes": comment.upvotes,
		"downvotes": comment.downvotes,
		"created": convert_datetime_to_unix(comment.created),
		"content_string": comment.content_string,
		"content_attributes": json.dumps(comment.content_attributes),
		"author": comment.author.id,
		"parent_thread": comment.parent_thread.id if comment.parent_thread != None else "",
		"parent_post": comment.parent_post.id if comment.parent_post != None else "",
		"num_childs": comment.num_childs,
		"num_subtree_nodes": comment.num_subtree_nodes,
		"is_hidden": "1" if comment.is_hidden == True else "0",
	}

	return data

def transform_vote_to_redis_object(vote):
	data = {
		"id": vote.id,
		"created": convert_datetime_to_unix(vote.created),
		"thread": vote.thread.id if vote.thread != None else "",
		"comment": vote.comment.id if vote.comment != None else "",
		"direction": vote.direction,
	}

	return data

def transform_user_to_redis_object(user):
	data = {
		"id": user.id,
		"created": convert_datetime_to_unix(user.created),
		"username": user.user.username,
		"is_banned": "1" if user.is_banned == True else "0",
		"banned_until": convert_datetime_to_unix(user.banned_until)
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
		redis_insert_comment_choose(comment, False)

def redis_insert_users_bulk(users):
	for user in users:
		redis_insert_user(user)

def redis_insert_comment_choose(comment, is_new):
	if comment.parent_thread != None:
		return redis_insert_comment(comment, comment.parent_thread.id, is_new)
	else:
		return redis_insert_child_comment(comment, is_new)

def redis_insert_votes_bulk(votes):
	for vote in votes:
		is_thread = (vote.comment == None)

		if is_thread:
			redis_insert_vote(vote, vote.thread.id, None)
		else:
			redis_insert_vote(vote, None, vote.comment.id)

def redis_insert_vote(vote, thread_id, comment_id):
	conn = get_redis_connection('default')
	redis_vote_object = transform_vote_to_redis_object(vote)
	conn.hmset("vote:" + str(vote.id), redis_vote_object)

	should_add_emoji = False if vote.direction == 0 else True

	if vote.thread:
		conn.hset("vote:user:" + str(vote.user.id), "thread:" + str(vote.thread.id), str(vote.id))

		if should_add_emoji:
			redis_add_emoji_by_thread_and_user_id(0 if vote.direction == 1 else 1, thread_id, vote.user.id)
	else:
		conn.hset("vote:user:" + str(vote.user.id), "comment:" + str(vote.comment.id), str(vote.id))

		if should_add_emoji:
			redis_add_emoji_by_comment_and_user_id(0 if vote.direction == 1 else 1, comment_id, vote.user.id)

	return redis_vote_serializer(conn.hgetall("vote:" + str(vote.id)))

def redis_insert_user(user):
	conn = get_redis_connection('default')
	redis_user_object = transform_user_to_redis_object(user)
	conn.hmset("user:" + str(user.id), redis_user_object)


def redis_get_game_list_at_epoch_time(time_point_in_epoch, count):
	conn = get_redis_connection('default')

	before_games_arr, before_scores = redis_get_game_list_by_before_epoch_time(time_point_in_epoch + 1, count)
	after_games_arr, after_scores = redis_get_game_list_by_after_epoch_time(time_point_in_epoch, count)

	return before_games_arr[::-1] + after_games_arr, before_scores[::-1] + after_scores


def redis_get_game_list_by_before_epoch_time(time_point_in_epoch, count):
	conn = get_redis_connection('default')

	# zrevrangebyscore(name, max, min, start=None, num=None, withscores=False, score_cast_func=<type 'float'>)

	encoded_games_with_scores = []
	encoded_games_with_scores = conn.zrevrangebyscore("game_timeline", time_point_in_epoch - 1, -float("inf"), 0, count, withscores=True)

	games_arr = []
	scores = []

	last_score = None
	seen_encoded_games = set()

	for encoded_game, score in encoded_games_with_scores:
		serialized_game = redis_game_serializer(conn.hgetall(encoded_game.decode()))
		seen_encoded_games.add(encoded_game)
		games_arr.append(serialized_game)
		scores.append(score)
		last_score = score
	
	if last_score != None:
		games_with_last_score = conn.zrevrangebyscore("game_timeline", last_score, last_score, withscores=True)
		for encoded_game, _ in encoded_games_with_scores:
			if encoded_game in seen_encoded_games:
				continue

			serialized_game = redis_game_serializer(conn.hgetall(encoded_game.decode()))
			game_arr.append(serialized_game)
			scores.append(last_score)

	return games_arr, scores


def redis_get_game_list_by_after_epoch_time(time_point_in_epoch, count):
	conn = get_redis_connection('default')

	encoded_games_with_scores = conn.zrangebyscore("game_timeline", time_point_in_epoch + 1, float("inf"), 0, count, withscores=True)
	
	games_arr = []
	scores = []

	last_score = None
	seen_encoded_games = set()

	for encoded_game, score in encoded_games_with_scores:
		serialized_game = redis_game_serializer(conn.hgetall(encoded_game.decode()))
		seen_encoded_games.add(encoded_game)
		games_arr.append(serialized_game)
		scores.append(score)
		last_score = score
	
	if last_score != None:
		games_with_last_score = conn.zrangebyscore("game_timeline", last_score, last_score, withscores=True)
		for encoded_game, _ in games_with_last_score:
			if encoded_game in seen_encoded_games:
				continue

			serialized_game = redis_game_serializer(conn.hgetall(encoded_game.decode()))
			game_arr.append(serialized_game)
			scores.append(last_score)

	return games_arr, scores

def redis_get_blacklisted_user_ids_by_user_id(user_id):
	conn = get_redis_connection('default')

	encoded_blacklisted_user_ids = conn.smembers("blacklisted_ids:user:" + str(user_id))
	serializer = []

	for encoded_blacklisted_user_id in encoded_blacklisted_user_ids:
		decoded_blacklisted_user_id = encoded_blacklisted_user_id.decode()
		serializer.append(decoded_blacklisted_user_id)

	return serializer

def redis_get_blacklisted_users_by_user_id(user_id):
	conn = get_redis_connection('default')

	encoded_blacklisted_user_ids = conn.smembers("blacklisted_ids:user:" + str(user_id))
	serializer = []

	for encoded_blacklisted_user_id in encoded_blacklisted_user_ids:
		decoded_blacklisted_user_id = encoded_blacklisted_user_id.decode()
		blacklisted_user = conn.hgetall("user:" + decoded_blacklisted_user_id)

		serializer.append(redis_user_serializer(blacklisted_user))

	return serializer

def redis_get_hidden_thread_ids_by_user_id(user_id):
	conn = get_redis_connection('default')

	encoded_hidden_thread_ids = conn.smembers("hidden_thread_ids:user:" + str(user_id))
	serializer = []

	for encoded_hidden_thread_id in encoded_hidden_thread_ids:
		decoded_hidden_thread_id = encoded_hidden_thread_id.decode()
		serializer.append(int(decoded_hidden_thread_id))

	return serializer

def redis_get_hidden_threads_by_user_id(user_id):
	conn = get_redis_connection('default')

	encoded_hidden_thread_ids = conn.smembers("hidden_thread_ids:user:" + str(user_id))
	serializer = []

	for encoded_hidden_thread_id in encoded_hidden_thread_ids:
		decoded_hidden_thread_id = encoded_hidden_thread_id.decode()

		thread = conn.hgetall("thread:" + decoded_hidden_thread_id)
		serializer.append(redis_thread_serializer(thread))

	return serializer

def redis_get_hidden_comment_ids_by_user_id(user_id):
	conn = get_redis_connection('default')

	encoded_hidden_comment_ids = conn.smembers("hidden_comment_ids:user:" + str(user_id))
	serializer = []

	for encoded_hidden_comment_id in encoded_hidden_comment_ids:
		decoded_hidden_comment_id = encoded_hidden_comment_id.decode()
		serializer.append(int(decoded_hidden_comment_id))

	return serializer

def redis_get_hidden_comments_by_user_id(user_id):
	conn = get_redis_connection('default')

	encoded_hidden_comment_ids = conn.smembers("hidden_comment_ids:user:" + str(user_id))
	serializer = []

	for encoded_hidden_comment_id in encoded_hidden_comment_ids:
		decoded_hidden_comment_id = encoded_hidden_comment_id.decode()

		comment = conn.hgetall("comment:" + decoded_hidden_comment_id)
		serializer.append(redis_comment_serializer(comment))

	return serializer

def redis_add_blacklisted_user_by_user_id(user_id, blacklisted_user_id):
	conn = get_redis_connection('default')
	conn.sadd("blacklisted_ids:user:" + str(user_id), str(blacklisted_user_id))

def redis_remove_blacklisted_user_by_user_id(user_id, blacklisted_user_id):
	conn = get_redis_connection('default')
	conn.srem("blacklisted_ids:user:" + str(user_id), str(blacklisted_user_id))

def redis_hide_thread_by_user_id(user_id, thread_id):
	conn = get_redis_connection('default')
	conn.sadd("hidden_thread_ids:user:" + str(user_id), str(thread_id))

def redis_unhide_thread_by_user_id(user_id, thread_id):
	conn = get_redis_connection('default')
	conn.srem("hidden_thread_ids:user:" + str(user_id), str(thread_id))

def redis_hide_comment_by_user_id(user_id, comment_id):
	conn = get_redis_connection('default')
	conn.sadd("hidden_comment_ids:user:" + str(user_id), str(comment_id))

def redis_unhide_comment_by_user_id(user_id, comment_id):
	conn = get_redis_connection('default')
	conn.srem("hidden_comment_ids:user:" + str(user_id), str(comment_id))

def redis_unvote(vote_id, thread_id, comment_id, user_id, original_vote_direction):
	conn = get_redis_connection('default')
	conn.hset("vote:" + str(vote_id), "direction", "0")

	if thread_id != None:
		is_success, count = redis_remove_emoji_by_thread_and_user_id(0 if original_vote_direction == 1 else 1, thread_id, user_id)
	else:
		is_success, count = redis_remove_emoji_by_comment_and_user_id(0 if original_vote_direction == 1 else 1, comment_id, user_id)
	return

def redis_set_upvote(vote_id, thread_id, comment_id, user_id):
	conn = get_redis_connection('default')
	conn.hset("vote:" + str(vote_id), "direction", "1")

	if thread_id != None:
		is_success, count = redis_add_emoji_by_thread_and_user_id(0, thread_id, user_id)
	else:
		is_success, count = redis_add_emoji_by_comment_and_user_id(0, comment_id, user_id)

	return

def redis_set_downvote(vote_id, thread_id, comment_id, user_id):
	conn = get_redis_connection('default')
	conn.hset("vote:" + str(vote_id), "direction", "-1")

	if thread_id != None:
		is_success, count = redis_add_emoji_by_thread_and_user_id(1, thread_id, user_id)
	else:
		is_success, count = redis_add_emoji_by_comment_and_user_id(1, comment_id, user_id)

	return

def redis_flip_upvote_to_downvote(vote_id, thread_id, comment_id, user_id):
	conn = get_redis_connection('default')
	conn.hset("vote:" + str(vote_id), "direction", "-1")

	if thread_id != None:
		redis_remove_emoji_by_thread_and_user_id(0, thread_id, user_id)
		redis_add_emoji_by_thread_and_user_id(1, thread_id, user_id)
	else:
		redis_remove_emoji_by_comment_and_user_id(0, comment_id, user_id)
		redis_add_emoji_by_comment_and_user_id(1, comment_id, user_id)

def redis_flip_downvote_to_upvote(vote_id, thread_id, comment_id, user_id):
	conn = get_redis_connection('default')
	conn.hset("vote:" + str(vote_id), "direction", "1")

	if thread_id != None:
		redis_remove_emoji_by_thread_and_user_id(1, thread_id, user_id)
		redis_add_emoji_by_thread_and_user_id(0, thread_id, user_id)
	else:
		redis_remove_emoji_by_comment_and_user_id(1, comment_id, user_id)
		redis_add_emoji_by_comment_and_user_id(0, comment_id, user_id)

def redis_insert_visited_game_by_user_id(user_id, game_id):
	conn = get_redis_connection('default')
	conn.zadd("game_visit_history:user:" + str(user_id), {"game:" + str(game_id): time.time()})

	max_game_history_limit = 10
	if conn.zcard("game_visit_history:user:" + str(user_id)) > max_game_history_limit:
		conn.zpopmin("game_visit_history:user:" + str(user_id))

	return True

def redis_get_game_history_by_user_id(user_id):
	conn = get_redis_connection('default')

	encoded_follow_games = conn.smembers("follow_games_user:" + str(user_id))
	encoded_games = conn.zrevrange("game_visit_history:user:" + str(user_id), 0, -1)

	decoded_game_arr = []
	for encoded_game in encoded_games:

		serialized_game = redis_game_serializer(conn.hgetall("game:" + str(int(encoded_game.decode().split(":")[1]))))
		
		# if encoded_game in encoded_follow_games:
		# 	serialized_game["is_followed"] = True

		# serialized_game['thread_count'] = conn.zcard(encoded_game.decode() + ".ranking")
		# serialized_game['follower_count'] = redis_get_game_followers_count(encoded_game.decode().split(":")[1])
		decoded_game_arr.append(serialized_game)

	return decoded_game_arr


def redis_get_game_list_by_genre_id_range(genre_id, start, count):
	conn = get_redis_connection('default')
	has_next_page = False

	games_arr = []

	encoded_game_ids = conn.lrange("genre_game_list:" + str(genre_id), start, start + count - 1)
	for encoded_game_id in encoded_game_ids:

		games_arr.append(redis_game_serializer(conn.hgetall(encoded_game_id.decode())))

	if (start + count) < conn.llen("genre_game_list:" + str(genre_id)):
		has_next_page = True

	return games_arr, has_next_page

def redis_get_genres_by_range(start, count):
	conn = get_redis_connection('default')
	has_next_page = False

	genre_arr = []
	encoded_genre_ids = conn.lrange("genres", start, start + count - 1)
	for encoded_genre_id in encoded_genre_ids:

		genre_arr.append(redis_genre_serializer(conn.hgetall(encoded_genre_id.decode())))

	if (start + count - 1) < conn.llen("genres"):
		has_next_page = True

	return genre_arr, has_next_page


def redis_get_forum_stats(game_id, user_id):
	conn = get_redis_connection('default')

	is_followed = conn.sismember("game_followers:" + str(game_id), "user:" + str(user_id))
	follower_count = conn.scard("game_followers:" + str(game_id))
	thread_count = conn.zcard("game:" + str(game_id) + ".ranking")

	return is_followed, follower_count, thread_count

def redis_insert_game(game):
	redis_insert_developer(game.developer)
	redis_insert_genre(game.genre)

	conn = get_redis_connection('default')
	redis_game_object = transform_game_to_redis_object(game)
	conn.hmset("game:" + str(game.id), redis_game_object)
	# conn.zadd("game_release_timeline:year:" + str(game.release_date.year) + "month:" + str(game.release_date.month), {"game:" + str(game.id): game.release_date.day})
	conn.zadd("game_timeline", {"game:" + str(game.id): convert_date_to_unix(game.release_date)})
	conn.rpush("genre_game_list:" + str(game.genre.id), "game:" + str(game.id))
	return redis_game_serializer(conn.hgetall("game:" + str(game.id)))

def redis_insert_developer(developer):
	conn = get_redis_connection('default')
	redis_developer_object = transform_developer_to_redis_object(developer)
	conn.hmset("developer:" + str(developer.id), redis_developer_object)
	return redis_developer_serializer(conn.hgetall("developer:" + str(developer.id)))

def redis_insert_genre(genre):
	conn = get_redis_connection('default')
	redis_genre_object = transform_genre_to_redis_object(genre)
	conn.hmset("genre:" + str(genre.id), redis_genre_object)

	conn.rpush("genres", "genre:" + str(genre.id))
	return redis_genre_serializer(conn.hgetall("genre:" + str(genre.id)))

def redis_insert_thread(new_thread):
	redis_thread_object = transform_thread_to_redis_object(new_thread)
	conn = get_redis_connection('default')
	conn.hmset("thread:" + str(new_thread.id), redis_thread_object)
	conn.zadd("game:" + str(new_thread.forum.id) + ".ranking", {"thread:" + str(new_thread.id): hot(redis_thread_object["upvotes"], redis_thread_object["downvotes"], epoch_seconds(redis_thread_object["created"]))})
	return redis_thread_serializer(conn.hgetall("thread:" + str(new_thread.id)))

def redis_increment_tree_count_by_comment_id(new_comment_id):
	conn = get_redis_connection('default')

	def find_parent(find_parent_new_comment_id):
		parent_thread_id = conn.hget("comment:" + str(find_parent_new_comment_id), "parent_thread").decode()
		parent_post_id = conn.hget("comment:" + str(find_parent_new_comment_id), "parent_post").decode()
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
	return redis_comment_serializer(conn.hgetall("comment:" + str(new_comment.id)))

def redis_insert_child_comment(new_secondary_comment, is_new):
	parent_comment = new_secondary_comment.parent_post
	redis_comment_object = transform_comment_to_redis_object(new_secondary_comment)

	conn = get_redis_connection('default')
	conn.hmset("comment:" + str(new_secondary_comment.id), redis_comment_object)
	conn.zadd("comment:" + str(parent_comment.id) + ".ranking",
				  {"comment:" + str(new_secondary_comment.id): epoch_seconds(redis_comment_object["created"])})
	
	if is_new:
		redis_increment_tree_count_by_comment_id(new_secondary_comment.id)

	return redis_comment_serializer(conn.hgetall("comment:" + str(new_secondary_comment.id)))

def redis_add_emoji_by_thread_and_user_id(emoji_id, thread_id, user_id):
	conn = get_redis_connection('default')

	if conn.zrank("thread:" + str(thread_id) + ":emojis", "emoji:" + str(emoji_id)) == None and conn.zcard("thread:" + str(thread_id) + ":emojis") == 10:
		return False, None

	conn.zadd("thread:" + str(thread_id) + ":emojis", {"emoji:" + str(emoji_id): time.time()}, True)
	conn.zadd("thread:" + str(thread_id) + ":emoji:" + str(emoji_id) + ":users", {"user:" + str(user_id): time.time()})

	return True, conn.zcard("thread:" + str(thread_id) + ":emoji:" + str(emoji_id) + ":users")

def redis_remove_emoji_by_thread_and_user_id(emoji_id, thread_id, user_id):
	conn = get_redis_connection('default')

	conn.zrem("thread:" + str(thread_id) + ":emoji:" + str(emoji_id) + ":users", "user:" + str(user_id))

	emoji_count = conn.zcard("thread:" + str(thread_id) + ":emoji:" + str(emoji_id) + ":users")
	if emoji_count == 0:
		conn.zrem("thread:" + str(thread_id) + ":emojis", "emoji:" + str(emoji_id))

	return True, emoji_count

def redis_add_emoji_by_comment_and_user_id(emoji_id, comment_id, user_id):
	conn = get_redis_connection('default')

	if conn.zcard("comment:" + str(comment_id) + ":emojis") == 10:
		return False, None

	conn.zadd("comment:" + str(comment_id) + ":emojis", {"emoji:" + str(emoji_id): time.time()}, True)
	conn.zadd("comment:" + str(comment_id) + ":emoji:" + str(emoji_id) + ":users", {"user:" + str(user_id): time.time()})

	return True, conn.zcard("comment:" + str(comment_id) + ":emoji:" + str(emoji_id) + ":users")

def redis_remove_emoji_by_comment_and_user_id(emoji_id, comment_id, user_id):
	conn = get_redis_connection('default')
	conn.zrem("comment:" + str(comment_id) + ":emoji:" + str(emoji_id) + ":users", "user:" + str(user_id))

	emoji_count = conn.zcard("comment:" + str(comment_id) + ":emoji:" + str(emoji_id) + ":users")
	if emoji_count == 0:
		conn.zrem("comment:" + str(comment_id) + ":emojis", "emoji:" + str(emoji_id))

	return True, emoji_count

def redis_thread_serializer(thread_response):
	decoded_response = {}

	for key, val in thread_response.items():
		decoded_key = key.decode()
		if decoded_key in transformer_dict:
			decoded_response[decoded_key] = transformer_dict[decoded_key](val.decode())
		else:
			decoded_response[decoded_key] = val.decode()

	return decoded_response

def redis_vote_serializer(vote_response):
	decoded_response = {}
	for key, val in vote_response.items():
		decoded_key = key.decode()
		if decoded_key in transformer_dict:
			decoded_response[decoded_key] = transformer_dict[decoded_key](val.decode())
		else:
			decoded_response[decoded_key] = val.decode()

	return decoded_response

def redis_game_serializer(game_response):
	decoded_response = {}
	for key, val in game_response.items():
		decoded_key = key.decode()
		if decoded_key in transformer_dict:
			decoded_response[decoded_key] = transformer_dict[decoded_key](val.decode())
		else:
			decoded_response[decoded_key] = val.decode()

	return decoded_response

def redis_genre_serializer(genre_response):
	decoded_response = {}
	for key, val in genre_response.items():
		decoded_key = key.decode()
		if decoded_key in transformer_dict:
			decoded_response[decoded_key] = transformer_dict[decoded_key](val.decode())
		else:
			decoded_response[decoded_key] = val.decode()
	return decoded_response

def redis_developer_serializer(developer_response):
	decoded_response = {}
	for key, val in developer_response.items():
		decoded_key = key.decode()
		if decoded_key in transformer_dict:
			decoded_response[decoded_key] = transformer_dict[decoded_key](val.decode())
		else:
			decoded_response[decoded_key] = val.decode()
	return decoded_response

def redis_comment_serializer(comment_response):
	decoded_response = {}
	for key, val in comment_response.items():
		decoded_key = key.decode()

		if decoded_key in transformer_dict:
			decoded_response[decoded_key] = transformer_dict[decoded_key](val.decode())
		else:
			decoded_response[decoded_key] = val.decode()

	return decoded_response

def redis_user_serializer(user_response):
	decoded_response = {}

	for key, val in user_response.items():
		decoded_key = key.decode()

		if decoded_key in transformer_dict:
			decoded_response[decoded_key] = transformer_dict[decoded_key](val.decode())
		else:
			decoded_response[decoded_key] = val.decode()
	return decoded_response

def redis_follow_game(user, game):
	conn = get_redis_connection('default')
	conn.sadd("follow_games_user:" + str(user.id), "game:" + str(game.id))
	conn.sadd("game_followers:" + str(game.id), "user:" + str(user.id))

	return

def redis_unfollow_game(user, game):
	conn = get_redis_connection('default')
	conn.srem("follow_games_user:" + str(user.id), "game:" + str(game.id))
	conn.srem("game_followers:" + str(game.id), "user:" + str(user.id))

	return

def redis_get_user_follow_games(user):
	conn = get_redis_connection('default')
	encoded_games = conn.smembers("follow_games_user:" + str(user.id))
	serializer = []

	for encoded_game in encoded_games:
		decoded_game = encoded_game.decode()
		response = conn.hgetall(decoded_game)
		# response['is_followed'] = True
		# response['thread_count'] = conn.zcard(decoded_game + ".ranking")
		# response['follower_count'] = redis_get_game_followers_count(decoded_game.split(":")[1])

		serializer.append(redis_game_serializer(response))

	return serializer

def redis_get_game_followers_count(game_id):
	conn = get_redis_connection('default')

	return conn.scard("game_followers:" + str(game_id))

def redis_get_user_by_id(id):
	conn = get_redis_connection('default')
	return redis_user_serializer(conn.hgetall("user:" + str(id)))

def redis_get_developer_by_id(id):
	conn = get_redis_connection('default')
	return redis_developer_serializer(conn.hgetall("developer:" + str(id)))

def redis_get_genre_by_id(id):
	conn = get_redis_connection('default')
	return redis_genre_serializer(conn.hgetall("genre:" + str(id)))

transformer_dict = {
	# thread
	"created": redis_sub_operations.get_date_time,
	"id": redis_sub_operations.convert_to_int,
	"author": redis_sub_operations.convert_to_int,
	"num_childs": redis_sub_operations.convert_to_int,
	"num_subtree_nodes": redis_sub_operations.convert_to_int,
	"upvotes": redis_sub_operations.convert_to_int,
	"downvotes": redis_sub_operations.convert_to_int,
	"flair": redis_sub_operations.convert_to_int,
	"forum": redis_sub_operations.convert_to_int,
	"is_hidden": redis_sub_operations.convert_to_bool,
	"content_attributes": redis_sub_operations.convert_to_json,
	"image_urls": redis_sub_operations.convert_to_json,

	#vote
	"thread": redis_sub_operations.convert_to_int,
	"comment": redis_sub_operations.convert_to_int,
	"user": redis_sub_operations.convert_to_int,
	"direction": redis_sub_operations.convert_to_int,

	#game
	"next_expansion_release_date": redis_sub_operations.get_date_time,
	"release_date": redis_sub_operations.get_date_time,
	"last_updated": redis_sub_operations.get_date_time,
	"developer": redis_get_developer_by_id,
	"genre": redis_get_genre_by_id,

	#comment
	"parent_thread": redis_sub_operations.convert_to_int,
	"parent_post": redis_sub_operations.convert_to_int,

	#user
	"banned_until": redis_sub_operations.get_date_time,
	"is_banned": redis_sub_operations.convert_to_bool,
}

def redis_get_all_games():
	conn = get_redis_connection('default')
	encoded_games = conn.lrange("games", 0, -1)
	serializer = []

	for encoded_game in encoded_games:
		decoded_game = encoded_game.decode()
		response = conn.hgetall(decoded_game)
		response['thread_count'] = conn.zcard(decoded_game + ".ranking")

		response['follower_count'] = redis_get_game_followers_count(decoded_game.split(":")[1])
		serializer.append(redis_game_serializer(response))

	return serializer

def redis_get_games_by_release_range(start_year, start_month, end_year, end_month):
	conn = get_redis_connection('default')

	encoded_games = []

	for month in range(start_month, 13):
		month_games = conn.zrevrange("game_release_timeline:year:" + str(start_year) + "month:" + str(month))
		encoded_games += month_games

	for month in range(0, end_month + 1):
		month_games = conn.zrevrange("game_release_timeline:year:" + str(start_year) + "month:" + str(month))
		encoded_games += month_games

	for year in range(start_year + 1, end_year):
		for month in range(12):
			month_games = conn.zrevrange("game_release_timeline:year:" + str(year) + "month:" + str(month))
			encoded_games += month_games
	
	serializer = []
	for encoded_game in encoded_games:
		decoded_game = encoded_game.decode()
		response = conn.hgetall(decoded_game)
		response['thread_count'] = conn.zcard(decoded_game + ".ranking")
		response['follower_count'] = redis_get_game_followers_count(decoded_game.split(":")[1])

		serializer.append(redis_game_serializer(response))

	return serializer

def redis_generate_emojis_response(decoded_prefix, seen_users, user_id):
	def get_author(encoded_author):
		decoded_author = encoded_author.decode().split(":")[1]
		if decoded_author in seen_users:
			return [seen_users[decoded_author]]

		user_serializer = []
		user_response = conn.hgetall("user:" + decoded_author)

		seen_users[decoded_author] = redis_user_serializer(user_response)
		user_serializer.append(seen_users[decoded_author])

		return user_serializer

	conn = get_redis_connection('default')
	encoded_emojis = conn.zrange(str(decoded_prefix) + ":emojis", 0, 9)
		
	user_arr_per_emoji_dict = collections.defaultdict(list)

	emojis_id_arr = []
	emoji_reaction_count_dict = {}

	did_react_to_emoji_dict = {}

	for encoded_emoji in encoded_emojis:
		decoded_emoji = encoded_emoji.decode()
		emoji_id = int(decoded_emoji.split(":")[1])
		emojis_id_arr.append(emoji_id)
		
		top_3_encoded_users_reacted_with_emoji = conn.zrange(decoded_prefix + ":emoji:" + str(emoji_id) + ":users", 0, 2)

		emoji_reaction_count = conn.zcard(decoded_prefix + ":emoji:" + str(emoji_id) + ":users")
		emoji_reaction_count_dict[emoji_id] = emoji_reaction_count

		user_exists_in_reaction = conn.zscore(decoded_prefix + ":emoji:" + str(emoji_id) + ":users", "user:" + str(user_id))
		if user_exists_in_reaction != None:
			did_react_to_emoji_dict[emoji_id] = True
		else:
			did_react_to_emoji_dict[emoji_id] = False

		for encoded_user in top_3_encoded_users_reacted_with_emoji:
			reacted_user = get_author(encoded_user)[0]
			user_arr_per_emoji_dict[emoji_id].append(reacted_user)

	return emojis_id_arr, user_arr_per_emoji_dict, emoji_reaction_count_dict, did_react_to_emoji_dict, seen_users

def redis_get_threads_by_game_id(game_id, start, count, user_id, blacklisted_user_ids, hidden_thread_ids):

	seen_users = {}

	def get_author(encoded_author):
		decoded_author = encoded_author.decode()
		if decoded_author in seen_users:
			return [seen_users[decoded_author]]

		user_serializer = []
		user_response = conn.hgetall("user:" + decoded_author)

		seen_users[decoded_author] = redis_user_serializer(user_response)
		user_serializer.append(seen_users[decoded_author])
		return user_serializer

	def get_vote(vote_id_response):
		vote_serializer = []
		if vote_id_response != None:
			vote_response = conn.hgetall("vote:" + vote_id_response.decode())
			vote_serializer.append(redis_vote_serializer(vote_response))
		return vote_serializer


	conn = get_redis_connection('default')
	encoded_threads = conn.zrevrange("game:" + str(game_id) + ".ranking", start, start + count - 1)
	serializer = []
	has_next_page = (start + count - 1) < conn.zcard("game:" + str(game_id) + ".ranking")

	encoded_authors = set()
	hidden_thread_ids_set = set(hidden_thread_ids)

	for encoded_thread in encoded_threads:
		decoded_thread = encoded_thread.decode()
		response = conn.hgetall(decoded_thread)

		if int(decoded_thread.split(":")[1]) in hidden_thread_ids_set or response["author".encode()].decode() in blacklisted_user_ids:
			continue

		encoded_authors.add(response["author".encode()])

		serialized_thread = redis_thread_serializer(response)
		emojis_id_arr, user_arr_per_emoji_dict, emoji_reaction_count_dict, did_react_to_emoji_dict, seen_users = redis_generate_emojis_response(decoded_thread, seen_users, user_id)

		serialized_thread["emojis"] = {"emojis_id_arr": emojis_id_arr, "user_arr_per_emoji_dict": user_arr_per_emoji_dict, "emoji_reaction_count_dict": emoji_reaction_count_dict, "did_react_to_emoji_dict": did_react_to_emoji_dict}
		serialized_thread["votes"] = get_vote(conn.hget("vote:user:" + str(user_id), decoded_thread))
		serialized_thread["users"] = get_author(response["author".encode()])
		serializer.append(serialized_thread)
		
	return serializer, has_next_page

# def redis_get_comments_by_thread_id(thread_id, start, count):
# 	conn = get_redis_connection('default')
# 	encoded_comments = conn.zrevrange("thread:" + str(thread_id) + ".ranking", start, start + count - 1)
# 	serializer = []

# 	for encoded_comment in encoded_comments:
# 		response = conn.hgetall(encoded_comment.decode())
# 		serializer.append(redis_comment_serializer(response))
# 	return serializer

# def redis_get_comments_by_parent_comment_id(parent_comment_id, start, count):
# 	conn = get_redis_connection('default')
# 	encoded_comments = conn.zrevrange("comment:" + str(parent_comment_id) + ".ranking", start, start + count - 1)
# 	serializer = []

# 	encoded_authors = set()
# 	for encoded_comment in encoded_comments:
# 		response = conn.hgetall(encoded_comment.decode())
# 		serializer.append(redis_comment_serializer(response))
# 		encoded_authors.add(response["author".encode()])

# 	user_serializer = []
# 	for encoded_author in encoded_authors:
# 		user_response = conn.hgetall("user:" + encoded_author.decode())
# 		user_serializer.append(redis_user_serializer(user_response))

# 	return serializer, user_serializer

def redis_generate_comment_tree_node(comment_id, response, user_id, seen_users):
	conn = get_redis_connection('default')
	def get_author(encoded_author):
		decoded_author = encoded_author.decode()
		if decoded_author in seen_users:
			return [seen_users[decoded_author]]

		user_serializer = []
		user_response = conn.hgetall("user:" + decoded_author)

		seen_users[decoded_author] = redis_user_serializer(user_response)
		user_serializer.append(seen_users[decoded_author])
		return user_serializer

	serialized_comment = redis_comment_serializer(response)
	vote_serializer = []
	vote_id_response = conn.hget("vote:user:" + str(user_id), "comment:" + str(comment_id))
	if vote_id_response != None:
		vote_response = conn.hgetall("vote:" + vote_id_response.decode())
		vote_serializer.append(redis_vote_serializer(vote_response))

	user_serializer = get_author(response["author".encode()])

	serialized_comment["votes"] = vote_serializer
	serialized_comment["users"] = user_serializer

	return serialized_comment

def redis_generate_tree_by_parent_comment_id(parent_comment_id, size, count, next_page_start, user_id, blacklisted_user_ids, hidden_comment_ids):
	conn = get_redis_connection('default')

	next_page_start = next_page_start
	blacklisted_user_ids_set = set(blacklisted_user_ids)
	hidden_comment_ids_set = set(hidden_comment_ids)

	q = collections.deque([parent_comment_id])
	serialized_comment_nodes = []

	comment_breaks_arr = []

	seen_users = {}

	is_first_node = True

	while q and size > 0:
		node = q.popleft()
		nested_encoded_comments = conn.zrevrange("comment:" + str(node) + ".ranking", next_page_start, next_page_start + count - 1)
		if is_first_node == True:
			is_first_node = False
			next_page_start = 0

		for encoded_comment in nested_encoded_comments:
			_, comment_id = encoded_comment.decode().split(":")

			prefix = "comment:" + str(comment_id)
			response = conn.hgetall(prefix)
			if comment_id in hidden_comment_ids_set or response["author".encode()].decode() in blacklisted_user_ids:
				continue

			q.append(comment_id)
			serialized_comment_nodes.append(redis_generate_comment_tree_node(comment_id, response, user_id, seen_users))
			size -= 1
			if size == 0:
				break

		# serialized_comment_nodes.append("#")
		comment_breaks_arr.append(len(serialized_comment_nodes) - 1)

	return serialized_comment_nodes, comment_breaks_arr

def redis_generate_tree_by_parent_thread_id(parent_thread_id, size, count, next_page_start, user_id, blacklisted_user_ids, hidden_comment_ids):
	conn = get_redis_connection('default')

	next_page_start = next_page_start
	blacklisted_user_ids_set = set(blacklisted_user_ids)
	hidden_comment_ids_set = set(hidden_comment_ids)

	is_thread = True
	q = collections.deque([parent_thread_id])

	serialized_comment_nodes = []
	comment_breaks_arr = []

	seen_users = {}

	is_first_node = True

	while q and size > 0:
		node = q.popleft()
		
		encoded_comments = []
		if is_thread:
			encoded_comments = conn.zrevrange("thread:" + str(node) + ".ranking", next_page_start, next_page_start + count - 1)
			is_thread = False
			next_page_start = 0
		else:
			encoded_comments = conn.zrevrange("comment:" + str(node) + ".ranking", next_page_start, next_page_start + count - 1)

		for encoded_comment in encoded_comments:
			_, comment_id = encoded_comment.decode().split(":")

			prefix = "comment:" + str(comment_id)
			response = conn.hgetall(prefix)
			if comment_id in hidden_comment_ids_set or response["author".encode()].decode() in blacklisted_user_ids:
				continue

			q.append(comment_id)

			serialized_comment_nodes.append(redis_generate_comment_tree_node(comment_id, response, user_id, seen_users))
			size -= 1
			if size == 0:
				break

		# serialized_comment_nodes.append("#")
		comment_breaks_arr.append(len(serialized_comment_nodes) - 1)

	return serialized_comment_nodes, comment_breaks_arr


# def redis_get_tree_by_parent_comments_id(roots, size, next_page_start, count, parent_comment_id, user_id, blacklisted_user_ids, hidden_comment_ids):
	
# 	blacklisted_user_ids_set = set(blacklisted_user_ids)
# 	hidden_comment_ids_set = set(hidden_comment_ids)

# 	conn = get_redis_connection('default')
# 	queue = collections.deque(roots[::-1])
# 	comments_to_be_added = []
# 	votes_to_be_added = []
# 	next_page_more_comments = conn.zrevrange("comment:" + str(parent_comment_id) + ".ranking", next_page_start + count, next_page_start + 2 * count - 1)

# 	# number of preloaded roots are under the maximum page count(as a result of total comments size limitation per load), check if there are more comments on same page
# 	if len(queue) < count:
# 		cur_page_unloaded_comments = conn.zrevrange("comment:" + str(parent_comment_id) + ".ranking", next_page_start + len(queue), next_page_start + count - 1)
# 		for comment in cur_page_unloaded_comments:
# 			queue.appendleft(comment.decode().split(":")[1])

# 	encoded_authors = set()
# 	while queue and size > 0:
# 		node = queue.pop()
# 		prefix = "comment:" + str(node)
# 		response = conn.hgetall(prefix)

# 		if node in hidden_comment_ids_set or response["author".encode()].decode() in blacklisted_user_ids:
# 			continue

# 		encoded_authors.add(response["author".encode()])

# 		serialized_comment = redis_comment_serializer(response)
# 		# emojis_id_arr, user_ids_arr_per_emoji_dict, emoji_reaction_count_dict, encoded_authors = redis_generate_emojis_response(prefix, encoded_authors, user_id)
# 		# serialized_comment["emojis"] = {"emojis_id_arr": emojis_id_arr, "user_ids_arr_per_emoji_dict": user_ids_arr_per_emoji_dict, "emoji_reaction_count_dict": emoji_reaction_count_dict}

# 		comments_to_be_added.append(serialized_comment)

# 		vote_id_response = conn.hget("vote:user:" + str(user_id), "comment:" + str(node))
# 		if vote_id_response != None:
# 			vote_response = conn.hgetall("vote:" + vote_id_response.decode())
# 			votes_to_be_added.append(redis_vote_serializer(vote_response))

# 		size -= 1
# 		if size == 0:
# 			break

# 		nested_encoded_comments = conn.zrevrange("comment:" + str(node) + ".ranking", 0, count - 1)
# 		for encoded_comment in nested_encoded_comments:
# 			_, comment_id = encoded_comment.decode().split(":")
# 			queue.appendleft(comment_id)

# 	user_serializer = []
# 	for encoded_author in encoded_authors:
# 		user_response = conn.hgetall("user:" + encoded_author.decode())
# 		user_serializer.append(redis_user_serializer(user_response))

# 	more_comments_response = [redis_comment_serializer(conn.hgetall("comment:" + str(node))) for node in list(reversed(queue))]
# 	next_page_more_comments_response = [redis_comment_serializer(conn.hgetall(encoded_comment.decode())) for encoded_comment in next_page_more_comments]

# 	return comments_to_be_added, more_comments_response + next_page_more_comments_response, votes_to_be_added, user_serializer

# def redis_get_tree_by_parent_thread_id(roots, size, next_page_start, count, parent_thread_id, user_id, blacklisted_user_ids, hidden_comment_ids):
# 	blacklisted_user_ids_set = set(blacklisted_user_ids)
# 	hidden_comment_ids_set = set(hidden_comment_ids)

# 	conn = get_redis_connection('default')
# 	queue = []
# 	comments_to_be_added = []
# 	next_page_more_comments = []
# 	votes_to_be_added = []

# 	if next_page_start == 0:
# 		queue = collections.deque([int(encoded_comment.decode().split(":")[1]) for encoded_comment in conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", 0, count - 1)])
# 		next_page_more_comments = conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", count, 2 * count - 1)
# 	else:
# 		queue = collections.deque(roots[::-1])
# 		next_page_more_comments = conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", next_page_start + count, next_page_start + 2 * count - 1)

# 	encoded_authors = set()
# 	while queue and size > 0:
# 		node = queue.pop()
# 		prefix = "comment:" + str(node)
# 		response = conn.hgetall(prefix)

# 		if node in hidden_comment_ids_set or response["author".encode()].decode() in blacklisted_user_ids:
# 			continue

# 		encoded_authors.add(response["author".encode()])

# 		serialized_comment = redis_comment_serializer(response)
# 		# emojis_id_arr, user_ids_arr_per_emoji_dict, emoji_reaction_count_dict, encoded_authors = redis_generate_emojis_response(prefix, encoded_authors, user_id)
# 		# serialized_comment["emojis"] = {"emojis_id_arr": emojis_id_arr, "user_ids_arr_per_emoji_dict": user_ids_arr_per_emoji_dict, "emoji_reaction_count_dict": emoji_reaction_count_dict}

# 		comments_to_be_added.append(serialized_comment)

# 		vote_id_response = conn.hget("vote:user:" + str(user_id), "comment:" + str(node))

# 		if vote_id_response != None:
# 			vote_response = conn.hgetall("vote:" + vote_id_response.decode())
# 			votes_to_be_added.append(redis_vote_serializer(vote_response))

# 		size -= 1
# 		if size == 0:
# 			break

# 		nested_encoded_comments = conn.zrevrange("comment:" + str(node) + ".ranking", 0, count - 1)
# 		for encoded_comment in nested_encoded_comments:
# 			_, comment_id = encoded_comment.decode().split(":")
# 			queue.appendleft(comment_id)

# 	user_serializer = []
# 	for encoded_author in encoded_authors:
# 		user_response = conn.hgetall("user:" + encoded_author.decode())
# 		user_serializer.append(redis_user_serializer(user_response))

# 	more_comments_response = [redis_comment_serializer(conn.hgetall("comment:" + str(node))) for node in list(reversed(queue))]
# 	next_page_more_comments_response = [redis_comment_serializer(conn.hgetall(encoded_comment.decode())) for encoded_comment in next_page_more_comments]
# 	return comments_to_be_added, more_comments_response + next_page_more_comments_response, votes_to_be_added, user_serializer

def flush_redis():
	conn = get_redis_connection('default')
	conn.flushall()