# RAG_JET_Lab

## Run the app

The API reads the existing Chroma index at `chroma_db/` (collection `jet_lab`, embedded with `all-MiniLM-L6-v2`). Answers are streamed from OpenAI.

1. Put your key in `.env` (`OPENAI_API_KEY`). A template is in `.env.example`.
2. From the project root, install dependencies and start the API:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.api.main:app --reload --port 8000
```

3. In another terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000.

## setup (Windows/Linux):

* Download + install Ollama from the webste
* set up a virtual environment: `python -m venv venv`
* activate it: `venv\Scripts\activate`
* install the requirements: `pip install -r requirements.txt`
* install jupyter notebook: `pip install notebook`
* Select the current venv environment on the advanced_rag.ipynb

## setup (macOS):

* Download + install Ollama from the webste
* set up a virtual environment: `python -m venv venv`
* activate it: `source venv/bin/activate`
* install the requirements: `python -m pip install -r requirements.txt`
* install jupyter notebook: `python -m pip install notebook ipykernel`
* Select the current venv environment on the advanced_rag.ipynb