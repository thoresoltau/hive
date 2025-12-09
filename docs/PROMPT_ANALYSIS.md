# Analyse: OpenAI Prompting Guides vs. Hive Agent Prompts

> Erstellt: 2025-11-28 (aktualisiert mit GPT-5.1 Guides)
> Quellen: 
> - GPT-5.1 Prompting Guide
> - GPT-5-Codex Prompting Guide
> - Build a Coding Agent with GPT-5.1
> - Codex Code Review SDK Guide

---

## Executive Summary

Die aktuellen OpenAI GPT-5.1 Prompting Guides enthalten **kritische Best Practices**, die in unseren Agent-Prompts fehlen. Besonders wichtig: **"Less is more"** - GPT-5-Codex ist für Coding optimiert, zu viel Prompting kann die Qualität verschlechtern.

**Priorität der Änderungen:**
1. 🔴 **Kritisch**: Solution Persistence (`<solution_persistence>` Pattern)
2. 🔴 **Kritisch**: Plan Tool Integration (2-5 Milestones)
3. 🟡 **Wichtig**: Git-Awareness (nie fremde Änderungen reverten)
4. 🟡 **Wichtig**: Code Review Fokus (Bugs > Summaries)
5. 🟢 **Nice-to-Have**: Minimale Prompts für Codex
6. 🟢 **Nice-to-Have**: Context7 MCP Integration für Docs

---

## 1. Solution Persistence (GPT-5.1) 🔴 KRITISCH

### Was OpenAI empfiehlt (GPT-5.1 Prompting Guide):

```xml
<solution_persistence>
- Treat yourself as an autonomous senior pair-programmer: once the user gives 
  a direction, proactively gather context, plan, implement, test, and refine 
  without waiting for additional prompts at each step.
- Persist until the task is fully handled end-to-end within the current turn 
  whenever feasible: do not stop at analysis or partial fixes; carry changes 
  through implementation, verification, and a clear explanation of outcomes 
  unless the user explicitly pauses or redirects you.
- Be extremely biased for action. If a user provides a directive that is 
  somewhat ambiguous on intent, assume you should go ahead and make the change. 
  If the user asks a question like "should we do x?" and your answer is "yes", 
  you should also go ahead and perform the action. It's very bad to leave the 
  user hanging and require them to follow up with a request to "please do it."
</solution_persistence>
```

### Was wir haben:

❌ **Keine** Persistence-Anweisungen  
❌ **Keine** expliziten "Don't Guess" Anweisungen  
❌ **Keine** Planning-Aufforderungen  

### Empfehlung:

**Jeden Agent-Prompt erweitern mit:**
```yaml
## Arbeitsweise
- Arbeite autonom bis das Problem vollständig gelöst ist
- Nutze IMMER Tools um Informationen zu verifizieren - rate NIEMALS
- Plane jeden Schritt BEVOR du ein Tool aufrufst
- Reflektiere nach jedem Tool-Aufruf über das Ergebnis
```

---

## 2. Strukturierter Workflow (SWE-bench Pattern)

### Was OpenAI empfiehlt:

Der SWE-bench Prompt definiert einen **8-Schritte Workflow**:

1. **Understand the problem deeply** - Carefully read and think critically
2. **Investigate the codebase** - Explore files, search functions, gather context
3. **Develop a detailed plan** - Break down into small, incremental steps
4. **Implement incrementally** - Make small, testable changes
5. **Debug as needed** - Determine root cause, not symptoms
6. **Test frequently** - Run tests after each change
7. **Final verification** - Review solution for correctness
8. **Final reflection** - Think about edge cases, write additional tests

### Was wir haben:

Unsere Prompts haben:
- ✅ Aufgaben-Liste
- ✅ Tool-Beschreibungen
- ❌ **Keinen** strukturierten Workflow
- ❌ **Keine** expliziten Debugging-Anweisungen
- ❌ **Keine** Test-Betonung

### Empfehlung:

