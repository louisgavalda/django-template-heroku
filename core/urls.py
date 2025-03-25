from django.urls import path

from . import views


urlpatterns = [
    path("", views.FileSearchView.as_view(), name="file_search"),
    path("results/", views.FileSearchResultsView.as_view(), name="file_search_results"),
    path("file/<int:file_id>/", views.file_detail_view, name="file_detail"),
]
