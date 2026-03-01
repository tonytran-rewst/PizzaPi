#!/usr/bin/env python3
"""
Automated demo video generator.

Pipeline:
  1. Generate a script (narration + terminal commands) from story context
  2. Record terminal session with asciinema
  3. Generate voiceover with ElevenLabs
  4. Compose final video with ffmpeg

Usage:
  python3 generate_demo.py --story 81121 --generate-script
  python3 generate_demo.py --script my_script.yaml
  python3 generate_demo.py --script my_script.yaml --voice-only
  python3 generate_demo.py --script my_script.yaml --record-only

System dependencies (brew):
  brew install asciinema agg ffmpeg

Python dependencies are auto-installed into a managed venv.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Self-bootstrapping venv
# ---------------------------------------------------------------------------

SKILL_DIR = Path(__file__).parent
VENV_DIR = SKILL_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
PIP_DEPS = ["elevenlabs", "pyyaml"]


def _ensure_venv() -> None:
    """Create the skill's venv and install dependencies if needed."""
    if VENV_PYTHON.exists():
        return

    print("🔧 Setting up demo-generator venv (one-time)...")
    venv.create(str(VENV_DIR), with_pip=True, clear=True)
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--quiet", *PIP_DEPS],
        check=True,
    )
    print("✅ Venv ready\n")


def _reexec_in_venv() -> None:
    """Re-execute this script inside the managed venv if we're not already in it."""
    # Already running from the venv — nothing to do
    if Path(sys.executable).resolve() == VENV_PYTHON.resolve():
        return

    _ensure_venv()
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])


# Bootstrap before any third-party imports
_reexec_in_venv()

import yaml  # noqa: E402  — available after venv bootstrap


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUTPUT_DIR = SKILL_DIR / "output"
SCRIPTS_DIR = SKILL_DIR / "scripts"
TEMPLATES_DIR = SKILL_DIR / "templates"

# ElevenLabs defaults
DEFAULT_VOICE_ID = "nPczCjzI2devNBz1zQrb"  # "Brian" — deep, resonant, professional
DEFAULT_MODEL_ID = "eleven_turbo_v2_5"

# Recording defaults
DEFAULT_COLS = 120
DEFAULT_ROWS = 35
DEFAULT_TYPING_DELAY = 0.04
DEFAULT_PAUSE_BETWEEN = 0.8
DEFAULT_FONT_SIZE = 16


# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

def check_dependencies(skip_voice: bool = False, skip_record: bool = False) -> list[str]:
    """Check that required tools are installed. Returns list of missing tools."""
    missing = []

    if not skip_record:
        if not shutil.which("asciinema"):
            missing.append("asciinema (brew install asciinema)")
        if not shutil.which("agg"):
            missing.append("agg (brew install agg)")

    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg (brew install ffmpeg)")

    if not skip_voice:
        if not os.environ.get("ELEVENLABS_API_KEY"):
            missing.append("ELEVENLABS_API_KEY environment variable")

    return missing


# ---------------------------------------------------------------------------
# Step 1: Script Generation
# ---------------------------------------------------------------------------

def generate_script_template(
    story_id: str,
    story_title: str = "Story Title",
    problem_summary: str = "We identified and fixed the root cause.",
    primary_file: str = ".",
    test_command: str = "echo 'tests pass'",
) -> dict[str, Any]:
    """Generate a demo script dict from story context."""
    return {
        "title": story_title,
        "story_id": story_id,
        "settings": {
            "cols": DEFAULT_COLS,
            "rows": DEFAULT_ROWS,
            "typing_delay": DEFAULT_TYPING_DELAY,
            "pause_between": DEFAULT_PAUSE_BETWEEN,
            "font_size": DEFAULT_FONT_SIZE,
        },
        "scenes": [
            {
                "narration": f"Let me show you what we fixed in story {story_id}. {problem_summary}",
                "commands": [
                    f"# SC-{story_id}: {story_title}",
                    "git log --oneline -3",
                ],
            },
            {
                "narration": "Here's the key change we made.",
                "commands": [
                    "git diff HEAD~1 --stat",
                ],
            },
            {
                "narration": "Let's look at the actual code changes.",
                "commands": [
                    f"git diff HEAD~1 -- {primary_file}",
                ],
            },
            {
                "narration": "And here are the tests passing to confirm the fix works.",
                "commands": [
                    test_command,
                ],
            },
            {
                "narration": "That's it! The fix is clean, tested, and ready for review.",
                "commands": [
                    "echo 'Demo complete ✅'",
                ],
            },
        ],
    }


