import django_filters

from .models import File


class FileFilter(django_filters.FilterSet):
    name_contains = django_filters.CharFilter(
        field_name="name", lookup_expr="icontains"
    )
    name_exact = django_filters.CharFilter(field_name="name", lookup_expr="iexact")
    extension = django_filters.CharFilter(field_name="extension", lookup_expr="iexact")
    extension_in = django_filters.CharFilter(method="filter_extension_in")
    path_contains = django_filters.CharFilter(
        field_name="path", lookup_expr="icontains"
    )
    directory_path = django_filters.CharFilter(
        field_name="directory__path", lookup_expr="startswith"
    )
    size_min = django_filters.NumberFilter(field_name="size", lookup_expr="gte")
    size_max = django_filters.NumberFilter(field_name="size", lookup_expr="lte")
    modified_after = django_filters.DateTimeFilter(
        field_name="modified_at", lookup_expr="gte"
    )
    modified_before = django_filters.DateTimeFilter(
        field_name="modified_at", lookup_expr="lte"
    )

    def filter_extension_in(self, queryset, name, value):
        extensions = [ext.strip().lower() for ext in value.split(",")]
        return queryset.filter(extension__in=extensions)

    class Meta:
        model = File
        fields = ["name", "extension", "mime_type", "directory"]
