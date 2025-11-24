from .views import main_page,login_page,signup_page
from django.urls import path

urlpatterns = [
    path('',main_page,name='index'),
    path('login/',login_page,name='login'),
    path('signup/',signup_page,name='signup')
]