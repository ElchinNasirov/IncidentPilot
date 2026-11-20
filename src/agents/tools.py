import sqlite3  # Built-in Python library to query our SQLite incident database
import pandas as pd  # Data analysis library to inspect our CSV server logs
from langchain_core.tools import tool  # Decorator that turns a normal Python function into an AI tool
from langchain_huggingface import HuggingFaceEmbeddings  # Local embedding model (must match Day 2!)
from langchain_chroma import Chroma  # Modern standalone Chroma vector database connector


# Load the exact same local embedding model we used in build_vector_store.py
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Connect to our existing persistent Chroma DB folder on disk
vector_db = Chroma(
    collection_name="engineering_runbooks",
    embedding_function=embedding_model,
    persist_directory="./chroma_db"
)


@tool
def search_engineering_runbooks(error_query: str, service_name: str = "") -> str:
    """
    Searches internal engineering runbooks for troubleshooting and recovery steps.
    Use this tool whenever you find an error message or outage and need instructions on how to fix it.
    Args:
        error_query: The error message or symptom (e.g., 'Postgres pool exhausted' or 'HTTP 503').
        service_name: Optional microservice name (e.g., 'payment-gateway') to narrow down results.
    """
    print(f"\n[TOOL CALLED: search_engineering_runbooks] Query='{error_query}' | Service='{service_name}'")

    # Perform a semantic similarity search (returns a LIST of Document objects)
    results = vector_db.similarity_search(error_query, k=1)

    # if the database returned nothing, inform the agent clearly
    if not results:
        return "No matching runbook found in the knowledge base."

    # Grab the first Document object out of the list using [0]
    top_doc = results[0]
    source_file = top_doc.metadata.get("source", "Unknown")
    severity = top_doc.metadata.get("severity", "Unknown")

    return f"Found Runbook: {source_file} (Severity: {severity})\n\n{top_doc.page_content}"


@tool
def query_past_incidents(service_name: str) -> str:
    """
    Queries the historical SQLite incident database to see if a specific microservice has crashed before.
    Use this tool to check past root causes and how long previous outages took to resolve.
    Args:
        service_name: The exact name of the microservice (e.g., 'payment-gateway', 'auth-service').
    """
    print(f"\n[TOOL CALLED: query_past_incidents] Checking history for service='{service_name}'")

    conn = sqlite3.connect("data/incident_history.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT incident_id, date_occurred, root_cause, resolution_time_mins FROM past_incidents WHERE affected_service = ?",
        (service_name,)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return f"No past incidents found in the database for service '{service_name}'."

    # Unpack each tuple index cleanly: row[0]=ID, row[1]=Date, row[2]=Cause, row[3]=Minutes
    formatted_history = [
        f"- [{row[0]}] Date: {row[1]} | Root Cause: {row[2]} | Resolved in {row[3]} mins"
        for row in rows
    ]
    return f"Historical Outages for {service_name}:\n" + "\n".join(formatted_history)


@tool
def analyze_server_logs(service_name: str = "") -> str:
    """
    Analyzes recent server traffic logs (CSV) to detect HTTP error spikes (status >= 400) and high latency.
    Use this tool first when investigating a reported outage or slowdown.
    Args:
        service_name: Optional microservice name to filter logs (leave empty to scan all services).
    """
    print(f"\n[TOOL CALLED: analyze_server_logs] Scanning logs for service='{service_name or 'ALL'}'")

    df = pd.read_csv("data/logs/server_logs.csv")

    if service_name:
        df = df[df["service_name"] == service_name]

    if df.empty:
        return f"No log records found for service '{service_name}'."

    errors_df = df[df["status_code"] >= 400]
    avg_latency = round(df["latency_ms"].mean(), 2)
    max_latency = df["latency_ms"].max()
    top_errors = errors_df["error_message"].value_counts().to_dict()

    return (
        f"Log Summary ({service_name or 'All Services'}):\n"
        f"- Total Requests Analyzed: {len(df)}\n"
        f"- Total Error Requests (HTTP >= 400): {len(errors_df)}\n"
        f"- Average Latency: {avg_latency} ms | Peak Latency: {max_latency} ms\n"
        f"- Breakdown of Error Messages: {top_errors}"
    )


# --- STANDALONE SANITY TEST ---
if __name__ == "__main__":
    print("=== TESTING INCIDENTPILOT TOOLS ===")
    print(analyze_server_logs.invoke({"service_name": "payment-gateway"}))
    print(query_past_incidents.invoke({"service_name": "payment-gateway"}))
    print(search_engineering_runbooks.invoke({"error_query": "Upstream Postgres pool exhausted"}))
