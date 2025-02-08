import os
import requests
import logging
import hashlib
import threading
from flask import Flask, send_from_directory, request, Response
from functools import lru_cache
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import os
import hashlib
import logging
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime


@dataclass
class HashInfo:
    filename: str
    hash_value: str
    last_update: datetime


class PlaylistHashManager:
    def __init__(self, cache_directory: str):
        self.cache_directory = cache_directory
        self.logger = logging.getLogger(__name__)

    def _generate_hash(self, filepath: str) -> Optional[str]:
        """Génère le hash MD5 d'un fichier"""
        if not os.path.exists(filepath):
            self.logger.warning(f"🚫 Fichier introuvable: {filepath}")
            return None

        try:
            hasher = hashlib.md5()
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            self.logger.error(
                f"❌ Erreur pendant la génération du hash pour {filepath}: {str(e)}"
            )
            return None

    def get_playlist_hash_info(self, playlist_index: int) -> Optional[HashInfo]:
        """Récupère les infos de hash pour une playlist donnée"""
        cache_file = f"{self.cache_directory}/externe{playlist_index}.m3u"
        hash_file = f"{self.cache_directory}/externe{playlist_index}.hash"

        if not os.path.exists(cache_file):
            return None

        current_hash = self._generate_hash(cache_file)
        if not current_hash:
            return None

        # On récupère la date de dernière modification du fichier
        last_update = datetime.fromtimestamp(os.path.getmtime(cache_file))

        return HashInfo(
            filename=cache_file, hash_value=current_hash, last_update=last_update
        )

    def has_playlist_changed(self, playlist_index: int) -> bool:
        """Vérifie si une playlist a changé en comparant son hash"""
        hash_file = f"{self.cache_directory}/externe{playlist_index}.hash"
        current_info = self.get_playlist_hash_info(playlist_index)

        if not current_info:
            return True

        if not os.path.exists(hash_file):
            self._save_hash(playlist_index, current_info.hash_value)
            return True

        try:
            with open(hash_file, "r") as f:
                old_hash = f.read().strip()
            return current_info.hash_value != old_hash
        except Exception as e:
            self.logger.error(
                f"❌ Erreur lecture hash pour externe{playlist_index}: {str(e)}"
            )
            return True

    def _save_hash(self, playlist_index: int, hash_value: str) -> None:
        """Sauvegarde le hash d'une playlist"""
        hash_file = f"{self.cache_directory}/externe{playlist_index}.hash"
        try:
            with open(hash_file, "w") as f:
                f.write(hash_value)
            self.logger.info(f"💾 Hash sauvegardé pour externe{playlist_index}")
        except Exception as e:
            self.logger.error(
                f"❌ Erreur sauvegarde hash pour externe{playlist_index}: {str(e)}"
            )

    def update_all_hashes(self, num_playlists: int) -> Dict[int, HashInfo]:
        """Met à jour les hashes de toutes les playlists"""
        results = {}
        for idx in range(1, num_playlists + 1):
            info = self.get_playlist_hash_info(idx)
            if info:
                self._save_hash(idx, info.hash_value)
                results[idx] = info
                self.logger.info(f"✅ Hash mis à jour pour externe{idx}")
        return results


# Configuration des logs avec emojis 😎
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Variables d'environnement avec fallback par défaut
PLAYLIST_URLS = os.getenv("PLAYLIST_URL", "").split(",")
LOCAL_IP = os.getenv("LOCAL_IP", "http://192.168.10.183")
CUSTOM_STREAMS = os.getenv("CUSTOM_STREAMS", "").split(",")
CACHE_DIRECTORY = "/app/cache"
MERGED_PLAYLIST = f"{CACHE_DIRECTORY}/playlist.m3u"
EXTERNAL1_LAST_FETCH = f"{CACHE_DIRECTORY}/externe1_last_fetch.txt"
MAX_CHANNELS_FILE = f"{CACHE_DIRECTORY}/max_channels_last.txt"
CACHE_DURATION_MINUTES = int(os.getenv("CACHE_DURATION_MINUTES", "10"))
MAX_TIMEOUT = int(
    os.getenv("MAX_TIMEOUT", "300")
)  # Timeout pour les gros fichiers IPTV


# Fonction pour récupérer `MAX_CHANNELS` dynamiquement
def get_max_channels():
    return int(os.getenv("MAX_CHANNELS", "100000"))  # Nombre max de chaînes fusionnées


