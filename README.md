# Uncle Yaw — Voice-Enabled Intelligent Assistant

A fully functional voice assistant that listens to spoken commands, fetches real-time information from the internet, and responds out loud — with a custom Ghanaian-accent voice and a real-time animated UI that reacts to your speech.

<!-- Record a 10-15s screen capture of the blob UI and export as demo/demo.gif -->
![Demo](demo/demo.gif)

## What It Does

- **Listens** to voice commands and transcribes them in real time.
- **Understands and answers** queries by sending them to a large language model that can search the internet.
- **Speaks back** using natural text-to-speech, with a voice given a Ghanaian accent for character.
- **Shows what it's doing** through an animated blob that pulses with your voice volume and changes colour depending on whether it is listening, thinking, or speaking.

Built from scratch as a project for an AI & Robotics course, alongside my final-year capstone.

## Tech Stack

| Component        | Technology                  |
|------------------|-----------------------------|
| Speech-to-text   | Google Web Speech API       |
| Query handling   | Gemini 2.5 Flash Lite       |
| Text-to-speech   | ElevenLabs API              |
| Animated UI      | pygame                      |
| Language         | Python                      |

## How It Works

The assistant runs a continuous listen → think → speak loop:

1. **Listen** — `speech_to_text.py` captures microphone audio and converts speech to text via the Google Web Speech API.
2. **Think** — `llm_query.py` sends the transcribed text to Gemini 2.5 Flash Lite, which interprets the request and retrieves information from the internet where needed.
3. **Speak** — `text_to_speech.py` converts the model's response back into audio using ElevenLabs, with a custom voice profile.
4. **Visualise** — `ui.py` drives a pygame animation that responds to voice volume in real time and reflects the current state of the system.

See [`architecture.diagram.png`](architecture.diagram.png) for a fuller breakdown of the pipeline.

My focus throughout was on the **system architecture and control logic** — how the components fit together and hand off to one another — rather than writing every line by hand.

## Repository Structure

```
uncle-yaw-voice-assistant/
├── src/
│   ├── main.py             # orchestration loop
│   ├── speech_to_text.py   # Google Web Speech API
│   ├── llm_query.py        # Gemini 2.5 Flash Lite
│   ├── text_to_speech.py   # ElevenLabs + voice config
│   └── ui.py               # pygame animated blob
├── demo/
│   └── demo.gif            # UI reacting to voice
├── docs/
│   └── architecture.md     # pipeline diagram and notes
├── .env.example            # required API key names (no real keys)
├── requirements.txt
└── README.md
```

## Getting Started

```bash
git clone https://github.com/YOUR_USERNAME/uncle-yaw-voice-assistant.git
cd uncle-yaw-voice-assistant
pip install -r requirements.txt
```

This project needs API keys for the speech and language services. Copy the example file and fill in your own keys:

```bash
cp .env.example .env
# then open .env and add your keys
```

Run the assistant:

```bash
python src/main.py
```

> **API keys are never committed.** Real keys live in a local `.env` file, which
> is excluded by `.gitignore`. The committed `.env.example` lists only the
> variable names you need to fill in.

## What I'd Build Next

Adding wake-word detection so the assistant can run hands-free, and caching common queries to cut response latency.

## View Demo Here
▶️ [Watch the Uncle Yaw demo on YouTube](https://youtu.be/v2ovnbLVgaw)

## About

Course project for AI & Robotics, B.Sc. Electrical & Electronics Engineering, Academic City University, Accra, Ghana.

<!-- Optional: add a license note if you include a LICENSE file -->
Licensed under the MIT License.
