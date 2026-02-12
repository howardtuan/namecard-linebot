# namecard-linebot
namecard-linebot

## Run With Docker

1. Prepare env file:

   Copy `bot/.env.example` to `bot/.env` and fill LINE credentials.

2. Build and start services:

   ```bash
   docker compose up --build
   ```

3. Open app:

   - `http://localhost:8000/admin/`
   - webhook endpoint: `http://localhost:8000/webhook/`

4. Stop services:

   ```bash
   docker compose down
   ```

5. Remove db volume (optional):

   ```bash
   docker compose down -v
   ```
