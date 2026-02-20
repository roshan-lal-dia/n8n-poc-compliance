# Compliance App DB — Schema Reference

**Host:** `unifi-cdmp-server-pg.postgres.database.azure.com`  
**DB:** `npc_compliance_test`  
**User:** `db_admin`  
**SSL:** required

---

## Table Inventory (27 tables)

| Table | Purpose |
|---|---|
| `dmn_domains` | 12 domains (e.g. Data Quality Management) |
| `dmn_standards` | 1 standard per domain (12 total) |
| `dmn_std_dimensions` | Dimensions within a standard (e.g. DAM.1 Plan) |
| `dmn_std_controls` | Controls within a dimension (e.g. DAM.1.1) |
| `dmn_std_specifications` | Specs within a control (e.g. DAM.1.1.1) |
| `dmn_sub_specifications` | Sub-specs (JSONB detail) linked to specs |
| `dmn_questions` | 159 audit questions linked to specs |
| `dmn_guidelines` | Guidelines per domain |
| `dmn_policy` | Policy documents |
| `asmnt_assessments` | 66 assessment runs |
| `asmnt_question_map` | 25,450 rows — maps questions to assessments |
| `asmnt_answers` | 7,194 answers submitted by entities |
| `asmnt_entity_domain_and_owner_map` | Assigns domain ownership per entity per assessment |
| `asmnt_entity_map` | Maps entities into assessments |
| `ent_entity` | 7 entities (ministries / orgs) |
| `users` / `usr_account` / `usr_profile` / `usr_role` | User management |
| `ministries` | Ministry lookup |
| `cfg_settings` | App config |
| `log_user_activity` | Audit log |
| `push_subscriptions` | Push notification tokens |
| `user_notifications` | Notifications |
| `user_role_permissions` | RBAC |
| `user_details` | Extended user info |

---

## Core Domain Hierarchy

All IDs are UUIDs. The readable identifiers are stored as `serial_id` columns.

```
dmn_domains (uuid)
  └── dmn_standards (uuid)
        └── dmn_std_dimensions  (uuid)  serial: DAM.1, DAM.2, DMSG.1 ...
              └── dmn_std_controls      (uuid)  serial: DAM.1.1, DAM.2.1 ...
                    └── dmn_std_specifications (uuid)  serial: DAM.1.1.1 ...
                          └── dmn_questions (uuid)
```

---

## Domains (12)

| UUID | Name |
|---|---|
| `a14d13d9-81eb-46da-ab4f-8476c6469dd3` | Data Architecture and Modeling |
| `f1b48d90-4f9a-46b4-b6f7-a1fb2b8d68fd` | Data Catalog and Metadata Management |
| `98b03b0e-3a90-4ffb-a332-25a2de2191b5` | Data Culture and Literacy |
| `9dbe7809-ce9c-471f-84c1-61e02d39b7c7` | Data Management Strategy and Governance |
| `86b0e9f6-aef3-4c93-84c0-b26afbe184cb` | Data Monetization |
| `ad4bdcc2-182a-4d06-bc03-8fca91056c81` | Data Quality Management |
| `75e2eabb-6b69-465e-a6cb-f6bb1b0ed697` | Data Security, Privacy and Other Regulations |
| `6ec7535e-6134-4010-9817-8c0849e8f59b` | Data Sharing, Integration & Interoperability |
| `4d3a47dd-df31-435e-a8da-b5e758ca3668` | Data Storage and Operations |
| `4b793d57-a04e-4618-a275-082fb5c81792` | Document and Content Management |
| `78739b15-7c02-49be-b03e-2b0c2f502c22` | Master and Reference Data Management |
| `91feeabb-ef97-493c-98b8-accdac8324f3` | Statistics & Analytics |

---

## Standards (12 — one per domain)

