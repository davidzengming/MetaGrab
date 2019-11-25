from .models import Game, Genre, Developer, Forum, Thread, User, UserProfile, Group, Comment, Vote
from .serializers import GameSerializer, GenreSerializer, ThreadSerializer, ForumSerializer, DeveloperSerializer, \
    UserSerializer, UserProfileSerializer, GroupSerializer, CommentSerializer, VoteSerializer
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate, login
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db import models, connection

from . import redis_helpers
from django_redis import get_redis_connection
import json, datetime


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)

        # Add extra responses here
        # data['user_id'] = self.user.user_id
        # data['groups'] = self.user.groups.values_list('name', flat=True)
        return data


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class GameViewSet(viewsets.ModelViewSet):
    # permission_classes = [IsAuthenticated]
    queryset = Game.objects.all()
    serializer_class = GameSerializer

    def get_recent_games(self, request, pk=None):
        recent_games = Game.objects.all().order_by('-release_date')
        serializer = self.get_serializer(recent_games, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_followed_games_by_user_id(self, request):
        user_id = request.user.id
        user = User.objects.get(pk=user_id)
        followed_games = user.userprofile.find_followed_games()
        serializer = self.get_serializer(followed_games, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def follow_game_by_game_id(self, request, pk=None):
        game = self.get_object()
        user_id = request.user.id
        user = User.objects.get(pk=user_id)
        user.userprofile.follow_game(game)
        return Response()

    @action(detail=True, methods=['post'])
    def unfollow_game_by_game_id(self, request, pk=None):
        game = self.get_object()
        user_id = request.user.id
        user = User.objects.get(pk=user_id)
        user.userprofile.unfollow_game(game)
        return Response()


class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer


class DeveloperViewSet(viewsets.ModelViewSet):
    queryset = Developer.objects.all()
    serializer_class = DeveloperSerializer


class ForumViewSet(viewsets.ModelViewSet):
    queryset = Forum.objects.all()
    serializer_class = ForumSerializer


class ThreadViewSet(viewsets.ModelViewSet):
    queryset = Thread.objects.all()
    serializer_class = ThreadSerializer

    @action(detail=False, methods=['post'])
    def post_thread_by_game_id(self, request, pk=None):
        game_id = int(request.GET['game_id'])
        forum = Forum.objects.get(pk=game_id)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        title = body['title']
        flair = body['flair']
        content = body['content']
        user_id = request.user.id
        user = User.objects.get(pk=user_id)

        new_thread = Thread.create(flair=flair, title=title, content=content, author=User.objects.get(pk=user_id), forum=forum)
        redis_helpers.redis_insert_thread(new_thread)
        new_vote = Vote.create(user, True, new_thread, None)
        redis_helpers.redis_insert_vote(new_vote)

        serializer = self.get_serializer(new_thread, many=False)
        vote_serializer = VoteSerializer(new_vote, many=False)

        return Response({"thread_response": serializer.data, "vote_response": vote_serializer.data})

    @action(detail=False, methods=['get'])
    def get_threads_by_game_id(self, request):
        game_id = int(request.GET['game'])
        start = int(request.GET['start'])
        count = int(request.GET['count'])
        user_id = request.user.id

        if game_id:
            threads_response, has_next_page, votes_response = redis_helpers.redis_get_threads_by_game_id(game_id, start, count, user_id)
            return Response({"threads_response": threads_response, "has_next_page": has_next_page, "votes_response": votes_response})
            # try:
            #     forum = Forum.objects.get(pk=game_id)
            # except Forum.DoesNotExist:
            #     forum = None

            # threads_get_by_forum_id = Thread.objects.filter(forum=forum)
            # serializer = self.get_serializer(threads_get_by_forum_id, many=True)
            # return Response(serializer.data)

class VoteViewSet(viewsets.ModelViewSet):
    queryset = Vote.objects.all()
    serializer_class = VoteSerializer

    @action(detail=False, methods=['post'])
    def upvote_by_comment_id(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        comment_id = body['comment_id']
        comment = Comment.objects.get(pk=comment_id)
        user_id = request.user.id
        user = User.objects.get(pk=user_id)

        new_vote = Vote.create(user, True, None, comment)
        updated_comment = comment.increment_upvotes()
        redis_helpers.redis_insert_comment_choose(updated_comment)
        redis_helpers.redis_insert_vote(new_vote)

        serializer = self.get_serializer(new_vote, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def downvote_to_upvote_by_comment_id(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        vote_id = body['vote_id']
        user_id = request.user.id

        found_vote = Vote.objects.get(pk=vote_id)
        updated_comment = found_vote.switch_vote_comment()
        redis_helpers.redis_insert_comment_choose(updated_comment)
        redis_helpers.redis_delete_vote(found_vote.id, user_id, False, updated_comment.id)
        redis_helpers.redis_insert_vote(found_vote)

        serializer = self.get_serializer(found_vote, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def downvote_by_comment_id(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        comment_id = body['comment_id']
        user_id = request.user.id
        comment = Comment.objects.get(pk=comment_id)
        user = User.objects.get(pk=user_id)

        new_vote = Vote.create(user, False, None, comment)
        updated_comment = comment.increment_downvotes()
        redis_helpers.redis_insert_comment_choose(updated_comment)
        redis_helpers.redis_insert_vote(new_vote)

        serializer = self.get_serializer(new_vote, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def upvote_to_downvote_by_comment_id(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        vote_id = body['vote_id']
        user_id = request.user.id

        found_vote = Vote.objects.get(pk=vote_id)
        updated_comment = found_vote.switch_vote_comment()
        redis_helpers.redis_insert_comment_choose(updated_comment)
        redis_helpers.redis_delete_vote(found_vote.id, user_id, False, updated_comment.id)
        redis_helpers.redis_insert_vote(found_vote)

        serializer = self.get_serializer(found_vote, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def upvote_by_thread_id(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        thread_id = body['thread_id']
        user_id = request.user.id
        thread = Thread.objects.get(pk=thread_id)
        user = User.objects.get(pk=user_id)

        new_vote = Vote.create(user, True, thread, None)
        updated_thread = thread.increment_upvotes()
        redis_helpers.redis_insert_thread(updated_thread)
        redis_helpers.redis_insert_vote(new_vote)

        serializer = self.get_serializer(new_vote, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def downvote_to_upvote_by_thread_id(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        vote_id = body['vote_id']
        user_id = request.user.id

        found_vote = Vote.objects.get(pk=vote_id)
        updated_thread = found_vote.switch_vote_thread()
        redis_helpers.redis_insert_thread(updated_thread)
        redis_helpers.redis_delete_vote(found_vote.id, user_id, True,updated_thread.id)
        redis_helpers.redis_insert_vote(found_vote)

        serializer = self.get_serializer(found_vote, many=False)
        return Response(serializer.data)


    @action(detail=False, methods=['post'])
    def downvote_by_thread_id(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        thread_id = body['thread_id']
        user_id = request.user.id
        thread = Thread.objects.get(pk=thread_id)
        user = User.objects.get(pk=user_id)

        new_vote = Vote.create(user, False, thread, None)
        updated_thread = thread.increment_downvotes()
        redis_helpers.redis_insert_thread(updated_thread)
        redis_helpers.redis_insert_vote(new_vote)

        serializer = self.get_serializer(new_vote, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def upvote_to_downvote_by_thread_id(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        vote_id = body['vote_id']
        user_id = request.user.id

        found_vote = Vote.objects.get(pk=vote_id)
        updated_thread = found_vote.switch_vote_thread()
        redis_helpers.redis_insert_thread(updated_thread)
        redis_helpers.redis_delete_vote(found_vote.id, user_id, True, updated_thread.id)
        redis_helpers.redis_insert_vote(found_vote)

        serializer = self.get_serializer(found_vote, many=False)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def delete_vote_by_vote_id_thread(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        vote_id = body['vote_id']
        user_id = request.user.id
        updated_thread = Vote.delete_thread_vote(vote_id)
        redis_helpers.redis_insert_thread(updated_thread)
        redis_helpers.redis_delete_vote(vote_id, user_id, True, updated_thread.id)
        serializer = ThreadSerializer(updated_thread, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def delete_vote_by_vote_id_comment(self, request, pk=None):
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        vote_id = body['vote_id']
        user_id = request.user.id
        updated_comment = Vote.delete_comment_vote(vote_id)
        redis_helpers.redis_insert_comment(updated_comment)
        redis_helpers.redis_delete_vote(vote_id, user_id, False, updated_comment.id)

        serializer = CommentSerializer(updated_comment, many=False)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer

    @action(detail=False, methods=['get'])
    def get_comments_by_thread_id(self, request, pk=None):
        thread_id = int(request.GET['thread_id'])
        start = int(request.GET['start'])
        count = int(request.GET['count'])

        return Response(redis_helpers.redis_get_comments_by_thread_id(thread_id, start, count))
        # comments = thread.comment_set.all()
        # serializer = CommentSerializer(comments, many=True)

        # return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def post_comment_by_thread_id(self, request, pk=None):
        thread_id = int(request.GET['thread_id'])
        parent_thread = Thread.objects.get(pk=thread_id)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        content = body['content']
        user_id = request.user.id
        user = User.objects.get(pk=user_id)

        new_comment = Comment.create(parent_thread=parent_thread, parent_post=None, content=content, author=user)
        new_vote = Vote.create(user, True, None, new_comment)

        redis_helpers.redis_insert_comment(new_comment, thread_id)
        redis_helpers.redis_insert_vote(new_vote)

        serializer = CommentSerializer(new_comment, many=False)
        vote_serializer = VoteSerializer(new_vote, many=False)

        return Response({"comment_response": serializer.data, "vote_response":vote_serializer.data})

    @action(detail=False, methods=['get'])
    def get_comments_by_parent_comment_id(self, request, pk=None):
        parent_comment_id = int(request.GET['parent_comment_id'])
        start = int(request.GET['start'])
        count = int(request.GET['count'])

        return Response(redis_helpers.redis_get_comments_by_parent_comment_id(parent_comment_id, start, count))
        # secondary_comments = primary_comment.commentsecondary_set.all()
        # serializer = CommentSecondarySerializer(secondary_comments, many=True)
        # return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def post_comment_by_parent_comment_id(self, request, pk=None):
        parent_comment_id = int(request.GET['parent_comment_id'])
        parent_comment = Comment.objects.get(pk=parent_comment_id)
        body_unicode = request.body.decode('utf-8') 
        body = json.loads(body_unicode)
        content = body['content']
        user_id = request.user.id
        user = User.objects.get(pk=user_id)

        new_child_comment = Comment.create(parent_thread=None, parent_post=parent_comment, content=content, author=user)
        new_vote = Vote.create(user, True, None, new_child_comment)

        redis_helpers.redis_insert_child_comment(new_child_comment)
        redis_helpers.redis_insert_vote(new_vote)

        serializer = CommentSerializer(new_child_comment, many=False)
        vote_serializer = VoteSerializer(new_vote, many=False)
        return Response({"comment_response": serializer.data, "vote_response": vote_serializer.data})

    @action(detail=False, methods=['get'])
    def get_comment_tree_by_parent_comments(self, request, pk=None):
        roots = request.GET.getlist('roots')
        start = int(request.GET['start'])
        count = int(request.GET['count'])
        size = int(request.GET['count'])
        parent_comment_id = int(request.GET['parent_comment_id'])
        user_id = request.user.id

        serialized_added_comments, serialized_more_comments_cache, serialized_votes = redis_helpers.redis_get_tree_by_parent_comments_id(roots, size, start, count, parent_comment_id, user_id)
        return Response({"added_comments": serialized_added_comments, "more_comments": serialized_more_comments_cache, "added_votes": serialized_votes})

    @action(detail=False, methods=['get'])
    def get_comment_tree_by_thread_id(self, request, pk=None):
        roots = request.GET.getlist('roots')
        start = int(request.GET['start'])
        count = int(request.GET['count'])
        size = int(request.GET['count'])
        parent_thread_id = int(request.GET['parent_thread_id'])
        user_id = request.user.id

        serialized_added_comments, serialized_more_comments_cache, serialized_votes = redis_helpers.redis_get_tree_by_parent_thread_id(roots, size, start, count, parent_thread_id, user_id)
        return Response({"added_comments": serialized_added_comments, "more_comments": serialized_more_comments_cache, "added_votes": serialized_votes})


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class RedisServices(viewsets.GenericViewSet):
    queryset = ""

    @action(detail=False, methods=['get'])
    def migrate_to_redis(self, request, pk=None):
        games = Game.objects.all()
        threads = Thread.objects.all()
        comments = Comment.objects.all()
        votes = Vote.objects.all()
        
        redis_helpers.flush_redis()
        redis_helpers.redis_insert_games_bulk(games)
        redis_helpers.redis_insert_threads_bulk(threads)
        redis_helpers.redis_insert_comments_bulk(comments)
        redis_helpers.redis_insert_votes_bulk(votes)

        conn = get_redis_connection('default')
        res = []
        for thread in threads:
            response = conn.hgetall("thread:" + str(thread.id))
            res.append(redis_helpers.redis_thread_serializer(response))
        
        # print(res) 
        # print(conn.zrevrange("thread:1.ranking", 0, -1, withscores = True))
        # print(conn.zrevrange("game:2.ranking", 0, -1, withscores = True))
        # print(conn.zrevrange("game:3.ranking", 0, -1, withscores = True))
        # serialized_threads = ThreadSerializer(threads, many=True)
        # serialized_comments = CommentSerializer(comments, many=True)
        serialized_votes = VoteSerializer(votes, many=True)
        return Response(serialized_votes.data)
