"""Quick test that the placeholder validator works."""
import os
import re
import sys
import subprocess


def check_url(name, db_url, should_pass, expected_placeholder=None):
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
    assert passed, f"FAIL {name}: stdout={result.stdout!r} stderr={result.stderr!r}"


def test_placeholder_validation():
    # Test placeholder rejection
    check_url(
        "all placeholders",
        "postgresql+psycopg2://postgres.<PROJECT_REF>:<PASSWORD>@aws-0-<REGION>.pooler.supabase.com:6543/postgres",
        should_pass=False,
    )
    check_url(
        "only <REGION>",
        "postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:actual_pw@aws-0-<REGION>.pooler.supabase.com:6543/postgres",
        should_pass=False,
    )
    check_url(
        "only <PROJECT_REF>",
        "postgresql+psycopg2://postgres.<PROJECT_REF>:actual_pw@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
        should_pass=False,
    )
    check_url(
        "only <PASSWORD>",
        "postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:<PASSWORD>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
        should_pass=False,
    )

    # Test valid URLs
    check_url(
        "fully resolved with sslmode",
        "postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:actual_pw@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require",
        should_pass=True,
    )
    check_url(
        "fully resolved no sslmode",
        "postgresql+psycopg2://postgres.uzrtydpbxemuncdkpekv:actual_pw@aws-0-ap-south-1.pooler.supabase.com:6543/postgres",
        should_pass=True,
    )
    check_url(
        "localhost dev URL",
        "postgresql+psycopg2://os:os@localhost:5432/os",
        should_pass=True,
    )


if __name__ == "__main__":
    test_placeholder_validation()
    print("All placeholder validation tests passed!")
