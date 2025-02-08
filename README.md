# 📡 IPTV Merger - Fusion de Playlists IPTV

## 📌 Description
IPTV Merger est un service qui permet de récupérer plusieurs playlists IPTV (M3U), de les fusionner et d'ajouter des flux personnalisés. Il sert ensuite la playlist fusionnée via une API Flask, ce qui permet une mise à jour automatique et un accès facile aux chaînes TV.

Le projet est conçu pour être déployé via Docker et inclut une gestion avancée des logs, un cache optimisé et une mise à jour automatique des playlists grâce à un planificateur de tâches.

---

## 🚀 Fonctionnalités
✅ Télécharge automatiquement plusieurs playlists IPTV.
✅ Fusionne les flux IPTV en une seule playlist M3U.
✅ Permet l'ajout de flux personnalisés (ex: caméras locales).
✅ Met en cache les playlists pour optimiser la performance.
✅ Vérifie automatiquement les mises à jour des playlists externes.
✅ Serve une playlist IPTV à travers une API Flask.
✅ Rotation des logs pour éviter un remplissage disque.

---

## 🔄 Gestion des mises à jour des playlists
Le premier fichier M3U défini dans la variable `PLAYLIST_URL` doit être la playlist principale de votre fournisseur IPTV. Cette playlist est mise à jour uniquement toutes les 24 heures afin d'éviter des requêtes excessives. 

Les autres fichiers M3U listés après le premier sont mis à jour à chaque exécution du service ou selon la valeur de `CACHE_DURATION_MINUTES`. Ces fichiers peuvent être des flux supplémentaires, des fichiers M3U locaux ou des playlists personnalisées.

De plus, `CUSTOM_STREAMS` est utilisé pour ajouter des flux IPTV spécifiques sous format M3U8. Ceux-ci peuvent être des flux en direct issus de caméras locales, de serveurs privés ou d'autres sources externes.

---

## 🛠️ Déploiement avec Docker

### **1️⃣ Installation de Docker (si non installé)**

**Linux:**
```sh
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

**Windows / Mac:**
Téléchargez Docker Desktop : [https://www.docker.com/get-started](https://www.docker.com/get-started)

### **2️⃣ Cloner le projet**
```sh
git clone https://github.com/votre-repo/iptv-merger.git
cd iptv-merger
```

### **3️⃣ Configuration du fichier `.env`**
Créez un fichier `.env` à la racine du projet et ajoutez vos paramètres :

```env
TZ=Europe/Paris
PLAYLIST_URL=http://example.com/playlist1.m3u, http://example.com/playlist2.m3u
LOCAL_IP=http://192.168.10.183
CUSTOM_STREAMS=http://192.168.10.183:8011/stream1.m3u8, http://192.168.10.183:8011/stream2.m3u8
CACHE_DURATION_MINUTES=10
MAX_TIMEOUT=300
LOG_PATH=/app/logs/iptv-merger.log
CHANNEL_GROUP_NAME=MEDO_GROUP
PORT=5200
```

### **4️⃣ Lancer le conteneur Docker**
```sh
docker-compose --env-file .env up -d
```

Le service IPTV Merger est maintenant disponible sur `http://localhost:5200/playlist.m3u`

---

## 🔧 Gestion et maintenance

### **Vérifier les logs**
```sh
docker logs -f iptv-merger
```

### **Arrêter le service**
```sh
docker-compose down
```

### **Mettre à jour et redémarrer**
```sh
git pull
docker-compose --env-file .env up -d --build
```

---

## 📡 Accès à la playlist IPTV fusionnée

| Ressource | URL |
|-----------|-----|
| Playlist fusionnée | `http://localhost:5200/playlist.m3u` |
| Cache des fichiers | `http://localhost:5200/cache/<nom_du_fichier>` |

Remplacez `localhost` par l'adresse IP du serveur si vous accédez depuis un autre appareil.

---

## ⚠️ Notes et recommandations
- Certaines playlists IPTV nécessitent une authentification. Vérifiez si votre fournisseur demande un `username` et `password`.
- Un timeout élevé (MAX_TIMEOUT) est utile pour les grandes playlists IPTV.
- Pensez à surveiller l'utilisation du stockage, car certaines playlists sont volumineuses.

---

## 📜 Licence
Ce projet est sous licence MIT. Vous êtes libre de l'utiliser, le modifier et le distribuer.

---

## 📞 Support & Contributions
- Ouvrez une issue sur GitHub si vous avez un problème.
- Les contributions sont les bienvenues ! Forkez le projet et soumettez une pull request.

💡 **Améliorations futures** : Support HLS, meilleur cache, interface web de gestion.

---

🚀 **Profitez de votre IPTV sans tracas !**

