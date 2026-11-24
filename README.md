# organize-mistral

Turn PDF extractions from the [Mistral OCR playground](https://console.mistral.ai/document-ai/ocr-playground) into stable Markdown files with local images.

The playground export is a folder per PDF with a top-level `markdown.md`, per-page folders, and images referenced by bare placeholders such as `![img-0.jpeg](img-0.jpeg)`. `organize-mistral-extract` copies each export to:

- `<md-root>/<paper-slug>.md`: the Markdown with every local image reference rewritten to a relative path;
- `<img-root>/<paper-slug>/`: the images those references point to.

The raw export is never modified. Remote image URLs are left as they are. Standard library only; no dependencies.

## Usage

No install needed: run it with `uvx` from any project:

```sh
uvx --from git+https://github.com/HugoHakem/organize-mistral organize-mistral-extract --dry-run
uvx --from git+https://github.com/HugoHakem/organize-mistral organize-mistral-extract
```

Defaults match this layout (override with `--extract-root`, `--md-root`, `--img-root`):

```text
papers/
  pdf/              # source PDFs
  mistral-extract/  # raw playground exports (input, never edited)
  md/               # normalized Markdown (output)
  img/              # copied images (output)
```

Options:

- `--paper "<export folder name>"`: process only that export.
- `--dry-run`: report what would be written, without writing.

For a category subfolder, point all three roots at it:

```sh
uvx --from git+https://github.com/HugoHakem/organize-mistral organize-mistral-extract \
  --extract-root papers/mistral-extract/ehr-model \
  --md-root papers/md/ehr-model --img-root papers/img/ehr-model
```

## Getting the exports

1. Open the [OCR playground](https://console.mistral.ai/document-ai/ocr-playground) and drop in the PDF.
2. Export the full result: top-level `markdown.md`, per-page `markdown.md`, images, hyperlinks.
3. Save it as `papers/mistral-extract/<pdf file name>.pdf/`, keeping the PDF's file name, so the slug matches the source.

Expected export shape:

```text
papers/mistral-extract/
  Example Paper.pdf/
    markdown.md
    pages/
      page-1/
        markdown.md
        hyperlinks.md
        img-0.jpeg
```

The playground is free to use on Mistral's Free plan. The Mistral OCR API is a separate, metered product (about $4 per 1,000 pages for OCR 4.1) and is not included in the Free plan's API limits.

## Development

```sh
uv run --group dev pytest
```
