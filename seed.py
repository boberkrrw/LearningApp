"""
Seed script: reads the Data Engineer skill matrix xlsx, parses topics/subtopics,
infers dependencies and priority scores, and populates the SQLite database.
"""
import json
import os
import sys
import pandas as pd
from db.database import init_db, get_session
from db.models import Topic, Subtopic, Progress, ProgressStatus

XLSX_PATH = os.path.join(
    os.path.expanduser("~"),
    "OneDrive", "Робочий стіл", "Data Engineer_v.0.1.xlsx",
)

# Priority map: (topic_name, subtopic_name) -> (priority_score, tier, dependency_names)
PRIORITY_MAP = {
    # Tier 1 — Foundational
    ("Programming & Scripting", "SQL (Joins, Aggregations, CTEs, Window Functions)"): (1, 1, []),
    ("Programming & Scripting", "Python for Data Processing (pandas, pyarrow)"): (2, 1, []),
    ("Programming & Scripting", "Writing Efficient SQL Queries"): (3, 1, ["SQL (Joins, Aggregations, CTEs, Window Functions)"]),
    ("ETL / ELT Pipelines", "ETL/ELT Concepts & Data Movement"): (4, 1, ["SQL (Joins, Aggregations, CTEs, Window Functions)", "Python for Data Processing (pandas, pyarrow)"]),
    # Tier 2 — Core Data Engineering
    ("Data Modeling & Warehousing", "Dimensional Modeling (Star, Snowflake schemas)"): (5, 2, ["SQL (Joins, Aggregations, CTEs, Window Functions)"]),
    ("Data Modeling & Warehousing", "Data Normalization / Denormalization"): (6, 2, ["Dimensional Modeling (Star, Snowflake schemas)"]),
    ("Data Modeling & Warehousing", "Slowly Changing Dimensions (Type 1/2/3)"): (7, 2, ["Dimensional Modeling (Star, Snowflake schemas)"]),
    ("Data Modeling & Warehousing", "Columnar Storage Design (Parquet, ORC)"): (8, 2, ["Data Normalization / Denormalization"]),
    ("Cloud Platforms & Infrastructure", "Cloud Storage (GCS, AWS S3, Azure Blob)"): (9, 2, []),
    ("Data Modeling & Warehousing", "Data Warehouse Solutions (BigQuery/Snowflake/Redshift/Snowflake)"): (10, 2, ["Dimensional Modeling (Star, Snowflake schemas)", "Cloud Storage (GCS, AWS S3, Azure Blob)"]),
    ("Cloud Platforms & Infrastructure", "Data Lakes (Delta Lake, Apache Iceberg, Hudi)"): (11, 2, ["Columnar Storage Design (Parquet, ORC)", "Cloud Storage (GCS, AWS S3, Azure Blob)"]),
    # Tier 3 — Pipeline Operations
    ("ETL / ELT Pipelines", "Orchestration Tools (Airflow, Prefect, Dagster)"): (12, 3, ["ETL/ELT Concepts & Data Movement"]),
    ("ETL / ELT Pipelines", "Pipeline Scheduling & Monitoring"): (13, 3, ["Orchestration Tools (Airflow, Prefect, Dagster)"]),
    ("ETL / ELT Pipelines", "Job Idempotency & Retry Logic"): (14, 3, ["ETL/ELT Concepts & Data Movement"]),
    ("ETL / ELT Pipelines", "CDC (Debezium, Fivetran, log-based replication)"): (15, 3, ["ETL/ELT Concepts & Data Movement"]),
    ("Programming & Scripting", "Shell/Bash scripting for automation"): (16, 3, []),
    # Tier 4 — Quality, Testing & DevOps
    ("Data Quality & Governance", "Data Validation (Great Expectations, Soda)"): (17, 4, ["SQL (Joins, Aggregations, CTEs, Window Functions)", "Python for Data Processing (pandas, pyarrow)"]),
    ("Data Quality & Governance", "Schema Evolution & Backward Compatibility"): (18, 4, ["Dimensional Modeling (Star, Snowflake schemas)"]),
    ("Monitoring, Testing, CI/CD", "Data Testing (unit, integration, regression)"): (19, 4, ["Python for Data Processing (pandas, pyarrow)", "Data Validation (Great Expectations, Soda)"]),
    ("Monitoring, Testing, CI/CD", "CI/CD for Data Pipelines (GitHub Actions, GitLab)"): (20, 4, ["Data Testing (unit, integration, regression)", "Shell/Bash scripting for automation"]),
    ("Monitoring, Testing, CI/CD", "Pipeline Logging & Monitoring (Prometheus, Grafana)"): (21, 4, ["Pipeline Scheduling & Monitoring"]),
    ("Monitoring, Testing, CI/CD", "Alerting & Incident Response"): (22, 4, ["Pipeline Logging & Monitoring (Prometheus, Grafana)"]),
    # Tier 5 — Security & Governance
    ("Cloud Platforms & Infrastructure", "IAM, Secrets Management (Vault, AWS IAM)"): (23, 5, ["Cloud Storage (GCS, AWS S3, Azure Blob)"]),
    ("Security, Compliance & Privacy", "Data Classification & Sensitivity"): (24, 5, []),
    ("Security, Compliance & Privacy", "Data Encryption (At rest, In transit)"): (25, 5, ["Data Classification & Sensitivity", "Cloud Storage (GCS, AWS S3, Azure Blob)"]),
    ("Security, Compliance & Privacy", "Role-Based Access Control (RBAC)"): (26, 5, ["IAM, Secrets Management (Vault, AWS IAM)"]),
    ("Security, Compliance & Privacy", "GDPR, HIPAA, Compliance"): (27, 5, ["Data Classification & Sensitivity", "Data Encryption (At rest, In transit)", "Role-Based Access Control (RBAC)"]),
    # Tier 6 — Supplementary
    ("Data Quality & Governance", "Metadata Management (OpenMetadata, DataHub, Amundsen)"): (28, 6, ["Data Validation (Great Expectations, Soda)"]),
    ("Data Quality & Governance", "Lineage Tracking (OpenLineage, Marquez)"): (29, 6, ["Metadata Management (OpenMetadata, DataHub, Amundsen)"]),
    ("Programming & Scripting", "Type Hints & Static Analysis (Python)"): (30, 6, ["Python for Data Processing (pandas, pyarrow)"]),
    ("Security, Compliance & Privacy", "Data Masking & Tokenization Techniques"): (31, 6, ["Data Encryption (At rest, In transit)"]),
    ("Cloud Platforms & Infrastructure", "Serverless Technologies: Use Cloud Functions, Lambda."): (32, 6, ["Cloud Storage (GCS, AWS S3, Azure Blob)"]),
    ("Cloud Platforms & Infrastructure", "Networking: Understand VPC, subnets, firewalls."): (33, 6, ["Cloud Storage (GCS, AWS S3, Azure Blob)"]),
    ("Cloud Platforms & Infrastructure", "Kubernetes for Data Pipelines"): (34, 6, ["Cloud Storage (GCS, AWS S3, Azure Blob)"]),
}