| UUID | Domain | Standard Name |
|---|---|---|
| `850c0e75-e8c8-4bea-8aa9-b63c37c41a3e` | Data Architecture and Modeling | Data Architecture and Modeling Standards |
| `71d9c1b6-07f0-4e71-8445-aeb5df154029` | Data Catalog and Metadata Management | Data Catalog and Metadata Management Standards |
| `3ad7bd59-24b8-4728-a342-b4ad8568fab6` | Data Culture and Literacy | Data Culture and Literacy Standards |
| `3c6f0802-4b7a-42bf-93ec-bfd1e47d300a` | Data Management Strategy and Governance | Data Management Strategy and Governance Standard |
| `2a91017e-bfe1-41a1-b109-00692f10975c` | Data Monetization | Data Monetization Standards |
| `894b9a36-dae0-4999-9dd5-1fbebcd877f5` | Data Quality Management | Data Quality Management Standards |
| `14284f7d-3a3f-4f30-8ff2-9dc27527d583` | Data Security, Privacy and Other Regulations | Data Security, Privacy and Other Regulations Standards |
| `04f1d36c-b6f5-46ca-b16b-c08fae48ffd6` | Data Sharing, Integration & Interoperability | Data Sharing, Integration & Interoperability |
| `dec57f50-e79d-484b-b905-09f6990924cc` | Data Storage and Operations | Data Storage and Operations Standards |
| `de48929c-08b5-4574-b402-721ac5a95435` | Document and Content Management | Document and Content Management Standards |
| `5516735e-814c-4a1a-8985-56adcb422927` | Master and Reference Data Management | Master and Reference Data Management Standards |
| `406d49e1-1444-488c-9843-d6c5493d5b51` | Statistics & Analytics | Statistics & Analytics Standards |

---

## Dimension Serial IDs (prefix pattern)

Each domain's standard has 3 dimensions: Plan / Implement / Operate.

| Serial Prefix | Domain Abbreviation |
|---|---|
| `DAM` | Data Architecture and Modeling |
| `DCMM` | Data Catalog and Metadata Management |
| `DCL` | Data Culture and Literacy |
| `DMSG` | Data Management Strategy and Governance |
| `DM` | Data Monetization |
| `DQM` | Data Quality Management |
| `DSP` | Data Security, Privacy and Other Regulations |
| `DSI` | Data Sharing, Integration & Interoperability |
| `DSO` | Data Storage and Operations |
| `DCM` | Document and Content Management |
| `MRDM` | Master and Reference Data Management |
| `SA` | Statistics & Analytics |

---

## Questions Table — `dmn_questions`

