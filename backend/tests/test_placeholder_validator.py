"""Quick test that the placeholder validator works."""
import os
import re
import sys
import subprocess


def test(name, db_url, should_pass, expected_placeholder=None):
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["APP_SECRET_KEY"] = "test-secret"
    env["WORKER_ENABLED"] = "false"
    env["DB_STARTUP_TIMEOUT"] = "2"
    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app; print('OK')"],
        cwd=os.path.dirname(__file__) or ".",
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout + result.stderr
    passed = should_pass if ("OK" in result.stdout) else not should_pass
    if should_pass and "OK" in result.stdout:
        print(f"  PASS  {name}")
    elif not should_pass and "unresolved placeholder" in output:
        ph = re.search(r"'<[^>]+>'", output)
        print(f"  PASS  {name} (rejected: {ph.group(0) if ph else '?'})")
    else:
        print(f"  FAIL  {name}: stdout={result.stdout!r} stderr={result.stderr!r}")


print("Test placeholder rejection:")
test(
    "all placeholders",
    "postgresql+psycopg2://postgres.<PROJECT_REF>:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres",
    should_pass=False,
)
test(
    "only <REGION>",
    "postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:actual_pw@aws-0-<REGION>.pooler.supabase.com:6543/postgres",
    should_pass=False,
)
test(
    "only <PROJECT_REF>",
    "postgresql+psycopg2://postgres.<PROJECT_REF>:actual_pw@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
    should_pass=False,
)
test(
    "only <PASSWORD>",
    "postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:<PASSWORD>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
    should_pass=False,
)

print("\nTest valid URLs:")
test(
    "fully resolved with sslmode",
    "postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:actual_pw@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require",
    should_pass=True,
)
test(
    "fully resolved no sslmode",
    "postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:actual_pw@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
    should_pass=True,
)
test(
    "localhost dev URL",
    "postgresql+psycopg2://os:os@localhost:5432/os",
    should_pass=True,
)
