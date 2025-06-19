from datetime import datetime

from django.utils import timezone
from django.views.generic import ListView, TemplateView, FormView
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from .forms import FileCountForm
from .models import File, Directory
from .filters import FileFilter


class FileCountView(FormView):
    template_name = "core/filecount_form.html"
    form_class = FileCountForm
    success_url = "."

    def form_valid(self, form):
        month = int(form.cleaned_data["month"])
        year = int(form.cleaned_data["year"])
        path_prefix = form.cleaned_data["path_prefix"]
        exclusions = [
            term.strip()
            for term in form.cleaned_data["exclusions"].split(",")
            if term.strip()
        ]

        # Créer la date de référence
        reference_date = timezone.make_aware(datetime(year, month, 1))

        # Filtrer les fichiers
        queryset = File.objects.filter(modified_at__gte=reference_date)

        # Appliquer le préfixe de chemin si fourni
        if path_prefix:
            queryset = queryset.filter(path__startswith=path_prefix)

        # Appliquer les exclusions
        for exclusion in exclusions:
            queryset = queryset.exclude(path__icontains=exclusion)

        # Compter les fichiers
        file_count = queryset.count()

        return self.render_to_response(
            self.get_context_data(
                form=form, file_count=file_count, count_performed=True
            )
        )


class StatsView(TemplateView):
    template_name = "core/stats.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["directory_tree"] = Directory.objects.filter(
            parent=Directory.objects.get(path="/Volumes/TRANSFORMATIONS")
        )
        return context


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
