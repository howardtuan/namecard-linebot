from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from cards.models import BusinessCard


class Command(BaseCommand):
    help = "Delete uploaded business card image files and clear BusinessCard.image values."

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-orphans",
            action="store_true",
            help="Also delete files under MEDIA_ROOT/business_cards that are not referenced by the database.",
        )

    def handle(self, *args, **options):
        deleted = 0
        cleared = 0
        failed = 0

        for card in BusinessCard.objects.exclude(image=""):
            image_name = card.image.name
            try:
                card.image.delete(save=False)
                deleted += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(f"Failed to delete {image_name}: {exc}")

            card.image = ""
            card.save(update_fields=["image", "updated_at"])
            cleared += 1

        orphan_deleted = 0
        if options["include_orphans"]:
            orphan_deleted = self.delete_orphan_files()

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleared {cleared} image fields, deleted {deleted} referenced files, "
                f"deleted {orphan_deleted} orphan files, failed {failed} deletes."
            )
        )

    def delete_orphan_files(self) -> int:
        media_root = Path(settings.MEDIA_ROOT).resolve()
        business_cards_root = (media_root / "business_cards").resolve()
        if not business_cards_root.exists():
            return 0
        if not self.is_relative_to(business_cards_root, media_root):
            raise RuntimeError("Refusing to delete files outside MEDIA_ROOT.")

        deleted = 0
        for path in business_cards_root.rglob("*"):
            if not path.is_file():
                continue
            path.unlink()
            deleted += 1

        self.remove_empty_dirs(business_cards_root)
        return deleted

    @staticmethod
    def remove_empty_dirs(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            root.rmdir()
        except OSError:
            pass

    @staticmethod
    def is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return True
