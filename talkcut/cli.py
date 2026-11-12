import argparse
import os
import shutil
import sys

from . import edit
from .transcribe import load_audio, load_or_transcribe, project_path, save


def show_progress(p):
    print(f"\rtranscribing {p:4.0%}", end="", file=sys.stderr, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="talkcut", description="Edit spoken audio by editing its transcript."
    )
    ap.add_argument("media", help="audio file to edit (never modified)")
    ap.add_argument("--model", default="base",
                    help="Whisper model: tiny, base, small, medium, large-v3 (default: base)")
    ap.add_argument("--remove-fillers", action="store_true",
                    help="delete um/uh/etc. and export, without opening the editor")
    ap.add_argument("--srt", action="store_true",
                    help="also write <name>.edited.srt and <name>.edited.txt matching the export")
    ap.add_argument("-o", "--out", help="output file (default: <name>.edited.<ext>)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="don't open the editor page")
    args = ap.parse_args(argv)

    media = os.path.abspath(args.media)
    if not os.path.isfile(media):
        ap.error(f"no such file: {args.media}")
    if not shutil.which("ffmpeg"):
        ap.error("ffmpeg not found; install it first (macOS: brew install ffmpeg)")
    if os.path.exists(project_path(media)):
        print(f"using saved transcript {os.path.basename(project_path(media))} "
              "(delete it to transcribe again)", file=sys.stderr)

    if not args.remove_fillers:
        from .server import serve

        try:
            serve(media, args.model, args.port, open_browser=not args.no_browser)
        except OSError as e:
            ap.error(f"can't listen on port {args.port} ({e.strerror}); try --port")
        return

    project = load_or_transcribe(media, args.model, on_progress=show_progress)
    print(file=sys.stderr)
    fillers = edit.find_fillers(project["words"])
    project["deleted"] = sorted(set(project["deleted"]) | set(fillers))
    save(project, project_path(media))
    dst = args.out or edit.edited_path(media)
    levels = edit.frame_levels(load_audio(media))
    length = edit.export(project, media, dst, levels)
    print(f"removed {len(fillers)} fillers: {project['duration']:.1f}s -> {length:.1f}s, "
          f"wrote {dst}")
    if args.srt:
        cuts = edit.final_cuts(project, levels)
        base = os.path.splitext(dst)[0]
        srt = base + ".srt"
        txt = base + ".txt"
        edit.export_subtitles(project, cuts, srt, txt)
        print(f"wrote {srt} and {txt}")


if __name__ == "__main__":
    main()
