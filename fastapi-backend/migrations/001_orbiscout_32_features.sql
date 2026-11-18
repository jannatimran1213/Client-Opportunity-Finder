-- OrbiScout 32-feature release: schema for the new tables (PostgreSQL 15+ / Supabase).
-- The backend also creates these automatically on startup (app/db/init_db.py: create_all + idempotent ALTERs).
-- Run this file only if you prefer managing the schema by hand (e.g. Supabase SQL editor).

ALTER TABLE saved_businesses ADD COLUMN IF NOT EXISTS workspace_id UUID;
CREATE INDEX IF NOT EXISTS ix_saved_businesses_workspace_id ON saved_businesses (workspace_id);

CREATE TABLE IF NOT EXISTS workspaces (
	id UUID NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	slug VARCHAR(80) NOT NULL, 
	owner_id UUID NOT NULL, 
	company_name VARCHAR(160), 
	company_website VARCHAR(300), 
	services TEXT, 
	settings JSONB NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_workspaces_slug ON workspaces (slug);
CREATE INDEX IF NOT EXISTS ix_workspaces_owner_id ON workspaces (owner_id);

CREATE TABLE IF NOT EXISTS background_jobs (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	user_id UUID, 
	kind VARCHAR(40) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	runner VARCHAR(20), 
	celery_task_id VARCHAR(80), 
	payload JSONB NOT NULL, 
	result JSONB, 
	error TEXT, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_background_jobs_workspace_id ON background_jobs (workspace_id);
CREATE INDEX IF NOT EXISTS ix_background_jobs_kind ON background_jobs (kind);

CREATE TABLE IF NOT EXISTS competitor_benchmarks (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	target_url VARCHAR(500) NOT NULL, 
	competitor_urls JSONB NOT NULL, 
	ranking JSONB NOT NULL, 
	insights JSONB NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_competitor_benchmarks_workspace_id ON competitor_benchmarks (workspace_id);

CREATE TABLE IF NOT EXISTS lead_lists (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	color VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_lead_lists_workspace_id ON lead_lists (workspace_id);

CREATE TABLE IF NOT EXISTS notifications (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	user_id UUID, 
	title VARCHAR(200) NOT NULL, 
	body TEXT, 
	link VARCHAR(300), 
	read BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_notifications_workspace_id ON notifications (workspace_id);
CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);

CREATE TABLE IF NOT EXISTS search_jobs (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	user_id UUID, 
	kind VARCHAR(20) NOT NULL, 
	business_type VARCHAR(120), 
	city VARCHAR(120), 
	country VARCHAR(120), 
	target_url VARCHAR(500), 
	status VARCHAR(20) NOT NULL, 
	result_count INTEGER NOT NULL, 
	results JSONB NOT NULL, 
	error TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_search_jobs_workspace_id ON search_jobs (workspace_id);

CREATE TABLE IF NOT EXISTS subscriptions (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	plan VARCHAR(30) NOT NULL, 
	interval VARCHAR(10) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	trial_ends_at TIMESTAMP WITH TIME ZONE, 
	billing_mode VARCHAR(10) NOT NULL, 
	current_period_end TIMESTAMP WITH TIME ZONE, 
	cancel_at_period_end BOOLEAN NOT NULL, 
	stripe_customer_id VARCHAR(120), 
	stripe_subscription_id VARCHAR(120), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_subscriptions_workspace_id ON subscriptions (workspace_id);

CREATE TABLE IF NOT EXISTS workspace_invites (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	token VARCHAR(80) NOT NULL, 
	accepted BOOLEAN NOT NULL, 
	invited_by UUID, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_workspace_invites_email ON workspace_invites (email);
CREATE INDEX IF NOT EXISTS ix_workspace_invites_workspace_id ON workspace_invites (workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_workspace_invites_token ON workspace_invites (token);

CREATE TABLE IF NOT EXISTS workspace_members (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_workspace_member UNIQUE (workspace_id, user_id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_workspace_members_user_id ON workspace_members (user_id);
CREATE INDEX IF NOT EXISTS ix_workspace_members_workspace_id ON workspace_members (workspace_id);

CREATE TABLE IF NOT EXISTS workspace_usage (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	period VARCHAR(7) NOT NULL, 
	metric VARCHAR(40) NOT NULL, 
	count INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_usage_metric UNIQUE (workspace_id, period, metric), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_workspace_usage_workspace_id ON workspace_usage (workspace_id);
CREATE INDEX IF NOT EXISTS ix_workspace_usage_period ON workspace_usage (period);

CREATE TABLE IF NOT EXISTS advanced_audits (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	url VARCHAR(500) NOT NULL, 
	overall_score FLOAT, 
	speed_score FLOAT, 
	security_score FLOAT, 
	mobile_score FLOAT, 
	seo_score FLOAT, 
	trust_score FLOAT, 
	leak_count INTEGER, 
	tech_stack JSONB NOT NULL, 
	report JSONB NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_advanced_audits_workspace_id ON advanced_audits (workspace_id);
CREATE INDEX IF NOT EXISTS ix_advanced_audits_business_id ON advanced_audits (business_id);

CREATE TABLE IF NOT EXISTS channel_messages (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	channel VARCHAR(20) NOT NULL, 
	direction VARCHAR(10) NOT NULL, 
	to_address VARCHAR(255) NOT NULL, 
	subject VARCHAR(300), 
	body TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	provider_message_id VARCHAR(200), 
	error TEXT, 
	meta JSONB NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_channel_messages_workspace_id ON channel_messages (workspace_id);
CREATE INDEX IF NOT EXISTS ix_channel_messages_business_id ON channel_messages (business_id);
CREATE INDEX IF NOT EXISTS ix_channel_messages_provider_message_id ON channel_messages (provider_message_id);

CREATE TABLE IF NOT EXISTS copy_drafts (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	batch_id VARCHAR(40), 
	kind VARCHAR(30) NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	industry VARCHAR(60), 
	subject VARCHAR(300), 
	body TEXT NOT NULL, 
	meta JSONB NOT NULL, 
	source VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_copy_drafts_business_id ON copy_drafts (business_id);
CREATE INDEX IF NOT EXISTS ix_copy_drafts_batch_id ON copy_drafts (batch_id);
CREATE INDEX IF NOT EXISTS ix_copy_drafts_workspace_id ON copy_drafts (workspace_id);

CREATE TABLE IF NOT EXISTS lead_list_items (
	id UUID NOT NULL, 
	list_id UUID NOT NULL, 
	business_id UUID NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_list_business UNIQUE (list_id, business_id), 
	FOREIGN KEY(list_id) REFERENCES lead_lists (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_lead_list_items_list_id ON lead_list_items (list_id);
CREATE INDEX IF NOT EXISTS ix_lead_list_items_business_id ON lead_list_items (business_id);

CREATE TABLE IF NOT EXISTS lead_profiles (
	business_id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	priority VARCHAR(10) NOT NULL, 
	tags JSONB NOT NULL, 
	linkedin_url VARCHAR(500), 
	whatsapp_number VARCHAR(40), 
	email_status VARCHAR(20), 
	email_reason VARCHAR(200), 
	phone_status VARCHAR(20), 
	phone_e164 VARCHAR(40), 
	website_status VARCHAR(20), 
	website_http_code INTEGER, 
	validation_score INTEGER, 
	validated_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (business_id), 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE CASCADE, 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_lead_profiles_workspace_id ON lead_profiles (workspace_id);

CREATE TABLE IF NOT EXISTS linkedin_tasks (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	profile_url VARCHAR(500) NOT NULL, 
	contact_name VARCHAR(160), 
	action VARCHAR(20) NOT NULL, 
	message TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	scheduled_for TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_linkedin_tasks_workspace_id ON linkedin_tasks (workspace_id);

CREATE TABLE IF NOT EXISTS meetings (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	created_by UUID, 
	title VARCHAR(200) NOT NULL, 
	start_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	end_at TIMESTAMP WITH TIME ZONE, 
	timezone VARCHAR(60) NOT NULL, 
	location VARCHAR(300), 
	meeting_link VARCHAR(500), 
	attendee_name VARCHAR(160), 
	attendee_email VARCHAR(255), 
	attendee_phone VARCHAR(40), 
	notes TEXT, 
	status VARCHAR(20) NOT NULL, 
	outcome TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_meetings_business_id ON meetings (business_id);
CREATE INDEX IF NOT EXISTS ix_meetings_start_at ON meetings (start_at);
CREATE INDEX IF NOT EXISTS ix_meetings_workspace_id ON meetings (workspace_id);

CREATE TABLE IF NOT EXISTS site_pages (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	name VARCHAR(160) NOT NULL, 
	kind VARCHAR(10) NOT NULL, 
	template_key VARCHAR(60), 
	blocks JSONB NOT NULL, 
	theme JSONB NOT NULL, 
	subdomain VARCHAR(63), 
	published BOOLEAN NOT NULL, 
	published_html TEXT, 
	published_at TIMESTAMP WITH TIME ZONE, 
	view_count INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_site_pages_workspace_id ON site_pages (workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_site_pages_subdomain ON site_pages (subdomain);

CREATE TABLE IF NOT EXISTS tracked_emails (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	token VARCHAR(40) NOT NULL, 
	recipient VARCHAR(255) NOT NULL, 
	subject VARCHAR(300), 
	sent_via VARCHAR(30), 
	status VARCHAR(20) NOT NULL, 
	open_count INTEGER NOT NULL, 
	click_count INTEGER NOT NULL, 
	first_opened_at TIMESTAMP WITH TIME ZONE, 
	last_event_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_tracked_emails_workspace_id ON tracked_emails (workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_tracked_emails_token ON tracked_emails (token);

CREATE TABLE IF NOT EXISTS follow_ups (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	meeting_id UUID, 
	title VARCHAR(200) NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	due_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	notes TEXT, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL, 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_follow_ups_business_id ON follow_ups (business_id);
CREATE INDEX IF NOT EXISTS ix_follow_ups_due_at ON follow_ups (due_at);
CREATE INDEX IF NOT EXISTS ix_follow_ups_workspace_id ON follow_ups (workspace_id);

CREATE TABLE IF NOT EXISTS next_steps (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	business_id UUID, 
	meeting_id UUID, 
	title VARCHAR(200) NOT NULL, 
	owner VARCHAR(160), 
	due_date DATE, 
	stage VARCHAR(30), 
	done BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(business_id) REFERENCES saved_businesses (id) ON DELETE SET NULL, 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_next_steps_business_id ON next_steps (business_id);
CREATE INDEX IF NOT EXISTS ix_next_steps_workspace_id ON next_steps (workspace_id);

CREATE TABLE IF NOT EXISTS tracking_events (
	id UUID NOT NULL, 
	tracked_email_id UUID NOT NULL, 
	event_type VARCHAR(10) NOT NULL, 
	url TEXT, 
	ip VARCHAR(64), 
	user_agent VARCHAR(400), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tracked_email_id) REFERENCES tracked_emails (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_tracking_events_tracked_email_id ON tracking_events (tracked_email_id);

CREATE TABLE IF NOT EXISTS reminders (
	id UUID NOT NULL, 
	workspace_id UUID NOT NULL, 
	meeting_id UUID, 
	follow_up_id UUID, 
	remind_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	recipient VARCHAR(255), 
	message TEXT, 
	sent BOOLEAN NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	error TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
	FOREIGN KEY(meeting_id) REFERENCES meetings (id) ON DELETE CASCADE, 
	FOREIGN KEY(follow_up_id) REFERENCES follow_ups (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_reminders_sent ON reminders (sent);
CREATE INDEX IF NOT EXISTS ix_reminders_remind_at ON reminders (remind_at);
CREATE INDEX IF NOT EXISTS ix_reminders_meeting_id ON reminders (meeting_id);
CREATE INDEX IF NOT EXISTS ix_reminders_workspace_id ON reminders (workspace_id);