# Fonction pour récupérer le hash d'un fichier
def get_file_hash(filename):
    if not os.path.exists(filename):
        return None
    hasher = hashlib.md5()
    with open(filename, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


# Fonction pour formater une entrée playlist
def format_playlist_entry(name, url):
    """Format une entrée de playlist avec le groupe par défaut"""
    return f'#EXTINF:-1 group-title="{CHANNEL_GROUP_NAME}",{name}\n{url.strip()}\n'


# Vérification si externe1 a été téléchargée il y a moins de 24h
def can_fetch_externe1():
    if os.path.exists(EXTERNAL1_LAST_FETCH):
        with open(EXTERNAL1_LAST_FETCH, "r") as f:
            last_fetch_time = datetime.fromisoformat(f.read().strip())
        return datetime.now() - last_fetch_time > timedelta(hours=24)
    return True


# Mise à jour de la dernière récupération de externe1
def update_externe1_fetch_time():
    with open(EXTERNAL1_LAST_FETCH, "w") as f:
        f.write(datetime.now().isoformat())
        logger.info(f"🔄 Mise à jour de la dernière récupération de externe1.")


# Vérification si MAX_CHANNELS a changé
def has_max_channels_changed():
    max_channels = get_max_channels()
    if os.path.exists(MAX_CHANNELS_FILE):
        with open(MAX_CHANNELS_FILE, "r") as f:
            last_value = int(f.read().strip())
        if last_value != max_channels:
            logger.info(f"🔄 MAX_CHANNELS changé: {last_value} ➝ {max_channels}.")
            return True
    return False


# Mise à jour du fichier MAX_CHANNELS
def update_max_channels_file():
    with open(MAX_CHANNELS_FILE, "w") as f:
        f.write(str(get_max_channels()))


# Initialisation du scheduler
def init_scheduler():
    logger.info("🚀 Initialisation du scheduler unique")
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: threading.Thread(target=fetch_playlists).start(),
        "interval",
        minutes=CACHE_DURATION_MINUTES,
    )
    scheduler.start()


def init_app():
    init_scheduler()
    threading.Thread(target=fetch_playlists).start()


# Création d'une instance globale du gestionnaire de hash
hash_manager = PlaylistHashManager(CACHE_DIRECTORY)


def has_external_changed():
    """Vérifie si les fichiers externes ont changé via leur hash"""
    any_changed = False
    for index in range(1, len(PLAYLIST_URLS) + 1):
        cache_file = f"{CACHE_DIRECTORY}/externe{index}.m3u"
        hash_file = f"{CACHE_DIRECTORY}/externe{index}.hash"

        if not os.path.exists(cache_file):
            continue

        current_hash = get_file_hash(cache_file)

        if os.path.exists(hash_file):
            try:
                with open(hash_file, "r") as f:
                    old_hash = f.read().strip()
                if current_hash != old_hash:
                    logger.info(
                        f"🔄 Hash changé pour externe{index}: {old_hash} → {current_hash}"
                    )
                    any_changed = True
            except Exception as e:
                logger.error(f"❌ Erreur lecture hash pour externe{index}: {str(e)}")
                any_changed = True
        else:
            # Pas de hash précédent, on le crée
            logger.info(f"📝 Création du hash initial pour externe{index}")
            with open(hash_file, "w") as f:
                f.write(current_hash)
            any_changed = True

    if any_changed:
        logger.info("🔄 Changements détectés dans les fichiers externes")
    return any_changed


def update_external_hashes():
    """Met à jour les hashes des fichiers externes"""
    for index in range(1, len(PLAYLIST_URLS) + 1):
        cache_file = f"{CACHE_DIRECTORY}/externe{index}.m3u"
        hash_file = f"{CACHE_DIRECTORY}/externe{index}.hash"

        if os.path.exists(cache_file):
            current_hash = get_file_hash(cache_file)
            with open(hash_file, "w") as f:
                f.write(current_hash)


# Ajout dans les variables d'environnement
CHANNEL_GROUP_NAME = os.getenv("CHANNEL_GROUP_NAME", "MEDO_GROUP")


def process_playlist_file(
    file_path, base_content, max_channels, total_channels, is_externe1=False
):
    """Traite un fichier playlist ligne par ligne pour économiser la mémoire"""
    channel_count = 0
    current_extinf = None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                # Si c'est externe1 et qu'on a atteint la limite, on arrête
                if is_externe1 and channel_count >= max_channels:
                    break

                line = line.strip()
                if line.startswith("#EXTINF"):
                    current_extinf = line
                    # Si ce n'est pas externe1, on modifie le groupe
                    if not is_externe1:
                        if "group-title=" in current_extinf:
                            current_extinf = current_extinf.replace(
                                'group-title="'
                                + current_extinf.split('group-title="')[1].split('"')[0]
                                + '"',
                                f'group-title="{CHANNEL_GROUP_NAME}"',
                            )
                        else:
                            current_extinf = current_extinf.replace(
                                ",", f' group-title="{CHANNEL_GROUP_NAME}",'
                            )
                elif current_extinf and line and not line.startswith("#"):
                    base_content += f"{current_extinf}\n{line}\n\n"
                    channel_count += 1
                    total_channels += 1
                    current_extinf = None

                    if channel_count % 1000 == 0:
                        logger.info(f"📺 {channel_count} chaînes traitées...")

    except Exception as e:
        logger.error(f"❌ Erreur pendant le traitement de {file_path}: {str(e)}")

    return base_content, channel_count, total_channels


