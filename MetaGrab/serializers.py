from rest_framework import serializers
from .models import Game, Genre, Developer, Forum, Thread, UserProfile, Comment
from django.contrib.auth.models import User, Group
from rest_framework.serializers import Serializer

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = '__all__'

class DeveloperSerializer(serializers.ModelSerializer):
    class Meta:
        model = Developer
        fields = '__all__'

class GameSerializer(serializers.ModelSerializer):
    def to_representation(self, data):
        self.fields['developer'] = DeveloperSerializer()
        self.fields['genre'] = GenreSerializer()
        return super(GameSerializer, self).to_representation(data)
    class Meta:
        model = Game
        fields = '__all__'

class ForumSerializer(serializers.ModelSerializer):
    game = GameSerializer('game')
    class Meta:
        model = Forum
        fields = ('id', 'game')

class ThreadSerializer(serializers.ModelSerializer):
    def to_representation(self, data):
        self.fields['forum'] = ForumSerializer()
        return super(ThreadSerializer, self).to_representation(data)

    class Meta:
        model = Thread
        fields = '__all__'

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = '__all__'

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    def create(self,validate_data):
        user = User.objects.create_user(username = validate_data['username'] , password = validate_data['password'], email = validate_data['email'])
        return user

    class Meta:
        model = User
        fields = '__all__'

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'