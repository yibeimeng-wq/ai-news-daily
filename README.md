# AI Daily News Summary - GitHub Actions

Automated AI news aggregation system that runs daily on GitHub Actions and pushes summaries to Feishu.

## Features

- 🤖 Automatically fetches latest AI news from Brave Search API
- 📝 Generates intelligent Chinese summaries using LLM
- 📱 Pushes formatted summaries to Feishu
- ⏰ Runs daily at 9:00 AM Beijing time
- 🔒 Daily execution lock to protect API quota
- ☁️ Runs on GitHub Actions (no local computer needed)

## Setup Instructions

### 1. Fork or Create Repository

1. Create a new GitHub repository (can be private)
2. Upload these files to your repository:
   - `ai_news_daily.py`
   - `feishu_push.py`
   - `.github/workflows/daily-news.yml`

### 2. Configure GitHub Secrets

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `BRAVE_API_KEY` | Your Brave Search API key | `BSAoSBQpdOGtvYY8qJDmwqjGVL2wa29` |
| `FEISHU_WEBHOOK` | Your Feishu bot webhook URL | `https://open.feishu.cn/open-apis/bot/v2/hook/...` |
| `FEISHU_KEYWORD` | Feishu bot security keyword | `dailynews` |
| `OPENAI_API_KEY` | OpenAI API key (provided by Manus) | `sk-...` |
| `OPENAI_BASE_URL` | OpenAI API base URL (provided by Manus) | `https://api.openai.com/v1` |

### 3. Enable GitHub Actions

1. Go to your repository → Actions tab
2. Click "I understand my workflows, go ahead and enable them"
3. The workflow will run automatically at 9:00 AM Beijing time daily

### 4. Manual Trigger (Optional)

To test immediately:

1. Go to Actions tab
2. Select "AI Daily News Summary" workflow
3. Click "Run workflow" → "Run workflow"

## How It Works

### Workflow Schedule

The workflow runs at:
- **9:00 AM Beijing time (UTC+8)** = **1:00 AM UTC**
- Cron expression: `0 1 * * *`

### Execution Steps

1. **Checkout code**: Gets the latest code from repository
2. **Setup Python**: Installs Python 3.11
3. **Install dependencies**: Installs `requests` and `openai` packages
4. **Run script**: Executes `ai_news_daily.py` with environment variables
5. **Upload artifact**: Saves the generated report as artifact (kept for 7 days)

### Output

- **Feishu push**: Formatted news summary card sent to your Feishu group
- **GitHub artifact**: Markdown report file (`ai_news_summary_YYYYMMDD.md`)

## Viewing Results

### Feishu Notification

Check your Feishu group for the daily news summary card.

### GitHub Artifacts

1. Go to Actions tab
2. Click on the latest workflow run
3. Scroll down to "Artifacts" section
4. Download "news-report" to view the Markdown file

## Quota Management

### Brave Search API

- **Free tier**: 2000 requests/month
- **Daily usage**: 1 request/day = ~30 requests/month
- **Usage rate**: 1.5% (safe margin: 98.5%)

### GitHub Actions

- **Free tier**: 2000 minutes/month for private repos (unlimited for public repos)
- **Daily usage**: ~2 minutes/day = ~60 minutes/month
- **Usage rate**: 3% (plenty of room)

## Troubleshooting

### Workflow Failed

Check the workflow logs:
1. Go to Actions tab
2. Click on the failed run
3. Click on "fetch-and-push-news" job
4. Expand each step to see error messages

Common issues:
- **Invalid API key**: Check `BRAVE_API_KEY` secret
- **Feishu push failed**: Verify `FEISHU_WEBHOOK` and `FEISHU_KEYWORD`
- **OpenAI API error**: Check `OPENAI_API_KEY` and `OPENAI_BASE_URL`

### No Feishu Notification

1. Verify Feishu webhook URL is correct
2. Check keyword matches bot security settings
3. Look at workflow logs for error messages
4. Test webhook manually using `curl`

### Change Schedule Time

Edit `.github/workflows/daily-news.yml`:

```yaml
schedule:
  # Change the cron expression
  # Format: minute hour day month weekday
  # Example: '0 2 * * *' = 10:00 AM Beijing time (2:00 AM UTC)
  - cron: '0 1 * * *'
```

## Customization

### Change News Query

Edit `ai_news_daily.py`:

```python
articles = fetch_ai_news(
    query="your custom query",  # Change this
    count=20,
    freshness="pd"  # pd=past day, pw=past week
)
```

### Modify Summary Style

Edit the prompt in `categorize_and_summarize_news()` function in `ai_news_daily.py`.

### Add More Push Platforms

Create new push modules (e.g., `telegram_push.py`, `email_push.py`) and import in `ai_news_daily.py`.

## Security Notes

- ✅ All sensitive credentials are stored as GitHub Secrets (encrypted)
- ✅ Secrets are never exposed in logs or code
- ✅ Repository can be private for additional security
- ⚠️ Do not commit API keys or webhook URLs to the repository

## License

MIT License - Feel free to modify and use for your own purposes.
