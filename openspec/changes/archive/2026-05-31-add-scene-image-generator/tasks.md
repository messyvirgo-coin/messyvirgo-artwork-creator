## 1. Scene Prompting and Execution

- [x] 1.1 Add failing tests for scene prompt composition, empty field validation, dry-run plan data, metadata, resume, and provider request behavior.
- [x] 1.2 Add scene prompt YAML configuration derived from the Messy reference prompts.
- [x] 1.3 Implement scene prompt loading/composition and scene execution with PNG output, metadata, retry, regenerate, and dry-run support.

## 2. CLI Integration

- [x] 2.1 Add failing tests for the `scene` CLI subcommand and preservation of existing command parsing.
- [x] 2.2 Implement the `scene` CLI subcommand.

## 3. Local Web Interface

- [x] 3.1 Add failing tests for web page rendering, scene dry-run handling, reference dry-run handling, and error rendering.
- [x] 3.2 Implement the `web` CLI subcommand and standard-library local web server.

## 4. Documentation and Verification

- [x] 4.1 Document scene generation and the web interface in README and the runbook.
- [x] 4.2 Run OpenSpec status, the full unit test suite, and iterative review/fix passes until no actionable findings remain.
