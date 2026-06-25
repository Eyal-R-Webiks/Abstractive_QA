- human-signal-dashboard: do not classify choice "3" + text as skip; this collides with valid level-3 labels and causes false "0 annotators" coverage.
- For task completion in this project, treat any non-excluded submitted annotation as done; relying on is_labeled alone undercounts completed tasks.

- answer-eval dashboard on this repo runs on Python 3.9: avoid label-studio-sdk 2.x; prefer refresh-token exchange via /api/token/refresh and direct REST endpoints for project/tasks/users.
