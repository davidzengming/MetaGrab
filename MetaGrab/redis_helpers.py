
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
		"name": genre.name
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
		"created": convert_datetime_to_unix(user.date_joined),
		"username": user.username,
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

def redis_insert_game(game):
	redis_insert_developer(game.developer)
	redis_insert_genre(game.genre)

	conn = get_redis_connection('default')
	redis_game_object = transform_game_to_redis_object(game)
	conn.hmset("game:" + str(game.id), redis_game_object)
	conn.zadd("game_release_timeline:year:" + str(game.release_date.year) + "month:" + str(game.release_date.month), {"game:" + str(game.id): game.release_date.day})
	conn.rpush("games", "game:" + str(game.id))
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
		if key.decode() == "created":
			decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz).strftime('%Y-%m-%dT%H:%M:%S')
		elif key.decode() in {"id", "author", "num_childs", "num_subtree_nodes", "upvotes", "downvotes", "flair"}:
			decoded_response[key.decode()] = int(val.decode())
		# forum field in json response is nested, additional O(1) retrieve call required
		elif key.decode() == "forum":
			forum = Forum.objects.get(pk=int(val.decode()))
			serializer = ForumSerializer(forum, many=False)
			decoded_response[key.decode()] = serializer.data
		elif key.decode() in {"content_attributes", "image_urls"}:
			decoded_response[key.decode()] = json.loads(val.decode())
		else:
			decoded_response[key.decode()] = val.decode()

	return decoded_response

def redis_vote_serializer(vote_response):
	decoded_response = {}
	for key, val in vote_response.items():
		if key.decode() == "created":
			decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz)
		elif key.decode() in {"id", "thread", "comment", "user"}:
			if val.decode() != "":
				decoded_response[key.decode()] = int(val.decode())
			else:
				decoded_response[key.decode()] = None

		elif key.decode() in {"direction"}:
			decoded_response[key.decode()] = int(val.decode())
		else:
			decoded_response[key.decode()] = val.decode()

	return decoded_response

def redis_game_serializer(game_response):
	decoded_response = {}
	for key, val in game_response.items():
		if key.decode() in {"created", "release_date", "next_expansion_release_date", "last_updated"}:
			if val.decode() != "":
				decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz).strftime('%Y-%m-%dT%H:%M:%S')
			else:
				decoded_response[key.decode()] = None
		elif key.decode() in {"id"}:
			if val.decode() != "":
				decoded_response[key.decode()] = int(val.decode())
			else:
				decoded_response[key.decode()] = None
		elif key.decode() == "developer":
			decoded_response[key.decode()] = redis_get_developer_by_id(int(val.decode()))
		elif key.decode() == "genre":
			decoded_response[key.decode()] = redis_get_genre_by_id(int(val.decode()))
		else:
			decoded_response[key.decode()] = val.decode()

	return decoded_response

def redis_genre_serializer(genre_response):
	decoded_response = {}
	for key, val in genre_response.items():
		if key.decode() in {"created"}:
			if val.decode() != "":
				decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz)
			else:
				decoded_response[key.decode()] = None
		elif key.decode() in {"id"}:
			if val.decode() != "":
				decoded_response[key.decode()] = int(val.decode())
			else:
				decoded_response[key.decode()] = None
		else:
			decoded_response[key.decode()] = val.decode()
	return decoded_response

def redis_developer_serializer(developer_response):
	decoded_response = {}
	for key, val in developer_response.items():
		if key.decode() in {"created"}:
			if val.decode() != "":
				decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz)
			else:
				decoded_response[key.decode()] = None
		elif key.decode() in {"id"}:
			if val.decode() != "":
				decoded_response[key.decode()] = int(val.decode())
			else:
				decoded_response[key.decode()] = None
		else:
			decoded_response[key.decode()] = val.decode()
	return decoded_response

def redis_comment_serializer(comment_response):
	decoded_response = {}
	for key, val in comment_response.items():
		if key.decode() == "created":
			decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz).strftime('%Y-%m-%dT%H:%M:%S')
		elif key.decode() in {"id", "author", "num_childs", "num_subtree_nodes", "upvotes", "downvotes"}:
			decoded_response[key.decode()] = int(val.decode())
		elif key.decode() in {"parent_thread", "parent_post"}:
			if val.decode() == "":
				decoded_response[key.decode()] = None
			else:
				decoded_response[key.decode()] = int(val.decode())
		elif key.decode() == "content_attributes":
			decoded_response[key.decode()] = json.loads(val.decode())
		else:
			decoded_response[key.decode()] = val.decode()

	return decoded_response

def redis_user_serializer(user_response):
	decoded_response = {}

	for key, val in user_response.items():
		if key.decode() == "created":
			decoded_response[key.decode()] = datetime.fromtimestamp(float(val.decode()), tz).strftime('%Y-%m-%dT%H:%M:%S')
		elif key.decode() in {"id"}:
			decoded_response[key.decode()] = int(val.decode())
		else:
			decoded_response[key.decode()] = val.decode()
	return decoded_response

