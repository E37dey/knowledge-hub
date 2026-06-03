# Knowledge Hub — Project Context

> מסמך הקשר קבוע ל-Claude Code. המפרט המלא ב-`PROJECT_2_SPEC.md`.
> זו הרחבה של פרויקט 1 (`engineering-rag`) לאפליקציית full-stack רב-משתמשים.

## מה זה
פלטפורמת RAG **רב-משתמשים** עם auth: כל משתמש נרשם, מתחבר, מעלה PDFs משלו, שואל שאלות עליהם, ורואה היסטוריה. הליבה החכמה (RAG) זהה לפרויקט 1; החידוש: authentication, persistence, **בידוד נתונים מלא בין משתמשים**.

**הנרטיב לראיון:** "פרויקט 1 היה proof-of-concept של RAG. פרויקט 2 הפך אותו למוצר full-stack רב-משתמשים עם auth, מסד נתונים, ובידוד קורפוס per-user."

## Stack
- **Frontend:** React + Vite — state מורכב (auth, רשימות, היסטוריה) מצדיק framework
- **Backend:** FastAPI — המשך מפרויקט 1, async, OpenAPI אוטומטי
- **Database:** PostgreSQL ב-Docker — יחסי, production-grade, מתאים ל-multi-user
- **ORM:** SQLAlchemy + Alembic — ניהול schema מסודר עם migrations
- **Auth:** JWT (`python-jose`) + bcrypt password hashing (`passlib`) — stateless, מתאים ל-SPA
- **Vector DB:** Qdrant ב-Docker — מפרויקט 1, **עם תיוג user_id בכל chunk**
- **LLM:** Claude Sonnet 4.6 — מפרויקט 1
- **Embeddings:** Voyage AI (`voyage-4-large`, 1024-dim) מנוהל — הוחלף מ-sentence-transformers/torch המקומי לקראת פריסה (פחות זיכרון, build מהיר, איכות retrieval גבוהה). דורש `VOYAGE_API_KEY`.

## מודל הנתונים
- **users**: id (uuid), email (unique), hashed_password, created_at
- **documents**: id, user_id (FK), filename, status, chunk_count, uploaded_at
- **queries**: id, user_id (FK), question, answer, sources (JSON), response_time_ms, created_at

**עקרון הליבה — בידוד נתונים:** כל document וכל query שייכים ל-user_id. ב-Qdrant כל chunk מתויג ב-user_id, ו-retrieval מסנן לפי המשתמש המחובר. **זו נקודת אבטחה קריטית** — משתמש A לעולם לא רואה את הנתונים של משתמש B, ב-DB וב-vector store.

## ארכיטקטורה
```
[React + Vite (5173)]
       │  fetch + JWT in Authorization
       ▼
[FastAPI (8000)]
       ├── /auth/register, /auth/login  → JWT
       ├── /documents (upload, list, delete) → Postgres + ingestion pipeline
       └── /query → retrieval (Qdrant filtered by user_id) → Claude → save to Postgres
              │
              ├──► [PostgreSQL] users · documents · queries
              └──► [Qdrant] vectors tagged by user_id
```

## מבנה הריפו
```
backend/
├── app/
│   ├── main.py            FastAPI app + route registration
│   ├── config.py          settings מ-env
│   ├── database.py        SQLAlchemy engine/session
│   ├── models.py          User, Document, Query (ORM)
│   ├── schemas.py         Pydantic request/response
│   ├── auth/
│   │   ├── routes.py      register, login
│   │   ├── security.py    hashing, JWT create/verify
│   │   └── deps.py        get_current_user dependency
│   ├── documents/routes.py
│   ├── query/routes.py
│   └── rag/               מועתק/מותאם מפרויקט 1 — vectorstore עם user_id
├── alembic/               migrations
└── tests/
frontend/                  React + Vite
├── src/
│   ├── api/client.js      fetch wrapper עם JWT
│   ├── context/AuthContext.jsx
│   ├── pages/             Login, Register, Dashboard, Ask
│   └── components/        AnswerCard, SourceCard, etc.
docker-compose.yml         Postgres + Qdrant
```

