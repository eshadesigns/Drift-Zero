"""Drop maneuver_events table so compute_maneuver_events.py recreates it cleanly."""
import os, time
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()
w = WorkspaceClient(host=os.getenv("DATABRICKS_HOST"), token=os.getenv("DATABRICKS_TOKEN"))
wh = os.getenv("DATABRICKS_WAREHOUSE_ID")

r = w.statement_execution.execute_statement(
    statement="DROP TABLE IF EXISTS drift_zero.orbital.maneuver_events",
    warehouse_id=wh, wait_timeout="0s"
)
sid = r.statement_id
while True:
    r = w.statement_execution.get_statement(sid)
    s = r.status.state.value
    if s in ("SUCCEEDED", "FAILED", "CANCELED", "CLOSED"):
        break
    time.sleep(3)
print("Done:", s)
