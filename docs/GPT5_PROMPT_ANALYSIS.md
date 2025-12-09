# GPT-5.1 Prompting Guide Analyse für Hive Agent Swarm

> Erstellt: 2025-11-28
> Quellen:
> - [GPT-5.1 Prompting Guide](https://cookbook.openai.com/examples/gpt-5/gpt-5-1_prompting_guide)
> - [GPT-5-Codex Prompting Guide](https://cookbook.openai.com/examples/gpt-5-codex_prompting_guide)
> - [Build a Coding Agent with GPT-5.1](https://cookbook.openai.com/examples/build_a_coding_agent_with_gpt-5.1)

---

## Executive Summary

| Erkenntnis | Impact | Unser Status |
|------------|--------|--------------|
| **"Less is more"** - Codex ist vortrainiert | Hoch | ❌ Zu lange Prompts |
| **Solution Persistence** - Autonom bis fertig | Hoch | ❌ Fehlt |
| **Plan Tool** - 2-5 Milestones, 1x in_progress | Mittel | ✅ Vorhanden |
| **Git-Awareness** - Nie fremde Änderungen reverten | Hoch | ❌ Fehlt |
| **Code Review** - Bugs first, Summaries last | Mittel | 🟡 Teilweise |
| **Apply Patch** - Native Tool, 35% weniger Fehler | Hoch | ❌ Nicht genutzt |

---

## 🔴 1. Solution Persistence (KRITISCH)

### OpenAI Original:

```xml
<solution_persistence>
- Treat yourself as an autonomous senior pair-programmer: once the user gives 
  a direction, proactively gather context, plan, implement, test, and refine 
  without waiting for additional prompts at each step.
- Persist until the task is fully handled end-to-end within the current turn: 
  do not stop at analysis or partial fixes; carry changes through implementation, 
  verification, and a clear explanation of outcomes.
- Be extremely biased for action. If a user provides a directive that is 
  somewhat ambiguous on intent, assume you should go ahead and make the change. 
  If the user asks "should we do x?" and your answer is "yes", go ahead and 
  perform the action. It's very bad to leave the user hanging.
</solution_persistence>
```

### Empfehlung für unsere Agents:

```yaml
## Arbeitsweise (WICHTIG)
- Du bist ein autonomer Senior Pair-Programmer
- Arbeite proaktiv: Kontext sammeln → planen → implementieren → testen → verfeinern
- Beende Tasks END-TO-END - nicht bei Analyse oder Teilfixes aufhören
- Sei ACTION-BIASED: Im Zweifel mache die Änderung statt nachzufragen
- Lass den User niemals hängen mit "soll ich das machen?"
```

---

## 🔴 2. Git-Awareness (KRITISCH)

### OpenAI Original (Codex CLI):

```markdown
- You may be in a dirty git worktree.
  * NEVER revert existing changes you did not make unless explicitly requested
  * If asked to make a commit and there are unrelated changes, don't revert them
  * If changes are in files you've touched, read carefully and work WITH them
  * If changes are in unrelated files, ignore them and don't revert
- While working, if you notice unexpected changes you didn't make: 
  STOP IMMEDIATELY and ask the user how to proceed.
```

### Unser Status: ❌ Fehlt komplett

### Empfehlung:

```yaml
## Git-Verhalten
- NIEMALS existierende Änderungen reverten, die du nicht gemacht hast
- Bei unrelated changes: ignorieren, nicht reverten
- Bei unexpected changes: STOPPEN und User fragen
```

---

## 🔴 3. "Less is More" für Coding (KRITISCH)

### OpenAI Original:

> "The core prompting principle for GPT-5-Codex is 'less is more'":
> 1. Start with a minimal prompt, then add only essential guidance
> 2. Remove any prompting for preambles (model does not support them)
> 3. Reduce tools to only terminal + apply_patch
> 4. Make tool descriptions as concise as possible

### Unser Status: ❌ Unsere Prompts sind zu lang

### Empfehlung:

Unsere Developer-Prompts (Backend, Frontend) können gekürzt werden:
- Weniger aufgelistete Tools (nur die wichtigsten)
- Kürzere Tool-Beschreibungen
- Keine redundanten Anweisungen

---

## 🟡 4. Plan Tool Usage (WICHTIG)

### OpenAI Original:

```xml
<plan_tool_usage>
- For medium/larger tasks: create 2–5 milestone/outcome items BEFORE coding
- Avoid micro-steps (no "open file", "run tests")
- Never use single catch-all item like "implement entire feature"
- Exactly ONE item in_progress at a time
- Do not jump pending → completed: always set in_progress first
- Skip planning for straightforward tasks (easiest 25%)
- Do not make single-step plans
</plan_tool_usage>
```

### Unser Status: ✅ Wir haben `update_plan`

### Verbesserung:
- Agenten sollten Plan vor erstem Tool-Call erstellen
- Explizit "nur 1 Item in_progress" dokumentieren

---

## 🟡 5. Code Review Fokus (WICHTIG)

### OpenAI Original (Codex CLI):

```markdown
If the user asks for a "review", default to a code review mindset: 
- Prioritise identifying bugs, risks, behavioural regressions, and missing tests
- Findings must be the primary focus - keep summaries brief and AFTER issues
- Present findings FIRST (ordered by severity with file/line refs)
- Follow with open questions or assumptions
- Offer change-summary only as secondary detail
- If no findings: state explicitly and mention residual risks or testing gaps
```

### Unser Status: 🟡 Teilweise (Architect macht Review, aber Fokus fehlt)

### Empfehlung für Architect:

```yaml
## Code Review
- BUGS und RISKS zuerst (nach Severity sortiert, mit Datei:Zeile)
- Summaries nur als Nachsatz
- Wenn keine Findings: explizit sagen + Testing-Gaps nennen
```

---

## 🟢 6. Apply Patch Tool (NICE-TO-HAVE)

### OpenAI Original:

> "With GPT-5.1, you can use apply_patch as a new tool type without writing 
> custom descriptions. The named function decreased apply_patch failure rates by 35%."

### Unser Status: ❌ Wir nutzen `edit_file` stattdessen

### Empfehlung:
- Für zukünftige GPT-5.1 Integration: Native apply_patch nutzen
- Aktuell: Unser `edit_file` ist funktional äquivalent

---

## 🟢 7. Context7 MCP für Docs (NICE-TO-HAVE)

### OpenAI Original:

```python
from agents import HostedMCPTool
context7_tool = HostedMCPTool(
    tool_config={
        "type": "mcp",
        "server_label": "context7",
        "server_url": "https://mcp.context7.com/mcp",
    },
)
```

### Unser Status: ❌ Nicht integriert

### Empfehlung:
- Für Phase 2 RAG: Context7 MCP als Alternative/Ergänzung zu ChromaDB evaluieren
- Liefert aktuelle Dokumentation für externe APIs

---

## Konkrete Änderungen für `config/agents.yaml`

### 1. Neue gemeinsame Basis für ALLE Developer-Agents:

```yaml
## Arbeitsweise
- Du bist ein autonomer Senior Pair-Programmer
- Arbeite END-TO-END: Kontext → Plan → Implementierung → Test → Verifikation
- Sei ACTION-BIASED: Im Zweifel machen statt fragen
- NIEMALS fremde Git-Änderungen reverten ohne explizite Anfrage
- Bei unerwarteten Änderungen: STOPPEN und User fragen
```

### 2. Backend/Frontend Dev - Kürzen auf Essentials:

```yaml
## Verfügbare Tools
- read_file, write_file, edit_file (für Code)
- run_command (für Tests)
- git_commit, git_status (für Versionierung)
```

### 3. Architect - Code Review verbessern:

```yaml
## Code Review
Priorität der Findings:
1. 🔴 Bugs und Security Issues (mit Datei:Zeile)
2. 🟡 Performance und Regressions-Risiken
3. 🟢 Best Practices Verletzungen

Format: Findings ZUERST, Summary am Ende.
Keine Findings? → Explizit sagen + Testing-Gaps nennen.
```

---

## Zusammenfassung der Änderungen

| Bereich | Aktion | Priorität |
|---------|--------|-----------|
| Solution Persistence | Zu allen Dev-Prompts hinzufügen | 🔴 Hoch |
| Git-Awareness | Zu allen Dev-Prompts hinzufügen | 🔴 Hoch |
| Prompt-Länge | Dev-Prompts kürzen | 🔴 Hoch |
| Code Review | Architect-Prompt verbessern | 🟡 Mittel |
| Plan Tool | Dokumentation verbessern | 🟡 Mittel |
| Apply Patch | Für GPT-5.1 Migration vorbereiten | 🟢 Niedrig |
| Context7 MCP | In Phase 2 RAG evaluieren | 🟢 Niedrig |

---

## Nächste Schritte

1. **Sofort**: `config/agents.yaml` mit Solution Persistence + Git-Awareness aktualisieren
2. **Sofort**: Dev-Prompts kürzen ("less is more")
3. **Phase 2**: Context7 MCP Integration evaluieren
4. **Langfristig**: Migration auf native GPT-5.1 Tools (apply_patch, shell)
