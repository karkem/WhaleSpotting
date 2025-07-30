import os
import io
import time
import torch
import clip
import shutil
import telegram
from PIL import Image
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv

# === KONFIGURATION ===
load_dotenv()

import os
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FOLDER_ID = os.getenv("FOLDER_ID")
CHECK_INTERVAL = 10  # Sekunden
PROCESSED_IDS = set()
SAVE_DIR = "whales"

os.makedirs(SAVE_DIR, exist_ok=True)

# === TELEGRAM BOT ===
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# === GOOGLE DRIVE AUTH ===
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
def authenticate_google():
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("drive", "v3", credentials=creds)

# === WHALE DETEKTION ===
def detect_whale(image_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    texts = ["signs of a whale in the photo", "no whale in the photo"]
    text_tokens = clip.tokenize(texts).to(device)

    with torch.no_grad():
        image_features = model.encode_image(image)
        text_features = model.encode_text(text_tokens)
        probs = (image_features @ text_features.T).softmax(dim=-1).cpu().numpy()[0]

    return probs[0] > probs[1]  # True wenn Wal, sonst False

# === BILDER LADEN + BEARBEITEN ===
def check_for_new_images(service):
    query = f"'{FOLDER_ID}' in parents and mimeType contains 'image/'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    for file in results.get("files", []):
        file_id = file["id"]
        file_name = file["name"]

        if file_id in PROCESSED_IDS:
            continue

        print(f"📥 Neues Bild gefunden: {file_name}")
        PROCESSED_IDS.add(file_id)

        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        temp_path = f"temp_{file_name}"
        with open(temp_path, "wb") as f:
            f.write(fh.getvalue())

        if detect_whale(temp_path):
            print("✅ Wal entdeckt – sende an Telegram...")
            save_path = os.path.join(SAVE_DIR, file_name)
            shutil.move(temp_path, save_path)
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="🐋 Wal entdeckt!")
            bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=open(save_path, "rb"))
        else:
            print("❌ Kein Wal – lösche Datei.")
            os.remove(temp_path)

# === MAIN LOOP ===
def main():
    service = authenticate_google()
    print("🔁 Starte Überwachung...")
    while True:
        try:
            check_for_new_images(service)
        except Exception as e:
            print(f"⚠️ Fehler: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
