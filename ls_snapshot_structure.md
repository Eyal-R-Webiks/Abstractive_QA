# Snapshot Webiks Onset JSON Structure

This file provides a machine-readable mapping of the Label Studio export snapshot (`Snapshot_webiks_onset.json`). 

The root is a JSON array of **Task** objects `[]`.

## Task Object

The top-level object represents a single task/record in Label Studio.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Internal Label Studio task ID |
| `data` | Object | The input data payload (see **Data Payload** below) |
| `annotations` | Array | List of annotation results (see **Annotation Object** below) |
| `project` | Integer | Label Studio project ID |
| `created_at` | String | ISO timestamp of task creation |
| `updated_at` | String | ISO timestamp of last update |
| `total_annotations` | Integer | Total number of annotations for this task |
| `file_upload`, `meta`, `state` | Various | Meta information and internal sync state |

## Data Payload (`task.data`)

The actual input variables fed into the Label Studio UI interface.

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | String | Unique UUID for the record from the generation phase |
| `dataset` | String | Origin dataset (e.g., Wikipedia, Israel HaYom, Knesset) |
| `doc_id` | String | ID of the source document |
| `text` / `text_html` | String | The full article text (plain text or HTML formatting) |
| `excerpt` | String | The relevant excerpt or context |
| `question` | String | Generated question |
| `level` | String/Integer | Expected Bloom taxonomy level (0, 1, 2, or 3) |
| `reasoning` | String | Generated reasoning/rationale behind the question |

## Annotation Object (`task.annotations[0]`)

Records the annotators' actions and labels.

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Annotation ID |
| `completed_by` | Object | User details (`id`, `email`, `first_name`) |
| `lead_time` | Float | Time spent by the annotator in seconds |
| `result` | Array | The actual labels applied (see **Result Object** below) |
| `was_cancelled` | Boolean | Whether the annotator skipped/cancelled this task |

## Result Object (`task.annotations[0].result[N]`)

Individual labeling components matching the `from_name` components in Label Studio config.

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique ID for the specific result element |
| `from_name` | String | The Label Studio tag name (e.g. `level_validated`, `annotator_note`) |
| `to_name` | String | Target variable being labeled (e.g., `question`) |
| `type` | String | Input type (`choices`, `textarea`, etc.) |
| `value` | Object | The actual label. Depends on `type` (e.g. `{"choices": ["1"]}` for choices, `{"text": ["notes..."]}` for text) |
