import os
import json
import time
import requests
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files import File

from ...models import Document, DocumentImage


class Command(BaseCommand):
    help = "Importe les produits Louis Vuitton depuis leur API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--token",
            type=str,
            default="1e065749-d0e0-4caf-a0a6-87e2777ff102",
            help="Token d'identification pour l'API",
        )
        parser.add_argument(
            "--page-size", type=int, default=100, help="Nombre d'éléments par page"
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Délai entre les requêtes (en secondes)",
        )
        parser.add_argument(
            "--download-images",
            action="store_true",
            default=True,
            help="Télécharger les images",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            default=True,
            help="Ignorer les documents qui existent déjà",
        )
        parser.add_argument(
            "--output-file",
            type=str,
            default="",
            help="Chemin du fichier JSON de sortie (optionnel)",
        )
        parser.add_argument(
            "--gender",
            type=str,
            default="",
            choices=["Men", "Women", "Unisex", "NON APPLICABLE"],
            help="Filtre par sexe",
        )
        parser.add_argument(
            "--universe",
            type=str,
            default="",
            choices=["HARDSIDED", "LEATHER GOODS"],
            help="Filtre par univers",
        )
        parser.add_argument(
            "--start-from",
            type=int,
            default=0,
            help="Position de départ pour la pagination (pour reprendre après interruption)",
        )

    def handle(self, *args, **options):
        token_id = options["token"]
        page_size = options["page_size"]
        delay_seconds = options["delay"]
        download_images = options["download_images"]
        skip_existing = options["skip_existing"]
        output_file = options["output_file"]
        gender = options["gender"]
        universe = options["universe"]
        start_from = options["start_from"]

        # Configuration de l'URL et des headers
        url = "https://product-library.vuitton.net/api/search/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:136.0) Gecko/20100101 Firefox/136.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "Origin": "https://product-library.vuitton.net",
            "Connection": "keep-alive",
            "Referer": "https://product-library.vuitton.net/",
            "Cookie": f"tokenId={token_id}",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Priority": "u=0",
            "TE": "trailers",
        }

        # Position de départ (utilisez la valeur fournie)
        current_from = start_from
        # Nombre total de résultats (sera mis à jour lors de la première requête)
        total_hits = None
        # Liste pour stocker tous les produits si output_file est spécifié
        all_products = []
        # Compteurs pour statistiques
        stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "images_downloaded": 0,
            "images_not_found": 0,
            "images_damaged": 0,
            "images_forbidden": 0,
        }

        self.stdout.write(
            self.style.NOTICE(
                f"Démarrage de l'importation des produits Louis Vuitton (à partir de l'index {start_from})..."
            )
        )

        # Boucle principale pour récupérer tous les produits
        while total_hits is None or current_from < total_hits:
            # Préparation du payload avec la position actuelle
            payload = {
                "locale": "en_US",
                "size": page_size,
                "from": current_from,
                "search": "",
                "currency": "USD",
                "sortBy": {"field": "relevance", "isAsc": False},
                "filters": [
                    {
                        "field": "excludeObsoletes",
                        "value": False,
                        "key": "exclude_obsoletes_label",
                    },
                    {
                        "field": "includeCanceled",
                        "value": False,
                        "key": "include_cancelled_label",
                    },
                    {
                        "field": "includeSpecialCmd",
                        "value": False,
                        "key": "include_special_order_label",
                    },
                    {
                        "field": "includeNonSellable",
                        "value": False,
                        "key": "include_non_sellable_label",
                    },
                ],
            }

            if gender:
                payload["filters"].append({"field": "gender", "value": gender})
            if universe:
                payload["filters"].append({"field": "universe", "value": universe})

            self.stdout.write(
                f"Récupération des résultats {current_from+1} à {current_from+page_size}..."
            )

            try:
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()  # Lève une exception en cas d'erreur HTTP

                data = response.json()

                # Mise à jour du nombre total de résultats si c'est la première requête
                if total_hits is None:
                    total_hits = data["nbHits"]
                    self.stdout.write(
                        self.style.SUCCESS(f"Nombre total de résultats: {total_hits}")
                    )

                # Traitement des produits
                products = data.get("products", [])

                if output_file:
                    all_products.extend(products)

                # Importation des produits dans Django
                self._import_products(products, download_images, skip_existing, stats)

                # Mise à jour de la position pour la prochaine requête
                current_from += page_size

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Progression: {min(current_from, total_hits)}/{total_hits} "
                        f"({round(min(current_from, total_hits) / total_hits * 100, 2)}%), index actuel: {current_from}"
                    )
                )

                # Pause pour ne pas surcharger le serveur
                time.sleep(delay_seconds)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur lors de la requête: {e}"))
                # En cas d'erreur, on attend un peu plus longtemps avant de réessayer
                time.sleep(5)
                continue

        # Sauvegarde des résultats dans un fichier JSON si demandé
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_products, f, ensure_ascii=False, indent=2)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Tous les produits ont été sauvegardés dans {output_file}"
                )
            )

        # Affichage des statistiques finales
        self.stdout.write(self.style.SUCCESS("Importation terminée avec succès!"))
        self.stdout.write("Statistiques:")
        self.stdout.write(f"  - Documents créés: {stats['created']}")
        self.stdout.write(f"  - Documents mis à jour: {stats['updated']}")
        self.stdout.write(f"  - Documents ignorés: {stats['skipped']}")
        self.stdout.write(f"  - Images téléchargées: {stats['images_downloaded']}")
        self.stdout.write(f"  - Images non trouvées (404): {stats['images_not_found']}")
        self.stdout.write(f"  - Images endommagées (422): {stats['images_damaged']}")
        self.stdout.write(
            f"  - Images inaccessibles (403): {stats['images_forbidden']}"
        )
        self.stdout.write(f"  - Index final: {current_from}")
        self.stdout.write(
            f"  - Pour reprendre à ce point en cas d'interruption: --start-from={current_from}"
        )

    def _import_products(self, products, download_images, skip_existing, stats):
        """Importe les produits dans la base de données Django"""
        for product in products:
            document_id = product.get("_document_id")

            if not document_id:
                self.stdout.write(
                    self.style.WARNING(
                        f"Produit sans document_id ignoré: {product.get('idProduct')}"
                    )
                )
                stats["skipped"] += 1
                continue

            # Vérification si le document existe déjà
            document_exists = Document.objects.filter(document_id=document_id).exists()

            if document_exists and skip_existing:
                # Vérifier que toutes les images ont été téléchargées
                document = Document.objects.get(document_id=document_id)

                # Si le nombre d'images sauvegardées ne correspond pas au nombre d'images attendues
                # ou si au moins une image n'a pas encore été téléchargée, on retélécharge
                expected_images = product.get("images", [])
                existing_images = document.images.all()

                if len(existing_images) != len(expected_images) or any(
                    not img.image_file for img in existing_images
                ):
                    # Les images sont incomplètes, on efface les existantes et on les retélécharge
                    document.images.all().delete()
                    self.stdout.write(
                        f"Images incomplètes pour {document}, retéléchargement..."
                    )
                else:
                    self.stdout.write(f"Document existant ignoré: {document}")
                    stats["skipped"] += 1
                    continue

            if document_exists:
                # Le document existe, on le récupère pour mettre à jour ou l'utiliser
                document = Document.objects.get(document_id=document_id)
                if not skip_existing:
                    # Mise à jour du document
                    for key, value in self._prepare_document_data(product).items():
                        setattr(document, key, value)
                    document.save()
                    self.stdout.write(f"Document mis à jour: {document.product_name}")
                    stats["updated"] += 1
            else:
                # Création du document
                document = Document.objects.create(
                    document_id=document_id, **self._prepare_document_data(product)
                )
                self.stdout.write(f"Document créé: {document}")
                stats["created"] += 1

            # Traitement des images
            images = product.get("images", [])
            if images and download_images:
                self._process_images(document, images, stats)

    def _prepare_document_data(self, product):
        """Prépare les données du document à partir des données du produit"""
        # Conversion des dates si elles existent
        launch_date = None
        if product.get("launchDate"):
            try:
                launch_date = datetime.strptime(
                    product["launchDate"], "%d-%m-%Y"
                ).date()
            except (ValueError, TypeError):
                pass

        retrieval_date = None
        if product.get("retrievalDate"):
            try:
                retrieval_date = datetime.strptime(
                    product["retrievalDate"], "%d-%m-%Y"
                ).date()
            except (ValueError, TypeError):
                pass

        return {
            "score": product.get("_score"),
            "product_id": product.get("idProduct", ""),
            "sku_code": product.get("skuCode", ""),
            "price": product.get("price", 0),
            "product_name": product.get("productName", ""),
            "sap_name": product.get("sapName"),
            "sap_model": product.get("sapModel"),
            "material": product.get("material"),
            "material_id": product.get("materialId"),
            "launch_date": launch_date,
            "retrieval_date": retrieval_date,
            "color": product.get("color"),
            "macro_color_id": product.get("macroColorId"),
            "best_seller": (
                product.get("bestSeller")
                if (
                    type(product.get("bestSeller")) == bool
                    and product.get("bestSeller")
                )
                else False  # Car pour certains produits l'attribut a une chaîne de caractères bizarres pour valeur.
            ),
            "is_obsolete": product.get("isObsolete", False),
            "is_canceled": product.get("isCanceled", False),
            "is_blocked_sale": product.get("isBlockedSale", False),
            "sap_width": product.get("sapWidth"),
        }

    def _process_images(self, document, image_urls, stats):
        """Traite et télécharge les images d'un document"""
        # Créer le dossier pour les images dans media/XX/document_id/
        document_id = document.document_id
        prefix = document_id[:2] if len(document_id) >= 2 else "00"

        media_root = getattr(settings, "MEDIA_ROOT", "")
        document_path = os.path.join(prefix, document_id)
        document_folder = os.path.join(media_root, document_path)
        os.makedirs(document_folder, exist_ok=True)

        for index, image_url in enumerate(image_urls):
            image_url_ = requests.utils.unquote(image_url)
            # Extraire le nom du fichier depuis l'URL
            image_filename = os.path.basename(image_url_)
            if not image_filename:
                image_filename = f"{index + 1}.jpg"

            # Définir le chemin relatif et absolu du fichier
            relative_path = f"{document_path}/{image_filename}"
            file_path = os.path.join(media_root, relative_path)

            # Vérifier si l'image existe déjà en base
            image, created = DocumentImage.objects.get_or_create(
                document=document, image_url=image_url, defaults={"order": index}
            )

            try:
                # Télécharger l'image
                image_response = requests.get(image_url_, timeout=10)

                # Vérifier les codes d'erreur spécifiques
                if image_response.status_code == 404:
                    stats["images_not_found"] += 1
                    self.stdout.write(
                        self.style.WARNING(f"  Image non trouvée (404): {image_url}")
                    )
                    continue
                elif image_response.status_code == 403:
                    stats["images_forbidden"] += 1
                    self.stdout.write(
                        self.style.WARNING(f"  Image inaccessible (403): {image_url}")
                    )
                    continue
                elif image_response.status_code == 422:
                    stats["images_damaged"] += 1
                    self.stdout.write(
                        self.style.WARNING(f"  Image endommagée (422): {image_url}")
                    )
                    continue

                # Pour les autres erreurs HTTP, on lève une exception
                image_response.raise_for_status()

                # Sauvegarder directement le fichier sur le disque au lieu d'utiliser save()
                # pour éviter que Django ne renomme le fichier
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "wb") as f:
                    f.write(image_response.content)

                # Mettre à jour le chemin dans la base de données sans passer par save()
                # qui pourrait renommer le fichier
                if image.image_file.name != relative_path:
                    # Mettre à jour directement le champ sans passer par le mécanisme de sauvegarde normal
                    DocumentImage.objects.filter(pk=image.pk).update(
                        image_file=relative_path
                    )
                    # Rafraîchir l'instance depuis la base de données
                    image.refresh_from_db()

                stats["images_downloaded"] += 1
                self.stdout.write(f"  Image téléchargée: {relative_path}")

                # Petite pause pour ne pas surcharger le serveur
                time.sleep(0.2)

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # Pour les erreurs 404, on ignore simplement l'image et on continue
                    stats["images_not_found"] += 1
                    self.stdout.write(
                        self.style.WARNING(f"  Image non trouvée (404): {image_url}")
                    )
                    continue
                elif e.response.status_code == 422:
                    # Pour les erreurs 422, on ignore aussi et on continue
                    stats["images_damaged"] += 1
                    self.stdout.write(
                        self.style.WARNING(f"  Image endommagée (422): {image_url}")
                    )
                    continue
                else:
                    # Pour les autres erreurs HTTP, on arrête le script
                    error_msg = f"Erreur HTTP lors du téléchargement de l'image {image_url}: {e}"
                    self.stdout.write(self.style.ERROR(error_msg))
                    raise CommandError(error_msg)
            except Exception as e:
                # Pour toute autre erreur (réseau, disque, etc.), on arrête le script
                error_msg = f"Erreur lors du téléchargement de l'image {image_url}: {e}"
                self.stdout.write(self.style.ERROR(error_msg))
                raise CommandError(error_msg)
