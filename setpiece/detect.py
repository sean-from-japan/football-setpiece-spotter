"""Detecting people in panoramic footage, and caching the result.

The model resizes whatever it is given to 384x384. On a stitched panorama of a
whole pitch that leaves a player a handful of pixels tall, so the frame is cut
into tiles and each tile is run separately. This is not an optimisation to be
added later; without it the detector sees nothing.

This module is the only part of the project that needs torch, and it is
imported lazily so that the rest keeps working without it.
"""

import csv
import os

COLUMNS = ("frame", "x1", "y1", "x2", "y2", "score")

#: COCO's person class, which is what the pretrained checkpoints report.
PERSON = 1


class DetectorError(RuntimeError):
    """The model or the video could not be used."""


def tiles(width, height, columns, rows, overlap):
    """Return the tile rectangles covering an image.

    Tiles overlap so that a player standing on a seam is whole in at least one
    of them; the duplicate detections that creates are removed afterwards.
    """
    if columns < 1 or rows < 1:
        raise ValueError("columns and rows must be at least 1")
    if not 0 <= overlap < 0.5:
        raise ValueError("overlap must be within [0, 0.5)")

    step_x = width / columns
    step_y = height / rows
    pad_x = step_x * overlap
    pad_y = step_y * overlap
    out = []
    for row in range(rows):
        for column in range(columns):
            left = max(0, int(column * step_x - pad_x))
            top = max(0, int(row * step_y - pad_y))
            right = min(width, int((column + 1) * step_x + pad_x))
            bottom = min(height, int((row + 1) * step_y + pad_y))
            out.append((left, top, right, bottom))
    return out


def _overlaps(a, b):
    """Intersection over the smaller box.

    Plain IoU is the wrong test here: the same player seen in two tiles is
    often clipped in one of them, so the boxes agree on the visible part and
    disagree on the whole. Dividing by the smaller area sees that as the
    duplicate it is.
    """
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return intersection / smaller if smaller else 0.0


def deduplicate(boxes, threshold=0.55):
    """Drop boxes that are the same person seen from an adjacent tile."""
    kept = []
    for box in sorted(boxes, key=lambda b: b[4], reverse=True):
        if not any(_overlaps(box, other) > threshold for other in kept):
            kept.append(box)
    return kept


def foot_point(box):
    """Where a person meets the ground: the middle of the bottom edge."""
    return ((box[0] + box[2]) / 2.0, box[3])


def detect_video(path, destination, sample_fps=4.0, columns=8, rows=2,
                 overlap=0.08, threshold=0.4, model=None, limit=None,
                 progress=None):
    """Run the detector over a video and write one row per detection."""
    try:
        import cv2
    except ImportError:
        raise DetectorError("opencv-python is required; install the 'detect' extra")

    if model is None:
        try:
            from rfdetr import RFDETRNano
        except ImportError:
            raise DetectorError("rfdetr is required; install the 'detect' extra")
        model = RFDETRNano()

    from PIL import Image

    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise DetectorError(f"could not open {path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(fps / sample_fps)))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    grid = tiles(width, height, columns, rows, overlap)

    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    written = 0
    index = 0
    with open(destination, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(COLUMNS)
        while True:
            ok = capture.grab()
            if not ok:
                break
            index += 1
            if index % step:
                continue
            ok, frame = capture.retrieve()
            if not ok:
                break

            found = []
            for left, top, right, bottom in grid:
                crop = Image.fromarray(frame[top:bottom, left:right, ::-1])
                result = model.predict(crop, threshold=threshold)
                for box, score, label in zip(result.xyxy, result.confidence,
                                             result.class_id):
                    if int(label) != PERSON:
                        continue
                    found.append((float(box[0]) + left, float(box[1]) + top,
                                  float(box[2]) + left, float(box[3]) + top,
                                  float(score)))
            for box in deduplicate(found):
                writer.writerow([index] + [round(v, 1) for v in box[:4]]
                                + [round(box[4], 3)])
                written += 1
            if progress and index % (step * 100) == 0:
                progress(index, index / fps, written)
            if limit and index >= limit:
                break
    capture.release()
    return written


def load_detections(path):
    """Read a detection cache, grouped by frame."""
    frames = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != list(COLUMNS):
            raise DetectorError(f"{path} is not a detection cache; header was {header}")
        for frame, x1, y1, x2, y2, score in reader:
            frames.setdefault(int(frame), []).append(
                (float(x1), float(y1), float(x2), float(y2), float(score)))
    return frames