def redis_follow_game(user, game):
	conn = get_redis_connection('default')
	conn.sadd("follow_games_user:" + str(user.id), "game:" + str(game.id))
	return

def redis_unfollow_game(user, game):
	conn = get_redis_connection('default')
	conn.srem("follow_games_user:" + str(user.id), "game:" + str(game.id))
	return

def redis_get_user_follow_games(user):
	conn = get_redis_connection('default')
	encoded_games = conn.smembers("follow_games_user:" + str(user.id))
	serializer = []

	for encoded_game in encoded_games:
		decoded_game = encoded_game.decode()
		response = conn.hgetall(decoded_game)
		serializer.append(redis_game_serializer(response))

	return serializer

def redis_get_user_by_id(id):
	conn = get_redis_connection('default')
	return redis_user_serializer(conn.hgetall("user:" + str(id)))

def redis_get_developer_by_id(id):
	conn = get_redis_connection('default')
	return redis_developer_serializer(conn.hgetall("developer:" + str(id)))

def redis_get_genre_by_id(id):
	conn = get_redis_connection('default')
	return redis_genre_serializer(conn.hgetall("genre:" + str(id)))

def redis_get_all_games():
	conn = get_redis_connection('default')
	encoded_games = conn.lrange("games", 0, -1)
	serializer = []

	for encoded_game in encoded_games:
		decoded_game = encoded_game.decode()
		response = conn.hgetall(decoded_game)
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
		serializer.append(redis_game_serializer(response))

	return serializer

def redis_generate_emojis_response(decoded_prefix, encoded_users, user_id):
	conn = get_redis_connection('default')
	encoded_emojis = conn.zrange(str(decoded_prefix) + ":emojis", 0, 9)
		
	user_ids_arr_per_emoji_dict = collections.defaultdict(list)

	emojis_id_arr = []
	emoji_reaction_count_dict = {}

	encoded_authors = set()

	for encoded_emoji in encoded_emojis:
		decoded_emoji = encoded_emoji.decode()
		emoji_id = int(decoded_emoji.split(":")[1])
		emojis_id_arr.append(emoji_id)

		user_ids_arr_per_emoji_dict[emoji_id] = []
		
		top_3_encoded_users_reacted_with_emoji = conn.zrange(decoded_prefix + ":emoji:" + str(emoji_id) + ":users", 0, 2)

		emoji_reaction_count = conn.zcard(decoded_prefix + ":emoji:" + str(emoji_id) + ":users")
		emoji_reaction_count_dict[emoji_id] = emoji_reaction_count

		user_exists_in_reaction = conn.zscore(decoded_prefix + ":emoji:" + str(emoji_id), "user:" + str(user_id))
		if user_exists_in_reaction != None:
			user_ids_arr_per_emoji_dict[emoji_id].append(user_id)

		for encoded_user in top_3_encoded_users_reacted_with_emoji:
			if encoded_user == str(user_id).encode():
				continue

			encoded_authors.add(encoded_user)

			decoded_user_id = encoded_user.decode().split(":")[1]

			user_ids_arr_per_emoji_dict[emoji_id].append(int(decoded_user_id))

	return emojis_id_arr, user_ids_arr_per_emoji_dict, emoji_reaction_count_dict, encoded_users

def redis_get_threads_by_game_id(game_id, start, count, user_id):
	conn = get_redis_connection('default')
	encoded_threads = conn.zrevrange("game:" + str(game_id) + ".ranking", start, start + count - 1)
	serializer, vote_serializer = [], []
	has_next_page = (start + count - 1) < conn.zcard("game:" + str(game_id) + ".ranking")

	encoded_authors = set()

	for encoded_thread in encoded_threads:
		decoded_thread = encoded_thread.decode()
		response = conn.hgetall(decoded_thread)
		encoded_authors.add(response["author".encode()])

		serialized_thread = redis_thread_serializer(response)
		emojis_id_arr, user_ids_arr_per_emoji_dict, emoji_reaction_count_dict, encoded_authors = redis_generate_emojis_response(decoded_thread, encoded_authors, user_id)

		serialized_thread["emojis"] = {"emojis_id_arr": emojis_id_arr, "user_ids_arr_per_emoji_dict": user_ids_arr_per_emoji_dict, "emoji_reaction_count_dict": emoji_reaction_count_dict}
		serializer.append(serialized_thread)

		vote_id_response = conn.hget("vote:user:" + str(user_id), "thread:" + str(decoded_thread.split(":")[1]))
		if vote_id_response != None:
			vote_response = conn.hgetall("vote:" + vote_id_response.decode())
			vote_serializer.append(redis_vote_serializer(vote_response))
	
	user_serializer = []

	for encoded_author in encoded_authors:
		user_response = conn.hgetall("user:" + encoded_author.decode())
		user_serializer.append(redis_user_serializer(user_response))

	return serializer, has_next_page, vote_serializer, user_serializer

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

	encoded_authors = set()
	for encoded_comment in encoded_comments:
		response = conn.hgetall(encoded_comment.decode())
		serializer.append(redis_comment_serializer(response))
		encoded_authors.add(response["author".encode()])

	user_serializer = []
	for encoded_author in encoded_authors:
		user_response = conn.hgetall("user:" + encoded_author.decode())
		user_serializer.append(redis_user_serializer(user_response))

	return serializer, user_serializer

