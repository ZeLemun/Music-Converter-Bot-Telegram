import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
from yt_dlp import YoutubeDL

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Spotify credentials
SPOTIPY_CLIENT_ID = 'YOUR-SPOTIPY-CLIENT-ID'
SPOTIPY_CLIENT_SECRET = 'YOUR-SPOTIPY-CLIENT-SECRET'

# Set up Spotify API client
spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# Telegram bot token
TELEGRAM_TOKEN = 'YOUR-TELEGRAM-TOKEN'

# YouTube Download Configuration
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'quiet': True
}


async def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""
    await update.message.reply_text('Ciao! Mandami un messaggio di una canzone che vorresti che io installi!')


def get_youtube_link(song_name):
    """Search for the song on YouTube and return the best match."""
    search_query = f"{song_name} official audio"
    with YoutubeDL({'quiet': True}) as ydl:
        try:
            results = ydl.extract_info(f"ytsearch:{search_query}", download=False)['entries']
            return results[0]['webpage_url']
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return None


def download_youtube_audio(youtube_url, output_path='downloads/'):
    """Download audio from YouTube and return the path to the MP3 file."""
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp3')
            return filename
    except Exception as e:
        logger.error(f"Error downloading YouTube audio: {e}")
        return None


async def spotify_to_mp3(update: Update, context: CallbackContext):
    """Handle Spotify link or search query and download MP3."""
    user_input = update.message.text.strip()
    
    try:
        if 'open.spotify.com' in user_input:
            # If input is a Spotify URL
            await handle_spotify_link(update, context, user_input)
        else:
            # If input is a search query
            await handle_search_query(update, context, user_input)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("There was an error processing your request.")


async def handle_spotify_link(update: Update, context: CallbackContext, url: str):
    """Process the Spotify link and convert it to MP3."""
    try:
        track_info = spotify.track(url)
        track_name = track_info['name']
        artist_name = track_info['artists'][0]['name']
        song_name = f"{track_name} - {artist_name}"
        
        await update.message.reply_text(f"Found {song_name} on Spotify. Searching for YouTube link...")

        # Search for the song on YouTube
        youtube_url = get_youtube_link(song_name)
        if not youtube_url:
            await update.message.reply_text("Sorry, couldn't find the track on YouTube.")
            return

        await update.message.reply_text(f"Found {song_name} on YouTube. Downloading audio...")

        # Download and convert to mp3
        await download_and_send_mp3(update, context, youtube_url)
    
    except Exception as e:
        logger.error(f"Error handling Spotify link: {e}")
        await update.message.reply_text("There was an error processing the Spotify link.")


async def handle_search_query(update: Update, context: CallbackContext, query: str):
    """Process a text search query and convert it to MP3."""
    await update.message.reply_text(f"Searching for {query} on YouTube...")
    
    youtube_url = get_youtube_link(query)
    if not youtube_url:
        await update.message.reply_text("Sorry, couldn't find the track on YouTube.")
        return

    await update.message.reply_text(f"Found {query} on YouTube. Downloading audio...")
    await download_and_send_mp3(update, context, youtube_url)


async def download_and_send_mp3(update: Update, context: CallbackContext, youtube_url: str):
    """Download the audio from YouTube and send it to the user as an MP3 file."""
    mp3_filename = download_youtube_audio(youtube_url)
    
    if mp3_filename and os.path.exists(mp3_filename):
        # Check file size to avoid Telegram file size limit issues (50MB)
        if os.path.getsize(mp3_filename) < 50 * 1024 * 1024:  # 50MB
            # Send file to the user
            await update.message.reply_audio(audio=open(mp3_filename, 'rb'))
            os.remove(mp3_filename)  # Cleanup after sending
        else:
            await update.message.reply_text("The file is too large to send via Telegram.")
    else:
        await update.message.reply_text("Sorry, something went wrong with the download.")


async def error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning(f'Update {update} caused error {context.error}')


def main():
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))

    # Message handler for Spotify links and search queries
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, spotify_to_mp3))

    # Log all errors
    application.add_error_handler(error)

    # Start the Bot
    application.run_polling()


if __name__ == '__main__':
    main()