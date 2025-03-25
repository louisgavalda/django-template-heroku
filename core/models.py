from datetime import datetime
import os

from django.db import models


class Directory(models.Model):
    path = models.CharField(max_length=1024, unique=True)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    last_modified = models.DateTimeField()
    last_indexed = models.DateTimeField(default=datetime.now)

    def __str__(self):
        return self.path

    class Meta:
        verbose_name_plural = "Directories"
        indexes = [
            models.Index(fields=["path"]),
            models.Index(fields=["name"]),
            models.Index(fields=["parent"]),
        ]


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
    last_indexed = models.DateTimeField(default=datetime.now)

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
