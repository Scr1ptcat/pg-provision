"""
Security behavior tests for secret handling in create_db_and_user.

Ensures password is not exposed on the psql command line by verifying that
psql reads SQL from stdin and that the SQL stream contains the password
(not the argv). Also verifies support for CREATE_PASSWORD_FILE.
"""

import re

import pytest


@pytest.mark.unit
def test_create_user_password_not_in_argv(tmp_path, bash):
    cap = tmp_path / "cap.txt"
    sqlcap = tmp_path / "sql.txt"
    env = {
        "CAP": str(cap),
        "SQLCAP": str(sqlcap),
        "CREATE_USER": "alice",
        "CREATE_DB": "testdb",
        "CREATE_PASSWORD": "s3cr3t!",  # pragma: allowlist secret
    }
    script = r"""
      CAP="${CAP:?}"
      SQLCAP="${SQLCAP:?}"
      : > "$CAP"
      : > "$SQLCAP"
      psql() { echo "psql $*" >> "$CAP"; cat > "$SQLCAP"; return 0; }
      shred() { :; }
      create_db_and_user || true
      cat "$CAP"
    """
    r = bash(script, env=env)
    assert r.rc == 0, r.stderr
    line = r.stdout.strip().splitlines()[-1]
    assert re.search(r"\bpsql\b", line)
    assert "-f" not in line
    # Ensure password does not appear in argv
    assert "s3cr3t!" not in line
    sql = sqlcap.read_text(encoding="utf-8")
    assert "s3cr3t!" in sql
    assert "CREATE ROLE \"alice\" LOGIN PASSWORD ''s3cr3t!''" in sql
    assert 'CREATE DATABASE "testdb" OWNER "alice"' in sql
    assert "\\gexec" in sql
    assert "DO $$" not in sql
    assert 'CREATE DATABASE "testdb" OWNER "alice";' not in sql


@pytest.mark.unit
def test_create_user_password_from_file(tmp_path, bash):
    cap = tmp_path / "cap.txt"
    sqlcap = tmp_path / "sql.txt"
    pwf = tmp_path / "pw.txt"
    pwf.write_text("Pa$$wd", encoding="utf-8")
    env = {
        "CAP": str(cap),
        "SQLCAP": str(sqlcap),
        "CREATE_USER": "bob",
        "CREATE_PASSWORD_FILE": str(pwf),
    }
    script = r"""
      CAP="${CAP:?}"
      SQLCAP="${SQLCAP:?}"
      : > "$CAP"
      : > "$SQLCAP"
      psql() { echo "psql $*" >> "$CAP"; cat > "$SQLCAP"; return 0; }
      shred() { :; }
      create_db_and_user || true
      cat "$CAP"
    """
    r = bash(script, env=env)
    assert r.rc == 0, r.stderr
    line = r.stdout.strip().splitlines()[-1]
    # Ensure stdin execution is used and password not exposed via argv
    assert "Pa$$wd" not in line
    assert "-f" not in line
    sql = sqlcap.read_text(encoding="utf-8")
    assert "Pa$$wd" in sql
    assert "DO $$" not in sql
    assert "\\gexec" in sql


@pytest.mark.unit
def test_create_db_without_create_user_omits_owner(tmp_path, bash):
    sqlcap = tmp_path / "sql.txt"

    r = bash(
        """
      SQLCAP="${SQLCAP:?}"
      : > "$SQLCAP"
      psql() { cat > "$SQLCAP"; return 0; }
      CREATE_DB=appdb
      create_db_and_user
        """,
        env={"SQLCAP": str(sqlcap)},
    )

    assert r.rc == 0, r.stderr
    sql = sqlcap.read_text(encoding="utf-8")
    assert 'CREATE DATABASE "appdb"' in sql
    assert " OWNER " not in sql
    assert "\\gexec" in sql
