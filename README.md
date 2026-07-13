# 🩺 AI Medical Assistant (RAG Architecture)

An enterprise-grade, secure, and real-time AI Medical Assistant built using a **Retrieval-Augmented Generation (RAG)** pipeline. This backend architecture allows authenticated users to securely upload medical documents (PDFs), ask complex clinical questions, and receive context-aware answers streamed in real time.

---

# 🚀 Key Features

- 🔒 **Strict Data Isolation & Security**
  - JWT-based authentication ensures that users can only query and retrieve context from their own uploaded medical documents.

- 📄 **Advanced Document Processing**
  - Extracts text from complex medical PDFs using **PyMuPDF** and utilizes **LangChain** for semantic chunking.

- ⚡ **High-Performance Vector Retrieval**
  - Leverages **Redis Stack** as a vector database for lightning-fast similarity search.

- 🤖 **State-of-the-Art Generative AI**
  - Powered by **Google Gemini 3.5 Flash** for reasoning and **gemini-embedding-2** for high-dimensional text vectorization.

- 🌐 **Real-Time Streaming (SSE)**
  - Delivers AI responses dynamically using **Server-Sent Events (SSE)**, providing a ChatGPT-like responsive UI experience.

---

# 🏗️ Architecture & Workflow Pipeline

The application follows a linear **4-step RAG lifecycle**.

## 1. Authentication & State Phase

- Users get registered via:

```http
POST /api/auth/register
```

- Users authenticate via:

```http
POST /api/auth/token
```

The backend:

- Validates credentials against a local SQLite database.
- Issues a secure JSON Web Token (JWT).

---

## 2. Ingestion & Embedding Phase

- Authenticated users upload medical PDFs via:

```http
POST /api/documents/upload
```

### Workflow

1. **PyMuPDFLoader** extracts raw text.
2. **RecursiveCharacterTextSplitter** chunks the document into overlapping segments while preserving medical context.
3. Chunks are vectorized using **Google's `gemini-embedding-2`** model.
4. The vectors are indexed in **Redis Stack** and tagged with the authenticated user's `user_id` metadata to prevent cross-account data leakage.

---

## 3. Retrieval Phase

- The user submits a question via:

```http
POST /api/chat/stream
```

### Workflow

1. The user's query is embedded.
2. A **k-NN (k-Nearest Neighbors)** similarity search is performed in Redis.
3. A strict runtime filter retrieves only vectors matching the authenticated `user_id`.

---

## 4. Generation & Streaming Phase

1. Retrieved document context and the user's query are passed to **Gemini 3.5 Flash**.
2. A strict system prompt minimizes hallucinations.
3. The generated response is streamed back chunk-by-chunk using **Server-Sent Events (SSE)**.

---

# 🛠️ Tech Stack

| Category | Technologies |
|----------|--------------|
| **Backend Framework** | FastAPI, Python, Uvicorn |
| **AI & Machine Learning** | Google Generative AI, LangChain |
| **Vector Database** | Redis Stack |
| **Relational Database** | SQLite, SQLAlchemy ORM |
| **Authentication & Security** | JWT (`python-jose`), Passlib (Bcrypt), OAuth2 |
| **Document Processing** | PyMuPDF (`fitz`) |

---

# 📂 Project Structure

```text
ai-medical-assistant/
├── app/
│   ├── api/                       # FastAPI Routers
│   │   ├── auth.py                # Login and JWT generation
│   │   ├── documents.py           # Secure PDF upload endpoints
│   │   └── chat.py                # SSE streaming chat endpoints
│   │
│   ├── core/                      # Global configs, logging, and security
│   │   ├── config.py              # Environment variables and application settings
│   │   ├── logging.py             # Loguru configuration and request tracking middleware
│   │   └── security.py            # Password hashing, JWT validation, auth dependencies
│   │
│   ├── db/                        # Database connection and schemas
│   │   ├── database.py            # SQLAlchemy engine and session management
│   │   └── models.py              # Database table definitions
│   │
│   ├── services/                  # Core business logic
│   │   ├── vector_store.py        # PDF parsing, chunking, Redis ingestion
│   │   └── rag_service.py         # Retrieval, prompting, Gemini streaming
│   │
│   └── main.py                    # FastAPI application entry point
│
├── redis_schema.yaml              # LangChain Redis vector search schema
├── requirements.txt               # Python dependencies
└── .gitignore                     # Files ignored by Git
```

---

# 💻 Local Setup & Installation

## 1. Prerequisites

- Python **3.10+**
- Redis Stack
- Docker
- Postman
- Google Gemini API Key

---

## 2. Clone the Repository

```bash
git clone https://github.com/MSaad-10/ai-medical-assistant.git

cd ai-medical-assistant
```

---

## 3. Start Redis Stack

- Run Redis Stack locally using Docker:

```bash
docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
```

---

## 4. Create a Virtual Environment & Install Dependencies

### Windows (Command Prompt / PowerShell)

```bash
python -m venv .venv

source .venv\Scripts\activate

pip install -r requirements.txt
```

### Linux / macOS

```bash
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

---

## 5. Configure Environment Variables

- Create a `.env` file in the project root.

```env
GOOGLE_API_KEY=your_google_api_key_here

PROJECT_NAME="AI Medical Assistant"

REDIS_URL="redis://localhost:6379"

DATABASE_URL="sqlite:///./medical_assistant.db"
```

---

## 6. Run the Server

```bash
python -m uvicorn app.main:app --reload
```

### Base API

```text
http://127.0.0.1:8000
```

### Swagger UI

```text
http://127.0.0.1:8000/docs
```

### ReDoc

```text
http://127.0.0.1:8000/redoc
```

---

# 🧪 Usage Instructions

## 1. Explore the API

Open the interactive Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

## 2. Create a User / Login

Use the **Authentication** endpoints to register (if applicable) and obtain a JWT access token.

---

## 3. Upload a Medical Document

Use the **Documents** endpoint to upload a medical PDF.

---

## 4. Chat with the AI (Using Postman)

1. Open **Postman** and create a new `POST` request to

```http
POST http://127.0.0.1:8000/api/chat/stream
```

2. Go to the **Authorization** tab, select **Bearer Token**, and paste your JWT token.
3. Go to the **Body** tab, select raw and **JSON**, and paste your query payload:

```http
{
  "query": "What does the clinical lab test report say about the health status of the patient?",
  "session_id": "test_session_001"
}
```

4. Click **Send**.
5. In the Postman response pane at the bottom, click the **down arrow (`↓`)** to expand the line containing the response. You will see the AI stream its medical analysis **chunk-by-chunk** in real-time using **Server-Sent Events (SSE)**.

# 🔄 End-to-End RAG Workflow

```text
                     User
                       │
                       ▼
                Authenticate (JWT)
                       │
                       ▼
                Upload Medical PDF
                       │
                       ▼
             PyMuPDF Text Extraction
                       │
                       ▼
          RecursiveCharacterTextSplitter
                       │
                       ▼
            gemini-embedding-2 Embeddings
                       │
                       ▼
             Redis Stack Vector Store
                       │
                       ▼
                  User Question
                       │
                       ▼
                 Query Embedding
                       │
                       ▼
          k-NN Similarity Search (Redis)
                       │
                       ▼
            Retrieve Relevant Chunks
                       │
                       ▼
             Gemini 3.5 Flash LLM
                       │
                       ▼
              Stream Response via SSE
                       │
                       ▼
                     Client
```

---
