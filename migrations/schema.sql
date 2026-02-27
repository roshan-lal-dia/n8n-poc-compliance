-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- auto-generated definition
create table kb_standards
(
    id                serial
        primary key,
    domain_id         uuid,
    standard_name     varchar(500) not null,
    filename          varchar(500),
    file_hash         varchar(64)
        unique,
    total_chunks      integer      default 0,
    qdrant_collection varchar(100) default 'compliance_standards'::character varying,
    uploaded_at       timestamp    default now()
);

alter table kb_standards
    owner to n8n;

create index idx_kb_domain_id
    on kb_standards (domain_id);

create index idx_kb_hash
    on kb_standards (file_hash);



-- auto-generated definition
create table audit_sessions
(
    session_id               uuid        default uuid_generate_v4() not null
        primary key,
    domain_id                uuid,
    initiated_by             varchar(255),
    status                   varchar(50) default 'pending'::character varying,
    job_id                   varchar(100),
    started_at               timestamp   default now(),
    completed_at             timestamp,
    total_questions          integer     default 0,
    answered_questions       integer     default 0,
    overall_compliance_score numeric(5, 2),
    metadata                 jsonb
);

alter table audit_sessions
    owner to n8n;

create index idx_sessions_status
    on audit_sessions (status);

create index idx_sessions_domain_id
    on audit_sessions (domain_id);

create index idx_sessions_started
    on audit_sessions (started_at desc);

create index idx_sessions_jobid
    on audit_sessions (job_id);

-- auto-generated definition
create table audit_questions
(
    id                                uuid      default uuid_generate_v4() not null
        primary key,
    question_id                       uuid,
    domain_id                         uuid                                 not null,
    question_year                     integer   default 2026               not null,
    question_text                     text                                 not null,
    prompt_instructions               text,
    is_document_upload_enabled        boolean   default false              not null,
    is_cloud_sync_enabled             boolean   default false              not null,
    cloud_sync_api_url                text,
    cloud_sync_evaluation_instruction text,
    created_at                        timestamp default now(),
    updated_at                        timestamp default now(),
    accepted_evidence                 text,
    specification_number              text
);

alter table audit_questions
    owner to n8n;

create unique index idx_questions_question_id
    on audit_questions (question_id)
    where (question_id IS NOT NULL);

create index idx_questions_domain_id
    on audit_questions (domain_id);

create index idx_questions_year
    on audit_questions (question_year);

create index idx_questions_doc_upload
    on audit_questions (domain_id)
    where (is_document_upload_enabled = true);

create index idx_questions_cloud_sync
    on audit_questions (domain_id)
    where (is_cloud_sync_enabled = true);


-- auto-generated definition
create table audit_logs
(
    id          serial
        primary key,
    session_id  uuid not null,
    question_id uuid,
    step_name   varchar(200),
    status      varchar(50),
    ai_response jsonb,
    message     text,
    percentage  integer   default 0,
    created_at  timestamp default now()
);

alter table audit_logs
    owner to n8n;

create index idx_logs_session
    on audit_logs (session_id);

create index idx_logs_question_id
    on audit_logs (question_id);

create index idx_logs_status
    on audit_logs (status);

create index idx_logs_timestamp
    on audit_logs (created_at desc);

-- auto-generated definition
create table audit_evidence
(
    id              serial
        primary key,
    session_id      uuid  not null,
    question_id     uuid,
    domain_id       uuid,
    filename        varchar(500),
    file_hash       varchar(64),
    file_size_bytes bigint,
    evidence_order  integer   default 1,
    extracted_data  jsonb not null,
    created_at      timestamp default now(),
    constraint unique_evidence_per_session
        unique (session_id, question_id, file_hash)
);

alter table audit_evidence
    owner to n8n;

create index idx_evidence_session
    on audit_evidence (session_id);

create index idx_evidence_question_id
    on audit_evidence (question_id);

create index idx_evidence_domain_id
    on audit_evidence (domain_id);

create index idx_evidence_hash
    on audit_evidence (file_hash);

-- auto-generated definition
create table audit_domains
(
    id         uuid         not null
        primary key,
    name       varchar(255) not null
        unique,
    created_at timestamp default now()
);

alter table audit_domains
    owner to n8n;