def parse_xlsx():
    df = pd.read_excel(XLSX_PATH, sheet_name="Competency Matrix", header=None)

    topics_data = []
    current_topic = None

    for _, row in df.iterrows():
        topic_val = row.iloc[1]
        subtopic_val = row.iloc[2]
        description_val = row.iloc[3]
        senior_val = row.iloc[6]

        if pd.notna(topic_val) and str(topic_val).strip() and str(topic_val).strip() not in ("Topic", "Category"):
            current_topic = str(topic_val).strip()

        if pd.notna(subtopic_val) and str(subtopic_val).strip() and current_topic and str(subtopic_val).strip() != "Subtopic":
            senior_level = str(senior_val).strip() if pd.notna(senior_val) else "L3"
            desc = str(description_val).strip() if pd.notna(description_val) else ""
            topics_data.append({
                "topic": current_topic,
                "subtopic": str(subtopic_val).strip(),
                "description": desc,
                "senior_level": senior_level,
            })

    return topics_data


def seed_database():
    init_db()
    session = get_session()

    existing = session.query(Topic).count()
    if existing > 0:
        print(f"Database already seeded ({existing} topics found). Skipping.")
        session.close()
        return

    topics_data = parse_xlsx()
    print(f"Parsed {len(topics_data)} subtopics from the skill matrix.")

    # Create topics
    topic_objects = {}
    for item in topics_data:
        if item["topic"] not in topic_objects:
            topic_obj = Topic(name=item["topic"])
            session.add(topic_obj)
            session.flush()
            topic_objects[item["topic"]] = topic_obj

    # Create subtopics with priority info
    subtopic_name_to_id = {}
    for item in topics_data:
        topic_obj = topic_objects[item["topic"]]
        key = (item["topic"], item["subtopic"])
        priority_info = PRIORITY_MAP.get(key, (50, 6, []))

        subtopic_obj = Subtopic(
            topic_id=topic_obj.id,
            name=item["subtopic"],
            description=item["description"],
            senior_level=item["senior_level"],
            priority_score=priority_info[0],
            tier=priority_info[1],
            dependencies=json.dumps(priority_info[2]),
        )
        session.add(subtopic_obj)
        session.flush()
        subtopic_name_to_id[item["subtopic"]] = subtopic_obj.id

        # Create initial progress record
        progress = Progress(
            subtopic_id=subtopic_obj.id,
            status=ProgressStatus.NOT_STARTED,
        )
        session.add(progress)

    session.commit()
    print(f"Seeded {len(topic_objects)} topics and {len(subtopic_name_to_id)} subtopics.")
    session.close()


if __name__ == "__main__":
    seed_database()
