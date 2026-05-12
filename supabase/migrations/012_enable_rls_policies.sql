-- Migration 012: Enable RLS Policies
-- Owner: Yehia (taking over for Hozaifa)
-- Date: 2026-05-12
-- Significance: Without RLS, anyone with the anon key can read/write every table.

-- Enable RLS on all user-facing tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmap_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE interaction_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE roadmap_mutations ENABLE ROW LEVEL SECURITY;
ALTER TABLE interest_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrieval_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE xp_transactions ENABLE ROW LEVEL SECURITY;

-- clinical_tasks: read-only for authenticated users
ALTER TABLE clinical_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read clinical_tasks"
  ON clinical_tasks FOR SELECT
  TO authenticated
  USING (true);

-- retention_settings: service role only (no anon/authenticated access)
ALTER TABLE retention_settings ENABLE ROW LEVEL SECURITY;
-- No policies = no access for anon/authenticated

-- Users table: read/update own row only
CREATE POLICY "Users can read own row"
  ON users FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can update own row"
  ON users FOR UPDATE
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can insert own row"
  ON users FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);

-- user_profiles: own profile only
CREATE POLICY "Users can read own profile"
  ON user_profiles FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can update own profile"
  ON user_profiles FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile"
  ON user_profiles FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- assessment_responses: own responses only
CREATE POLICY "Users can read own assessments"
  ON assessment_responses FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own assessments"
  ON assessment_responses FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- roadmaps: own roadmaps only
CREATE POLICY "Users can read own roadmaps"
  ON roadmaps FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own roadmaps"
  ON roadmaps FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- roadmap_tasks: access via roadmap ownership
CREATE POLICY "Users can access roadmap tasks"
  ON roadmap_tasks FOR ALL
  TO authenticated
  USING (
    roadmap_id IN (
      SELECT id FROM roadmaps WHERE user_id = auth.uid()
    )
  );

-- interest_profiles: own profile only
CREATE POLICY "Users can access own interest profile"
  ON interest_profiles FOR ALL
  TO authenticated
  USING (auth.uid() = user_id);

-- chat_sessions: own sessions only
CREATE POLICY "Users can access own chat sessions"
  ON chat_sessions FOR ALL
  TO authenticated
  USING (auth.uid() = user_id);

-- chat_messages: access via session ownership
CREATE POLICY "Users can access chat messages"
  ON chat_messages FOR ALL
  TO authenticated
  USING (
    session_id IN (
      SELECT id FROM chat_sessions WHERE user_id = auth.uid()
    )
  );

-- interaction_logs: own logs only
CREATE POLICY "Users can read own interaction logs"
  ON interaction_logs FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own interaction logs"
  ON interaction_logs FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- xp_transactions: own transactions only
CREATE POLICY "Users can read own XP transactions"
  ON xp_transactions FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

-- retrieval_logs: own logs only
CREATE POLICY "Users can insert own retrieval logs"
  ON retrieval_logs FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

-- roadmap_mutations: own mutations only
CREATE POLICY "Users can access own roadmap mutations"
  ON roadmap_mutations FOR ALL
  TO authenticated
  USING (auth.uid() = user_id);