**Workflow-Sektion zu allen Dev-Agents hinzufügen:**
```yaml
## Workflow

### 1. Problem verstehen
- Lies das Ticket und alle Acceptance Criteria sorgfältig
- Stelle Rückfragen wenn etwas unklar ist

### 2. Codebase untersuchen
- Nutze list_directory und find_files um relevante Dateien zu finden
- Lies existierenden Code um Patterns zu verstehen
- Identifiziere die Root Cause bei Bugs

### 3. Plan erstellen
- Brich die Aufgabe in kleine, testbare Schritte
- Dokumentiere deinen Plan bevor du implementierst

### 4. Inkrementell implementieren
- Mache kleine Änderungen
- Committe nach jedem logischen Schritt

### 5. Testen
⚠️ KRITISCH: Unzureichendes Testen ist der häufigste Fehlergrund!
- Führe Tests nach JEDER Änderung aus
- Teste Edge Cases
- Schreibe zusätzliche Tests wenn nötig

### 6. Verifizieren
- Prüfe ob alle Acceptance Criteria erfüllt sind
- Führe einen finalen Test-Durchlauf durch
```

---

## 3. Code Review Prompt

### Was OpenAI empfiehlt:

```
You are acting as a reviewer for a proposed code change made by another engineer. 
Focus on issues that impact correctness, performance, security, maintainability, 
or developer experience. Flag only actionable issues introduced by the pull request. 
When you flag an issue, provide a short, direct explanation and cite the affected 
file and line range. Prioritize severe issues and avoid nit-level comments unless 
they block understanding of the diff. After listing findings, produce an overall 
correctness verdict ("patch is correct" or "patch is incorrect") with a concise 
justification and a confidence score between 0 and 1.
```

### Was wir haben:

Unser Architect-Prompt für Code Review:
- ✅ Prüft Code-Qualität
- ✅ Prüft Architektur-Konformität
- ❌ **Keine** Prioritätsstufen für Issues
- ❌ **Kein** Confidence Score
- ❌ **Keine** Fokussierung auf "actionable issues"

### Empfehlung:

**Code-Review Prompt verbessern:**
```yaml
## Code Review
Führe ein Review durch und fokussiere auf:
1. **Korrektheit** - Funktioniert der Code wie erwartet?
2. **Sicherheit** - Gibt es Security-Vulnerabilities?
3. **Performance** - Gibt es Performance-Probleme?
4. **Wartbarkeit** - Ist der Code lesbar und wartbar?

### Regeln:
- Flagge NUR actionable Issues, die durch diese Änderung eingeführt wurden
- Priorisiere schwerwiegende Issues über Nit-Picking
- Gib für jedes Issue: Datei, Zeile, Severity (error/warning/info), Erklärung
- Gib am Ende ein Verdict: "approved" oder "changes_requested"
- Gib einen Confidence Score (0-1) für dein Review
```

---

## 4. Prompt-Struktur

### Was OpenAI empfiehlt:

```markdown
# Role and Objective
# Instructions
## Sub-categories for detailed instructions
# Reasoning Steps
# Output Format
# Examples
## Example 1
# Context
# Final instructions and prompt to think step by step
```

### Was wir haben:

```yaml
Du bist ein erfahrener [Rolle].

## Deine Aufgaben
- ...

## Verfügbare Tools
- ...
```

### Empfehlung:

**Prompts umstrukturieren:**
```yaml
# Rolle und Ziel
Du bist der [Rolle] im Hive Agent Swarm Team.
Dein Ziel: [klares, messbares Ziel]

# Anweisungen
## Kernaufgaben
- ...

## Arbeitsweise
- Arbeite autonom bis das Problem gelöst ist
- Nutze Tools - rate NIEMALS
- Plane vor jedem Tool-Aufruf

# Workflow
1. ...
2. ...

# Verfügbare Tools
## File-Tools
- read_file: [Beschreibung + wann nutzen]
...

# Output-Format
[Erwartetes Format der Antworten]

# Beispiele
## Beispiel: Ticket analysieren
[Konkretes Beispiel]

# Kontext
[Projekt-spezifischer Kontext]

# Abschließende Anweisung
Denke Schritt für Schritt. Verifiziere jeden Schritt bevor du fortfährst.
```

---

## 5. Delimiters

### Was OpenAI empfiehlt:

