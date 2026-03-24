flowchart TD
    subgraph TRIGGER["Trigger"]
        API["FastAPI\napi.py"]
        SCHED["APScheduler\n8:00 AM daily"]
        CLI["CLI\npython daily_runner.py"]
    end

    subgraph PIPELINE["daily_runner.py — run_daily_pipeline()"]
        S1["Step 1: run_scrapers()\nrunner.py"]
        S2["Step 2: process_anthropic_markdown()\nservices/process_anthropic.py"]
        S3["Step 3: process_youtube_transcripts()\nservices/process_youtube.py"]
        S4["Step 4: process_digests()\nservices/process_digest.py"]
        S5["Step 5: send_digest_email()\nservices/process_email.py"]
    end

    subgraph SCRAPERS["Scrapers"]
        YT["youtube.py\nRSS + Transcript API"]
        OAI["openai.py\nRSS Feed"]
        ANT["anthropic.py\nRSS Feed + Docling"]
    end

    subgraph SOURCES["External Sources"]
        YTRSS["YouTube RSS\nyoutube.com/feeds/videos.xml"]
        OAIRSS["OpenAI RSS\nopenai.com/news/rss.xml"]
        ANTRSS["Anthropic RSS\ngithub.com/Olshansk/rss-feeds"]
        YTAPI["YouTube Transcript API"]
        ANTPAGE["Anthropic Article Pages\n(Docling → Markdown)"]
    end

    subgraph DB["PostgreSQL Database"]
        TBL1["youtube_videos\nvideo_id, title, url, transcript"]
        TBL2["openai_articles\nguid, title, url, description"]
        TBL3["anthropic_articles\nguid, title, url, markdown"]
        TBL4["digests\nid, title, summary, article_type"]
    end

    subgraph AGENTS["LLM Agents — Cerebras llama3.1-8b"]
        DA["DigestAgent\nSummarizes each article"]
        CA["CuratorAgent\nRanks by user profile"]
        EA["EmailAgent\nWrites personalized intro"]
    end

    subgraph PROFILE["User Profile"]
        UP["user_profile.py\nTony — interests, expertise,\npreferences"]
    end

    subgraph EMAIL["Email Output"]
        SEND["email.py\nSMTP send"]
        INBOX["Your Inbox\nTop 10 ranked articles"]
    end

    %% Triggers → Pipeline
    SCHED --> API
    CLI --> PIPELINE
    API --> PIPELINE

    %% Pipeline steps in order
    S1 --> S2 --> S3 --> S4 --> S5

    %% Step 1: Scrapers
    S1 --> YT & OAI & ANT
    YTRSS --> YT
    OAIRSS --> OAI
    ANTRSS --> ANT
    YTAPI --> YT

    %% Scrapers → DB
    YT -->|"bulk save\n(no transcript yet)"| TBL1
    OAI --> TBL2
    ANT -->|"no markdown yet"| TBL3

    %% Step 2: Anthropic markdown enrichment
    S2 -->|"fetch articles\nwhere markdown IS NULL"| TBL3
    ANTPAGE --> ANT
    S2 -->|"update markdown"| TBL3

    %% Step 3: YouTube transcript enrichment
    S3 -->|"fetch videos\nwhere transcript IS NULL"| TBL1
    S3 --> YTAPI
    S3 -->|"update transcript"| TBL1

    %% Step 4: Digest generation
    S4 -->|"get articles\nwithout digest"| TBL1 & TBL2 & TBL3
    S4 --> DA
    DA -->|"LLM: title + summary"| TBL4

    %% Step 5: Email
    S5 -->|"get recent digests"| TBL4
    UP --> CA & EA
    S5 --> CA
    CA -->|"ranked list"| S5
    S5 --> EA
    EA -->|"personalized intro"| SEND
    SEND --> INBOX
