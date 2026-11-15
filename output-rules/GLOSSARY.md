# Glossary: output rules

Terms for the rules that shape or enforce the form of model output. No implementation details here.

**doubled form** — A sentence that states a thing twice: once negated, once asserted. Forms: `it is not X, it is Y`, `not because X, but because Y`, `not just X, but Y`, `the question is not X. The question is Y`.

**compressed contrast** — A single clause that names two poles, `X, not Y`. Banned in all output, with no per-paragraph allowance.

**bare negation** — A plain "not" with no asserted contrast, such as `Silence is not a yes`. Allowed.

**trope** — A phrase or construction that marks text as machine-written. Negative parallelism and compressed contrast are the tropes this glossary covers.

**trope gate** — The shared check that flags tropes in text. It runs on chat replies, on files before a save, and on demand.

**surface** — A place where output appears: a chat reply, a saved file, a message sent to another person, or a code comment.

**Stop hook** — A check that runs when a reply ends. It can block the end of the reply and require a rewrite.

**pre-save hook** — A check that runs before a file write. It can block the write.

**overlap** — Two skills state the same rule.

**conflict** — Two skills give opposite instructions for the same output.

**competition** — Two skills claim the same surface, and no rule sets which one wins.

**always-on layer** — The set of output rules that apply to every chat reply without a request.
