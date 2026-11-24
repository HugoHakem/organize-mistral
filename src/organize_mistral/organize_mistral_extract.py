"""Copy Mistral PDF extracts into stable markdown and image locations."""

from __future__ import annotations

import argparse
import posixpath
import re
import shutil
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
HTML_IMAGE_SRC_RE = re.compile(r"(<img\b[^>]*?\bsrc=[\"'])([^\"']+)([\"'][^>]*>)", re.IGNORECASE)


@dataclass(frozen=True)
class PaperResult:
    paper: str
    markdown_path: Path
    copied_images: int
    rewritten_refs: int


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "paper"


def is_local_image_ref(ref: str) -> bool:
    parsed = urlparse(ref)
    if parsed.scheme or parsed.netloc:
        return False
    path = unquote(parsed.path)
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def build_image_targets(paper_dir: Path, image_out_dir: Path) -> dict[str, Path]:
    image_paths = sorted(
        path
        for path in paper_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    basename_counts = Counter(path.name for path in image_paths)
    targets: dict[str, Path] = {}

    for image_path in image_paths:
        if basename_counts[image_path.name] == 1:
            target_name = image_path.name
        else:
            page_name = image_path.parent.name
            target_name = f"{page_name}-{image_path.name}"

        relative_key = image_path.relative_to(paper_dir).as_posix()
        targets[relative_key] = image_out_dir / target_name

        if basename_counts[image_path.name] == 1:
            targets[image_path.name] = image_out_dir / target_name

    return targets


def resolve_image_ref(ref: str, image_targets: dict[str, Path]) -> Path | None:
    parsed = urlparse(ref)
    decoded_path = unquote(parsed.path)
    normalized_path = posixpath.normpath(decoded_path)

    candidates = [
        decoded_path,
        normalized_path,
        decoded_path.lstrip("./"),
        normalized_path.lstrip("./"),
        Path(decoded_path).name,
    ]
    for candidate in candidates:
        target = image_targets.get(candidate)
        if target is not None:
            return target

    return None


def rewrite_markdown(
    content: str,
    image_targets: dict[str, Path],
    markdown_path: Path,
) -> tuple[str, int, list[str]]:
    missing_refs: list[str] = []
    rewritten_refs = 0

    def replacement_path(target: Path) -> str:
        return posixpath.relpath(target.as_posix(), start=markdown_path.parent.as_posix())

    def replace_markdown_image(match: re.Match[str]) -> str:
        nonlocal rewritten_refs
        alt_text, ref, title = match.groups()
        if not is_local_image_ref(ref):
            return match.group(0)

        target = resolve_image_ref(ref, image_targets)
        if target is None:
            missing_refs.append(ref)
            return match.group(0)

        rewritten_refs += 1
        return f"![{alt_text}]({replacement_path(target)}{title or ''})"

    def replace_html_image(match: re.Match[str]) -> str:
        nonlocal rewritten_refs
        prefix, ref, suffix = match.groups()
        if not is_local_image_ref(ref):
            return match.group(0)

        target = resolve_image_ref(ref, image_targets)
        if target is None:
            missing_refs.append(ref)
            return match.group(0)

        rewritten_refs += 1
        return f"{prefix}{replacement_path(target)}{suffix}"

    content = MARKDOWN_IMAGE_RE.sub(replace_markdown_image, content)
    content = HTML_IMAGE_SRC_RE.sub(replace_html_image, content)
    return content, rewritten_refs, missing_refs


def process_paper(paper_dir: Path, md_root: Path, img_root: Path, dry_run: bool) -> PaperResult:
    source_markdown = paper_dir / "markdown.md"
    if not source_markdown.exists():
        raise FileNotFoundError(f"missing {source_markdown}")

    paper_stem = paper_dir.name.removesuffix(".pdf")
    paper_slug = slugify(paper_stem)
    markdown_path = md_root / f"{paper_slug}.md"
    image_out_dir = img_root / paper_slug

    image_targets = build_image_targets(paper_dir, image_out_dir)
    content = source_markdown.read_text(encoding="utf-8")
    rewritten_content, rewritten_refs, missing_refs = rewrite_markdown(content, image_targets, markdown_path)
    if missing_refs:
        refs = ", ".join(sorted(set(missing_refs)))
        raise ValueError(f"{paper_dir.name}: could not resolve image reference(s): {refs}")

    copied_images = 0
    for source_key, target in sorted(image_targets.items()):
        if "/" not in source_key:
            continue
        source = paper_dir / source_key
        copied_images += 1
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    if not dry_run:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(rewritten_content, encoding="utf-8")

    return PaperResult(
        paper=paper_dir.name,
        markdown_path=markdown_path,
        copied_images=copied_images,
        rewritten_refs=rewritten_refs,
    )


def find_paper_dirs(extract_root: Path) -> list[Path]:
    return sorted(path for path in extract_root.iterdir() if path.is_dir() and (path / "markdown.md").exists())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy Mistral PDF extracts to papers/md and papers/img with rewritten image references.",
    )
    parser.add_argument("--extract-root", type=Path, default=Path("papers/mistral-extract"))
    parser.add_argument("--md-root", type=Path, default=Path("papers/md"))
    parser.add_argument("--img-root", type=Path, default=Path("papers/img"))
    parser.add_argument("--paper", help="Process only one extracted paper directory name.")
    parser.add_argument("--dry-run", action="store_true", help="Report work without writing files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    extract_root = args.extract_root
    if not extract_root.exists():
        print(f"extract root does not exist: {extract_root}", file=sys.stderr)
        return 1

    paper_dirs = find_paper_dirs(extract_root)
    if args.paper:
        paper_dirs = [path for path in paper_dirs if path.name == args.paper]
        if not paper_dirs:
            print(f"paper not found under {extract_root}: {args.paper}", file=sys.stderr)
            return 1

    if not paper_dirs:
        print(f"no extracted papers found under {extract_root}", file=sys.stderr)
        return 1

    for paper_dir in paper_dirs:
        result = process_paper(paper_dir, args.md_root, args.img_root, args.dry_run)
        action = "would write" if args.dry_run else "wrote"
        print(
            f"{action} {result.markdown_path} "
            f"({result.rewritten_refs} refs, {result.copied_images} images)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
