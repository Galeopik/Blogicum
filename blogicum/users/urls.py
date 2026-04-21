from django.urls import path

from . import views

urlpatterns = [
    path(
        'registration/', views.UserCreativeView.as_view(), name='registration'
    ),
]
