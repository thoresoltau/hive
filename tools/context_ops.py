"""Context operations tools."""

import json
from typing import Optional, Any
from pathlib import Path

from core.context import ContextManager
from tools.base import Tool, ToolParameter, ToolResult, ToolResultStatus


class UpdateContextTool(Tool):
    """
    Tool for updating the project's global context (project.yaml).
    Allows agents to memorize important files, architectural decisions, and the tech stack.
    """
    name = "update_context"
    description = "Update the project's global context (project.yaml). Use this to memorize important files, architecture notes, or the tech stack so that all agents share the same knowledge."

    parameters = [
        ToolParameter(
            name="languages",
            type="array",
            description="List of programming languages used in the project.",
            items_type="string",
            required=False,
        ),
        ToolParameter(
            name="frameworks",
            type="array",
            description="List of frameworks used (e.g., React, Express).",
            items_type="string",
            required=False,
        ),
        ToolParameter(
            name="databases",
            type="array",
            description="List of databases used (e.g., PostgreSQL, Redis).",
            items_type="string",
            required=False,
        ),
        ToolParameter(
            name="tools",
            type="array",
            description="List of tools used (e.g., Docker, Jest).",
            items_type="string",
            required=False,
        ),
        ToolParameter(
            name="important_files",
            type="array",
            description="List of critical files (e.g., docs/architektur.md, src/server.js). Replaces the existing list.",
            items_type="string",
            required=False,
        ),
        ToolParameter(
            name="architecture_notes",
            type="string",
            description="Important architectural decisions, patterns, or notes. Replaces existing notes.",
            required=False,
        ),
        ToolParameter(
            name="test_commands",
            type="object",
            description="A dictionary of commands used to run tests in this project (e.g., {'frontend': 'npm test', 'backend': 'pytest', 'e2e': 'cypress run'}).",
            required=False,
        ),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the context update operation."""
        try:
            if not self.workspace_path:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error="No workspace path provided.",
                )

            ctx = ContextManager(self.workspace_path)

            # Load current configuration
            config = await ctx.load()
            if not config:
                try:
                    name = Path(self.workspace_path).name
                    config = await ctx.initialize(name=name)
                except Exception as e:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        output=None,
                        error=f"Project is not initialized and auto-initialization failed: {e}",
                    )

            updates_made = {}

            # Update Tech Stack if provided
            tech_stack_updates = {}
            if "languages" in kwargs:
                tech_stack_updates["languages"] = kwargs["languages"]
            if "frameworks" in kwargs:
                tech_stack_updates["frameworks"] = kwargs["frameworks"]
            if "databases" in kwargs:
                tech_stack_updates["databases"] = kwargs["databases"]
            if "tools" in kwargs:
                tech_stack_updates["tools"] = kwargs["tools"]

            if tech_stack_updates:
                # Need to update the nested object
                for k, v in tech_stack_updates.items():
                    setattr(config.tech_stack, k, v)
                    updates_made[f"tech_stack.{k}"] = v
                # Calling update to save
                await ctx.update(tech_stack=config.tech_stack)

            # Update other top-level context fields
            if "important_files" in kwargs:
                await ctx.update(important_files=kwargs["important_files"])
                updates_made["important_files"] = kwargs["important_files"]

            if "architecture_notes" in kwargs:
                await ctx.update(architecture_notes=kwargs["architecture_notes"])
                updates_made["architecture_notes"] = kwargs["architecture_notes"]

            if "test_commands" in kwargs:
                if isinstance(kwargs["test_commands"], dict):
                    # Merge or replace existing test commands
                    if not hasattr(config, "test_commands") or not config.test_commands:
                        config.test_commands = {}
                    config.test_commands.update(kwargs["test_commands"])
                    await ctx.update(test_commands=config.test_commands)
                    updates_made["test_commands"] = kwargs["test_commands"]

            if not updates_made:
                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    output="No updates provided. Context remains unchanged.",
                )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"Project context updated successfully.\nChanges made: {json.dumps(updates_made, indent=2)}",
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Failed to update context: {str(e)}",
            )