- **Markdown** (empfohlen): `#`, `##`, ``` für Code
- **XML**: Gut für strukturierte Daten
- **JSON**: Vermeiden bei Long Context

### Was wir haben:

✅ Wir nutzen bereits Markdown - das ist gut!

### Empfehlung:

Keine Änderung nötig, aber konsistenter sein bei der Verwendung.

---

## 6. Tool-Beschreibungen

### Was OpenAI empfiehlt:

> "Developers should name tools clearly to indicate their purpose and add a clear, 
> detailed description in the 'description' field of the tool."

> "If your tool is particularly complicated and you'd like to provide examples of 
> tool usage, we recommend that you create an # Examples section in your system 
> prompt and place the examples there."

### Was wir haben:

Unsere Tool-Beschreibungen sind kurz:
```python
description = "Löscht eine Datei. Kann keine Verzeichnisse löschen."
```

### Empfehlung:

**Tool-Beschreibungen erweitern:**
```python
description = """Löscht eine einzelne Datei permanent.

Wann nutzen:
- Zum Entfernen von temporären oder generierten Dateien
- Beim Aufräumen nach Refactoring

Einschränkungen:
- Kann KEINE Verzeichnisse löschen (nutze dafür delete_directory)
- Gelöschte Dateien können nicht wiederhergestellt werden
"""
```

---

## Implementierungsplan

### Phase 1: Kritische Änderungen (sofort)

1. **Persistence/Planning/Don't-Guess Reminders** zu allen Prompts hinzufügen
2. **Workflow-Sektion** zu Backend/Frontend Dev hinzufügen
3. **Test-Betonung** verstärken

### Phase 2: Wichtige Verbesserungen (nächste Iteration)

4. **Code-Review Prompt** mit Prioritäten und Confidence Score
5. **Prompt-Struktur** vereinheitlichen nach OpenAI-Template
6. **Tool-Beschreibungen** erweitern

### Phase 3: Nice-to-Have (später)

7. **Beispiele** zu jedem Prompt hinzufügen
8. **Chain-of-Thought** explizit anfordern
9. **Structured Output** für Reviews

---

## Konkrete Änderungen für agents.yaml

### Neue gemeinsame Basis-Sektion:

```yaml
# Füge zu JEDEM Agent hinzu:

## Arbeitsweise (WICHTIG)
- Du bist ein autonomer Agent - arbeite bis das Problem VOLLSTÄNDIG gelöst ist
- Beende NIEMALS ohne Lösung, außer du brauchst explizit Input
- Nutze IMMER deine Tools um Informationen zu verifizieren
- Rate oder erfinde NIEMALS Antworten
- Plane JEDEN Schritt bevor du ein Tool aufrufst
- Reflektiere NACH jedem Tool-Aufruf über das Ergebnis
```

### Backend Dev - Neue Test-Sektion:

```yaml
## Testing (KRITISCH)
⚠️ Unzureichendes Testen ist der #1 Grund für Fehler!

1. Führe Tests NACH JEDER Code-Änderung aus
2. Teste alle Edge Cases
3. Schreibe zusätzliche Tests wenn nötig
4. Beende erst wenn ALLE Tests grün sind
```

---

## Zusammenfassung

| Bereich | Aktuell | Empfohlen | Priorität |
|---------|---------|-----------|-----------|
| Persistence Reminders | ❌ | ✅ | 🔴 Kritisch |
| Don't Guess Anweisung | ❌ | ✅ | 🔴 Kritisch |
| Planning Anweisung | ❌ | ✅ | 🔴 Kritisch |
| Strukturierter Workflow | ❌ | ✅ | 🟡 Wichtig |
| Test-Betonung | 🟡 | ✅ | 🟡 Wichtig |
| Code Review Prompt | 🟡 | ✅ | 🟡 Wichtig |
| Prompt-Struktur | 🟡 | ✅ | 🟢 Nice-to-Have |
| Tool-Beschreibungen | 🟡 | ✅ | 🟢 Nice-to-Have |
| Beispiele | ❌ | ✅ | 🟢 Nice-to-Have |

**Geschätzter Impact der Änderungen: +15-25% bessere Task-Completion**  
(basierend auf OpenAIs eigenen SWE-bench Ergebnissen: +20% durch Reminders)
