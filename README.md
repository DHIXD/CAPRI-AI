# Capri AI

### Setup Instructions

1. Open a command terminal in this folder.
2. Create and activate a virtual environment:
   ```cmd
   python -m venv venv
   venv\Scripts\activate
 

1.
Install the required packages:
pip install -r requirements.txt

2.
(Optional, if using the local clone voice):
set COQUI_TOS_AGREED=1

3.
Run the app:
streamlit run capri_app.py

4.
Paste your Gemini API key into the sidebar box when the browser opens.
Here is what your friend needs to do:

Open Google AI Studio in a web browser.

Generate a free Gemini API key.

Copy the key to the clipboard.

Launch Capri in their browser.

Paste the key directly into the Gemini API Key box in the sidebar.





WARNING REMINDER!!!: 

"venv\Scripts\activate" AND "set COQUI_TOS_AGREED=1" are only needed if someone is running the heavy local voice cloning model (XTTS). If you uses the default Edge-TTS preset voices (which run instantly and need no setup), they can skip those commands entirely.

"py -m streamlit run capri_app.py" can just be simplified to "streamlit run capri_app.py."