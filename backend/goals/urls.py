from django.urls import path

from .views import GoalDetailView, GoalListView

urlpatterns = [
    path("", GoalListView.as_view(), name="goals-list"),
    path("<str:goal_id>/", GoalDetailView.as_view(), name="goals-detail"),
]