## סדר משימות אג'נטי
כל משימה = יחידה שלמה. אחריה **המשתמש בודק** לפני שממשיכים.

0. **Scaffolding + Infra** — מבנה + docker-compose (Postgres + Qdrant) + requirements + .env.example
1. **DB + Models + Migrations** — SQLAlchemy models, חיבור ל-Postgres, Alembic migration ראשונה
2. **Authentication** — register + login, bcrypt hashing, JWT, get_current_user dependency. **קריטי לבדוק: 401 בלי token, 200 עם token, סיסמאות hashed ב-DB**
3. **RAG core (העתקה מפרויקט 1)** — התאמת vectorstore לבידוד per-user
4. **Documents (upload + ingestion)** — endpoint להעלאת PDF, שמירה ב-Postgres, ingestion ל-Qdrant עם user_id. **קריטי לבדוק: משתמש B לא רואה מסמכי A**
5. **Query (מבודד per-user)** — /query עם retrieval מסונן ל-user, שמירת השאלה+תשובה ב-Postgres
6. **React Frontend** — Vite + React. Login/Register/Dashboard/Ask + AuthContext + fetch wrapper. **הכבד ביותר**
7. **Eval + README + Polish** — tests (auth + isolation), README עם screenshots ודיאגרמה

## עקרונות עבודה (מועברים מפרויקט 1)
- **אל תכתוב קוד פרויקט עד שהמשתמש מאשר משימה ספציפית.** המסמך הזה לא הזמנה להתחיל.
- **אחרי כל משימה — עצור.** המשתמש בודק לפני שממשיכים. נקודות הביקורת הן הסיפור של "validate AI-generated work".
- **דווח על "הצלחה" רק אחרי אימות.** הלקח הכי חשוב מפרויקט 1: "agent-reported success ≠ verified success." הראה פלט אמיתי, לא הצהרות צופות פני עתיד.
- **בידוד נתונים הוא דרישה מהותית, לא feature.** כל endpoint שמחזיר נתונים חייב לסנן ב-user_id. כל chunk ב-Qdrant חייב להיות מתויג. בדוק את זה idempotently עם 2 משתמשים בכל משימה רלוונטית.
- **אבטחה אמיתית, לא דמו.** bcrypt לסיסמאות, JWT עם expiry, לעולם לא להחזיר hashed_password ב-response.

## Local environment quirks
- **Python Scripts/ לא ב-PATH על המכונה הזו.** הריץ כלי Python CLI דרך `py -m <tool>`, לא ישירות:
  - `py -m alembic upgrade head` (לא `alembic upgrade head`)
  - `py -m uvicorn app.main:app --port 8000` (לא `uvicorn ...`)
  - `py -m pytest` (לא `pytest`)
  המסלול שבו ה-exes יושבים הוא `C:\Users\sound\AppData\Local\Programs\Python\Python314\Scripts\`.
- **`py` במקום `python`**. ב-Windows עם Python Launcher, `py` הוא הנקודה הסטנדרטית.
- **מלכודת namespace package**: ספרייה מקומית בשם זהה לחבילת pip (למשל `alembic/` כתיקיית migrations) תיראה כ-namespace package אם החבילה עצמה לא מותקנת. סימן: `import X` עובד אבל `X.__file__ is None`. הפתרון: `pip install`.

## החלטות שצריך להגן עליהן (לראיון)
1. **JWT על פני sessions** — stateless, מתאים ל-SPA + API, scalable horizontally
2. **בידוד נתונים בשתי שכבות** — Postgres FK + Qdrant payload filter. defense in depth
3. **PostgreSQL על SQLite** — production-grade, יחסי, תומך concurrent writes
4. **bcrypt על פלאט/MD5/SHA** — תכן ל-password hashing (slow by design, salted)
5. **React על vanilla JS** (שלא כמו פרויקט 1) — state מורכב (auth, רשימות, היסטוריה) מצדיק framework
6. **מגבלות מוכרות:** אין rate limiting, אין refresh tokens, ingestion סינכרוני (פרודקשן היה background job)

## שפה
המשתמש מדבר עברית. ענה בעברית בשיחה. קוד, שמות משתנים, והערות בקוד — באנגלית.
