# Demo Video Generator

Generate polished demo videos for any story or fix — terminal recordings with AI voiceover, composited into a final MP4.

## When to Use This Skill

Use this when the user asks to:
- Generate a demo for a story/ticket (e.g., "generate a demo for SC-81121")
- Record a terminal walkthrough of their changes
- Create a video with voiceover explaining their work
- Produce a shareable demo of a fix, feature, or PR

## Prerequisites

The pipeline requires these tools installed on the system:

```bash
brew install asciinema agg ffmpeg
pip3 install elevenlabs pyyaml
```

The `ELEVENLABS_API_KEY` environment variable must be set for voiceover generation.

## Pipeline Overview

```
Story/Context → Script (YAML) → Record (asciinema) → Voice (ElevenLabs) → Compose (ffmpeg) → .mp4
```

The pipeline has 4 stages that can be run independently or together:

1. **Script Generation** — Create a YAML script with scenes (narration + terminal commands)
2. **Terminal Recording** — Record each scene's commands with asciinema, convert to MP4
3. **Voice Generation** — Generate voiceover audio for each scene with ElevenLabs TTS
4. **Composition** — Merge video + audio into a final MP4 with ffmpeg

## Instructions

### Step 1: Generate the Script

The script is a YAML file that defines scenes. Each scene has narration (what the voice says) and commands (what the terminal shows). Use the pipeline tool at `{SKILL_DIR}/generate_demo.py`.

Generate a template from a story ID:

```bash
python3 {SKILL_DIR}/generate_demo.py --story 81121 --generate-script
```

Or write a script directly. See `{SKILL_DIR}/templates/script-template.yaml` for the format.

**When writing scripts for a user's work, leverage what you already know:**
- The story description and context from Shortcut
- The git diff and changed files from the branch
- The test results you've seen
- The problem/solution narrative from the conversation

A good demo script follows this arc:
1. **Problem** — What was broken and why it matters
2. **Code** — Show the key changes (diff or file highlights)
3. **Verification** — Tests passing, behavior confirmed
4. **Wrap-up** — Clean summary

### Step 2: Record, Voice, and Compose

Run the full pipeline:

```bash
python3 {SKILL_DIR}/generate_demo.py --script path/to/script.yaml --cwd /path/to/repo
```

Or run stages independently:

```bash
# Terminal recording only (no voice)
python3 {SKILL_DIR}/generate_demo.py --script script.yaml --record-only

# Voiceover only (no recording)
python3 {SKILL_DIR}/generate_demo.py --script script.yaml --voice-only

# Both (full pipeline)
python3 {SKILL_DIR}/generate_demo.py --script script.yaml
```

Output goes to `{SKILL_DIR}/output/`.

### Step 3: Review and Iterate

The user can:
- Edit the YAML script and re-run specific stages
- Adjust typing speed, pause duration, voice selection
- Re-record individual scenes without regenerating everything

## Configuration

### ElevenLabs Voices

The default voice is "Rachel" (clear, professional). To use a different voice, pass `--voice-id` or set it in the script YAML:

```yaml
voice_id: "21m00Tcm4TlvDq8ikWAM"  # Rachel (default)
```

Popular alternatives:
- `EXAVITQu4vr4xnSDxMaL` — "Bella" (warm, conversational)
- `ErXwobaYiN019PkySvjV` — "Antoni" (male, clear)
- `MF3mGyEYCl7XYWbV9V6O` — "Elli" (young, friendly)

### Recording Settings

In the script YAML:
```yaml
settings:
  cols: 120          # Terminal width
  rows: 35           # Terminal height
  typing_delay: 0.04 # Seconds between keystrokes
  pause_between: 0.8 # Seconds between commands
  font_size: 16      # Font size in generated video
```

## Example: End-to-End Demo for a Story

When the user says "generate a demo for SC-81121", follow these steps:

1. **Gather context** — Read the story, look at the branch diff, recall the conversation
2. **Write the script** — Create a YAML file with 4-6 scenes covering problem → fix → tests
3. **Check prerequisites** — Verify asciinema, agg, ffmpeg, elevenlabs are installed
4. **Ask the user** — Show them the script and ask if they want to adjust anything
5. **Run the pipeline** — Execute generate_demo.py with the script
6. **Deliver** — Tell the user where the output MP4 is
