# Project 2 — Knowledge Hub (Full-Stack RAG Platform)

> מפרט עבודה ל-Claude Code. פתח ב-VS Code לצד הריפו, או שמור כ-`CLAUDE.md` בתיקיית הפרויקט החדש.
> זו הרחבה של פרויקט 1 (engineering-rag) לאפליקציית full-stack רב-משתמשים.

---

## 1. מה אנחנו בונים ולמה

פלטפורמה רב-משתמשים שבה כל משתמש נרשם, מתחבר, מעלה מסמכים משלו, ושואל עליהם שאלות — עם היסטוריית שאלות נשמרת. זו גרסת ה"מוצר" של ה-RAG מפרויקט 1: אותה ליבה חכמה, אבל עכשיו עם authentication, persistence, ובידוד נתונים בין משתמשים.

**הנרטיב לראיון:** "פרויקט 1 היה proof of concept של RAG. פרויקט 2 הפך אותו למוצר full-stack רב-משתמשים עם auth, מסד נתונים, ובידוד קורפוס per-user."

**מה זה מוכיח (מיפוי לתיאור התפקיד):**

| דרישה בתפקיד | איפה זה בא לידי ביטוי |
|---|---|
| Full-stack engineering | React frontend + FastAPI backend |
| Databases, data handling | PostgreSQL: users, documents, queries |
| Authentication | JWT-based auth, password hashing |
| API development | RESTful endpoints, protected routes |
| Deployment pipelines | docker-compose מלא (Postgres + Qdrant + API) |
| System design | בידוד נתונים per-user, ארכיטקטורת שכבות |
| LLM integration, RAG | הליבה מפרויקט 1, מורחבת |

---

## 2. ה-Stack המלא (וההצדקה לראיון)

- **Frontend:** React (עם Vite) — סטנדרט תעשייתי; מתאים למצב מורכב (auth state, רשימות, היסטוריה)
- **Backend:** FastAPI — המשך מפרויקט 1, async, OpenAPI אוטומטי
- **Database:** PostgreSQL ב-Docker — production-grade; טבלאות יחסיות ל-users/documents/queries
- **ORM:** SQLAlchemy + Alembic (migrations) — סטנדרט פייתון, מראה ניהול schema מסודר
- **Auth:** JWT (python-jose) + password hashing (passlib/bcrypt) — אבטחה אמיתית, לא דמו
- **Vector DB:** Qdrant ב-Docker — מפרויקט 1, אבל עם בידוד per-user (collection או filter לפי user_id)
- **LLM:** Claude API — מפרויקט 1
- **Embeddings:** sentence-transformers מקומי — מפרויקט 1

---

## 3. מודל הנתונים (PostgreSQL)

```
users
  id (PK, uuid)
  email (unique)
  hashed_password
  created_at

documents
  id (PK, uuid)
  user_id (FK -> users.id)
  filename
  status (processing / indexed / failed)
  chunk_count
  uploaded_at

queries
  id (PK, uuid)
  user_id (FK -> users.id)
  question
  answer
  sources (JSON)
  response_time_ms
  created_at
```

**עקרון הליבה — בידוד נתונים:** כל document וכל query שייכים ל-user_id. משתמש A לעולם לא רואה את המסמכים או השאלות של משתמש B. ב-Qdrant, כל chunk מתויג ב-user_id, וה-retrieval מסנן לפי המשתמש המחובר. *זה נקודת אבטחה קריטית להדגיש בראיון.*

---

## 4. ארכיטקטורה

```
[React Frontend]  (Vite, port 5173)
       │  fetch + JWT in Authorization header
       ▼
[FastAPI Backend]  (port 8000)
       │
       ├── /auth/register, /auth/login  ──► JWT
       ├── /documents (upload, list, delete)  ──► PostgreSQL + ingestion pipeline
       └── /query  ──► retrieval (Qdrant, filtered by user_id) ──► Claude ──► save to PostgreSQL
       │
       ├──► [PostgreSQL]  (users, documents, queries)
       └──► [Qdrant]  (vectors, tagged by user_id)
```

---

## 5. מבנה הריפו

```
knowledge-hub/
├── README.md
├── docker-compose.yml          ← Postgres + Qdrant
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic/                ← migrations
│   ├── app/
│   │   ├── main.py             ← FastAPI app + route registration
│   │   ├── config.py           ← settings מ-env
│   │   ├── database.py         ← SQLAlchemy engine/session
│   │   ├── models.py           ← User, Document, Query (ORM)
│   │   ├── schemas.py          ← Pydantic request/response
│   │   ├── auth/
│   │   │   ├── routes.py        ← register, login
│   │   │   ├── security.py      ← hashing, JWT create/verify
│   │   │   └── deps.py          ← get_current_user dependency
│   │   ├── documents/routes.py  ← upload, list, delete
│   │   ├── query/routes.py      ← ask question
│   │   └── rag/                 ← מועתק/מותאם מפרויקט 1
│   │       ├── chunking.py
│   │       ├── embeddings.py
│   │       ├── vectorstore.py   ← עם בידוד user_id
│   │       ├── retrieval.py
│   │       ├── prompts.py
│   │       └── generate.py
│   └── tests/
└── frontend/                    ← React + Vite
    ├── package.json
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api/client.js        ← fetch wrapper עם JWT
        ├── context/AuthContext.jsx
        ├── pages/
        │   ├── Login.jsx
        │   ├── Register.jsx
        │   ├── Dashboard.jsx    ← רשימת מסמכים + העלאה
        │   └── Ask.jsx          ← שאילתה + היסטוריה
        └── components/          ← AnswerCard, SourceCard, etc.
```

