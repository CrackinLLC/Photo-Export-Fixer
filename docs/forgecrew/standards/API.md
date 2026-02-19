# API Standards

<!-- This file is tracked and should be customized for your project -->

## Overview

This document defines API design patterns, endpoint conventions, and error
handling standards for the project.

## Quick Start

These are universal best practices that apply to most API designs:

- **Use consistent naming** - Prefer plural nouns for resources (`/users`, `/orders`)
- **Return appropriate status codes** - 200 for success, 4xx for client errors, 5xx for server errors
- **Validate inputs** - Check all inputs at API boundaries before processing
- **Don't leak internals** - Error responses should be helpful but not expose stack traces or system details
- **Include request IDs** - Return a unique identifier in error responses for debugging

---

## Customization Guide

This section helps you build out project-specific API standards.

### What to Document

- API versioning strategy (URL path, headers, query params)
- Authentication method (JWT, API keys, OAuth)
- Rate limiting policies
- Pagination conventions (cursor vs offset)
- Response envelope structure
- Error response format
- Deprecation policy

### Interview Questions

An agent can use these questions to help you define standards:

1. What authentication method does this project use? (JWT, API keys, session cookies, OAuth)
2. Do you need API versioning? If so, how should it be handled?
3. What should the standard error response format look like?
4. Are there rate limiting requirements for endpoints?
5. What pagination style do you prefer for list endpoints?

---

## Project-Specific Standards

<!-- TODO: Add your project-specific API standards here -->

### Authentication

_Define your authentication approach here._

### Response Format

_Define your standard response envelope here._

### Error Handling

_Define your error response format and codes here._

### Versioning

_Define your API versioning strategy here._

<!-- ForgeCrew v0.3.12 -->
