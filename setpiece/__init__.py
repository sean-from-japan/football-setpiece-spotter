"""Set-piece candidate spotting for fixed wide-angle amateur football footage.

The package is deliberately layered: everything up to and including the
evaluator runs on the standard library plus ``ffprobe``/``ffmpeg``, and only the
detector needs torch. See ``docs/DECISIONS.md``.
"""

__version__ = "0.1.0"
