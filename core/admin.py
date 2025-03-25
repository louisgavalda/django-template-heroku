from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Directory, File


@admin.register(Directory)
class DirectoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "path",
        "parent",
        "file_count",
        "last_modified",
        "last_indexed",
    )
    list_filter = ("last_indexed",)
    search_fields = ("name", "path")
    readonly_fields = ("last_indexed",)
    raw_id_fields = ("parent",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            file_count=Count("files", distinct=True),
        )
        return queryset

    def file_count(self, obj):
        return obj.file_count

    file_count.admin_order_field = "file_count"
    file_count.short_description = "Nombre de fichiers"

    def has_delete_permission(self, request, obj=None):
        # Protéger contre la suppression accidentelle de répertoires avec des fichiers
        if obj and obj.files.exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "extension",
        "size_formatted",
        "directory_link",
        "mime_type",
        "modified_at",
        "last_indexed",
    )
    list_filter = ("extension", "mime_type", "modified_at", "last_indexed")
    search_fields = ("name", "path", "directory__path")
    readonly_fields = (
        "size",
        "extension",
        "mime_type",
        "created_at",
        "modified_at",
        "last_indexed",
        "path",
        "checksum",
    )
    raw_id_fields = ("directory",)
    date_hierarchy = "modified_at"
    list_per_page = 50

    fieldsets = (
        ("Informations de base", {"fields": ("name", "path", "directory")}),
        ("Propriétés", {"fields": ("size", "extension", "mime_type", "checksum")}),
        ("Dates", {"fields": ("created_at", "modified_at", "last_indexed")}),
    )

    def size_formatted(self, obj):
        """Affiche la taille du fichier en format lisible"""
        # Convertir les octets en KB, MB, GB selon la taille
        if obj.size < 1024:
            return f"{obj.size} octets"
        elif obj.size < 1024 * 1024:
            return f"{obj.size / 1024:.2f} KB"
        elif obj.size < 1024 * 1024 * 1024:
            return f"{obj.size / (1024 * 1024):.2f} MB"
        else:
            return f"{obj.size / (1024 * 1024 * 1024):.2f} GB"

    size_formatted.admin_order_field = "size"
    size_formatted.short_description = "Taille"

    def directory_link(self, obj):
        """Crée un lien vers le répertoire parent dans l'admin"""
        if obj.directory:
            url = f"/admin/core/directory/{obj.directory.id}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.directory.path)
        return "-"

    directory_link.admin_order_field = "directory__path"
    directory_link.short_description = "Répertoire"

    def has_add_permission(self, request):
        # Les fichiers sont créés uniquement par le scan
        return False

    def get_readonly_fields(self, request, obj=None):
        # Rendre tous les champs en lecture seule lors de l'édition
        if obj:
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields
