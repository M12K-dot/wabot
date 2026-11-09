# Portage Levanter → NOVA — suivi

Statuts : ✅ déjà fait · ➕ ajouté (ce chantier) · 🔧 besoin-outil local · 🌉 besoin-endpoint bridge · 🚫 non-pertinent

Outils détectés : ffmpeg ✅, ffprobe ✅, ImageMagick (`convert`) ✅, yt-dlp ❌, magick ❌, potrace ❌, TTS Windows SAPI ✅ (PowerShell).

Endpoints bridge dispo : `/api/send` (+mentions, media_path), `/api/download`, `/api/group` (jid,user,phone,admin), `/api/group-action` (kick/add/promote/demote), `/api/group-setname`, `/api/group-settopic`, `/api/group-announce`, `/api/react`, `/api/poll`, journal `events.jsonl` (join/leave/revoke/edit).

| Commande | Statut | Note |
|---|---|---|
| add | ✅ | group-action |
| afk | ✅ | |
| alive | ✅ | |
| allvar | ➕ | alias de vars |
| amute | ➕ | alias de mute |
| antiedit | ✅ | |
| antifake | ➕ | config groupe (kick numéro hors indicatifs autorisés, sur join) |
| antigm | 🌉 | besoin métadonnée mention + delete |
| antigstatus | 🌉 | besoin endpoint statut |
| antilink | ➕ | config groupe, action warn/kick (delete = 🌉) |
| antispam | ➕ | config groupe, flood → warn/kick |
| antiword | ➕ | config groupe, mots bannis → warn/kick (delete = 🌉) |
| apk | 🔧 | besoin API/yt-dlp |
| aunmute | ➕ | alias de unmute |
| avm | ➕ | alias de tomp3/toaudio (voice note) |
| backup | 🚫 | hébergement |
| bass | ➕ | ffmpeg audio |
| bing | ➕ | alias IA (Ollama) |
| black | ➕ | ImageMagick (N&B) |
| block | 🌉 | besoin endpoint block |
| bloody | 🚫 | overlay/asset art |
| bokeh | ➕ | ImageMagick (flou) |
| budget | ➕ | finance locale (json) |
| call | 🌉 | besoin endpoint appel |
| cartoon | ➕ | ImageMagick |
| cinfo | ➕ | infos chat |
| circle | ➕ | ImageMagick (masque rond) |
| clear | 🌉 | besoin endpoint delete |
| color | ➕ | ImageMagick (couleur moyenne) |
| common | 🌉 | besoin multi-group |
| compress | ➕ | ffmpeg |
| creact | ➕ | config (auto-réaction aux commandes) |
| crop | ➕ | ffmpeg/ImageMagick |
| cut | ➕ | ffmpeg (alias trim) |
| dale | 🔧 | AI image gen (API) |
| dall | 🔧 | AI image gen (API) |
| dark | ➕ | ImageMagick (assombrir) |
| delbudget | ➕ | finance |
| delcmd | ➕ | commandes custom |
| delete | 🌉 | besoin endpoint delete |
| delgreet | ➕ | alias welcome/goodbye off |
| delschedule | ➕ | alias cancel (reminder) |
| delvar | ➕ | reset d'une var |
| demon | 🚫 | overlay art |
| demote | ✅ | |
| dlt | 🌉 | besoin endpoint delete |
| dyno | 🚫 | hébergement |
| enhance | ➕ | ImageMagick (netteté/contraste) basique |
| exif | ➕ | sticker packname (best-effort) |
| expense | ➕ | finance |
| fancy | ➕ | polices unicode |
| fb | ➕ | yt-dlp (python -m yt_dlp) |
| filter | ✅ | |
| forward | 🌉 | besoin endpoint forward |
| fullpp | 🌉 | besoin endpoint pp |
| fullss | 🔧 | screenshot web (besoin outil) |
| gandm | ➕ | alias list |
| gauth | 🚫 | auth |
| gemini | ➕ | alias IA (Ollama) |
| getcmd | ➕ | commandes custom |
| getgreet | ➕ | affiche welcome/goodbye |
| getschedule | ➕ | alias reminders |
| getvar | ✅ | get |
| gfilter | ✅ | |
| ginfo | ➕ | infos groupe (/api/group) |
| gjid | ➕ | alias jid groupe |
| goodbye | ✅ | |
| gpp | 🌉 | besoin endpoint pp |
| gpt | ➕ | alias IA (Ollama) |
| groq | ➕ | alias IA (Ollama) |
| gstatus | 🌉 | besoin endpoint statut |
| gstop | ✅ | |
| gupload | 🌉 | besoin endpoint |
| help | ✅ | menu |
| histo | ➕ | finance (historique) |
| horned | 🚫 | overlay art |
| img | 🔧 | recherche image (API) |
| inactive | ➕ | membres inactifs (messages.db + /api/group) |
| income | ➕ | finance |
| insta | ➕ | yt-dlp (python -m yt_dlp) |
| invite | 🌉 | besoin endpoint lien d'invitation |
| ison | 🌉 | besoin endpoint présence |
| jid | ➕ | alias id |
| join | 🌉 | besoin endpoint join invite |
| kick | ✅ | |
| kiss | 🔧 | gif API |
| left | 🌉 | besoin endpoint leave |
| list | ➕ | membres (/api/group) |
| look | 🚫 | overlay art |
| low | ➕ | ImageMagick (basse lumière) |
| lydia | ➕ | alias IA (Ollama) |
| makeup | 🚫 | overlay art |
| mediafire | 🔧 | besoin scrape/API |
| mention | ➕ | config (auto-mention) |
| menu | ✅ | |
| merge | 🌉 | besoin contexte 2 médias |
| movie | 🔧 | besoin API |
| mp3 | ➕ | tomp3 (reply) ; url = yt-dlp |
| mp4 | ➕ | yt-dlp (python -m yt_dlp) |
| msgs | ➕ | compteur messages par membre |
| mute | ✅ | |
| news | ➕ | RSS (urllib, sans clé) |
| online | 🌉 | besoin endpoint présence |
| pdf | ➕ | images→pdf (ImageMagick) |
| pdm | ➕ | config annonce promote/demote |
| pencil | ➕ | ImageMagick (croquis) |
| pfilter | ➕ | filtre privé |
| photo | ✅ | sticker→image |
| pinterest | ➕ | yt-dlp (python -m yt_dlp) |
| pitch | ➕ | ffmpeg audio |
| ping | ✅ | |
| plugin | ➕ | alias plugins |
| poll | ✅ | |
| pp | 🌉 | besoin endpoint pp |
| promote | ✅ | |
| pstop | ➕ | stop filtre privé |
| qr | ✅ | |
| react | ✅ | |
| read | 🌉 | besoin endpoint read |
| reboot | 🚫 | hébergement |
| reddit | ➕ | yt-dlp (python -m yt_dlp) |
| reminder | ✅ | |
| remove | ➕ | alias kick |
| reset | ➕ | réinit réglages (owner) |
| restart | 🚫 | hébergement |
| reverse | ✅ | |
| revoke | 🌉 | besoin endpoint revoke invite |
| rmbg | 🔧 | besoin API/outil |
| rotate | ➕ | ffmpeg/ImageMagick |
| save | ➕ | sauver vers soi (texte) |
| scstatus | 🌉 | besoin endpoint statut |
| setcmd | ➕ | commandes custom |
| setgreet | ➕ | alias welcome/goodbye |
| setschedule | ➕ | alias reminder |
| setstatus | 🌉 | besoin endpoint statut |
| setvar | ➕ | alias set |
| shutdown | 🚫 | hébergement |
| sketch | ➕ | ImageMagick |
| skull | 🚫 | overlay art |
| song | ➕ | yt-dlp (python -m yt_dlp) |
| spotify | ➕ | yt-dlp (python -m yt_dlp) |
| ss | 🔧 | screenshot web (besoin outil) |
| status | 🌉 | besoin endpoint statut |
| sticker | ✅ | |
| stop | ✅ | |
| story | ➕ | yt-dlp (python -m yt_dlp) |
| summary | ➕ | alias sum |
| tag | ➕ | all / admins / notadmins / caché (mentions) |
| take | ➕ | sticker + packname |
| task | ➕ | todo local |
| tictactoe | ➕ | jeu local |
| tiktok | ➕ | yt-dlp (python -m yt_dlp) |
| tog | ✅ | |
| treble | ➕ | ffmpeg audio |
| trim | ➕ | ffmpeg |
| trt | ➕ | alias tr (traduction) |
| tts | ➕ | Windows SAPI → audio |
| twitter | ➕ | yt-dlp (python -m yt_dlp) |
| unblock | 🌉 | besoin endpoint |
| unmute | ✅ | |
| upload | 🌉/🔧 | host externe |
| url | ➕ | alias raccourci |
| vector | 🔧 | besoin potrace |
| video | ➕ | yt-dlp (python -m yt_dlp) |
| vote | ➕ | alias poll |
| wanted | 🚫 | overlay art |
| warn | ➕ | avertissement + auto-kick (warn-limit) |
| wcg | ➕ | jeu local (word chain) |
| weather | ✅ | |
| welcome | ✅ | |
| whois | ➕ | RDAP domaine (urllib, sans clé) |
| wrg | ➕ | retire un avertissement |
| yt | ➕ | yt-dlp (url/recherche) |
| yta | ➕ | yt-dlp (python -m yt_dlp) |
| ytlogin | 🚫 | auth |
| yts | ➕ | yt-dlp (python -m yt_dlp) |
| ytv | ➕ | yt-dlp (python -m yt_dlp) |
| zombie | 🚫 | overlay art |

## Réglages de comportement (settings + panneau)
alwaysonline, autostatusview, cmd-reaction (creact), mention (auto), rejectcall, send-read, whitelist, antibot, sticker-packname, warn-limit/messages, timezone → exposés dans settings.json (certains = 🌉 besoin endpoint pour l'effet réel : présence, read, rejectcall, status).

## Synthèse (mise à jour — yt-dlp installé)
- **NOVA = 218 commandes** enregistrées (menu auto + onglet Plugins).
- Downloaders : yt-dlp est dispo via `python -m yt_dlp` → song/video/yt/ytv/yts/yta/mp4/insta/tiktok/fb/twitter/reddit/pinterest/spotify/story = **faisables** (téléchargent en temp puis envoient via /api/send, nettoyage auto, cap 80 Mo). `img`/`apk`/`mediafire`/`movie` restent 🔧 (API/scrape spécifique).
- Médias : sticker/take, photo, tomp3/avm, bass/pitch/treble, rotate/trim/cut/compress/crop, pdf, color, et effets ImageMagick (black/dark/low/sketch/pencil/bokeh/cartoon/enhance/circle) = ➕. Les art-overlays (wanted/zombie/demon/skull/horned/bloody/makeup/look) = 🚫 (assets), vector = 🔧 (potrace), rmbg/ss/fullss = 🔧 (outil/API).
- Groupe : kick/add/promote/demote/gname/gdesc/mute/unmute/react/poll/vote + tag(all/admins/notadmins/caché)/tagall/everyone/list/gandm/ginfo/cinfo/msgs/inactive/warn/wrg/pdm + welcome/goodbye/getgreet/delgreet + modération antilink/antiword(+antispam/antifake config) = ➕. Restent 🌉 (nouveaux endpoints bridge) : invite/revoke/join/left/block/unblock/pp/fullpp/gpp/forward/delete/dlt/clear/common/online/ison/read/status*.
- Config : vars/set/get/allvar/setvar/getvar/delvar, warn-limit, sticker-packname, cmd-reaction, auto-mention (+ alwaysonline/rejectcall/send-read/antibot stockés, effet = 🌉). Commandes custom setcmd/getcmd/delcmd/allcmd. Finance budget/expense/income/delbudget/histo. Jeux tictactoe/wcg. IA gpt/gemini/groq/bing/lydia/openrouter → Ollama local.
- Non-pertinent (hébergement/VPS/auth) : backup/dyno/reboot/restart/shutdown/update/gauth/ytlogin, et art-overlays sans assets.
