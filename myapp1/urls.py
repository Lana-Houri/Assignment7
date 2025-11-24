from django.urls import path
from .views import home, create_contact, update_contact, delete_contact, success, recommend, search, chatbot, contact_detail

urlpatterns = [
    path('', home, name='home'),
    path('create/', create_contact, name='create_contact'),
    path('update/<int:id>/', update_contact, name='update_contact'),
    path('delete/<int:id>/', delete_contact, name='delete_contact'),
    path('success/', success, name='success'),
    path('recommend/', recommend, name='recommend'),
    path('search/', search, name='search'),
    path("chatbot/", chatbot, name="chatbot"),
    path("profile/<int:id>/", contact_detail, name="contact_detail"),

]
