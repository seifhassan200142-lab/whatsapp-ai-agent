# WhatsApp AI Agent
**AI-Powered Customer Support Automation | FastAPI · Groq · WhatsApp Cloud API**

A lightweight, AI-powered WhatsApp customer support system designed to help businesses automate customer conversations, respond to inquiries, and manage human support requests through a centralized dashboard.

The system integrates Meta's WhatsApp Cloud API with Groq-hosted language models to provide context-aware responses based on company-specific information, while maintaining conversation history and supporting seamless human intervention.

## Overview

Businesses often receive repetitive customer inquiries regarding services, operating hours, and general information. Handling these requests manually can increase response times and operational workload.

WhatsApp AI Agent addresses this challenge by combining automated customer communication with human oversight.

The solution is designed for small and medium-sized businesses seeking an adaptable customer support automation system without complex infrastructure.

## Key Features

| Feature | Description |
|---|---|
| AI-Powered Responses | Generates contextual replies using Groq-hosted language models. |
| WhatsApp Integration | Receives and sends messages through the official Meta WhatsApp Cloud API. |
| Voice Message Support | Transcribes customer voice messages using Whisper and responds in text. |
| Company Knowledge Base | Uses business-specific information stored in an editable Markdown file. |
| Conversation Memory | Maintains recent conversation context and stores message history in SQLite. |
| Human Handoff | Escalates customer requests that require human assistance or cannot be answered reliably. |
| Admin Dashboard | Provides conversation monitoring, manual replies, and bot controls. |
| Multilingual Communication | Supports Arabic and English customer interactions. |
| API Security | Implements webhook signature validation and API-key-protected administration. |
| Error Handling | Tracks processing failures and preserves conversations for manual review. |

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12, FastAPI |
| AI Inference | Groq SDK |
| Language Model | GPT-OSS 20B |
| Speech-to-Text | Whisper Large V3 Turbo |
| Messaging Platform | Meta WhatsApp Cloud API |
| Database | SQLite |
| Knowledge Source | Markdown |
| Admin Interface | HTML, CSS, JavaScript |
| API Documentation | Swagger / OpenAPI |
| Development Tunnel | ngrok |
| Testing | Pytest |

The architecture intentionally avoids unnecessary infrastructure dependencies, including Docker, vector databases, and external workflow automation platforms.

## System Architecture

The system follows an event-driven workflow that separates message reception, AI processing, and outbound communication.

```text
          Customer (WhatsApp)
                   |
                   v
          Meta WhatsApp API
                   |
                   v
          FastAPI Webhook
                   |
                   v
       Message Validation & Queue
                   |
                   v
            Message Worker
                   |
          +--------+--------+
          |                 |
          v                 v
     Text Message     Voice Message
          |                 |
          |          Groq Whisper
          |                 |
          +--------+--------+
                   |
                   v
          Conversation Context
                   |
                   v
       Company Knowledge Base
                   |
                   v
            Groq LLM
                   |
          +--------+--------+
          |                 |
          v                 v
      AI Response      Human Handoff
          |                 |
          v                 v
    WhatsApp Reply     Admin Dashboard
                   |
                   v
              SQLite
```

### Message Processing

1. Incoming customer messages are received through Meta's WhatsApp webhook.
2. Webhook authenticity is verified before processing.
3. Messages are stored in SQLite and submitted for sequential processing.
4. Voice messages are transcribed through Groq Whisper.
5. Relevant conversation history and company information are provided to the language model.
6. The system generates a response or escalates the conversation for human review.
7. Outbound messages are sent through the WhatsApp Cloud API, and their delivery status can be tracked.

## Human Handoff & Conversation Management

The system supports controlled transitions between AI automation and human assistance.

Conversations can be managed through three primary states:

- **Active:** The AI agent processes incoming messages automatically.
- **Human Required:** Automated responses are paused, allowing an operator to review the conversation and reply manually.
- **Resolved:** The conversation is closed until an administrator explicitly reactivates the bot.

Human intervention may be triggered by direct customer requests, insufficient knowledge, or processing failures.

The admin dashboard provides access to conversation history, escalation summaries, manual messaging, and conversation status controls.

Human handoff is dashboard-based; external employee notifications are not included.

## Project Structure

