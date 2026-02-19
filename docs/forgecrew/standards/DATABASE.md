# Database Standards

<!-- This file is tracked and should be customized for your project -->

## Overview

This document defines database conventions, query patterns, and migration
standards for the project.

## Quick Start

These are universal best practices that apply to most database work:

- **Use parameterized queries** - Never interpolate user input into SQL strings
- **Wrap multi-step writes in transactions** - Ensure data consistency
- **Create migrations for schema changes** - Track all schema modifications in version control
- **Index foreign keys** - Foreign key columns should be indexed for join performance
- **Use explicit column lists** - Avoid `SELECT *` in production code

---

## Customization Guide

This section helps you build out project-specific database standards.

### What to Document

- Database engine (PostgreSQL, MySQL, SQLite, MongoDB)
- ORM or query builder in use
- Migration tool and workflow
- Naming conventions (tables, columns, constraints)
- Soft delete vs hard delete policy
- Audit/timestamp columns (created_at, updated_at)
- Connection pooling configuration

### Interview Questions

An agent can use these questions to help you define standards:

1. What database engine does this project use?
2. What ORM or query builder is used? (Prisma, Drizzle, Knex, raw SQL)
3. How should migrations be organized and named?
4. Do tables need audit columns (created_at, updated_at, deleted_at)?
5. What naming convention do you use? (snake_case, camelCase)
6. Is there a soft-delete policy or should records be hard deleted?

---

## Project-Specific Standards

<!-- TODO: Add your project-specific database standards here -->

### Database Engine

_Specify your database and version here._

### Naming Conventions

_Define table, column, and constraint naming patterns here._

### Migrations

_Define your migration workflow and naming convention here._

### Audit Columns

_Define which tables need audit columns and their format here._

<!-- ForgeCrew v0.3.12 -->