def redis_get_tree_by_parent_comments_id(roots, size, next_page_start, count, parent_comment_id, user_id):
	conn = get_redis_connection('default')
	queue = collections.deque(roots[::-1])
	comments_to_be_added = []
	votes_to_be_added = []
	next_page_more_comments = conn.zrevrange("comment:" + str(parent_comment_id) + ".ranking", next_page_start + count, next_page_start + 2 * count - 1)

	# number of preloaded roots are under the maximum page count(as a result of total comments size limitation per load), check if there are more comments on same page
	if len(queue) < count:
		cur_page_unloaded_comments = conn.zrevrange("comment:" + str(parent_comment_id) + ".ranking", next_page_start + len(queue), next_page_start + count - 1)
		for comment in cur_page_unloaded_comments:
			queue.appendleft(comment.decode().split(":")[1])

	encoded_authors = set()
	while queue and size > 0:
		node = queue.pop()

		prefix = "comment:" + str(node)
		response = conn.hgetall(prefix)
		encoded_authors.add(response["author".encode()])

		serialized_comment = redis_comment_serializer(response)
		emojis_id_arr, user_ids_arr_per_emoji_dict, emoji_reaction_count_dict, encoded_authors = redis_generate_emojis_response(prefix, encoded_authors, user_id)
		serialized_comment["emojis"] = {"emojis_id_arr": emojis_id_arr, "user_ids_arr_per_emoji_dict": user_ids_arr_per_emoji_dict, "emoji_reaction_count_dict": emoji_reaction_count_dict}

		comments_to_be_added.append(serialized_comment)

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

	user_serializer = []
	for encoded_author in encoded_authors:
		user_response = conn.hgetall("user:" + encoded_author.decode())
		user_serializer.append(redis_user_serializer(user_response))

	more_comments_response = [redis_comment_serializer(conn.hgetall("comment:" + str(node))) for node in list(reversed(queue))]
	next_page_more_comments_response = [redis_comment_serializer(conn.hgetall(encoded_comment.decode())) for encoded_comment in next_page_more_comments]

	return comments_to_be_added, more_comments_response + next_page_more_comments_response, votes_to_be_added, user_serializer

def redis_get_tree_by_parent_thread_id(roots, size, next_page_start, count, parent_thread_id, user_id):
	conn = get_redis_connection('default')
	queue = []
	comments_to_be_added = []
	next_page_more_comments = []
	votes_to_be_added = []

	if next_page_start == 0:
		queue = collections.deque([int(encoded_comment.decode().split(":")[1]) for encoded_comment in conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", 0, count - 1)])
		next_page_more_comments = conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", count, 2 * count - 1)
	else:
		queue = collections.deque(roots[::-1])
		next_page_more_comments = conn.zrevrange("thread:" + str(parent_thread_id) + ".ranking", next_page_start + count, next_page_start + 2 * count - 1)

	encoded_authors = set()
	while queue and size > 0:
		node = queue.pop()
		prefix = "comment:" + str(node)
		response = conn.hgetall(prefix)
		encoded_authors.add(response["author".encode()])

		serialized_comment = redis_comment_serializer(response)
		emojis_id_arr, user_ids_arr_per_emoji_dict, emoji_reaction_count_dict, encoded_authors = redis_generate_emojis_response(prefix, encoded_authors, user_id)
		serialized_comment["emojis"] = {"emojis_id_arr": emojis_id_arr, "user_ids_arr_per_emoji_dict": user_ids_arr_per_emoji_dict, "emoji_reaction_count_dict": emoji_reaction_count_dict}

		comments_to_be_added.append(serialized_comment)

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

	user_serializer = []
	for encoded_author in encoded_authors:
		user_response = conn.hgetall("user:" + encoded_author.decode())
		user_serializer.append(redis_user_serializer(user_response))

	more_comments_response = [redis_comment_serializer(conn.hgetall("comment:" + str(node))) for node in list(reversed(queue))]
	next_page_more_comments_response = [redis_comment_serializer(conn.hgetall(encoded_comment.decode())) for encoded_comment in next_page_more_comments]
	return comments_to_be_added, more_comments_response + next_page_more_comments_response, votes_to_be_added, user_serializer

def flush_redis():
	conn = get_redis_connection('default')
	conn.flushall()