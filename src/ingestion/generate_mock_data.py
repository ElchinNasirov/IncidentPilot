# IMPORTS - bringing in the tools we need
import os              # Lets Python create folders and check file paths on your computer
import random          # Lets Python pick random numbers or random items from a list
from datetime import datetime, timedelta  # Helps us create fake timestamps (dates and times)
import pandas as pd    # Industry-standard data library; we use it to save data as a CSV file
import sqlite3  # Built-in Python library for creating and querying SQLite databases

def generate_server_logs(num_rows: int = 500) -> None: 
    # Define a list of fake microservices (the different parts of our imaginary web app)
    services = ["auth-service", "payment-gateway", "inventory-api", "user-profile-db"]
    
    # Create an empty list to hold every row of log data we generate
    records = []
    
    # Set our starting clock to 6 hours before right now
    base_time = datetime.now() - timedelta(hours=6)

    # Loop 500 times (from i = 0 up to 499) to create 500 rows of server logs
    for i in range(num_rows):
        # Add 0.7 minutes to the clock for each new row so time moves forward realistically
        timestamp = base_time + timedelta(minutes=i * 0.7)
        
        # Pick one random service from our list above for this specific log row
        service = random.choice(services)
        
        # SIMULATING A SERVER CRASH: 
        
        # Between row 350 and 420, if the service is 'payment-gateway', force an error!
        if 350 <= i <= 420 and service == "payment-gateway":
            status_code = random.choice([500, 503])  # 500 = Server Crash, 503 = Overloaded
            latency_ms = random.randint(2500, 8000)  # Slow response time (2.5 to 8 seconds)
            error_msg = "ERR_CONNECTION_REFUSED: Upstream Postgres pool exhausted"
        else:
            # For all other rows, simulate normal healthy traffic
            status_code = 200                        # 200 = Everything worked fine
            latency_ms = random.randint(45, 220)     # Fast response time (45 to 220 milliseconds)
            error_msg = "OK"

        # Pack all 5 pieces of data for this single row into a Python dictionary
        row_data = {
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"), # Format time as readable text
            "service_name": service,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "error_message": error_msg
        }
        
        # Adding this finished dictionary row into our master 'records' list
        records.append(row_data)

    # Convert our list of 500 dictionaries into a structured Pandas DataFrame - a table
    df = pd.DataFrame(records)
    
    # Define where to save the file
    csv_path = "data/logs/server_logs.csv"
    
    # Save the table as a CSV file. 'index=False' stops Pandas from adding an extra row-number column
    df.to_csv(csv_path, index=False)
    print(f"Done! Created {num_rows} log rows at {csv_path}")


def generate_incident_database() -> None:
    # Define the file path where our single-file SQLite database will live
    db_path = "data/incident_history.db"
    
    # Open a connection to the database. If 'incident_history.db' doesn't exist yet, SQLite creates it automatically.
    conn = sqlite3.connect(db_path)
    
    # Create a 'cursor' object. Think of the cursor as a pen that lets us write and execute SQL commands.
    cursor = conn.cursor()

    # Delete the table if it already exists. This guarantees that if you run this script twice, 
    # you won't get duplicate rows or "Table already exists" errors.
    cursor.execute("DROP TABLE IF EXISTS past_incidents")

    # Write a standard SQL command to build a structured table with 6 specific columns and data types.
    # PRIMARY KEY ensures every incident_id (like 'INC-101') is strictly unique.
    cursor.execute("""
        CREATE TABLE past_incidents (
            incident_id TEXT PRIMARY KEY,
            date_occurred TEXT,
            affected_service TEXT,
            root_cause TEXT,
            resolution_time_mins INTEGER,
            resolved_by TEXT
        )
    """)

    # Create a Python list of tuples. Each tuple represents one historical server crash record.
    historical_data = [
        ("INC-101", "2026-09-14", "payment-gateway", "Database connection pool exhausted during flash sale", 45, "Sarah Jenkins"),
        ("INC-102", "2026-10-02", "auth-service", "Expired TLS certificate on internal load balancer", 20, "Marcus Vance"),
        ("INC-103", "2026-10-19", "payment-gateway", "Redis cache eviction spike caused cascading timeout", 35, "Sarah Jenkins"),
        ("INC-104", "2026-11-01", "inventory-api", "Unindexed SQL query locked main product table", 60, "David Chen")
    ]

    # 'executemany' inserts all 4 tuples into the table in one fast batch.
    # The six '?' symbols are security placeholders that safely map to the 6 values in each tuple.
    cursor.executemany("INSERT INTO past_incidents VALUES (?, ?, ?, ?, ?, ?)", historical_data)

    # Save (commit) all changes permanently to the hard drive file.
    conn.commit()
    
    # Close the database connection cleanly so the file isn't locked when our AI Agent reads it later.
    conn.close()
    print(f"Done! Created SQLite database at {db_path}")


def generate_engineering_runbooks() -> None:

    # Create the 'data/runbooks' folder automatically if it doesn't exist yet
    os.makedirs("data/runbooks", exist_ok=True)

    # Create a Python dictionary where:
    # - The 'key' is the filename we want to create (e.g., "runbook_db_pool.md")
    # - The 'value' is the multi-line Markdown text content inside that file
    runbooks = {
        "runbook_db_pool.md": """# Runbook: Database Connection Pool Exhaustion
**Target Service:** payment-gateway, user-profile-db
**Error Signature:** `ERR_CONNECTION_REFUSED: Upstream Postgres pool exhausted`
**Severity:** Critical (Tier 1)

## Diagnosis Steps
1. Check active connection counts in the server logs (`status_code == 500` or `503`).
2. Verify if latency spikes exceed 2000ms.

## Recovery Procedure (Requires Human Approval)
1. Execute the `restart_connection_pool` tool targeting the affected service.
2. Monitor latency metrics for 5 minutes to confirm stabilization below 250ms.
""",
        "runbook_redis_eviction.md": """# Runbook: Redis Cache Eviction Spike
**Target Service:** payment-gateway, auth-service
**Error Signature:** `HTTP_503: Service Unavailable - Redis cache eviction threshold exceeded`
**Severity:** High (Tier 2)

## Diagnosis Steps
1. Confirm spike in `HTTP_503` responses alongside high memory eviction warnings.

## Recovery Procedure (Requires Human Approval)
1. Execute the `flush_stale_cache` tool to clear expired session keys.
2. Scale read-replicas if traffic remains elevated.
"""
    }

    # Loop through each filename and its matching text content in our dictionary
    for filename, content in runbooks.items():
        # Safely combine the folder path and filename to create the full file path
        filepath = os.path.join("data/runbooks", filename)
        
        # Open the file in write mode ("w") with UTF-8 encoding so special characters don't break
        # Using 'with' automatically closes the file safely when Python finishes writing
        with open(filepath, "w", encoding="utf-8") as file:
            # .strip() removes any accidental blank spaces at the very top or bottom of the text
            file.write(content.strip())

    print(f"Done! Created {len(runbooks)} engineering runbooks in data/runbooks/")


# This line ensures the code only runs when you execute this specific file directly
if __name__ == "__main__":
    generate_server_logs()
    generate_incident_database()
    generate_engineering_runbooks()