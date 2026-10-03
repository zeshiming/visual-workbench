"""One-time legacy image copy; source files remain available for rollback."""

import os
import shutil
import tempfile
from pathlib import Path


def migrate_legacy_images(source: Path, target: Path) -> int:
    marker = target / '.legacy-images-v1.complete'
    if marker.exists() or not source.is_dir() or source.resolve() == target.resolve():
        return 0
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for original in sorted(source.rglob('*')):
        if original.is_symlink():
            raise ValueError('Legacy image migration does not follow symbolic links')
        if not original.is_file():
            continue
        relative = original.relative_to(source)
        if not (len(relative.parts) == 1 and original.suffix == '.json' or relative.parts[0] == 'assets'):
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            continue
        # Publish only a complete copy. link() never overwrites a newer target,
        # including when another process creates it during the copy.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as out:
                temporary = Path(out.name)
                with original.open('rb') as inp:
                    shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
            try:
                os.link(temporary, destination)
                copied += 1
            except FileExistsError:
                pass
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    # Written only after all copies succeed. Prevents deleted migrated photos
    # from reappearing on subsequent application starts.
    marker.touch(exist_ok=True)
    return copied
