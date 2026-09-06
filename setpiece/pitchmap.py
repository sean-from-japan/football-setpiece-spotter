"""Learning where a point in the panorama is on the pitch.

The release ships a homography and a pair of distortion maps, and neither takes
pitch metres to the pixels of the distributed video: all twenty-two players of
a frame land in a band about 150 px wide (``docs/DATASET_NOTES.md``). So the
mapping is fitted here instead, from the annotated player positions.

A single homography would be wrong anyway. The video is stitched from several
cameras, so straight lines on the pitch are not straight in the image and no
one projective transform describes the whole frame. A low-order polynomial
absorbs that.

**What this can and cannot be used for.** Fitting on ground truth measures the
cost of *perception* — detection and tracking — with the geometry held correct.
It says nothing about a camera nobody has annotated, which is the deployment
case and a separate problem.
"""

import numpy as np

try:
    from scipy.optimize import linear_sum_assignment
except ImportError:  # pragma: no cover - scipy ships with the detect extra
    linear_sum_assignment = None


class FitError(RuntimeError):
    """The mapping could not be fitted."""


def _features(points, degree):
    """Polynomial features of normalised image coordinates."""
    points = np.asarray(points, float).reshape(-1, 2)
    x, y = points[:, 0], points[:, 1]
    columns = []
    for total in range(degree + 1):
        for power in range(total + 1):
            columns.append((x ** (total - power)) * (y ** power))
    return np.column_stack(columns)


class PitchMap:
    """A fitted image-to-pitch mapping."""

    def __init__(self, coefficients, degree, scale):
        self.coefficients = np.asarray(coefficients, float)
        self.degree = int(degree)
        self.scale = np.asarray(scale, float)   # (width, height) used to normalise

    def __call__(self, points):
        points = np.asarray(points, float).reshape(-1, 2) / self.scale * 2.0 - 1.0
        return _features(points, self.degree) @ self.coefficients

    @property
    def parameters(self):
        return self.coefficients.size


def fit(image_points, pitch_points, degree=3, scale=(4096.0, 1080.0)):
    """Least-squares fit of image coordinates to pitch coordinates."""
    image_points = np.asarray(image_points, float).reshape(-1, 2)
    pitch_points = np.asarray(pitch_points, float).reshape(-1, 2)
    if len(image_points) != len(pitch_points):
        raise FitError("the two point sets have different lengths")
    needed = (degree + 1) * (degree + 2) // 2
    if len(image_points) < needed:
        raise FitError(f"a degree-{degree} fit needs at least {needed} points, "
                       f"got {len(image_points)}")

    normalised = image_points / np.asarray(scale, float) * 2.0 - 1.0
    design = _features(normalised, degree)
    coefficients, *_ = np.linalg.lstsq(design, pitch_points, rcond=None)
    return PitchMap(coefficients, degree, scale)


def error(model, image_points, pitch_points):
    """Return (RMSE, median) of the fit in metres."""
    predicted = model(image_points)
    distance = np.linalg.norm(predicted - np.asarray(pitch_points, float), axis=1)
    return float(np.sqrt(np.mean(distance ** 2))), float(np.median(distance))


def _pair_by_order(image_points, pitch_points):
    """A first guess at which detection is which player.

    The camera looks across the pitch from the halfway line, so a point further
    right in the image is further along the pitch. Ordering both sets by that
    axis pairs most of them correctly, which is all a starting point has to do.
    """
    order_image = np.argsort(np.asarray(image_points)[:, 0])
    order_pitch = np.argsort(np.asarray(pitch_points)[:, 0])
    count = min(len(order_image), len(order_pitch))
    keep_image = order_image[np.linspace(0, len(order_image) - 1, count).round().astype(int)]
    keep_pitch = order_pitch[np.linspace(0, len(order_pitch) - 1, count).round().astype(int)]
    return keep_image, keep_pitch


def _assign(predicted, pitch_points, cutoff):
    """Nearest-neighbour assignment, dropping pairs further apart than ``cutoff``."""
    cost = np.linalg.norm(predicted[:, None, :] - pitch_points[None, :, :], axis=2)
    if linear_sum_assignment is None:
        raise FitError("scipy is required for the assignment step")
    rows, columns = linear_sum_assignment(cost)
    good = cost[rows, columns] <= cutoff
    return rows[good], columns[good], cost[rows, columns][good]


def fit_by_alignment(frames, degree=3, scale=(4096.0, 1080.0), rounds=12,
                     cutoff=12.0, seed_frames=40):
    """Fit the mapping without knowing which detection is which player.

    ``frames`` is a sequence of ``(image_points, pitch_points)`` pairs, one per
    frame. The two sets are of different sizes — the detector also finds
    referees and people on the touchline, and misses players — so the
    correspondence is unknown.

    The loop is the usual one: pair the points, fit, re-pair using the fit,
    repeat. The first pairing is by position along the pitch, which is good
    enough to start because the camera never moves.

    ``rounds`` defaults to 12 because six is not enough: on the synthetic case
    in the tests six rounds leave a held-out error of 6.2 m and twelve bring it
    to 0.09 m. The loop tightens its own cutoff as it goes, and the last few
    rounds are where the mismatched pairs finally drop out.
    """
    if not frames:
        raise FitError("no frames to fit")

    seed_image, seed_pitch = [], []
    for image_points, pitch_points in frames[:seed_frames]:
        if len(image_points) < 8 or len(pitch_points) < 8:
            continue
        image_points = np.asarray(image_points, float)
        pitch_points = np.asarray(pitch_points, float)
        take_image, take_pitch = _pair_by_order(image_points, pitch_points)
        seed_image.append(image_points[take_image])
        seed_pitch.append(pitch_points[take_pitch])
    if not seed_image:
        raise FitError("no frame had enough points to seed the fit")

    model = fit(np.vstack(seed_image), np.vstack(seed_pitch), degree, scale)

    history = []
    for _ in range(rounds):
        paired_image, paired_pitch = [], []
        for image_points, pitch_points in frames:
            image_points = np.asarray(image_points, float)
            pitch_points = np.asarray(pitch_points, float)
            if len(image_points) < 4 or len(pitch_points) < 4:
                continue
            rows, columns, _ = _assign(model(image_points), pitch_points, cutoff)
            if len(rows) < 4:
                continue
            paired_image.append(image_points[rows])
            paired_pitch.append(pitch_points[columns])
        if not paired_image:
            raise FitError("the fit lost every correspondence; try a larger cutoff")
        image_all = np.vstack(paired_image)
        pitch_all = np.vstack(paired_pitch)
        model = fit(image_all, pitch_all, degree, scale)
        rmse, median = error(model, image_all, pitch_all)
        history.append({"pairs": len(image_all), "rmse": rmse, "median": median})
        cutoff = max(3.0, min(cutoff, rmse * 3))
    return model, history
