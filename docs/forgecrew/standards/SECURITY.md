# Security Standards

<!-- This file is tracked and should be customized for your project -->

## Overview

This document defines security requirements, authentication patterns, and
sensitive data handling for the project.

## Quick Start

These are universal best practices that apply to most applications:

- **Never log secrets** - Tokens, passwords, API keys must never appear in logs
- **Validate all inputs** - Check inputs at system boundaries before processing
- **Use established auth patterns** - Don't roll your own authentication or crypto
- **Principle of least privilege** - Grant minimum permissions required for each operation
- **Defense in depth** - Don't rely on a single security control

---

## Customization Guide

This section helps you build out project-specific security standards.

### What to Document

- Authentication method and session handling
- Authorization model (RBAC, ABAC, permissions)
- Secrets management (environment variables, vault)
- PII handling and data classification
- Input validation requirements
- CORS and CSP policies
- Security headers
- Audit logging requirements

### Interview Questions

An agent can use these questions to help you define standards:

1. How are users authenticated? (JWT, sessions, OAuth)
2. What authorization model is used? (role-based, permission-based)
3. How are secrets stored and accessed? (env vars, secrets manager)
4. What data is considered PII and how should it be handled?
5. Are there specific compliance requirements? (GDPR, HIPAA, SOC2)
6. What security headers should be enforced?

---

## Project-Specific Standards

<!-- TODO: Add your project-specific security standards here -->

### Authentication

_Define your authentication approach here._

### Authorization

_Define your authorization model here._

### Secrets Management

_Define how secrets are stored and accessed here._

### Sensitive Data

_Define PII handling and data classification here._

<!-- ForgeCrew v0.3.12 -->
