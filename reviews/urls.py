from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('evidence/', views.evidence_list_view, name='evidence_list'),
    path('evidence/add/', views.add_evidence_view, name='add_evidence'),
    path('create/', views.create_review_view, name='create_review'),
]
