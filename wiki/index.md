# Matsu Shi Wiki

Welcome to the internal documentation for **Matsu Shi** — an AI-powered diagnostic assistant for Komatsu heavy machinery. 

This wiki serves as the single source of truth for the project's architecture, data flows, and operational procedures.

## 🏗️ System Architecture

Matsu Shi is built on a high-performance RAG (Retrieval-Augmented Generation) pipeline, integrating Telegram's Mini App ecosystem with advanced LLM agents.

### Core Documentation
- **[[overview]]**: Executive summary, mission, and high-level architecture.
- **[[rag-pipeline]]**: Detailed technical breakdown of the 7-stage diagnostic pipeline.
- **[[backend/agents]]**: Documentation for the Pydantic AI agent cluster (Classifier, Reformulator, Responder).

---

## 📂 Technical Zones

The project is organized into 13 documentation zones, covering every layer of the stack:

### Backend & Core
- **[[backend/api]]**: FastAPI endpoints, SSE streaming, and auth contracts.
- **[[backend/bot]]**: aiogram-based Telegram bot for mechanic registration and admin alerts.
- **[[backend/database]]**: PostgreSQL schema, pgvector integration, and migrations.

### Frontend & Dashboards
- **[[frontend/mini-app]]**: The primary mechanic interface (React + Zustand + Telegram SDK).
- **[[frontend/admin-dashboard]]**: Management portal for operators (User approval, Query monitoring).

### Infrastructure & Operations
- **[[infrastructure/docker]]**: Containerization strategy and Nginx gateway configuration.
- **[[infrastructure/integrations]]**: External dependencies (OpenRouter, Langfuse, R2, Jina).
- **[[procedures/ingestion]]**: Guide to the 6-step PDF processing pipeline.
- **[[procedures/deployment]]**: Production setup and maintenance workflows.

### Quality & Governance
- **[[evaluation/rag-metrics]]**: Retrieval thresholds, model routing logic, and observability.
- **[[security/overview]]**: Authentication (HMAC/JWT), rate limiting, and data isolation.

---

## 🛠️ Developer Resources
- **[[BOOTSTRAP]]**: Initial project setup and roadmap.
- **[[SCHEMA]]**: Documentation standards and wiki structure rules.
- **[[log]]**: History of project updates and bootstrap milestones.

> "To repair a machine, one must first understand its spirit as documented in the manual."