```text
whatsapp-ai-agent/
|
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- whatsapp.py
|   |-- llm.py
|   |-- transcription.py
|   |-- database.py
|   |-- models.py
|   |-- handoff.py
|   |-- worker.py
|   |-- static/
|
|-- data/
|   |-- knowledge.md
|
|-- scripts/
|   |-- prepare_env.py
|   |-- check_setup.py
|
|-- tests/
|
|-- .env.example
|-- requirements.txt
|-- README.md
|-- VALIDATION.md
|-- START_HERE.html
```

## Configuration & Deployment

### Requirements

- Python 3.12
- Groq API credentials
- Meta Developer account with WhatsApp Cloud API access
- Public HTTPS webhook endpoint
- ngrok or an equivalent HTTPS endpoint for development

### Local Setup

Clone the repository and install the dependencies:

```bash
git clone https://github.com/seifhassan200142-lab/whatsapp-ai-agent.git
cd whatsapp-ai-agent

python -m venv .venv
python -m pip install -r requirements.txt
```

Activate the virtual environment using the appropriate command for your operating system.

Create a `.env` file from `.env.example` and initialize the local credentials:

```bash
python -m scripts.prepare_env
```

Configure the required integration credentials:

```dotenv
GROQ_API_KEY=
META_ACCESS_TOKEN=
META_PHONE_NUMBER_ID=
META_APP_SECRET=
META_VERIFY_TOKEN=
ADMIN_API_KEY=
```

The verification and administrator tokens can be generated by the setup script. The remaining credentials must be obtained from the corresponding service providers.

Validate the configuration:

```bash
python -m scripts.check_setup --groq --meta
```

Start the application:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

### Application Endpoints

| Endpoint | Purpose |
|---|---|
| `/health` | Application health and database status |
| `/docs` | Interactive API documentation |
| `/admin` | Customer support administration dashboard |
| `/webhook` | Meta WhatsApp webhook endpoint |

For local WhatsApp integration, expose port `8000` through ngrok and configure the HTTPS `/webhook` URL in the Meta Developer Dashboard. Subscribe to the `messages` webhook field.

## Company Knowledge Customization

The agent's business-specific information is maintained in:

`data/knowledge.md`

This file can be customized with company information, services, working hours, policies, and other approved customer-facing details.

Knowledge updates are loaded for new messages without requiring an application restart.

The current implementation uses a file-based knowledge source rather than a retrieval-augmented generation pipeline or vector database.

## Security & Reliability

The implementation includes several safeguards for development and controlled testing:

- Meta webhook signature verification.
- Administrative API-key authentication.
- Duplicate incoming message detection.
- Persistent SQLite conversation storage.
- Local AI request limits and request pacing.
- Restricted media download handling.
- Controlled human escalation and error tracking.
- Environment-based credential configuration.

API keys, access tokens, and local conversation databases must remain outside version control.

## Testing & Validation

The project includes automated tests covering application logic, message processing, and mocked external API interactions.

Run the test suite using:

```bash
python -m pytest -q
```

**Current validation scope:**

- Locally tested using Python 3.12.14 on Linux.
- Automated tests use the Groq SDK and simulated Meta network interactions.
- Windows setup targets Python 3.12.
- Live WhatsApp messaging, real Meta account integration, and real Groq account integration have not yet been validated end-to-end.

The application is currently a **development prototype intended for integration testing and business-specific customization**, rather than a production-certified customer support platform.

## Current Limitations

The current implementation uses a single application worker and a local SQLite database. It does not include distributed processing, automated data retention policies, multi-user administrative access, or production hosting infrastructure.

Free-form WhatsApp replies are restricted by Meta's customer service messaging window and applicable account permissions.

Additional deployment, security, privacy, and operational validation would be required before handling production customer traffic.

## Potential Business Applications

The architecture can be adapted for customer-facing workflows such as:

- Customer service and general inquiries.
- Company service and product information.
- Initial lead qualification.
- Business hours and availability inquiries.
- Customer request collection.
- Human support escalation.

Business-specific integrations and workflows can be introduced based on operational requirements.

---

**Project:** WhatsApp AI Agent  
**Category:** AI Automation / Customer Support  
**Developer:** Seif Eldeen Hassan  
**Repository:** https://github.com/seifhassan200142-lab/whatsapp-ai-agent
