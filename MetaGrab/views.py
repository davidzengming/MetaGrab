from .models import Game, Genre, Developer, Forum, Thread, User, UserProfile, Group, Comment, CommentSecondary
from .serializers import GameSerializer, GenreSerializer, ThreadSerializer, ForumSerializer, DeveloperSerializer, UserSerializer, UserProfileSerializer, GroupSerializer, CommentSerializer, CommentSecondarySerializer
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate, login
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db import models, connection
from rest_framework.pagination import CursorPagination
import json

class GameCursorSetPagination(CursorPagination):
    page_size = 50
    ordering = '-id'

class ThreadCursorSetPagination(CursorPagination):
    page_size = 10
    ordering = '-id'

class PrimaryCommentCursorSetPagination(CursorPagination):
    page_size = 10
    ordering = '-id'

class SecondaryCommentCursorSetPagination(CursorPagination):
    page_size = 10
    ordering = '-id'

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)

        # Add extra responses here
        #data['user_id'] = self.user.user_id
        #data['groups'] = self.user.groups.values_list('name', flat=True)
        return data

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class GameViewSet(viewsets.ModelViewSet):
    #permission_classes = [IsAuthenticated]
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    pagination_class = GameCursorSetPagination


    @action(detail=False, methods=['get'])
    def test_redis(self, request, pk=None):
        from django_redis import get_redis_connection
        con = get_redis_connection("default")

        print(con.zadd("threads:100", {"comment:1": 100, "comment:5": 5, "comment:7": 10000}))
        print(con.zrange("threads:100", 0, -1)[0])
        return Response(None)

    @action(detail=False, methods=['get'])
    def get_recent_games(self, request, pk=None):
        recent_games = Game.objects.all().order_by('-release_date')
        serializer = self.get_serializer(recent_games, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def get_followed_games_by_user_id(self, request):
        user_id = request.user.id
        user = User.objects.get(pk=user_id)
        followed_games = user.userprofile.followed_games.all()
        page = self.paginate_queryset(followed_games)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def follow_game_by_game_id(self, request, pk=None):
        game = self.get_object()
        user_id = request.user.id
        user = User.objects.get(pk=user_id)
        user_profile = user.userprofile
        user_profile.followed_games.add(game)
        user_profile.save()
        return Response()

    @action(detail=True, methods=['post'])
    def unfollow_game_by_game_id(self, request, pk=None):
        game = self.get_object()
        user_id = request.user.id
        user = User.objects.get(pk=user_id)
        user_profile = user.userprofile
        user_profile.followed_games.remove(game)
        user_profile.save()
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

    @action(detail=True, methods=['post'])
    def post_thread_by_forum_id(self, request, pk=None):
        forum = self.get_object()
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        title = body['title']
        flair = body['flair']
        content = body['content']
        user_id = request.user.id

        user = User.objects.get(pk=user_id)

        new_thread = Thread(flair=flair, title=title, content=content, author=user, forum=forum)
        new_thread.save()

        serializer = ThreadSerializer(new_thread, many=False)
        return Response(serializer.data)


class ThreadViewSet(viewsets.ModelViewSet):
    queryset = Thread.objects.all()
    serializer_class = ThreadSerializer
    pagination_class = ThreadCursorSetPagination

    @action(detail=False, methods=['get'])
    def get_threads_by_game_id(self, request):
        game_id = request.GET['game']
        if game_id:
            try:
                forum = Forum.objects.get(pk=game_id)
            except Forum.DoesNotExist:
                forum = None
            
            threads_get_by_forum_id = Thread.objects.filter(forum=forum)
            page = self.paginate_queryset(threads_get_by_forum_id)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'])
    def get_comments_by_thread_id(self, request, pk=None):
        thread = self.get_object()
        comments = thread.comment_set.all()
        page = self.paginate_queryset(comments)
        serializer = CommentSerializer(page, many=True)

        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def post_comment_by_thread_id(self, request, pk=None):
        parent_thread = self.get_object()

        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        content = body['content']
        user_id = request.user.id

        user = User.objects.get(pk=user_id)

        new_comment = Comment(parent_thread=parent_thread, content=content, author=user)
        new_comment.save()

        serializer = CommentSerializer(new_comment, many=False)
        return Response(serializer.data)

class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    pagination_class = PrimaryCommentCursorSetPagination

    @action(detail=True, methods=['get'])
    def get_comments_by_primary_comment_id(self, request, pk=None):
        primary_comment = self.get_object()
        secondary_comments = primary_comment.commentsecondary_set.all()
        page = self.paginate_queryset(secondary_comments)
        serializer = CommentSecondarySerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'])
    def post_comment_by_primary_comment_id(self, request, pk=None):
        primary_comment = self.get_object()
        parent_thread = primary_comment.parent_thread

        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        content = body['content']
        user_id = request.user.id

        user = User.objects.get(pk=user_id)

        new_secondary_comment = CommentSecondary(parent_post=primary_comment, content=content, author=user)
        new_secondary_comment.save()

        serializer = CommentSecondarySerializer(new_secondary_comment, many=False)
        return Response(serializer.data)

class CommentSecondaryViewSet(viewsets.ModelViewSet):
    queryset = CommentSecondary.objects.all()
    serializer_class = CommentSecondarySerializer
    pagination_class = SecondaryCommentCursorSetPagination

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