---

## 6. סדר עבודה אג'נטי (משימות ל-Claude Code)

כמו בפרויקט 1: כל משימה היא יחידה שסוכן מבצע מקצה לקצה, ואתה בודק בנקודת הביקורת. בנינו ככה בפרויקט 1 וזה עבד — אותה שיטה.

### משימה 0 — Scaffolding + Infra
> צור מבנה ריפו, docker-compose עם Postgres + Qdrant, requirements, .env.example. שלד בלבד.

**ביקורת:** `docker compose up -d` מרים את Postgres ו-Qdrant. בדוק חיבור לשניהם.

### משימה 1 — Database + Models + Migrations
> SQLAlchemy models (User, Document, Query), חיבור ל-Postgres, Alembic migration ראשונה.

**ביקורת:** הרץ migration, התחבר ל-Postgres (psql או DBeaver) וודא שהטבלאות נוצרו עם ה-schema הנכון.

### משימה 2 — Authentication
> register + login endpoints, password hashing (bcrypt), JWT creation/verification, get_current_user dependency.

**ביקורת — קריטי:** נסה להירשם, להתחבר, ולקבל token. נסה לגשת ל-endpoint מוגן בלי token (אמור להחזיר 401) ועם token (אמור לעבוד). *זו נקודת אבטחה — ודא שסיסמאות מאוחסנות hashed ולא plaintext.*

### משימה 3 — RAG core (העברה מפרויקט 1)
> העתק את ה-rag/ מפרויקט 1, התאם את vectorstore.py לבידוד per-user (כל chunk מתויג user_id, retrieval מסנן).

**ביקורת:** ודא שה-retrieval מחזיר רק chunks של המשתמש הנכון.

### משימה 4 — Documents (upload + ingestion)
> endpoint להעלאת PDF, שמירת metadata ב-Postgres, הרצת ingestion pipeline, אחסון vectors ב-Qdrant עם user_id. list + delete.

**ביקורת:** העלה מסמך כמשתמש A, ודא שהוא מופיע ברשימה שלו וב-Qdrant עם התיוג הנכון. התחבר כמשתמש B — אמור לא לראות אותו.

### משימה 5 — Query (השאלה, מבודדת per-user)
> endpoint /query: retrieval מסונן ל-user, generation עם Claude, שמירת השאלה+תשובה ב-Postgres.

**ביקורת:** שאל שאלה, קבל תשובה מצוטטת. בדוק שהשאלה נשמרה ב-Postgres עם ה-user_id הנכון.

### משימה 6 — React Frontend
> Vite + React. דפי Login/Register, Dashboard (רשימת מסמכים + העלאה), Ask (שאילתה + היסטוריה). AuthContext לניהול ה-token. fetch wrapper שמצרף JWT.

**ביקורת:** flow מלא בדפדפן — הרשמה → התחברות → העלאת מסמך → שאלה → תשובה. ורענון דף (הטוקן נשמר, נשארת מחובר).

### משימה 7 — Eval + README + Polish
> בדיקות בסיסיות (auth, isolation), README מקצועי עם screenshots ודיאגרמה.

---

## 7. החלטות הנדסיות להגן עליהן בראיון

1. **למה JWT ולא session?** — stateless, מתאים ל-API + SPA, scalable.
2. **איך מבטיחים בידוד נתונים?** — every query filtered by user_id, ב-DB וב-Qdrant. בדקתי שמשתמש לא רואה נתוני אחר.
3. **למה Postgres ולא SQLite?** — production-grade, יחסי, מתאים ל-multi-user.
4. **איך מאחסנים סיסמאות?** — bcrypt hashing, לעולם לא plaintext.
5. **למה React ולא vanilla JS (כמו פרויקט 1)?** — מצב מורכב (auth, רשימות, היסטוריה) מצדיק framework.
6. **מגבלות?** — אין rate limiting, אין refresh tokens, ingestion סינכרוני (בפרודקשן היה background job).

---

## 8. הערכת זמן

זה גדול יותר מפרויקט 1. עם Claude Code, בקצב של ~10-12 שעות שבועיות:
- משימות 0-2 (infra + DB + auth): שבוע ראשון
- משימות 3-5 (RAG + documents + query): שבוע שני
- משימה 6 (React): שבוע שלישי (הכי כבד — frontend לוקח זמן)
- משימה 7 (polish): סוף שבוע שלישי

**סה"כ: ~3-4 שבועות לפרויקט מלא ומלוטש.** אבל כל משימה שמסתיימת היא ניצחון בפני עצמו.

---

## 9. עיקרון מנחה

אותו עיקרון מפרויקט 1: **אתה מנהל הפרויקט והבודק, Claude Code כותב.** בכל נקודת ביקורת — אל תסמוך על דיווח "הצלחה", בדוק בעצמך (בדיוק כמו שתפסת את ה-Qdrant המקומי בפרויקט 1). זה הסקיל שהתפקיד הכי מבקש.
