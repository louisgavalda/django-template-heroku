import os

from django.db import models
from django.utils import timezone


class Directory(models.Model):
    path = models.CharField(max_length=1024, unique=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    last_modified = models.DateTimeField()
    last_indexed = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.path

    def children_clean(self):
        return self.children.exclude(name__in=["REF"])

    def total_files_count(self):
        count = self.files.exclude(name__in=[".DS_Store", "Thumbs.db"]).count()
        for child in self.children.exclude(name="REF"):
            count += child.total_files_count()
        return count

    class Meta:
        verbose_name_plural = "Directories"
        indexes = [
            models.Index(fields=["path"]),
            models.Index(fields=["name"]),
            models.Index(fields=["parent"]),
        ]
        ordering = ["path"]


class File(models.Model):
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=1024, unique=True)
    directory = models.ForeignKey(
        Directory, related_name="files", on_delete=models.CASCADE
    )
    size = models.BigIntegerField(default=0)
    extension = models.CharField(max_length=50, blank=True)
    mime_type = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    modified_at = models.DateTimeField(null=True, blank=True)
    last_indexed = models.DateTimeField(default=timezone.now)

    # Métadonnées supplémentaires potentielles
    checksum = models.CharField(
        max_length=64, blank=True
    )  # Pour détecter les doublons ?

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["extension"]),
            models.Index(fields=["directory"]),
            models.Index(fields=["size"]),
            models.Index(fields=["modified_at"]),
        ]
        ordering = ["path"]
