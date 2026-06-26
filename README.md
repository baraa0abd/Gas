# SeparatorSizer Pro

Petroleum separator sizing tool (2/3-phase, vertical/horizontal) using UTM Ch.4 correlations.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub: [baraa0abd/Gas](https://github.com/baraa0abd/Gas)
2. Sign in at [share.streamlit.io](https://share.streamlit.io)
3. **Create app** → select **baraa0abd/Gas**, branch **main**, main file **`app.py`**
4. Deploy — your app will be live at a `*.streamlit.app` URL

See [Streamlit deployment docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started).

## Engineering

Sizing logic lives in `backend/separator_engine.py`. The Streamlit UI in `app.py` calls the same engine used by the optional Flask/React stack in `frontend/`.
