# Installing Demiurge

Demiurge is highly portable. Because it is fundamentally a system of prompts and knowledge files, it works by injecting Marcus and Buckminster into your preferred AI agent environment.

Below are the setup instructions organized by the three major frontier model ecosystems, covering Web, CLI, and IDE usage.

---

## 1. Google Gemini Ecosystem

### Google AI Studio (Web & API)

1. Create a new **System Instruction** prompt in Google AI Studio.
2. Paste the contents of `skills/marcus/SKILL.md` (or Buckminster).
3. Append the contents of `research/RESEARCH.md` below the instructions to ensure the agent has the correct foundational knowledge.
4. Save the prompt to use via the Gemini API or chat directly in the studio.

### Gemini Spark (Web)

1. Create a new **Gem** in Gemini.
2. Copy the contents of `skills/marcus/SKILL.md` and `skills/buckminster/SKILL.md` into the Gem's instructions.
3. Paste the contents of `research/RESEARCH.md` so the Gem has the baseline knowledge.

### Antigravity (IDE & CLI)

Antigravity is natively integrated with the Gemini ecosystem.

- **Antigravity IDE**: Open the Demiurge repository. The IDE automatically discovers the `.agents` and `skills` directories. Simply mention `@marcus` or `@buckminster` in your chat.
- **Antigravity CLI (`agy`)**:
  In your terminal, navigate to the project and install the skills locally:

  ```bash
  npx skills add path/to/demiurge/skills/marcus
  npx skills add path/to/demiurge/skills/buckminster
  ```

  Run `agy` and the agents will be available in your toolbelt.

---

## 2. Anthropic Claude Ecosystem

### Claude (Web)

1. Create a **Project** in the Claude web interface.
2. Upload `skills/marcus/SKILL.md`, `skills/buckminster/SKILL.md`, and `research/RESEARCH.md` to the Project Knowledge.
3. In the Custom Instructions, specify:
   > "You have access to two agent personas: Marcus and Buckminster. Read their respective SKILL.md files to assume their roles."

### Claude Code (CLI)

1. Claude Code supports standard Markdown-based system prompts.
2. Use the provided sync script to deploy the skills to `~/.claude/skills/`:

   ```bash
   bash scripts/sync-skills.sh
   ```

3. Run `claude` in your terminal, and the agents will be loaded.

---

## 3. OpenAI Ecosystem

### ChatGPT (Web)

1. Create a **Custom GPT**.
2. Upload `RESEARCH.md`, `skills/marcus/SKILL.md`, and `skills/buckminster/SKILL.md` to the Knowledge base.
3. In the GPT instructions, tell it to adopt the Marcus and Buckminster personas by reading the attached files when requested.

### Codex (CLI / API)

1. If you are using Codex through a custom harness, point your system prompt configuration to the `skills/` directory.
2. Ensure `RESEARCH.md` is loaded into the context window prior to generating agent architectures.

---

## 4. Universal IDE Integrations

### VS Code (via extensions like Cline or GitHub Copilot)

1. Open the Demiurge workspace.
2. For **Cline**: Cline automatically reads `.clinerules` or instructions in the workspace. You can set the workspace instructions to point to the `skills/` directory.
3. For **Copilot**: Mention `@workspace` and explicitly ask it to "Act as Marcus by reading skills/marcus/SKILL.md".

---

## 5. Optional Tooling: Research Connectors (For Buckminster)

Demiurge decouples synthesis from empirical research:

- **Marcus** (agent design, generation, and gate validation) is **fully offline and deterministic**. It executes via Python 3 standard library scripts and local reference documentation without external network access or tool dependencies.
- **Buckminster** surveys academic and empirical literature to propose updates to `research/RESEARCH.md`.

Fresh clones operate out-of-the-box without external connectors. Connecting scholarly Model Context Protocol (MCP) integrations improves research quality, verification depth, and retraction screening.

### Coverage Breakdown

| Connector | Empirical Coverage | Key Strength |
|---|---|---|
| [Undermind](https://undermind.ai) | 200M+ academic papers | Multi-agent systematic literature exploration, ranked evidence synthesis, and full-text PDF retrieval |
| [scite](https://scite.ai/mcp) | 210M+ records, 1.2B+ citations | Smart Citations indicating whether claims are supported, contrasted, or mentioned; surfaces `editorialNotices` for retractions and errata |
| [Consensus](https://consensus.app) | 220M+ peer-reviewed papers | Structured search across PubMed, Semantic Scholar, and arXiv; consensus ratios and study design filters |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov) | 36M+ biomedical citations | Direct NCBI access; useful for specialized life-sciences agent architectures (filtered out for CS/AI engineering) |

### Dependency Status and Fallback Behavior

- **Non-Breaking Dependency**: Missing connectors will not break Demiurge, Marcus, or repository test suites.
- **Graceful Degradation**: When connectors are unavailable in an agent runtime, Buckminster falls back to standard web search engines and open-access archives (arXiv, IETF, vendor engineering portals).
- **Audit Requirement**: When connectors are absent, Buckminster explicitly notes in diff proposals that citation reception and retraction notices could not be validated via Smart Citations. Findings without reception verification cannot be promoted to `[SETTLED]`.

### Official Connector Documentation

Refer to the official vendor documentation for setup instructions on your preferred agent platform:

- [Undermind MCP Documentation](https://mcp.undermind.ai)
- [scite MCP Documentation](https://scite.ai/mcp)
- [Consensus MCP Documentation](https://mcp.consensus.app)
- [Claude PubMed MCP Service](https://pubmed.mcp.claude.com)
