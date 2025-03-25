import os, mimetypes, hashlib
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import Directory, File


class Command(BaseCommand):
    help = "Scan filesystem recursively and update index"

    def add_arguments(self, parser):
        parser.add_argument("root_path", type=str, help="Root directory to scan")
        parser.add_argument("--full", action="store_true", help="Perform full rescan")

    def handle(self, *args, **options):
        root_path = options["root_path"]
        full_scan = options["full"]

        self.stdout.write(f"Starting scan of {root_path}")

        # Map pour cacher les directories déjà scannés
        directory_cache = {}

        # Fonction pour obtenir ou créer un répertoire
        def get_or_create_directory(dir_path):
            if dir_path in directory_cache:
                return directory_cache[dir_path]

            dir_obj, created = Directory.objects.get_or_create(
                path=dir_path,
                defaults={
                    "name": os.path.basename(dir_path) or dir_path,
                    "last_modified": timezone.now(),
                },
            )

            # Mettre à jour le parent si nécessaire
            parent_path = os.path.dirname(dir_path)
            if parent_path and parent_path != dir_path:
                parent = get_or_create_directory(parent_path)
                dir_obj.parent = parent
                dir_obj.save(update_fields=["parent"])

            directory_cache[dir_path] = dir_obj
            return dir_obj

        # Fonction récursive utilisant scandir
        def scan_directory(dir_path):
            self.stdout.write(f"Scanning {dir_path}")

            # Obtenir ou créer le répertoire actuel
            current_dir = get_or_create_directory(dir_path)
            current_dir.last_indexed = timezone.now()
            current_dir.save()

            try:
                # Utilisation de scandir pour de meilleures performances
                with os.scandir(dir_path) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir():
                                # Récursion sur les sous-répertoires
                                scan_directory(entry.path)
                            elif entry.is_file():
                                # Traitement du fichier
                                filename = entry.name
                                file_path = entry.path
                                stat = entry.stat()
                                extension = (
                                    os.path.splitext(filename)[1].lower().strip(".")
                                )

                                # Vérifier si le fichier existe déjà dans l'index
                                file_obj, created = File.objects.get_or_create(
                                    path=file_path,
                                    defaults={
                                        "name": filename,
                                        "directory": current_dir,
                                        "size": stat.st_size,
                                        "extension": extension,
                                        "mime_type": mimetypes.guess_type(filename)[0]
                                        or "",
                                        "created_at": timezone.datetime.fromtimestamp(
                                            stat.st_ctime
                                        ),
                                        "modified_at": timezone.datetime.fromtimestamp(
                                            stat.st_mtime
                                        ),
                                    },
                                )

                                # Mettre à jour si le fichier a été modifié
                                if not created and (
                                    full_scan
                                    or timezone.datetime.fromtimestamp(stat.st_mtime)
                                    > file_obj.last_indexed
                                ):
                                    file_obj.size = stat.st_size
                                    file_obj.modified_at = (
                                        timezone.datetime.fromtimestamp(stat.st_mtime)
                                    )
                                    file_obj.save()

                                file_obj.last_indexed = timezone.now()
                                file_obj.save(update_fields=["last_indexed"])

                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Error processing {entry.path}: {str(e)}"
                                )
                            )
            except PermissionError:
                self.stdout.write(self.style.WARNING(f"Permission denied: {dir_path}"))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error scanning directory {dir_path}: {str(e)}")
                )

        # Démarrer le scan
        scan_directory(root_path)
        self.stdout.write(self.style.SUCCESS("Successfully scanned files"))