def load_script(path: Path) -> dict[str, Any]:
    """Load a YAML demo script."""
    with open(path) as f:
        return yaml.safe_load(f)


def save_script(script: dict[str, Any], path: Path) -> None:
    """Save a demo script as YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(script, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Step 2: Terminal Recording (asciinema)
# ---------------------------------------------------------------------------

def record_scene_commands(
    commands: list[str],
    output_cast: Path,
    cwd: str | None = None,
    typing_delay: float = DEFAULT_TYPING_DELAY,
    pause_between: float = DEFAULT_PAUSE_BETWEEN,
    cols: int = DEFAULT_COLS,
    rows: int = DEFAULT_ROWS,
) -> None:
    """
    Record terminal commands to an asciinema .cast file.

    Builds a shell script that simulates realistic typing, then records
    it with asciinema.
    """
    script_lines = [
        "#!/bin/bash",
        "set -e",
        "",
        "# Auto-generated demo script",
        f"export PS1='$ '",
        "",
    ]

    for i, cmd in enumerate(commands):
        # Simulate typing: print each char with a delay
        for char in cmd:
            escaped = char.replace("\\", "\\\\").replace("'", "'\\''")
            script_lines.append(f"printf '{escaped}'")
            script_lines.append(f"sleep {typing_delay}")
        script_lines.append("printf '\\n'")
        script_lines.append(f"sleep 0.1")
        # Execute the command
        script_lines.append(cmd)
        if i < len(commands) - 1:
            script_lines.append(f"sleep {pause_between}")
    # Final pause so the output is visible
    script_lines.append("sleep 1.5")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write("\n".join(script_lines))
        script_path = f.name

    try:
        os.chmod(script_path, 0o755)
        output_cast.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                "asciinema", "rec",
                "--command", f"bash {script_path}",
                "--cols", str(cols),
                "--rows", str(rows),
                "--overwrite",
                str(output_cast),
            ],
            cwd=cwd,
            check=True,
            env={**os.environ, "ASCIINEMA_REC": "1"},
        )
    finally:
        os.unlink(script_path)


def cast_to_gif(cast_file: Path, gif_file: Path, font_size: int = DEFAULT_FONT_SIZE) -> None:
    """Convert asciinema .cast to GIF using agg."""
    subprocess.run(
        [
            "agg",
            "--font-size", str(font_size),
            str(cast_file),
            str(gif_file),
        ],
        check=True,
    )


def cast_to_mp4(cast_file: Path, mp4_file: Path, font_size: int = DEFAULT_FONT_SIZE) -> None:
    """Convert asciinema .cast to MP4 via agg (GIF) then ffmpeg."""
    gif_file = cast_file.with_suffix(".gif")
    cast_to_gif(cast_file, gif_file, font_size=font_size)

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(gif_file),
            "-movflags", "faststart",
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            str(mp4_file),
        ],
        check=True,
        capture_output=True,
    )

    # Clean up intermediate GIF
    gif_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Step 3: Voice Generation (ElevenLabs)
# ---------------------------------------------------------------------------

def generate_voiceover(
    text: str,
    output_path: Path,
    voice_id: str = DEFAULT_VOICE_ID,
    model_id: str = DEFAULT_MODEL_ID,
) -> None:
    """Generate voiceover audio using ElevenLabs TTS API."""
    from elevenlabs import ElevenLabs

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY environment variable not set")

    client = ElevenLabs(api_key=api_key)

    audio_generator = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=model_id,
        text=text,
        output_format="mp3_44100_128",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)

    size_kb = output_path.stat().st_size / 1024
    print(f"  ✓ Voice: {output_path.name} ({size_kb:.1f} KB)")


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of an audio file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


# ---------------------------------------------------------------------------
# Step 4: Compose Final Video (ffmpeg)
# ---------------------------------------------------------------------------

def compose_video(
    video_segments: list[Path],
    audio_segments: list[Path],
    output_path: Path,
) -> None:
    """
    Compose final video by concatenating segments and overlaying audio.

    Pads each scene's video to match its audio duration so narration
    plays in sync with the terminal content.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        padded_videos: list[Path] = []

        # Pad each video segment to match its corresponding audio duration
        for i, (vp, ap) in enumerate(zip(video_segments, audio_segments)):
            audio_dur = get_audio_duration(ap)
            padded = tmpdir_path / f"padded_{i:02d}.mp4"

            # Use tpad filter to extend the last frame to match audio length
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(vp),
                    "-vf", f"tpad=stop_mode=clone:stop_duration={audio_dur}",
                    "-t", str(audio_dur + 0.5),  # slight buffer
                    "-pix_fmt", "yuv420p",
                    str(padded),
                ],
                check=True,
                capture_output=True,
            )
            padded_videos.append(padded)

        # Concatenate all padded video segments
        video_list = tmpdir_path / "videos.txt"
        with open(video_list, "w") as f:
            for vp in padded_videos:
                f.write(f"file '{vp.resolve()}'\n")

        concat_video = tmpdir_path / "concat_video.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(video_list),
                "-c", "copy",
                str(concat_video),
            ],
            check=True,
            capture_output=True,
        )

        # Concatenate all audio segments
        audio_list = tmpdir_path / "audios.txt"
        with open(audio_list, "w") as f:
            for ap in audio_segments:
                f.write(f"file '{ap.resolve()}'\n")

        concat_audio = tmpdir_path / "concat_audio.mp3"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(audio_list),
                "-c", "copy",
                str(concat_audio),
            ],
            check=True,
            capture_output=True,
        )

        # Merge video + audio
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(concat_video),
                "-i", str(concat_audio),
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-movflags", "faststart",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    print(f"\n✅ Demo video: {output_path}")
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"   Size: {size_mb:.1f} MB")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    script: dict[str, Any],
    output_name: str | None = None,
    cwd: str | None = None,
    skip_voice: bool = False,
    skip_record: bool = False,
    voice_id: str | None = None,
) -> Path | None:
    """Run the full demo generation pipeline. Returns path to output video."""
    story_id = script.get("story_id", "unknown")
    name = output_name or f"demo-sc-{story_id}"

    # Resolve settings
    settings = script.get("settings", {})
    cols = settings.get("cols", DEFAULT_COLS)
    rows = settings.get("rows", DEFAULT_ROWS)
    typing_delay = settings.get("typing_delay", DEFAULT_TYPING_DELAY)
    pause_between = settings.get("pause_between", DEFAULT_PAUSE_BETWEEN)
    font_size = settings.get("font_size", DEFAULT_FONT_SIZE)
    resolved_voice_id = voice_id or script.get("voice_id", DEFAULT_VOICE_ID)

    # Preflight
    missing = check_dependencies(skip_voice=skip_voice, skip_record=skip_record)
    if missing:
        print("❌ Missing dependencies:", file=sys.stderr)
        for m in missing:
            print(f"   • {m}", file=sys.stderr)
        sys.exit(1)

    work_dir = OUTPUT_DIR / name
    work_dir.mkdir(parents=True, exist_ok=True)

    scenes = script.get("scenes", [])
    if not scenes:
        print("❌ No scenes in script", file=sys.stderr)
        sys.exit(1)

    video_segments: list[Path] = []
    audio_segments: list[Path] = []

    for i, scene in enumerate(scenes):
        print(f"\n{'='*60}")
        print(f"Scene {i+1}/{len(scenes)}")
        print(f"{'='*60}")

        narration = scene.get("narration", "").strip()
        commands = scene.get("commands", [])

        # --- Record terminal ---
        cast_file = work_dir / f"scene_{i:02d}.cast"
        mp4_file = work_dir / f"scene_{i:02d}.mp4"

        if not skip_record and commands:
            print(f"  Recording {len(commands)} command(s)...")
            record_scene_commands(
                commands, cast_file,
                cwd=cwd,
                typing_delay=typing_delay,
                pause_between=pause_between,
                cols=cols,
                rows=rows,
            )
            cast_to_mp4(cast_file, mp4_file, font_size=font_size)
            video_segments.append(mp4_file)
            print(f"  ✓ Video: {mp4_file.name}")
        elif mp4_file.exists():
            video_segments.append(mp4_file)
            print(f"  ✓ Video: {mp4_file.name} (cached)")

        # --- Generate voiceover ---
        audio_file = work_dir / f"scene_{i:02d}.mp3"

        if not skip_voice and narration:
            print(f"  Generating voiceover ({len(narration)} chars)...")
            generate_voiceover(narration, audio_file, voice_id=resolved_voice_id)
            audio_segments.append(audio_file)
        elif audio_file.exists():
            audio_segments.append(audio_file)
            print(f"  ✓ Voice: {audio_file.name} (cached)")

    # --- Compose final video ---
    if video_segments and audio_segments:
        final_output = OUTPUT_DIR / f"{name}.mp4"
        print(f"\nComposing final video...")
        compose_video(video_segments, audio_segments, final_output)
        return final_output
    elif video_segments:
        print(f"\n⚠️  No audio — video-only output in {work_dir}/")
    elif audio_segments:
        print(f"\n⚠️  No video — audio-only output in {work_dir}/")
    else:
        print(f"\n❌ No segments generated")

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate demo videos with terminal recordings and AI voiceover",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a script template for a story
  %(prog)s --story 81121 --generate-script

  # Run the full pipeline from a script
  %(prog)s --script scripts/sc-81121.yaml --cwd /path/to/repo

  # Record terminal only (no voiceover)
  %(prog)s --script scripts/sc-81121.yaml --record-only

  # Generate voiceover only (reuse cached recordings)
  %(prog)s --script scripts/sc-81121.yaml --voice-only
        """,
    )
    parser.add_argument("--story", help="Shortcut story ID")
    parser.add_argument("--script", help="Path to a YAML demo script")
    parser.add_argument("--cwd", help="Working directory for terminal recording")
    parser.add_argument("--output", help="Output name (default: demo-sc-XXXXX)")
    parser.add_argument("--voice-id", help="ElevenLabs voice ID override")
    parser.add_argument("--voice-only", action="store_true", help="Only generate voiceover")
    parser.add_argument("--record-only", action="store_true", help="Only record terminal")
    parser.add_argument(
        "--generate-script", action="store_true",
        help="Generate a template script YAML (edit before recording)",
    )
    args = parser.parse_args()

    if args.story and args.generate_script:
        script = generate_script_template(story_id=args.story)
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        script_path = SCRIPTS_DIR / f"sc-{args.story}.yaml"
        save_script(script, script_path)
        print(f"✅ Script template: {script_path}")
        print(f"   Edit it, then run:")
        print(f"   python3 {__file__} --script {script_path}")
        return

    if args.script:
        script = load_script(Path(args.script))
    elif args.story:
        script = generate_script_template(story_id=args.story)
    else:
        parser.error("Provide --story or --script")
        return

    run_pipeline(
        script=script,
        output_name=args.output,
        cwd=args.cwd,
        skip_voice=args.record_only,
        skip_record=args.voice_only,
        voice_id=args.voice_id,
    )


if __name__ == "__main__":
    main()
