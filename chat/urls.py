from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.conversation_list, name='conversation_list'),
    path('new/',views.new_conversation,name = 'new_conversation'),
    path('<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    
]