from pathlib import Path

from organize_mistral.organize_mistral_extract import main, slugify


def make_export(root: Path, name: str) -> Path:
    """Build a minimal Mistral playground export: markdown.md + pages/page-N/ images."""
    paper = root / f"{name}.pdf"
    (paper / "pages" / "page-1").mkdir(parents=True)
    (paper / "pages" / "page-2").mkdir(parents=True)
    (paper / "pages" / "page-1" / "img-0.jpeg").write_bytes(b"jpeg-0")
    (paper / "pages" / "page-2" / "img-1.jpeg").write_bytes(b"jpeg-1")
    (paper / "markdown.md").write_text(
        "# Title\n\n![img-0.jpeg](img-0.jpeg)\n\n<img src=\"img-1.jpeg\">\n\n![web](https://example.org/x.png)\n",
        encoding="utf-8",
    )
    return paper


def test_slugify_strips_accents_and_punctuation():
    assert slugify("Vollenweider and Bühlmann - 2026 - Signal, Bounds") == "vollenweider-and-buhlmann-2026-signal-bounds"


def test_organizes_markdown_and_images(tmp_path: Path):
    extract, md, img = tmp_path / "extract", tmp_path / "md", tmp_path / "img"
    make_export(extract, "Doe et al. - 2026 - A Paper")

    assert main(["--extract-root", str(extract), "--md-root", str(md), "--img-root", str(img)]) == 0

    out = md / "doe-et-al-2026-a-paper.md"
    text = out.read_text(encoding="utf-8")
    assert "](../img/doe-et-al-2026-a-paper/img-0.jpeg)" in text
    assert 'src="../img/doe-et-al-2026-a-paper/img-1.jpeg"' in text
    assert "https://example.org/x.png" in text  # remote images are left alone
    assert (img / "doe-et-al-2026-a-paper" / "img-0.jpeg").read_bytes() == b"jpeg-0"
    assert (img / "doe-et-al-2026-a-paper" / "img-1.jpeg").read_bytes() == b"jpeg-1"


def test_dry_run_writes_nothing(tmp_path: Path):
    extract, md, img = tmp_path / "extract", tmp_path / "md", tmp_path / "img"
    make_export(extract, "Doe et al. - 2026 - A Paper")

    assert main(["--extract-root", str(extract), "--md-root", str(md), "--img-root", str(img), "--dry-run"]) == 0
    assert not md.exists() and not img.exists()


def test_no_images_drops_local_refs_and_copies_nothing(tmp_path: Path):
    extract, md, img = tmp_path / "extract", tmp_path / "md", tmp_path / "img"
    paper = make_export(extract, "Doe et al. - 2026 - A Paper")
    for image in paper.rglob("*.jpeg"):  # an export downloaded without images
        image.unlink()

    assert main(["--extract-root", str(extract), "--md-root", str(md), "--img-root", str(img), "--no-images"]) == 0

    text = (md / "doe-et-al-2026-a-paper.md").read_text(encoding="utf-8")
    assert "img-0.jpeg" not in text and "img-1.jpeg" not in text
    assert "https://example.org/x.png" in text  # remote images are kept
    assert "\n\n\n" not in text  # no leftover blank-line gaps
    assert text.startswith("# Title\n")
    assert not img.exists()


def test_missing_images_without_flag_still_fails(tmp_path: Path):
    extract = tmp_path / "extract"
    paper = make_export(extract, "Doe et al. - 2026 - A Paper")
    for image in paper.rglob("*.jpeg"):
        image.unlink()
    try:
        main(["--extract-root", str(extract), "--md-root", str(tmp_path / "md"), "--img-root", str(tmp_path / "img")])
    except ValueError as exc:
        assert "could not resolve image reference" in str(exc)
    else:
        raise AssertionError("expected a ValueError for unresolved images")


def test_missing_extract_root_fails(tmp_path: Path):
    assert main(["--extract-root", str(tmp_path / "nope")]) == 1
