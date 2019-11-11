from .models import Game, Genre, Developer, Forum, Thread, User, UserProfile, Group, Comment
from .serializers import GameSerializer, GenreSerializer, ThreadSerializer, ForumSerializer, DeveloperSerializer, \
    UserSerializer, UserProfileSerializer, GroupSerializer, CommentSerializer
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate, login
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db import models, connection

from . import redis_helpers
import json, datetime

# redis
from django_redis import get_redis_connection
from datetime import datetime, timedelta
from math import log
from time import mktime
import pytz

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

        new_thread = Thread.create(flair=flair, title=title, content=content, author=User.objects.get(pk=user_id), forum=forum)
        redis_helpers.redis_insert_thread(new_thread)

        serializer = self.get_serializer(new_thread, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_threads_by_game_id(self, request):
        game_id = int(request.GET['game'])
        start = int(request.GET['start'])
        count = int(request.GET['count'])

        if game_id:
            return Response(redis_helpers.redis_get_threads_by_game_id(game_id, start, count))
            # try:
            #     forum = Forum.objects.get(pk=game_id)
            # except Forum.DoesNotExist:
            #     forum = None

            # threads_get_by_forum_id = Thread.objects.filter(forum=forum)
            # serializer = self.get_serializer(threads_get_by_forum_id, many=True)
            # return Response(serializer.data)


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
        redis_helpers.redis_insert_comment(new_comment, thread_id)

        serializer = CommentSerializer(new_comment, many=False)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_comments_by_primary_comment_id(self, request, pk=None):
        primary_comment_id = int(request.GET['primary_comment_id'])
        primary_comment = Comment.objects.get(pk=primary_comment_id)
        start = int(request.GET['start'])
        count = int(request.GET['count'])

        return Response(redis_helpers.redis_get_comments_by_primary_comment_id(primary_comment_id, start, count))
        # secondary_comments = primary_comment.commentsecondary_set.all()
        # serializer = CommentSecondarySerializer(secondary_comments, many=True)
        # return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def post_comment_by_primary_comment_id(self, request, pk=None):
        primary_comment_id = int(request.GET['primary_comment_id'])
        primary_comment = Comment.objects.get(pk=primary_comment_id)
        parent_thread = primary_comment.parent_thread
        body_unicode = request.body.decode('utf-8') 
        body = json.loads(body_unicode)
        content = body['content']
        user_id = request.user.id
        user = User.objects.get(pk=user_id)

        new_secondary_comment = Comment.create(parent_thread=None, parent_post=primary_comment, content=content, author=user)
        redis_helpers.redis_insert_child_comment(new_secondary_comment)

        serializer = CommentSerializer(new_secondary_comment, many=False)
        return Response(serializer.data)


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
        conn = get_redis_connection('default')
        conn.flushall()
        games = Game.objects.all()
        threads = Thread.objects.all()
        comments = Comment.objects.all()

        redis_helpers.redis_insert_games_bulk(games)
        redis_helpers.redis_insert_threads_bulk(threads)
        redis_helpers.redis_insert_comments_bulk(comments)

        res = []
        for thread in threads:
            response = conn.hgetall("thread:" + str(thread.id))
            res.append(redis_helpers.redis_thread_serializer(response))
        
        # print(res) 
        # print(conn.zrevrange("thread:1.ranking", 0, -1, withscores = True))
        # print(conn.zrevrange("game:2.ranking", 0, -1, withscores = True))
        # print(conn.zrevrange("game:3.ranking", 0, -1, withscores = True))

        serialized_threads = ThreadSerializer(threads, many=True)
        serialized_comments = CommentSerializer(comments, many=True)
        return Response(res + serialized_threads.data + serialized_comments.data)
