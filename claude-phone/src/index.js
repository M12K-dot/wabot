require("dotenv").config();
const express = require("express");
const twilio = require("twilio");
const { ask, reset } = require("./claude");

const app = express();
app.use(express.urlencoded({ extended: false }));

const PORT = process.env.PORT || 3000;
const VOICE = process.env.TTS_VOICE || "Polly.Lea-Neural"; // voix francaise (Amazon Polly)
const LANG = process.env.TTS_LANG || "fr-FR";
const AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN;
const VALIDATE = process.env.VALIDATE_TWILIO !== "false";

// Securite : rejette les webhooks qui ne viennent pas vraiment de Twilio.
function twilioGuard(req, res, next) {
  if (!VALIDATE || !AUTH_TOKEN) return next();
  const signature = req.header("X-Twilio-Signature");
  const url = `${req.protocol}://${req.get("host")}${req.originalUrl}`;
  const valid = twilio.validateRequest(AUTH_TOKEN, signature, url, req.body);
  if (!valid) return res.status(403).send("Signature Twilio invalide");
  next();
}

// Check de vie (ouvre l'URL ngrok dans un navigateur pour verifier)
app.get("/", (_req, res) => res.send("claude-phone est en ligne"));

// ---------- SMS entrant ----------
app.post("/sms", twilioGuard, async (req, res) => {
  const from = req.body.From;
  const body = (req.body.Body || "").trim();
  const twiml = new twilio.twiml.MessagingResponse();

  try {
    if (/^(reset|stop|clear)$/i.test(body)) {
      reset(from);
      twiml.message("Conversation reinitialisee.");
    } else {
      const reply = await ask(from, body, { channel: "sms" });
      twiml.message(reply);
    }
  } catch (err) {
    console.error("Erreur SMS:", err.message);
    twiml.message("Oups, une erreur est survenue. Reessaie dans un instant.");
  }

  res.type("text/xml").send(twiml.toString());
});

// ---------- Appel vocal entrant ----------
app.post("/voice", twilioGuard, (req, res) => {
  const twiml = new twilio.twiml.VoiceResponse();
  const gather = twiml.gather({
    input: "speech",
    language: LANG,
    speechTimeout: "auto",
    action: "/voice/respond",
    method: "POST",
  });
  gather.say(
    { voice: VOICE, language: LANG },
    "Bonjour, ici Claude. Que puis-je faire pour vous ?"
  );
  // Si rien n'est dit, on relance l'accueil.
  twiml.redirect("/voice");
  res.type("text/xml").send(twiml.toString());
});

// ---------- Reponse apres transcription de la parole ----------
app.post("/voice/respond", twilioGuard, async (req, res) => {
  const from = req.body.From;
  const speech = (req.body.SpeechResult || "").trim();
  const twiml = new twilio.twiml.VoiceResponse();

  try {
    if (!speech) {
      twiml.say({ voice: VOICE, language: LANG }, "Je n'ai rien entendu. Au revoir.");
      twiml.hangup();
    } else {
      const reply = await ask(from, speech, { channel: "voice" });
      const gather = twiml.gather({
        input: "speech",
        language: LANG,
        speechTimeout: "auto",
        action: "/voice/respond",
        method: "POST",
      });
      gather.say({ voice: VOICE, language: LANG }, reply);
      // Si l'appelant ne dit plus rien, on repasse ici (qui raccrochera).
      twiml.redirect("/voice/respond");
    }
  } catch (err) {
    console.error("Erreur voix:", err.message);
    twiml.say({ voice: VOICE, language: LANG }, "Desole, une erreur est survenue. Au revoir.");
    twiml.hangup();
  }

  res.type("text/xml").send(twiml.toString());
});

app.listen(PORT, () => {
  console.log(`claude-phone a l'ecoute sur http://localhost:${PORT}`);
  console.log("Webhooks a configurer dans Twilio :");
  console.log("  SMS  -> POST <URL_PUBLIQUE>/sms");
  console.log("  Voix -> POST <URL_PUBLIQUE>/voice");
});
