from django.views.generic import ListView, TemplateView
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from .models import File, Directory
from .filters import FileFilter


class FileSearchView(TemplateView):
    template_name = "core/search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["directory_tree"] = Directory.objects.filter(parent=None)
        return context


# views.py
class FileSearchResultsView(ListView):
    model = File
    template_name = "core/search_results.html"
    paginate_by = 50

    def get_queryset(self):
        queryset = File.objects.all().select_related("directory")

        # Recherche rapide (terme q)
        q = self.request.GET.get("q", "").strip()
        if q:
            terms = q.split()
            query = Q()
            for term in terms:
                # Pour chaque terme, créer une condition OR
                term_query = (
                    Q(name__icontains=term)
                    | Q(path__icontains=term)
                    | Q(extension__icontains=term)
                    | Q(directory__name__icontains=term)
                )
                # Combine avec les autres termes (AND)
                query &= term_query
            queryset = queryset.filter(query)

        # Appliquer les filtres avancés seulement s'ils sont présents
        self.filterset = FileFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filterset"] = self.filterset
        context["q"] = self.request.GET.get("q", "")
        return context


def file_detail_view(request, file_id):
    file = get_object_or_404(File, id=file_id)
    return render(request, "core/file_detail.html", {"file": file})