| Column | Type | Notes |
|---|---|---|
| `dmn_question_id` | uuid | PK |
| `dmn_domain_id` | uuid | FK → dmn_domains |
| `dmn_standard_id` | uuid | FK → dmn_standards |
| `dmn_std_dimension_id` | uuid | FK → dmn_std_dimensions |
| `dmn_std_control_id` | uuid | FK → dmn_std_controls |
| `dmn_std_spec_id` | uuid | FK → dmn_std_specifications |
| `dmn_question_text` | text | The actual question |
| `dmn_question_year` | int | 2026 (154 q's), 2027 (1 q) |
| `dmn_question_source_of_answer` | text | Where answer is expected from |
| `dmn_is_document_upload_enabled` | bool | Whether entity must upload a doc |
| `dmn_is_cloud_sync_enabled` | bool | Auto-sync via API |
| `dmn_cloud_sync_api_curl` | text | API curl template for cloud sync |
| `is_deleted` | bool | Soft delete |

**Total active questions: 159**

---

## Assessment Answer Table — `asmnt_answers`

| Column | Type | Notes |
|---|---|---|
| `asmnt_answer_id` | uuid | PK |
| `asmnt_assessment_id` | uuid | FK → asmnt_assessments |
| `asmnt_question_map_id` | uuid | FK → asmnt_question_map |
| `asmnt_entity_map_id` | uuid | FK → asmnt_entity_map |
| `asmnt_entity_domain_owner_map_id` | uuid | FK → asmnt_entity_domain_and_owner_map |
| `asmnt_answer_text` | text | Free-text answer from entity |
| `asmnt_is_document_uploaded` | bool | Whether doc was attached |
| `asmnt_document_path` | text | Blob path: `compliance_assessment/{assessmentId}/{entityId}/{domainId}/{questionId}/{file}` |
| `asmnt_reference_document_path` | text | NPC reference doc path |
| `asmnt_score` | numeric | Human-reviewed score (0-100) |
| `asmnt_score_ai_gen` | numeric | AI-generated score |
| `asmnt_informatica_api_results` | jsonb | Cloud sync API results |
| `asmnt_plan` | text | Entity improvement plan |
| `asmnt_entity_is_reviewed` | bool | Entity self-review flag |
| `asmnt_entity_feedback_json` | jsonb | Entity feedback |
| `asmnt_npc_is_reviewed` | bool | NPC reviewer flag |
| `asmnt_npc_feedback_json` | jsonb | NPC reviewer feedback |

---

## Assessments — `asmnt_assessments`

| Column | Type | Notes |
|---|---|---|
| `asmnt_assessment_id` | uuid | PK |
| `asmnt_assessment_name` | varchar | Human name (e.g. `Compliance_2026`) |
| `asmnt_year` | int | All current are 2026 |
| `asmnt_status` | varchar | `In Progress`, `IN_PROGRESS`, `COMPLETED`, `PENDING` |

**66 total assessments in DB**

---

## Entities — `ent_entity`

| UUID | Name |
|---|---|
| `6b0d193e-e51b-4bd4-8801-c6ed296529fe` | Ashghal |
| `3ca13379-1e1b-47c2-8870-e98e48ef6854` | Karahma |
| `b2b249a4-38c7-46af-93ef-f471592aa585` | milk ministry testing two |
| `00c908d4-f790-4780-a559-e89999ff242b` | Ministry of finannce |
| `ea059d07-28be-43af-acc5-d5655419672e` | Ministry of Labour |
| `bf845137-7f14-4f15-a898-ee7a05f049d0` | NPC |
| `bb328fee-7c19-43b1-b02b-1645cfc8d041` | test2345466 |

---

## Blob Storage Path Convention

Documents uploaded by entities are stored in Azure Blob container `compliance` with this path structure:

```
compliance_assessment/{assessmentId}/{entityId}/{domainId}/{questionId}/{filename}
```

Example from live data:
```
compliance_assessment/74670759-6dd7-46ca-84f8-30f874fbb1b3
                     /bf845137-7f14-4f15-a898-ee7a05f049d0   <- NPC entity
                     /9dbe7809-ce9c-471f-84c1-61e02d39b7c7   <- Data Mgmt Strategy domain
                     /dd18a3a7-8187-454a-94b6-1c54327d01be   <- question map id
                     /130634524.pdf
```

---

## Key JOIN to resolve question context

To get the full human-readable context for a question:

```sql
SELECT
    q.dmn_question_id,
    q.dmn_question_text,
    q.dmn_question_year,
    d.dmn_domain_name,
    s.dmn_standard_name,
    dim.dmn_std_dim_serial_id,
    dim.dmn_std_dimension_name,
    c.dmn_std_control_serial_id,
    c.dmn_std_control_name,
    sp.dmn_std_spec_serial_id,
    sp.dmn_std_spec_name,
    sp.dmn_std_spec_tags,
    q.dmn_question_source_of_answer,
    q.dmn_is_document_upload_enabled
FROM dmn_questions q
JOIN  dmn_domains            d   ON q.dmn_domain_id         = d.dmn_domain_id
JOIN  dmn_standards          s   ON q.dmn_standard_id        = s.dmn_standard_id
LEFT JOIN dmn_std_specifications sp  ON q.dmn_std_spec_id    = sp.dmn_std_spec_id
LEFT JOIN dmn_std_controls       c   ON sp.dmn_std_control_id = c.dmn_std_control_id
LEFT JOIN dmn_std_dimensions     dim ON c.dmn_std_dimension_id= dim.dmn_std_dimension_id
WHERE q.is_deleted = false
  AND q.dmn_question_year = 2026
ORDER BY d.dmn_domain_name,
         dim.dmn_std_dim_serial_id,
         c.dmn_std_control_serial_id,
         sp.dmn_std_spec_serial_id;
```

---

## To fetch answers for a specific assessment + entity

```sql
SELECT
    ans.asmnt_answer_id,
    ans.asmnt_answer_text,
    ans.asmnt_document_path,
    ans.asmnt_score,
    ans.asmnt_score_ai_gen,
    d.dmn_domain_name,
    sp.dmn_std_spec_serial_id,
    q.dmn_question_text
FROM asmnt_answers ans
JOIN asmnt_question_map qm ON ans.asmnt_question_map_id  = qm.asmnt_question_map_id
JOIN dmn_questions      q  ON qm.dmn_question_id         = q.dmn_question_id
JOIN dmn_domains        d  ON q.dmn_domain_id            = d.dmn_domain_id
LEFT JOIN dmn_std_specifications sp ON q.dmn_std_spec_id = sp.dmn_std_spec_id
JOIN asmnt_entity_map   em ON ans.asmnt_entity_map_id    = em.asmnt_entity_map_id
WHERE em.asmnt_assessment_id = '<assessment_uuid>'
  AND em.entity_id           = '<entity_uuid>'
  AND ans.is_deleted         = false;
```

---

## Counts snapshot (Feb 20, 2026)

| Table | Rows |
|---|---|
| `dmn_questions` | 159 |
| `dmn_standards` | 12 |
| `dmn_std_dimensions` | 36 |
| `dmn_std_controls` | 61 |
| `dmn_std_specifications` | 162 |
| `asmnt_assessments` | 66 |
| `asmnt_question_map` | 25,450 |
| `asmnt_answers` | 7,194 |
| `ent_entity` | 7 |
