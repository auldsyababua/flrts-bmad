# Architecture Overview

## Executive Summary

This document outlines the comprehensive system architecture for the BrainBot FLRTS project. The architecture is designed to be modular, scalable, and performant, leveraging a webhook-based model for real-time message processing and the "Smart Rails" system for efficient, cost-effective LLM interactions.

The system is composed of five primary layers:
1.  **Bot Layer**: Handles communication with the Telegram API.
2.  **Processing Layer**: Implements the core "Smart Rails" logic for message routing and entity extraction.
3.  **Storage Layer**: Manages data persistence across various storage backends.
4.  **Intelligence Layer**: Interfaces with external AI services like OpenAI and provides memory capabilities.
5.  **Frontend Layer**: Provides a rich user interface through a Telegram Mini App.

## High-Level Architecture

```mermaid
graph TB
    subgraph "External Services"
        TG[Telegram API]
        OAI[OpenAI GPT-4o]
        SUPA[Supabase PostgreSQL]
        REDIS[Upstash Redis]
        VECTOR[Upstash Vector]
        NEO[Neo4j Graph DB]
    end

    subgraph "Bot Layer"
        WH[Webhook Server<br/>FastAPI]
        POLL[Polling Bot<br/>Development]
        HANDLER[Message Handlers]
    end

    subgraph "Processing Layer"
        ROUTER[Smart Rails Router]
        PREPROC[Deterministic Preprocessor]
        PROC[Entity Processors]
        LLM[LLM Service]
        MEM[mem0 Memory Service]
    end

    subgraph "Storage Layer"
        DOC[Document Storage Service]
        VSTORE[Vector Store Service]
        RSTORE[Redis Store Service]
        MEDIA[Media Storage Service]
    end

    subgraph "Frontend Layer"
        MINIAPP[Telegram Mini App<br/>React/TypeScript]
        CHAT[Chat Interface]
        DASHBOARD[Operations Dashboard]
    end

    TG -->|Webhook/Polling| WH
    TG -->|Webhook/Polling| POLL
    WH --> HANDLER
    POLL --> HANDLER
    
    HANDLER --> ROUTER
    ROUTER --> PREPROC
    PREPROC --> PROC
    PROC --> LLM
    LLM --> OAI
    
    PROC --> DOC
    PROC --> VSTORE
    PROC --> RSTORE
    PROC --> MEDIA
    
    DOC --> SUPA
    VSTORE --> VECTOR
    RSTORE --> REDIS
    MEM --> NEO
    
    MINIAPP --> TG
    MINIAPP --> SUPA
    CHAT --> MINIAPP
    DASHBOARD --> MINIAPP
```

## System Principles

1. **Modular Design**: Each component has a single responsibility
2. **Loose Coupling**: Components communicate via well-defined interfaces
3. **High Cohesion**: Related functionality is grouped together
4. **Fail-Safe**: Graceful degradation when services are unavailable
5. **Performance First**: Smart Rails preprocessing for efficiency
6. **Audit Everything**: Complete source tracking and version control
