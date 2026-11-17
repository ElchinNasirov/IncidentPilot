import os # Lets Python read files and folder paths on your computer
from langchain_core.documents import Document  # LangChain's standard container for text + metadata
from langchain_huggingface import HuggingFaceEmbeddings  # Free, local embedding model (no API key needed)
from langchain_community.vectorstores import Chroma  # Our persistent Vector Database


def load_and_parse_runbooks(runbooks_dir: str = "data/runbooks") -> list[Document]:
    """Reads all Markdown runbooks and extracts header metadata for filtering later."""

    documents = []

    # Loop through every filename inside the 'data/runbooks' folder
    for filename in os.listdir(runbooks_dir):

        # Skip any hidden files (like .DS_Store) and only process Markdown (.md) files
        if not filename.endswith(".md"):
            continue

        filepath= os.path.join(runbooks_dir, filename)

        # Open and read the full text of the runbook
        with open(filepath, "r", encoding="utf-8") as file:
            content= file.read()

        # --- METADATA EXTRACTION ---
        # Default metadata values in case a header is missing
        target_service = "general"
        severity = "Medium"

        # Read the file line-by-line to pull out our custom bold headers
        for line in content.splitlines():
            if line.startswith("**Target Service:**"):
                # Split at the colon, grab the right side, and strip extra spaces
                target_service = line.split(":**")[1].strip()

            elif line.startswith("**Severity:**"):
                severity= line.split(":**")[1].strip()

        # Wrap the raw text and extracted metadata into a formal LangChain Document object
        doc = Document(
            page_content=content,
            metadata={
                "source": filename,
                "target_service": target_service,
                "severity": severity
            }
        )
        documents.append(doc)
        print(f"[PARSED] {filename} -> Service: '{target_service}' | Severity: '{severity}'")

    return documents # returns a list of Document objects


def build_chroma_index(documents: list[Document], persist_dir: str = "./chroma_db") -> None:
    """Converts Documents into embeddings and saves them permanently to Chroma DB."""

    print("\n[INFO] Loading local HuggingFace embedding model (all-MiniLM-L6-v2)...")
    
    # Initialize a lightweight, fast open-source embedding model that runs locally on your CPU
    embedding_model= HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print(f"[INFO] Creating Chroma DB vector index at '{persist_dir}'...")
    
    # Create the Chroma vector database from our documents and save it to disk
    vector_db = Chroma.from_documents(
        documents=documents,
        embedding=embedding_model,
        collection_name="engineering_runbooks",
        persist_directory=persist_dir
    )

    print(f"[SUCCESS] Indexed {len(documents)} runbooks into Chroma DB!")

    # --- QUICK SANITY TEST ---
    # Run a test query to verify our vector search actually works before moving on
    test_query = "Postgres connection pool exhausted"
    print(f"\n[TEST SEARCH] Querying: '{test_query}'")
    
    results = vector_db.similarity_search(test_query, k=1)
    print(f"[TOP SEARCH MATCH] File: {results[0].metadata['source']} | Severity: {results[0].metadata['severity']}")


if __name__ == "__main__":
    # 1. Load and parse the Markdown files into Document objects
    parsed_docs = load_and_parse_runbooks()
    
    # 2. Embed and store them in Chroma DB
    build_chroma_index(parsed_docs)
