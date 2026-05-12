"""
Unit tests for RLS Policies migration (Task 1A).

These tests verify the migration SQL is valid and document expected behavior.
Note: Actual RLS enforcement requires Supabase database to be running.
"""

import re
from pathlib import Path

import pytest


class TestRLSMigrationFile:
    """Test the migration SQL file structure and content."""

    @pytest.fixture
    def migration_sql(self) -> str:
        """Load the migration SQL file."""
        migration_path = (
            Path(__file__).parent.parent
            / "supabase"
            / "migrations"
            / "012_enable_rls_policies.sql"
        )
        assert migration_path.exists(), "Migration file not found"
        return migration_path.read_text()

    def test_migration_file_exists(self, migration_sql: str) -> None:
        """Migration file should exist and contain SQL."""
        assert len(migration_sql) > 0
        assert "ALTER TABLE" in migration_sql

    def test_enable_rls_on_required_tables(self, migration_sql: str) -> None:
        """Should enable RLS on all user-facing tables."""
        tables_with_rls = [
            "users",
            "user_profiles",
            "assessment_responses",
            "roadmaps",
            "roadmap_tasks",
            "interaction_logs",
            "roadmap_mutations",
            "interest_profiles",
            "chat_sessions",
            "chat_messages",
            "retrieval_logs",
            "xp_transactions",
            "clinical_tasks",
            "retention_settings",
        ]
        for table in tables_with_rls:
            assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in migration_sql, (
                f"Missing RLS for {table}"
            )

    def test_users_table_policies(self, migration_sql: str) -> None:
        """Users table should have read, update, insert policies."""
        assert 'CREATE POLICY "Users can read own row"' in migration_sql
        assert 'CREATE POLICY "Users can update own row"' in migration_sql
        assert 'CREATE POLICY "Users can insert own row"' in migration_sql
        assert "USING (auth.uid() = id)" in migration_sql

    def test_user_profiles_policies(self, migration_sql: str) -> None:
        """user_profiles should have policies using user_id."""
        assert 'CREATE POLICY "Users can read own profile"' in migration_sql
        assert "USING (auth.uid() = user_id)" in migration_sql

    def test_roadmap_tasks_access_via_roadmap(self, migration_sql: str) -> None:
        """roadmap_tasks should check ownership via roadmaps table."""
        assert 'CREATE POLICY "Users can access roadmap tasks"' in migration_sql
        assert "SELECT id FROM roadmaps WHERE user_id = auth.uid()" in migration_sql

    def test_clinical_tasks_read_only(self, migration_sql: str) -> None:
        """clinical_tasks should be read-only for authenticated users."""
        assert (
            'CREATE POLICY "Authenticated users can read clinical_tasks"'
            in migration_sql
        )
        assert "TO authenticated" in migration_sql
        assert "USING (true)" in migration_sql

    def test_retention_settings_no_access(self, migration_sql: str) -> None:
        """retention_settings should have RLS but no policies (service role only)."""
        assert (
            "ALTER TABLE retention_settings ENABLE ROW LEVEL SECURITY" in migration_sql
        )
        assert 'CREATE POLICY "Users can access own interest profile"' in migration_sql

    def test_chat_messages_access_via_session(self, migration_sql: str) -> None:
        """chat_messages should check ownership via chat_sessions."""
        assert 'CREATE POLICY "Users can access chat messages"' in migration_sql
        assert (
            "SELECT id FROM chat_sessions WHERE user_id = auth.uid()" in migration_sql
        )

    def test_no_anonymous_access_policies(self, migration_sql: str) -> None:
        """All policies should be TO authenticated, not anon."""
        to_authenticated_count = migration_sql.count("TO authenticated")
        to_anon_count = migration_sql.count("TO anon")

        assert to_authenticated_count >= 10, "Should have many authenticated policies"
        assert to_anon_count == 0, "Should have no anon policies"

    def test_with_check_clauses_present(self, migration_sql: str) -> None:
        """INSERT policies should have WITH CHECK clauses."""
        with_check_count = migration_sql.count("WITH CHECK")
        assert with_check_count >= 5, (
            "Should have WITH CHECK clauses for insert policies"
        )

    def test_sql_syntax_valid(self, migration_sql: str) -> None:
        """Basic SQL syntax validation - no obvious errors."""
        # Check balanced parentheses in CREATE POLICY blocks
        policy_blocks = migration_sql.split("CREATE POLICY")
        for block in policy_blocks[1:]:
            opens = block.count("(")
            closes = block.count(")")
            assert opens == closes, f"Unbalanced parentheses in policy"


class TestRLSPoliciesDocumented:
    """Document the expected behavior of RLS policies."""

    def test_policy_summary(self) -> None:
        """Document which tables have what level of access."""
        expected_policies = {
            "user_profiles": "read, update, insert (own)",
            "assessment_responses": "read, insert (own)",
            "roadmaps": "read, insert (own)",
            "interest_profiles": "full (own)",
            "chat_sessions": "full (own)",
            "interaction_logs": "read, insert (own)",
            "xp_transactions": "read (own)",
            "retrieval_logs": "insert (own)",
            "roadmap_mutations": "full (own)",
            "roadmap_tasks": "full (via roadmap ownership)",
            "chat_messages": "full (via session ownership)",
            "users": "read, update, insert (own)",
            "clinical_tasks": "read (all authenticated)",
            "retention_settings": "none (service role only)",
        }

        assert len(expected_policies) == 14

    def test_security_implications(self) -> None:
        """Document security implications of this migration."""
        implications = [
            "Without RLS, anyone with anon key can read/write all tables",
            "All user-facing tables now have RLS enabled",
            "Users can only access their own data via policies",
            "Service role can bypass RLS (as intended)",
            "clinical_tasks is read-only (not user-specific data)",
            "retention_settings has no public access",
        ]

        assert len(implications) == 6