def fetch_playlists():
    os.makedirs(CACHE_DIRECTORY, exist_ok=True)
    max_channels = get_max_channels()

    force_fusion = (
        not os.path.exists(MERGED_PLAYLIST)
        or has_max_channels_changed()
        or has_external_changed()
    )

    # Téléchargement des playlists externes
    for index, url in enumerate(PLAYLIST_URLS, start=1):
        cache_file = f"{CACHE_DIRECTORY}/externe{index}.m3u"

        should_download = False
        if index == 1:  # Pour externe1
            should_download = can_fetch_externe1()
            if not should_download:
                logger.info(
                    "⏳ externe1 ne sera pas téléchargée (dernière mise à jour < 24h)"
                )
        else:  # Pour les autres fichiers
            should_download = True
            logger.info(f"🔄 Mise à jour systématique de externe{index}")

        if should_download:
            try:
                logger.info(f"📥 Téléchargement de la playlist depuis {url}")
                response = requests.get(url.strip(), timeout=MAX_TIMEOUT)
                response.raise_for_status()

                with open(cache_file, "w", encoding="utf-8", newline="\n") as f:
                    f.write(response.text)
                logger.info(f"✅ Playlist {url} sauvegardée sous {cache_file}")

                if index == 1:
                    update_externe1_fetch_time()

                force_fusion = True

            except Exception as e:
                logger.error(f"❌ Erreur lors du téléchargement de {url}: {str(e)}")

    # On procède à la fusion
    if force_fusion or True:  # On force toujours pour les CUSTOM_STREAMS
        update_max_channels_file()
        logger.info("🔄 Début de la fusion...")

        base_content = "#EXTM3U\n\n"
        total_channels = 0

        # Traitement des playlists en cache
        for index, _ in enumerate(PLAYLIST_URLS, start=1):
            cache_file = f"{CACHE_DIRECTORY}/externe{index}.m3u"
            if os.path.exists(cache_file):
                logger.info(f"📂 Lecture du cache pour externe{index}.m3u")
                file_size = os.path.getsize(cache_file)
                logger.info(f"📊 Taille du fichier: {file_size} bytes")

                # On applique max_channels uniquement pour externe1
                current_max = max_channels if index == 1 else float("inf")

                base_content, channel_count, total_channels = process_playlist_file(
                    cache_file,
                    base_content,
                    current_max,
                    total_channels,
                    is_externe1=(index == 1),
                )
                logger.info(
                    f"✅ {channel_count} chaînes ajoutées depuis externe{index}.m3u"
                )

        # Ajout des CUSTOM_STREAMS sans limite
        if CUSTOM_STREAMS:
            logger.info("➕ Ajout des streams personnalisés...")
            custom_count = 0
            for stream in CUSTOM_STREAMS:
                if stream.strip():
                    name = stream.split("/")[-1].replace(".m3u8", "").upper()
                    base_content += format_playlist_entry(name, stream)
                    custom_count += 1
                    total_channels += 1
            logger.info(f"✨ {custom_count} streams personnalisés ajoutés avec succès")

        # Écriture du fichier fusionné final
        if total_channels > 0:
            try:
                logger.info(
                    f"💾 Écriture de playlist.m3u ({total_channels} chaînes)..."
                )
                with open(MERGED_PLAYLIST, "w", encoding="utf-8") as f:
                    f.write(base_content.rstrip() + "\n")
                update_external_hashes()
                logger.info("✨ Playlist.m3u créée avec succès")
                logger.info(
                    f"📁 Taille finale: {os.path.getsize(MERGED_PLAYLIST)} bytes"
                )
            except Exception as e:
                logger.error(f"❌ Erreur écriture {MERGED_PLAYLIST}: {str(e)}")
        else:
            logger.error("❌ Aucune chaîne à fusionner !")


@app.route("/playlist.m3u")
def serve_playlist():
    """Sert le fichier playlist.m3u"""
    try:
        if os.path.exists(MERGED_PLAYLIST):
            logger.info("🎵 Envoi de playlist.m3u")
            return send_from_directory(
                CACHE_DIRECTORY,
                "playlist.m3u",
                mimetype="application/x-mpegurl",
                as_attachment=False,
            )
        else:
            logger.error("❌ playlist.m3u non trouvée!")
            return "Playlist non trouvée", 404
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'envoi de playlist.m3u: {str(e)}")
        return "Erreur serveur", 500


# Route pour les fichiers statiques du cache
@app.route("/cache/<path:filename>")
def serve_cache(filename):
    """Sert les fichiers du cache"""
    try:
        logger.info(f"📂 Accès au fichier: {filename}")
        return send_from_directory(CACHE_DIRECTORY, filename)
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'accès à {filename}: {str(e)}")
        return "Fichier non trouvé", 404


if __name__ == "__main__":
    logger.info("🌐 Lancement du serveur Flask...")
    app.run(host="0.0.0.0", port=5000)
else:
    init_app()
