# Translation Guidelines

[Contributing](../CONTRIBUTING.md) · [Development Guide](DEVELOPMENT.md)

## Choose a scope

Tell the maintainer which language and files you plan to translate, especially
for a new interface language. HDM currently stores interface text directly in
Python, HTML and JavaScript files; it does not have separate language catalogs
or a language-switching workflow yet.

For a new interface language, discuss integration before replacing existing
labels. Documentation translations can use language-specific files such as
`README.de.md` or `docs/de/USAGE.md`; keep the English originals available.

## Preserve behavior

- Translate visible labels, help text, messages and documentation.
- Keep code identifiers, HTML IDs, storage keys, API fields, URLs and commands
  unchanged unless the change is required and explained.
- Preserve format placeholders such as `{name}`, `{count}`, `%s`, and `${value}`.
- Keep product names, file extensions, keyboard shortcuts and technical terms
  consistent. Preserve existing license and copyright notices.
- Do not edit generated icon bundles, dependencies or third-party notices.

## Check and submit

Use concise wording that fits the interface. Review labels, dialogs and error
messages in context; include screenshots when changing interface text. For
Markdown, verify links and code blocks and check the rendered page.

Open a pull request naming the language, translated files and checks performed.
Describe any untranslated text or integration work still needed. Source and
contributions remain subject to the repository [license](../LICENSE).
