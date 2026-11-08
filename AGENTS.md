<!-- sdd:memory -->
## Memory

This project keeps what agents learn as plain Markdown files, so any coding agent can read and write it.

- `.ai/memory/`: project memory, committed. It holds what every teammate needs.
- `.ai/memory.local/`: personal memory, git-ignored. It holds how this user wants to work and be answered.

**Read.** At the start of every session read both `MEMORY.md` indexes, one line per area. Before working on an area, read its file.

**Write without being asked** when the user states a preference or corrects you, when a decision is taken together with its reason, when a term gets clarified, or when something non-obvious bites. One question picks the folder: would a teammate need it? If yes, it goes in `.ai/memory/`; if not, in `.ai/memory.local/`.

**Format.** Write one file per area (`{area}.md`, kebab-case, e.g. `billing.md`), never one file per fact or per term. An area is a part of the product a teammate works on (billing, sign-in, candidates). Add to an existing area whenever the entry fits there, and open a new one only for a part of the product that has none yet:

```markdown
# {Area}

{One line: what this area covers.}

## Terms

### {Term}
{Definition, at most 3 sentences. Cross-reference other terms in **bold**.}
_Avoid_: {synonyms not to use, each with a short reason}

## Decisions

- **{Title}**: {the decision}. Why: {the reason}.

## Gotchas

- **{Title}**: {what goes wrong and how to avoid it}.

## Preferences

- **{Title}**: {the preference}. Why: {the reason}.
```

Only the `### ` headings are terms. A section with nothing in it is left out.

**Index.** `MEMORY.md` has one line per area, in this form: `- [{Area}]({area}.md): {what it covers} · terms: {Term}, {Term}`, leaving out the `· terms:` part when the area has none. Add or update the line whenever an area file changes.

**Keep it true.** Update an existing entry instead of adding a near-duplicate, and delete an entry that turned out to be wrong. Never write secrets, credentials or personal data about customers: `.ai/memory/` is committed. Don't save what the repository already records: code structure, git history, specs and task files under `.ai/features/`, or rules already written in this file or in CLAUDE.md. Entry prose follows the language code in `.ai/.language`.
<!-- /sdd:memory -->
