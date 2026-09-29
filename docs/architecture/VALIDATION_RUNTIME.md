# Agent Execution Runtime Validation Runtime

Validation is a first-class Agent Execution Runtime runtime boundary.

## Pipeline

Agent / WorkUnit -> ValidationRuntime -> test, lint, type-check, build, custom validation -> ValidationReport -> .multiagentos/evidence/validation.json

Validation commands execute through the existing Local Tool Runtime, so process permissions and workspace path boundaries remain enforced.

## Required vs optional checks

Each validation step declares id, command, kind, required, and timeout.

A required failure makes the report fail. An optional failure is recorded as evidence without failing the overall report.

## Evidence

The report records command, return code, stdout, stderr, step kind, and pass/fail state. Evidence is persisted under the project workspace by default.

This is deliberately provider-neutral: no CI vendor, IDE, model provider, or external MCP service is required.

## Cost boundary

Validation runs locally through Agent Execution Runtime. It does not require a paid external MCP service. Mobile validation can later consume a locally executed MCP provider without changing this contract.
