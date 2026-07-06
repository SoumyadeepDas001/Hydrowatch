import os
import sys
import uuid
import logging
from datetime import datetime, timedelta
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("hydrowatch.storage")

# BigQuery client libraries
try:
    from google.cloud import bigquery
    from google.api_core.exceptions import GoogleAPIError
    from google.auth.errors import DefaultCredentialsError
    BQ_AVAILABLE = True
except ImportError:
    BQ_AVAILABLE = False

DB_NAME = "hydrowatch_local.db"
BQ_DATASET = os.environ.get("HYDROWATCH_BQ_DATASET", "hydrowatch_dataset")

class StorageManager:
    """Manages database storage, supporting Google BigQuery with a graceful local SQLite fallback."""
    
    def __init__(self):
        self.bq_client = None
        self.use_sqlite = True
        self.project_id = None

        if BQ_AVAILABLE:
            try:
                # Try to initialize BigQuery client
                self.bq_client = bigquery.Client()
                self.project_id = self.bq_client.project
                self.use_sqlite = False
                logger.info(f"BigQuery storage initialized successfully. Project: {self.project_id}, Dataset: {BQ_DATASET}")
            except (DefaultCredentialsError, Exception) as e:
                logger.warning(
                    f"Could not initialize BigQuery (credentials missing or project not configured): {e}. "
                    f"Falling back to local SQLite storage ({DB_NAME})."
                )
                self.use_sqlite = True
        else:
            logger.info(f"BigQuery Python libraries not installed or supported. Using local SQLite storage ({DB_NAME}).")
            self.use_sqlite = True

        self.init_db()

    def init_db(self):
        """Ensures that the required tables (readings, alerts) exist in SQLite or BigQuery."""
        if self.use_sqlite:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            # Create readings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS readings (
                    source_id TEXT,
                    village_id TEXT,
                    parameter TEXT,
                    value REAL,
                    unit TEXT,
                    date TEXT,
                    reported_by_id TEXT
                )
            """)
            # Create alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    source_id TEXT,
                    village_id TEXT,
                    severity TEXT,
                    message TEXT,
                    recipient TEXT,
                    timestamp TEXT,
                    status TEXT
                )
            """)
            # Migrate SQLite database if alerts table already exists without status column
            cursor.execute("PRAGMA table_info(alerts)")
            columns = [col[1] for col in cursor.fetchall()]
            if columns and "status" not in columns:
                cursor.execute("ALTER TABLE alerts ADD COLUMN status TEXT")
            conn.commit()
            conn.close()
            logger.info("Local SQLite tables initialized/verified.")
        else:
            # Initialize BigQuery dataset and tables
            try:
                dataset_ref = bigquery.DatasetReference(self.project_id, BQ_DATASET)
                try:
                    self.bq_client.get_dataset(dataset_ref)
                    logger.info(f"Dataset {BQ_DATASET} exists.")
                except Exception:
                    dataset = bigquery.Dataset(dataset_ref)
                    dataset.location = "US"
                    self.bq_client.create_dataset(dataset, timeout=30)
                    logger.info(f"Created BigQuery dataset {BQ_DATASET}.")

                # Create readings table schema
                readings_table_id = f"{self.project_id}.{BQ_DATASET}.readings"
                readings_schema = [
                    bigquery.SchemaField("source_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("village_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("parameter", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("value", "FLOAT", mode="REQUIRED"),
                    bigquery.SchemaField("unit", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("date", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("reported_by_id", "STRING", mode="REQUIRED"),
                ]
                self._ensure_bq_table(readings_table_id, readings_schema)

                # Create alerts table schema
                alerts_table_id = f"{self.project_id}.{BQ_DATASET}.alerts"
                alerts_schema = [
                    bigquery.SchemaField("alert_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("source_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("village_id", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("severity", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("message", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("recipient", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                    bigquery.SchemaField("status", "STRING", mode="NULLABLE"),
                ]
                self._ensure_bq_table(alerts_table_id, alerts_schema)
                
            except Exception as e:
                logger.error(f"Error initializing BigQuery dataset/tables: {e}. Switching to SQLite fallback.")
                self.use_sqlite = True
                self.init_db()

    def _ensure_bq_table(self, table_id, schema):
        """Helper to verify or create a BigQuery table."""
        try:
            self.bq_client.get_table(table_id)
            logger.info(f"BigQuery table {table_id} exists.")
        except Exception:
            table = bigquery.Table(table_id, schema=schema)
            self.bq_client.create_table(table)
            logger.info(f"Created BigQuery table {table_id}.")

    def log_reading(self, source_id: str, village_id: str, parameter: str, value: float, unit: str, date_str: str, reported_by_id: str):
        """Logs a clean, normalized water quality reading."""
        # Convert date to standard string format or validate ISO format
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            iso_date = dt.isoformat()
        except Exception:
            # Fallback to current time if parsing fails
            iso_date = datetime.utcnow().isoformat()

        if self.use_sqlite:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO readings VALUES (?, ?, ?, ?, ?, ?, ?)",
                (source_id, village_id, parameter, value, unit, iso_date, reported_by_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"[SQLite] Logged reading: {source_id} - {parameter}={value} {unit} on {iso_date}")
        else:
            table_id = f"{self.project_id}.{BQ_DATASET}.readings"
            rows_to_insert = [{
                "source_id": source_id,
                "village_id": village_id,
                "parameter": parameter,
                "value": float(value),
                "unit": unit,
                "date": iso_date,
                "reported_by_id": reported_by_id
            }]
            errors = self.bq_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                raise Exception(f"Failed to insert row into BigQuery: {errors}")
            logger.info(f"[BigQuery] Logged reading: {source_id} - {parameter}={value} {unit} on {iso_date}")

    def get_source_history(self, source_id: str) -> list:
        """Retrieves history for a given source ordered chronologically."""
        if self.use_sqlite:
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT source_id, village_id, parameter, value, unit, date, reported_by_id FROM readings WHERE source_id = ? ORDER BY date ASC",
                (source_id,)
            )
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        else:
            table_id = f"{self.project_id}.{BQ_DATASET}.readings"
            query = f"""
                SELECT source_id, village_id, parameter, value, unit, CAST(date AS STRING) as date, reported_by_id
                FROM `{table_id}`
                WHERE source_id = @source_id
                ORDER BY date ASC
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("source_id", "STRING", source_id)
                ]
            )
            query_job = self.bq_client.query(query, job_config=job_config)
            results = query_job.result()
            return [dict(row) for row in results]

    def save_alert(self, alert_id: str, source_id: str, village_id: str, severity: str, message: str, recipient: str, timestamp_str: str, status: str = "drafted") -> bool:
        """Saves a drafted alert to the alerts table."""
        if self.use_sqlite:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO alerts (alert_id, source_id, village_id, severity, message, recipient, timestamp, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (alert_id, source_id, village_id, severity, message, recipient, timestamp_str, status)
            )
            conn.commit()
            conn.close()
            logger.info(f"[SQLite] Saved alert: {alert_id} ({severity}) for {source_id} (status: {status})")
            return True
        else:
            table_id = f"{self.project_id}.{BQ_DATASET}.alerts"
            rows_to_insert = [{
                "alert_id": alert_id,
                "source_id": source_id,
                "village_id": village_id,
                "severity": severity,
                "message": message,
                "recipient": recipient,
                "timestamp": timestamp_str,
                "status": status
            }]
            errors = self.bq_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                raise Exception(f"Failed to save alert to BigQuery: {errors}")
            logger.info(f"[BigQuery] Saved alert: {alert_id} ({severity}) for {source_id} (status: {status})")
            return True

    def get_recent_alerts(self, source_id: str, limit_hours: int = 48) -> list:
        """Retrieves recent alerts for a source within the specified hours (used for rate-limiting)."""
        cutoff_time = (datetime.utcnow() - timedelta(hours=limit_hours)).isoformat()
        
        if self.use_sqlite:
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT alert_id, source_id, village_id, severity, message, recipient, timestamp FROM alerts WHERE source_id = ? AND timestamp >= ? AND severity = 'IMMEDIATE_HAZARD'",
                (source_id, cutoff_time)
            )
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        else:
            table_id = f"{self.project_id}.{BQ_DATASET}.alerts"
            query = f"""
                SELECT alert_id, source_id, village_id, severity, message, recipient, CAST(timestamp AS STRING) as timestamp
                FROM `{table_id}`
                WHERE source_id = @source_id AND timestamp >= @cutoff_time AND severity = 'IMMEDIATE_HAZARD'
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("source_id", "STRING", source_id),
                    bigquery.ScalarQueryParameter("cutoff_time", "TIMESTAMP", cutoff_time)
                ]
            )
            query_job = self.bq_client.query(query, job_config=job_config)
            results = query_job.result()
            return [dict(row) for row in results]

    def get_all_sources_summary(self) -> list:
        """Retrieves a list of all monitored sources with their village and latest readings."""
        if self.use_sqlite:
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT source_id, village_id FROM readings")
            sources = [dict(row) for row in cursor.fetchall()]
            
            result = []
            for src in sources:
                cursor.execute(
                    "SELECT parameter, value, unit, date FROM readings WHERE source_id = ? ORDER BY date DESC",
                    (src["source_id"],)
                )
                rows = cursor.fetchall()
                if rows:
                    latest_readings = []
                    seen_params = set()
                    for row in rows:
                        p = row["parameter"]
                        if p not in seen_params:
                            seen_params.add(p)
                            latest_readings.append({
                                "parameter": p,
                                "value": row["value"],
                                "unit": row["unit"],
                                "date": row["date"]
                            })
                    result.append({
                        "source_id": src["source_id"],
                        "village_id": src["village_id"],
                        "latest_readings": latest_readings
                    })
            conn.close()
            return result
        else:
            table_id = f"{self.project_id}.{BQ_DATASET}.readings"
            query = f"SELECT DISTINCT source_id, village_id FROM `{table_id}`"
            query_job = self.bq_client.query(query)
            sources = [dict(row) for row in query_job.result()]
            
            result = []
            for src in sources:
                query_detail = f"""
                    SELECT parameter, value, unit, CAST(date AS STRING) as date 
                    FROM `{table_id}` 
                    WHERE source_id = @source_id 
                    ORDER BY date DESC
                """
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("source_id", "STRING", src["source_id"])]
                )
                query_job = self.bq_client.query(query_detail, job_config=job_config)
                rows = [dict(row) for row in query_job.result()]
                
                latest_readings = []
                seen_params = set()
                for row in rows:
                    p = row["parameter"]
                    if p not in seen_params:
                        seen_params.add(p)
                        latest_readings.append(row)
                result.append({
                    "source_id": src["source_id"],
                    "village_id": src["village_id"],
                    "latest_readings": latest_readings
                })
            return result

    def get_all_alerts_summary(self, limit: int = 50) -> list:
        """Retrieves historical alerts logged in the system."""
        if self.use_sqlite:
            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        else:
            table_id = f"{self.project_id}.{BQ_DATASET}.alerts"
            query = f"SELECT * FROM `{table_id}` ORDER BY timestamp DESC LIMIT @limit"
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("limit", "INTEGER", limit)]
            )
            query_job = self.bq_client.query(query, job_config=job_config)
            return [dict(row) for row in query_job.result()]
