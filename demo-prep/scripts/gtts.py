"""Google Cloud Text-to-Speech wrapper.

Looks up the service account from $GCP_SA_PATH or ~/.config/demo-prep/gcp-sa.json.
Default voice is en-GB-Chirp3-HD-Charon (British male, neutral, demo-paced).
"""
import os, json, base64, urllib.request, urllib.error
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SA = os.environ.get("GCP_SA_PATH") or os.path.expanduser(
    "~/.config/demo-prep/gcp-sa.json"
)

_creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def token():
    _creds.refresh(Request())
    return _creds.token


def synth(text, out, voice="en-GB-Chirp3-HD-Charon", rate=0.9, pitch=0.0):
    ac = {"audioEncoding": "MP3", "speakingRate": rate}
    if "Chirp3" not in voice:
        ac["pitch"] = pitch
    body = {
        "input": {"text": text},
        "voice": {"languageCode": "en-GB", "name": voice},
        "audioConfig": ac,
    }
    req = urllib.request.Request(
        "https://texttospeech.googleapis.com/v1/text:synthesize",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token()}",
            "Content-Type": "application/json",
        },
    )
    data = json.loads(urllib.request.urlopen(req, timeout=60).read())
    open(out, "wb").write(base64.b64decode(data["audioContent"]))


if __name__ == "__main__":
    out = "/tmp/gtts_test.mp3"
    try:
        synth("This is a test of the Google neural voice.", out)
        print(f"TTS OK -> {out}")
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:300])
