from django.urls import include, path
from rest_framework import routers
from django.conf.urls import url

from . import views

router = routers.DefaultRouter()
router.register(r'games', views.GameViewSet)
router.register(r'genre', views.GenreViewSet)
router.register(r'developers', views.DeveloperViewSet)
router.register(r'forums', views.ForumViewSet)
router.register(r'threads', views.ThreadViewSet)
router.register(r'users', views.UserViewSet)
router.register(r'users_profile', views.UserProfileViewSet)
router.register(r'groups', views.GroupViewSet)
router.register(r'comments', views.CommentViewSet)
router.register(r'redis', views.RedisServices, basename='redis')

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api/token/$', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    url(r'^api/token/refresh/$', TokenRefreshView.as_view(), name='token_refresh'),
]